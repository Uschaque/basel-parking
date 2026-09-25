#!/usr/bin/env python3
"""Optional publication figure; requires matplotlib (dashboard does not)."""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "results.json").read_text(encoding="utf-8"))

# Rathaus, Saturday at 16:00, within 1 km: positions calculated in the dashboard.
keys = ["storchen", "steinen", "kunstmuseum", "city", "europe", "elisabethen", "aeschen"]
profiles = [data["profiles"][key]["5"]["16"] for key in keys]
labels = [data["garages"][key]["name"] for key in keys]
risk = np.array([100 * row["near_full"] for row in profiles])
lower = np.array([100 * row["ci_low"] for row in profiles])
upper = np.array([100 * row["ci_high"] for row in profiles])
order = np.argsort(risk)[::-1]

fig, axes = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1.05, 1]})
fig.patch.set_facecolor("#f5f8f7")
for axis in axes:
    axis.set_facecolor("#f5f8f7")
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.grid(axis="x", color="#dbe7e2", zorder=0)
    axis.set_axisbelow(True)

y = np.arange(len(order))
axes[0].barh(y, risk[order], color=["#d34f39" if keys[i] == "storchen" else "#247a73" for i in order], zorder=2)
axes[0].errorbar(risk[order], y, xerr=[risk[order]-lower[order], upper[order]-risk[order]],
                 fmt="none", ecolor="#263e49", capsize=3, lw=1, zorder=3)
axes[0].set_yticks(y, [labels[i] for i in order]); axes[0].invert_yaxis()
axes[0].set_xlim(0, 125); axes[0].set_xlabel("Relevés avec moins de 10 places libres (%)")
axes[0].set_title("Rathaus · samedi 16 h", loc="left", weight="bold", fontsize=15)
for pos, i in enumerate(order):
    axes[0].text(upper[i]+3, pos, f"{profiles[i]['near_full_count']}/{profiles[i]['n']}",
                 va="center", fontsize=9, color="#243e44")

model = np.array([data["evaluation"][key]["mae_median"] for key in keys])
baseline = np.array([data["evaluation"][key]["mae_previous_week"] for key in keys])
axes[1].barh(y+0.17, baseline[order], height=0.34, color="#b3c5c1", label="Semaine précédente")
axes[1].barh(y-0.17, model[order], height=0.34, color="#276f83", label="Médiane 26 semaines")
axes[1].set_yticks(y, [labels[i] for i in order]); axes[1].invert_yaxis()
axes[1].set_xlabel("Erreur absolue moyenne (places libres)")
axes[1].set_title("Évaluation chronologique · 56 jours", loc="left", weight="bold", fontsize=15)
axes[1].legend(frameon=False, loc="upper right")

fig.suptitle("Basel Parking Lab · choisir avec des données vérifiées", x=.06, ha="left", fontsize=19, weight="bold", color="#13343d")
fig.text(.06, .02, "Données : Kanton Basel-Stadt, CC BY 4.0 · instantané du 25.09.2026. Intervalles de Wilson à 95 % : échantillonnage seul.", fontsize=9, color="#506970")
fig.subplots_adjust(left=.13, right=.98, top=.83, bottom=.13, wspace=.39)
out = ROOT / "portfolio_figure.png"
fig.savefig(out, dpi=170, facecolor=fig.get_facecolor())
print(out)
