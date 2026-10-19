#!/usr/bin/env python3
"""Reproducible chronological evaluation for Basel Parking.

The script reads the Basel-Stadt hourly export already downloaded by
``basel_parking.build.refresh``.  It cleans and stores observations in SQLite,
creates a fixed 182-day training window and a 56-day holdout, evaluates three
models, and generates a self-contained HTML report.

No observation at or after the holdout boundary is used to fit the historical
median or the ridge calendar model.  The previous-week baseline only uses an
observation that was available seven days before the target timestamp.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = ROOT / "basel_parking" / "data" / "all_historical.csv"
CONFIG_PATH = ROOT / "basel_parking" / "config.json"
APP_RESULTS = ROOT / "basel_parking" / "results.json"
OUT = ROOT / "analysis" / "outputs"
DB_PATH = OUT / "basel_parking.sqlite"
TRAIN_DAYS = 182
HOLDOUT_DAYS = 56
VALIDATION_DAYS = 28
ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0)
RNG_SEED = 42


@dataclass(frozen=True)
class Split:
    train_start: pd.Timestamp
    holdout_start: pd.Timestamp
    cutoff: pd.Timestamp


def read_source(path: Path = SOURCE_CSV) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return raw rows and validated, de-duplicated observations."""
    raw = pd.read_csv(path, sep=";", low_memory=False)
    required = {"published", "id2", "name", "address", "free", "total"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"Missing source columns: {sorted(missing)}")

    raw = raw.copy()
    raw["published_utc"] = pd.to_datetime(raw["published"], utc=True, errors="coerce")
    raw["free_num"] = pd.to_numeric(raw["free"], errors="coerce")
    raw["total_num"] = pd.to_numeric(raw["total"], errors="coerce")
    raw["garage_id"] = raw["id2"].fillna("").astype(str).str.strip()
    raw["valid"] = (
        raw["published_utc"].notna()
        & raw["garage_id"].ne("")
        & raw["free_num"].notna()
        & raw["total_num"].notna()
        & raw["free_num"].ge(0)
        & raw["total_num"].gt(0)
        & raw["free_num"].le(raw["total_num"])
    )

    clean = raw.loc[raw["valid"], [
        "published_utc", "garage_id", "name", "address", "free_num", "total_num"
    ]].rename(columns={"free_num": "free", "total_num": "total"})
    clean["free"] = clean["free"].astype(int)
    clean["total"] = clean["total"].astype(int)
    clean = clean.sort_values(["garage_id", "published_utc"])
    clean = clean.drop_duplicates(["garage_id", "published_utc"], keep="last")
    clean["published_local"] = clean["published_utc"].dt.tz_convert("Europe/Zurich")
    clean["weekday"] = clean["published_local"].dt.weekday
    clean["hour"] = clean["published_local"].dt.hour
    clean["local_date"] = clean["published_local"].dt.date.astype(str)
    clean["free_ratio"] = clean["free"] / clean["total"]
    return raw, clean.reset_index(drop=True)


def make_split(clean: pd.DataFrame) -> Split:
    cutoff = clean["published_utc"].max()
    holdout_start = cutoff - pd.Timedelta(days=HOLDOUT_DAYS)
    train_start = holdout_start - pd.Timedelta(days=TRAIN_DAYS)
    return Split(train_start=train_start, holdout_start=holdout_start, cutoff=cutoff)


def select_trusted_garages() -> tuple[set[str], dict]:
    app_results = json.loads(APP_RESULTS.read_text(encoding="utf-8"))
    audit = app_results["audit"]
    trusted = {garage for garage, row in audit.items() if row.get("included")}
    if not trusted:
        raise RuntimeError("No garage passed the application's quality checks")
    return trusted, audit


def quality_audit(raw: pd.DataFrame, clean: pd.DataFrame, app_audit: dict) -> pd.DataFrame:
    raw_counts = raw.groupby("garage_id", dropna=False).agg(
        raw_rows=("garage_id", "size"),
        invalid_rows=("valid", lambda s: int((~s).sum())),
    ).reset_index()
    clean_counts = clean.groupby("garage_id").agg(
        valid_rows=("garage_id", "size"),
        first_observation=("published_utc", "min"),
        last_observation=("published_utc", "max"),
        capacity_min=("total", "min"),
        capacity_max=("total", "max"),
    ).reset_index()
    q = raw_counts.merge(clean_counts, on="garage_id", how="outer").fillna({"raw_rows": 0, "invalid_rows": 0, "valid_rows": 0})
    q["invalid_pct"] = np.where(q["raw_rows"] > 0, 100 * q["invalid_rows"] / q["raw_rows"], np.nan)
    q["included"] = q["garage_id"].map(lambda x: bool(app_audit.get(x, {}).get("included")))
    q["exclusion_reason"] = q["garage_id"].map(lambda x: "; ".join(app_audit.get(x, {}).get("reasons", [])))
    return q.sort_values(["included", "garage_id"], ascending=[False, True]).reset_index(drop=True)


def feature_matrix(frame: pd.DataFrame, origin: pd.Timestamp) -> np.ndarray:
    local = frame["published_local"]
    hour = local.dt.hour.to_numpy(dtype=float)
    weekday = local.dt.weekday.to_numpy(dtype=float)
    day_of_year = local.dt.dayofyear.to_numpy(dtype=float)
    trend = ((frame["published_utc"] - origin).dt.total_seconds() / 86400.0).to_numpy(dtype=float)
    capacity = frame["total"].to_numpy(dtype=float)
    capacity = np.log1p(capacity)
    cols = [
        np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24),
        np.sin(4 * np.pi * hour / 24), np.cos(4 * np.pi * hour / 24),
        np.sin(6 * np.pi * hour / 24), np.cos(6 * np.pi * hour / 24),
        np.sin(2 * np.pi * weekday / 7), np.cos(2 * np.pi * weekday / 7),
        np.sin(4 * np.pi * weekday / 7), np.cos(4 * np.pi * weekday / 7),
        (weekday >= 5).astype(float),
        np.sin(2 * np.pi * day_of_year / 365.25), np.cos(2 * np.pi * day_of_year / 365.25),
        trend,
        capacity,
    ]
    return np.column_stack(cols)


def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float) -> dict:
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale[scale < 1e-12] = 1.0
    xs = (x - mean) / scale
    design = np.column_stack([np.ones(len(xs)), xs])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return {"mean": mean, "scale": scale, "beta": beta, "alpha": alpha}


def predict_ridge(model: dict, x: np.ndarray) -> np.ndarray:
    xs = (x - model["mean"]) / model["scale"]
    design = np.column_stack([np.ones(len(xs)), xs])
    return np.clip(design @ model["beta"], 0.0, 1.0)


def mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def choose_alpha(train: pd.DataFrame, garage_origin: pd.Timestamp) -> tuple[float, list[dict]]:
    validation_start = train["published_utc"].max() - pd.Timedelta(days=VALIDATION_DAYS)
    fitting = train[train["published_utc"] < validation_start]
    validation = train[train["published_utc"] >= validation_start]
    if len(fitting) < 500 or len(validation) < 100:
        return 10.0, []
    x_fit = feature_matrix(fitting, garage_origin)
    y_fit = fitting["free_ratio"].to_numpy(dtype=float)
    x_val = feature_matrix(validation, garage_origin)
    actual = validation["free"].to_numpy(dtype=float)
    capacity = validation["total"].to_numpy(dtype=float)
    rows = []
    for alpha in ALPHAS:
        model = fit_ridge(x_fit, y_fit, alpha)
        pred = predict_ridge(model, x_val) * capacity
        rows.append({"alpha": alpha, "validation_mae": mae(actual, pred)})
    best = min(rows, key=lambda row: (row["validation_mae"], row["alpha"]))
    return float(best["alpha"]), rows


def add_predictions(clean: pd.DataFrame, trusted: set[str], split: Split) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = clean[
        clean["garage_id"].isin(trusted)
        & clean["published_utc"].ge(split.train_start)
        & clean["published_utc"].le(split.cutoff)
    ].copy()
    train = frame[frame["published_utc"] < split.holdout_start].copy()
    test = frame[frame["published_utc"] >= split.holdout_start].copy()

    # Fixed historical profile built exclusively from training observations.
    profiles = train.groupby(["garage_id", "weekday", "hour"], as_index=False).agg(
        pred_historical_median=("free", "median"),
        median_training_samples=("free", "size"),
    )
    test = test.merge(profiles, on=["garage_id", "weekday", "hour"], how="left")

    # Previous occurrence of the same local weekday/hour. Source publication
    # seconds can drift, so an exact timestamp join would create artificial
    # missing values. Grouped shift keeps the baseline strictly in the past.
    frame = frame.sort_values(["garage_id", "weekday", "hour", "published_utc"])
    frame["pred_previous_week"] = frame.groupby(
        ["garage_id", "weekday", "hour"], sort=False
    )["free"].shift(1)
    weekly = frame[["garage_id", "published_utc", "pred_previous_week"]]
    test = test.merge(weekly, on=["garage_id", "published_utc"], how="left")

    model_selection = []
    ridge_parts = []
    for garage in sorted(trusted):
        g_train = train[train["garage_id"] == garage].copy()
        g_test = test[test["garage_id"] == garage].copy()
        if len(g_train) < 1000 or g_test.empty:
            continue
        origin = g_train["published_utc"].min()
        alpha, validation = choose_alpha(g_train, origin)
        for row in validation:
            model_selection.append({"garage_id": garage, **row, "selected": row["alpha"] == alpha})
        model = fit_ridge(
            feature_matrix(g_train, origin),
            g_train["free_ratio"].to_numpy(dtype=float),
            alpha,
        )
        ratio = predict_ridge(model, feature_matrix(g_test, origin))
        ridge_parts.append(pd.DataFrame({
            "row_id": g_test.index,
            "pred_ridge_calendar": ratio * g_test["total"].to_numpy(dtype=float),
            "ridge_alpha": alpha,
        }))
    ridge = pd.concat(ridge_parts, ignore_index=True).set_index("row_id")
    test = test.join(ridge, how="left")
    return test.reset_index(drop=True), pd.DataFrame(model_selection)


def model_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    model_cols = {
        "Historical median": "pred_historical_median",
        "Previous week": "pred_previous_week",
        "Ridge calendar": "pred_ridge_calendar",
    }
    rows = []
    groups = [("ALL", predictions)] + list(predictions.groupby("garage_id"))
    for garage, group in groups:
        for model_name, column in model_cols.items():
            usable = group[group[column].notna()]
            if usable.empty:
                continue
            actual = usable["free"].to_numpy(dtype=float)
            pred = usable[column].to_numpy(dtype=float)
            error = np.abs(actual - pred)
            rows.append({
                "garage_id": garage,
                "model": model_name,
                "n": len(usable),
                "coverage_pct": 100 * len(usable) / len(group),
                "mae": float(error.mean()),
                "median_ae": float(np.median(error)),
                "rmse": float(np.sqrt(np.mean((actual - pred) ** 2))),
                "wape_pct": float(100 * error.sum() / max(actual.sum(), 1.0)),
            })
    return pd.DataFrame(rows)


def paired_bootstrap(predictions: pd.DataFrame, challenger="pred_historical_median", baseline="pred_previous_week") -> dict:
    paired = predictions.dropna(subset=[challenger, baseline]).copy()
    paired["challenger_error"] = (paired["free"] - paired[challenger]).abs()
    paired["baseline_error"] = (paired["free"] - paired[baseline]).abs()
    paired["delta"] = paired["baseline_error"] - paired["challenger_error"]
    day_values = paired.groupby("local_date")["delta"].mean().to_numpy(dtype=float)
    rng = np.random.default_rng(RNG_SEED)
    samples = np.empty(2000)
    for i in range(len(samples)):
        samples[i] = rng.choice(day_values, size=len(day_values), replace=True).mean()
    return {
        "n_rows": int(len(paired)),
        "n_days": int(len(day_values)),
        "mae_improvement_spaces": float(paired["delta"].mean()),
        "ci95_low": float(np.quantile(samples, 0.025)),
        "ci95_high": float(np.quantile(samples, 0.975)),
        "method": "paired bootstrap over local calendar days, 2,000 resamples, seed 42",
    }


def write_sqlite(clean: pd.DataFrame, quality: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    db_clean = clean.copy()
    db_clean["published_utc"] = db_clean["published_utc"].astype(str)
    db_clean["published_local"] = db_clean["published_local"].astype(str)
    with sqlite3.connect(DB_PATH) as connection:
        db_clean.to_sql("observations", connection, if_exists="replace", index=False)
        quality.assign(
            first_observation=quality["first_observation"].astype(str),
            last_observation=quality["last_observation"].astype(str),
        ).to_sql("quality_audit", connection, if_exists="replace", index=False)
        connection.executescript("""
        CREATE INDEX IF NOT EXISTS idx_observations_garage_time
            ON observations(garage_id, published_utc);
        CREATE INDEX IF NOT EXISTS idx_observations_slot
            ON observations(garage_id, weekday, hour);
        """)


def esc(value) -> str:
    return html.escape(str(value))


def metric_card(value: str, label: str) -> str:
    return f'<div class="metric"><strong>{esc(value)}</strong><span>{esc(label)}</span></div>'


def bar_rows(overall: pd.DataFrame) -> str:
    max_mae = overall["mae"].max()
    colors_map = {"Historical median": "#087e8b", "Previous week": "#8b95a1", "Ridge calendar": "#e67e22"}
    chunks = []
    for row in overall.sort_values("mae").itertuples():
        width = 100 * row.mae / max_mae
        chunks.append(
            f'<div class="barrow"><span>{esc(row.model)}</span><div class="track"><i style="width:{width:.1f}%;background:{colors_map[row.model]}"></i></div><b>{row.mae:.2f}</b></div>'
        )
    return "".join(chunks)


def results_table(metrics: pd.DataFrame) -> str:
    garages = metrics[metrics["garage_id"] != "ALL"]
    pivot = garages.pivot(index="garage_id", columns="model", values="mae").reset_index()
    headers = ["Garage", "Historical median", "Previous week", "Ridge calendar", "Best"]
    body = []
    for _, row in pivot.iterrows():
        values = {model: float(row[model]) for model in headers[1:-1]}
        best = min(values, key=values.get)
        body.append("<tr>" + f"<td>{esc(row['garage_id'])}</td>" + "".join(
            f'<td class="num{(" best" if model == best else "")}">{values[model]:.2f}</td>' for model in headers[1:-1]
        ) + f"<td>{esc(best)}</td></tr>")
    return "<table><thead><tr>" + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def quality_table(quality: pd.DataFrame) -> str:
    rows = []
    for row in quality.itertuples():
        status = "Included" if row.included else "Excluded"
        reason = row.exclusion_reason or "Passed the documented application checks"
        rows.append(
            f"<tr><td>{esc(row.garage_id)}</td><td class='num'>{int(row.raw_rows):,}</td><td class='num'>{row.invalid_pct:.2f}%</td><td><span class='pill {status.lower()}'>{status}</span></td><td>{esc(reason)}</td></tr>"
        )
    return "<table><thead><tr><th>Garage</th><th>Raw rows</th><th>Invalid</th><th>Status</th><th>Reason</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def write_report(split: Split, raw: pd.DataFrame, clean: pd.DataFrame, trusted: set[str], quality: pd.DataFrame, predictions: pd.DataFrame, metrics: pd.DataFrame, bootstrap: dict) -> Path:
    overall = metrics[metrics["garage_id"] == "ALL"].copy()
    best = overall.sort_values("mae").iloc[0]
    source_rows = len(raw)
    valid_share = 100 * len(clean) / len(raw)
    improvement = bootstrap["mae_improvement_spaces"]
    ci = (bootstrap["ci95_low"], bootstrap["ci95_high"])
    conclusion = (
        f"On the common holdout rows, the historical median improves on the previous-week baseline by {improvement:.2f} free spaces MAE "
        f"(95% block-bootstrap interval {ci[0]:.2f} to {ci[1]:.2f})."
        if improvement >= 0 else
        f"On the common holdout rows, the historical median is {-improvement:.2f} free spaces MAE worse than the previous-week baseline "
        f"(95% block-bootstrap interval {ci[0]:.2f} to {ci[1]:.2f})."
    )
    generated = pd.Timestamp.now(tz="Europe/Zurich").strftime("%Y-%m-%d %H:%M %Z")
    css = """
    :root{--navy:#102a43;--teal:#087e8b;--orange:#e67e22;--ink:#1f2933;--muted:#5c6b7a;--line:#d7e0e8;--paper:#f7f9fb;--green:#237a57;--red:#b42318}*{box-sizing:border-box}body{margin:0;font:16px/1.55 Arial,sans-serif;color:var(--ink);background:white}header{background:var(--navy);color:white;padding:64px 24px 52px}header>div,main{max-width:1120px;margin:auto}header p{max-width:800px;color:#dce8f1;font-size:1.1rem}h1{font-size:2.7rem;line-height:1.08;margin:.2em 0}h2{color:var(--navy);margin-top:2.2em}h3{color:var(--teal)}main{padding:36px 24px 80px}.kicker{color:#8fe3e8;font-weight:700;letter-spacing:.12em;font-size:.8rem}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:26px 0}.metric{background:var(--paper);border:1px solid var(--line);padding:20px;border-radius:8px}.metric strong{display:block;font-size:1.9rem;color:var(--navy)}.metric span{color:var(--muted);font-size:.86rem}.callout{border-left:5px solid var(--teal);background:#eaf7f8;padding:18px 20px;margin:24px 0}.warning{border-left-color:var(--orange);background:#fff1e6}.barrow{display:grid;grid-template-columns:170px 1fr 65px;gap:12px;align-items:center;margin:12px 0}.track{height:16px;background:#e8edf2;border-radius:9px;overflow:hidden}.track i{display:block;height:100%;border-radius:9px}.barrow b{text-align:right}table{border-collapse:collapse;width:100%;font-size:.9rem;margin:18px 0;display:block;overflow-x:auto}th{background:var(--navy);color:white;text-align:left}th,td{padding:9px 11px;border:1px solid var(--line);vertical-align:top}tbody tr:nth-child(even){background:var(--paper)}.num{text-align:right;font-variant-numeric:tabular-nums}.best{background:#eaf7f0;font-weight:700;color:var(--green)}.pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:700}.included{background:#eaf7f0;color:var(--green)}.excluded{background:#fdecec;color:var(--red)}code{background:#eef2f5;padding:.1em .35em;border-radius:3px}pre{background:#0f2435;color:#eaf2f8;padding:18px;overflow:auto;border-radius:6px}.small{color:var(--muted);font-size:.86rem}footer{border-top:1px solid var(--line);margin-top:54px;padding-top:20px;color:var(--muted)}@media(max-width:760px){h1{font-size:2rem}.metrics{grid-template-columns:1fr 1fr}.barrow{grid-template-columns:120px 1fr 50px}}
    """
    html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Basel Parking - chronological data study</title><meta name="description" content="Reproducible chronological evaluation of Basel parking estimates."><style>{css}</style></head><body>
    <header><div><div class="kicker">REPRODUCIBLE DATA STUDY</div><h1>Can historical patterns improve Basel parking estimates?</h1><p>A chronological holdout evaluation of open Basel-Stadt parking data. The report separates data quality, baselines and model performance, and documents where the approach fails.</p></div></header>
    <main>
    <div class="metrics">{metric_card(f'{source_rows:,}', 'raw observations')}{metric_card(f'{valid_share:.1f}%', 'valid rows after basic checks')}{metric_card(str(len(trusted)), 'garages passing product quality rules')}{metric_card(f'{len(predictions):,}', 'holdout observations')}</div>
    <div class="callout"><strong>Result.</strong> The lowest overall MAE is <b>{esc(best.model)}</b> at <b>{best.mae:.2f} free spaces</b>. {esc(conclusion)}</div>
    <h2>1. Study design</h2><p>The evaluation uses a fixed training window from <b>{split.train_start.strftime('%Y-%m-%d')}</b> to just before <b>{split.holdout_start.strftime('%Y-%m-%d')}</b>. The following {HOLDOUT_DAYS} days form an untouched holdout ending on <b>{split.cutoff.strftime('%Y-%m-%d')}</b>. Model choice for the ridge calendar model uses only a validation slice inside the training period.</p>
    <ul><li><b>Historical median:</b> median free spaces for the same garage, weekday and local hour in the training window.</li><li><b>Previous week:</b> the observed free-space count exactly seven days earlier.</li><li><b>Ridge calendar:</b> regularized linear model on cyclical hour, weekday and annual seasonality, weekend, trend and capacity. It receives no holdout targets during fitting.</li></ul>
    <div class="callout warning"><strong>Scope.</strong> This evaluates reported free-space counts, not physical ground truth. It is a forecasting comparison, not a reservation guarantee. Events, tariffs, road conditions and new exceptional opening hours are not included.</div>
    <h2>2. Overall holdout performance</h2><p>Mean absolute error (MAE) is expressed in parking spaces; lower is better. Coverage differs when a baseline has no matching prior observation.</p>{bar_rows(overall)}
    <h2>3. Performance by garage</h2>{results_table(metrics)}<p class="small">Green cells mark the lowest MAE for that garage. A more complex model is not accepted automatically; the table preserves negative results.</p>
    <h2>4. Data quality audit</h2>{quality_table(quality)}
    <h2>5. Reproducibility and SQL</h2><p>The pipeline writes validated observations and the audit table to SQLite. Two indexes support time-series and weekday/hour queries. The database is generated locally and excluded from Git because the source export can be downloaded again.</p><pre>python -m pip install -r requirements.txt
python basel_parking/build.py --refresh
python analysis/run_analysis.py
python -m unittest discover -s analysis/tests -v</pre>
    <p>Useful SQL queries are stored in <code>analysis/sql/quality_summary.sql</code>. Aggregated model metrics, predictions and audit results are exported as CSV in <code>analysis/outputs/</code>.</p>
    <h2>6. What this project demonstrates</h2><ul><li>Data ingestion from a public API and deterministic cleaning.</li><li>A documented SQLite schema and reproducible analytical outputs.</li><li>Chronological train, validation and holdout boundaries that prevent target leakage.</li><li>Comparison with simple baselines before accepting a model.</li><li>Per-garage results, uncertainty for the main comparison and explicit limitations.</li></ul>
    <footer><p>Generated {esc(generated)} from Basel-Stadt datasets 100014 and 100088, CC BY 4.0. Source code: <a href="https://github.com/Uschaque/basel-parking">github.com/Uschaque/basel-parking</a>. Product: <a href="/">Basel Parking</a>.</p></footer>
    </main></body></html>"""
    report_path = ROOT / "analysis" / "report.html"
    report_path.write_text(html_doc, encoding="utf-8")
    netlify_report = ROOT / "basel-parking-netlify" / "data-study.html"
    netlify_report.write_text(html_doc, encoding="utf-8")
    return report_path


def run(refresh: bool = False) -> dict:
    if refresh or not SOURCE_CSV.exists():
        from basel_parking.build import refresh as refresh_source
        refresh_source()
    raw, clean = read_source()
    trusted, app_audit = select_trusted_garages()
    split = make_split(clean[clean["garage_id"].isin(trusted)])
    quality = quality_audit(raw, clean, app_audit)
    write_sqlite(clean, quality)
    predictions, selection = add_predictions(clean, trusted, split)
    metrics = model_metrics(predictions)
    bootstrap = paired_bootstrap(predictions)

    OUT.mkdir(parents=True, exist_ok=True)
    quality.to_csv(OUT / "quality_audit.csv", index=False)
    predictions.to_csv(OUT / "holdout_predictions.csv", index=False)
    metrics.to_csv(OUT / "model_metrics.csv", index=False)
    selection.to_csv(OUT / "ridge_model_selection.csv", index=False)
    report_path = write_report(split, raw, clean, trusted, quality, predictions, metrics, bootstrap)
    summary = {
        "source_rows": int(len(raw)),
        "clean_rows": int(len(clean)),
        "trusted_garages": sorted(trusted),
        "train_start": split.train_start.isoformat(),
        "holdout_start": split.holdout_start.isoformat(),
        "cutoff": split.cutoff.isoformat(),
        "holdout_rows": int(len(predictions)),
        "overall_metrics": metrics[metrics["garage_id"] == "ALL"].to_dict(orient="records"),
        "paired_bootstrap": bootstrap,
        "report": str(report_path.relative_to(ROOT)),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Download a fresh Basel-Stadt export first")
    args = parser.parse_args()
    result = run(refresh=args.refresh)
    print(json.dumps(result, indent=2))
