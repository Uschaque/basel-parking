# Basel Parking data study

This directory contains the reproducible evaluation behind Basel Parking. It is deliberately separate from the live product interface: the web application answers a user question, while this study tests whether its historical estimate beats simple alternatives on unseen dates.

## Reproduce

```sh
python -m pip install -r requirements.txt
python basel_parking/build.py --refresh
python analysis/run_analysis.py
python -m unittest discover -s analysis/tests -v
```

The pipeline:

1. validates the Basel-Stadt export and removes impossible or duplicate observations;
2. writes the clean table and the quality audit to SQLite;
3. creates a fixed 182-day training period and a subsequent 56-day holdout;
4. compares the historical median, the previous week and a regularized calendar model;
5. reports MAE, median absolute error, RMSE, WAPE and prediction coverage per garage;
6. uses a paired day-level bootstrap for the headline comparison;
7. generates `analysis/report.html` and machine-readable CSV/JSON outputs.

The SQLite database and row-level predictions are generated artifacts and are excluded from Git. Aggregate metrics remain small enough to review in a pull request.

## Leakage controls

- The median profile and ridge model are fitted only before the holdout boundary.
- Ridge hyperparameters use a validation slice inside the training period.
- The previous-week baseline uses a value that was available seven days before the target timestamp.
- The holdout is never used to select a model.

## Interpretation

The target is the public provider's reported count, not an independent physical count. Lower error therefore means closer agreement with later public reports. It does not guarantee a parking space and does not validate exceptional-event performance.
