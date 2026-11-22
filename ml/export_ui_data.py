"""Export real model output for the UI screens.

Run (from the EnergyPulse-AI folder, after both notebooks):
    python ml/export_ui_data.py

The UI is not connected to the model yet (that is the next evaluation), so the
screens read the static file ui/assets/data.js. Every reading, forecast, normal
range and alert in it comes from the trained XGBoost model and the alert rule of
Notebook 2 (|actual - forecast| > 3 x the meter's validation error std).
Only the review decisions on older alerts are example values ("demo": true).
"""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dateutil.easter import easter
from xgboost import XGBRegressor

ML = Path(__file__).resolve().parent
ROOT = ML.parent
FEATURES_FILE = ML / "data" / "features.csv.gz"
MODEL_FILE = ML / "outputs" / "models" / "xgb_forecaster.json"
META_FILE = ML / "outputs" / "models" / "model_meta.json"
UI_FILE = ROOT / "ui" / "assets" / "data.js"

NOW = pd.Timestamp("2014-06-19 10:00")       # the moment the screens pretend it is (inside the test year)
HISTORY_DAYS = 7
ALERTS_FROM = pd.Timestamp("2014-01-01")      # the alerts screen lists alerts since this date
STD_MULTIPLIER = 3                            # same rule as Notebook 2
TARIFF = 0.15                                 # example price per kWh; the user sets it in the app
MAX_GAP_HOURS = 1                             # flagged hours with <= 1 normal hour between them = one alert

DEMO_REVIEWS = ["investigate", "expected", "expected", "investigate", "expected", "expected", "expected",
                "investigate", "expected", "expected"]
DEMO_NOTES = {"investigate": "Asked the night shift to check which equipment was left running.",
              "expected": "Planned activity - nothing to follow up."}


def r(x, n=1):
    return None if pd.isna(x) else round(float(x), n)


def portugal_holidays(years):
    """Portuguese public holidays - shown on an alert as context only (the model does not use them)."""
    days = set()
    for y in years:
        e = easter(y)
        days |= {date(y, 1, 1), e - timedelta(days=2), e, date(y, 4, 25), date(y, 5, 1),
                 date(y, 6, 10), date(y, 8, 15), date(y, 12, 8), date(y, 12, 25)}
        if not 2013 <= y <= 2015:
            days |= {e + timedelta(days=60), date(y, 10, 5), date(y, 11, 1), date(y, 12, 1)}
    return days


def metrics(df, col):
    err = df.kwh - df[col]
    return {"mae": float(err.abs().mean()), "rmse": float(np.sqrt((err ** 2).mean())),
            "wape": float(err.abs().sum() / df.kwh.sum() * 100)}


def group_alerts(d, std):
    """Neighbouring flagged hours in the same direction -> one alert."""
    rows = []
    f = d[d.flag].assign(direction=lambda x: np.where(x.kwh > x.xgb, "spike", "drop"))
    for direction, g in f.groupby("direction"):
        gap = g.index.to_series().diff() > pd.Timedelta(hours=MAX_GAP_HOURS + 1)
        for _, ev in g.groupby(gap.cumsum()):
            excess = float((ev.kwh - ev.xgb).sum())
            ratio = float(((ev.kwh - ev.xgb).abs() / std).max())       # biggest miss, in "std" units
            rows.append({"start": ev.index[0], "end": ev.index[-1] + pd.Timedelta(hours=1), "hours": len(ev),
                         "direction": direction, "actual": float(ev.kwh.sum()), "expected": float(ev.xgb.sum()),
                         "excess": excess, "pct": excess / float(ev.xgb.sum()) * 100, "ratio": ratio,
                         "severity": "high" if ratio >= 6 else "medium" if ratio >= 4 else "low"})
    return pd.DataFrame(rows).sort_values("start").reset_index(drop=True) if rows else pd.DataFrame()


def main():
    data = pd.read_csv(FEATURES_FILE, index_col="timestamp", parse_dates=True)
    meta = json.loads(META_FILE.read_text())
    model = XGBRegressor()
    model.load_model(MODEL_FILE)
    feats = meta["features"]

    data["baseline"] = data["lag_24"] * data["scale"]
    data["xgb"] = np.maximum(model.predict(data[feats]) * data["scale"], 0)
    val, test = data[data.set == "val"], data[data.set == "test"].copy()
    std = (val.kwh - val.xgb).groupby(val.meter).std()                   # Notebook 2, step 6
    test["threshold"] = test.meter.map(STD_MULTIPLIER * std)
    test["flag"] = (test.kwh - test.xgb).abs() > test.threshold

    # example meter: the middle one by size, same choice as both notebooks
    m = data.groupby("meter").scale.first().sort_values().index[len(std) // 2]
    h = test[test.meter == m].copy()
    sd = float(std[m])
    h["lo"] = (h.xgb - STD_MULTIPLIER * sd).clip(lower=0)
    h["hi"] = h.xgb + STD_MULTIPLIER * sd
    holidays = portugal_holidays([2014])

    def points(d, with_actual=True):
        return [{"t": t.strftime("%Y-%m-%dT%H:%M"), "actual": r(x.kwh) if with_actual else None,
                 "expected": r(x.xgb), "lo": r(x.lo), "hi": r(x.hi),
                 "flag": bool(x.flag) if with_actual else False} for t, x in d.iterrows()]

    past = h.loc[NOW - pd.Timedelta(days=HISTORY_DAYS):NOW - pd.Timedelta(hours=1)]
    future = h.loc[NOW:NOW + pd.Timedelta(hours=23)]
    today = h.loc[NOW.normalize():NOW - pd.Timedelta(hours=1)]

    year_alerts = group_alerts(h, sd)
    a = year_alerts[(year_alerts.end <= NOW) & (year_alerts.start >= ALERTS_FROM)]
    a = a.sort_values("start", ascending=False).reset_index(drop=True)
    out_alerts = []
    for i, x in a.iterrows():
        hol = x.start.date() in holidays
        status = "needs_review" if i < 4 else ("expected" if hol else DEMO_REVIEWS[(i - 4) % len(DEMO_REVIEWS)])
        win = h.loc[x.start - pd.Timedelta(hours=18):min(x.end + pd.Timedelta(hours=17), NOW - pd.Timedelta(hours=1))]
        first = h.loc[x.start]
        out_alerts.append({
            "id": f"A-{x.start:%m%d}-{x.start:%H}", "start": x.start.strftime("%Y-%m-%dT%H:%M"),
            "end": x.end.strftime("%Y-%m-%dT%H:%M"), "hours": int(x.hours), "direction": x.direction,
            "actual": r(x.actual), "expected": r(x.expected), "excess": r(x.excess), "pct": r(x.pct),
            "severity": x.severity, "holiday": bool(hol), "normalLo": r(first.lo), "normalHi": r(first.hi),
            "status": status, "demo": status != "needs_review",
            "note": "Public holiday." if (hol and status == "expected") else DEMO_NOTES.get(status, ""),
            "series": points(win)})

    month = year_alerts[(year_alerts.direction == "spike") & (year_alerts.end <= NOW)
                        & (year_alerts.start >= NOW.normalize().replace(day=1))]
    mt = test[test.meter == m]
    this_base, this_xgb = metrics(mt, "baseline"), metrics(mt, "xgb")

    per_meter = {k: pd.DataFrame({mm: metrics(g, k) for mm, g in test.groupby("meter")}).T for k in ("baseline", "xgb")}
    wins = int((per_meter["xgb"].wape < per_meter["baseline"].wape).sum())

    out = {
        "generated_from": "ml/export_ui_data.py - XGBoost day-ahead model + alert rule of Notebook 2",
        "meter": {"id": m, "name": "Main meter", "source": "UCI ElectricityLoadDiagrams20112014",
                  "interval": "hourly (aggregated from 15-minute readings)",
                  "dataFrom": "2012-01-01", "dataTo": (NOW - pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")},
        "now": NOW.strftime("%Y-%m-%dT%H:%M"),
        "tariff": {"value": TARIFF, "currency": "EUR"},
        "today": {"actual": r(today.kwh.sum()), "expected": r(today.xgb.sum()),
                  "pct": r((today.kwh.sum() / today.xgb.sum() - 1) * 100), "hours": len(today)},
        "month": {"excessKwh": r(month.excess.sum() if len(month) else 0), "alerts": int(len(month))},
        "next24": {"total": r(future.xgb.sum()), "peak": r(future.xgb.max()),
                   "peakAt": future.xgb.idxmax().strftime("%Y-%m-%dT%H:%M"),
                   "low": r(future.xgb.min()), "lowAt": future.xgb.idxmin().strftime("%Y-%m-%dT%H:%M")},
        "accuracy": {"wape": r(this_xgb["wape"], 2), "baselineWape": r(this_base["wape"], 2)},
        "history": points(past), "forecast": points(future, with_actual=False), "alerts": out_alerts,
        "alertWindow": f"since {ALERTS_FROM.day} {ALERTS_FROM:%B %Y}",
        "report": {
            "testPeriod": "1 Jan - 31 Dec 2014", "trainedOn": "1 Jan 2012 - 30 Jun 2013",
            "settingsChosenOn": "1 Jul - 31 Dec 2013",
            "meters": int(test.meter.nunique()), "wins": wins, "meanKwh": r(mt.kwh.mean(), 1),
            "thisMeter": [{"key": "baseline", "label": "Same hour yesterday (baseline)", **{k: r(v, 2) for k, v in this_base.items()}},
                          {"key": "xgb", "label": "XGBoost (in use)", **{k: r(v, 2) for k, v in this_xgb.items()}}],
            "allMeters": [{"key": k, "label": lab, **{c: r(per_meter[k][c].mean(), 2) for c in ("mae", "rmse", "wape")}}
                          for k, lab in (("baseline", "Same hour yesterday (baseline)"), ("xgb", "XGBoost (in use)"))],
            "stdMultiplier": STD_MULTIPLIER, "thresholdKwh": r(STD_MULTIPLIER * sd, 1), "errorStdKwh": r(sd, 1),
            "flaggedHoursPct": r(test.flag.mean() * 100, 1),
            "flaggedHoursPerMeterMonth": r(test.flag.sum() / test.meter.nunique() / 12, 0),
            "alerts2014": {"total": int(len(year_alerts)), "perMonth": r(len(year_alerts) / 12, 1)},
            "features": len(feats)},
    }

    # how many alerts each sensitivity level would have produced for this meter in 2014
    levels = []
    for label, k in [("Fewer alerts", 4), ("Standard", STD_MULTIPLIER), ("More alerts", 2.5)]:
        n = len(group_alerts(h.assign(flag=(h.kwh - h.xgb).abs() > k * sd), sd))
        levels.append({"label": label, "multiplier": k, "alertsPerMonth": r(n / 12, 0)})
    out["sensitivity"] = {"multiplier": STD_MULTIPLIER, "levels": levels}

    # a real sample file for the upload screen: 8 weeks of hourly readings before NOW
    raw = data[data.meter == m].kwh.loc[NOW - pd.Timedelta(weeks=8):NOW - pd.Timedelta(hours=1)]
    raw = raw.round(2).rename("kwh").rename_axis("timestamp")
    raw.index = raw.index.strftime("%Y-%m-%d %H:%M")
    out["sampleCsv"] = raw.to_csv()
    sample = ROOT / "ui" / "sample" / f"meter_{m}_sample.csv"
    out["sampleFile"] = sample.name

    UI_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_FILE.write_text("// Generated by ml/export_ui_data.py - do not edit by hand.\nwindow.EP_DATA = "
                       + json.dumps(out, separators=(",", ":")) + ";\n", encoding="utf-8")
    sample.parent.mkdir(parents=True, exist_ok=True)
    for old in sample.parent.glob("meter_*_sample.csv"):
        if old != sample:
            old.unlink()
    raw.to_csv(sample)
    print(f"meter {m}: {len(past)} past hours, {len(future)} forecast hours, {len(out_alerts)} alerts since "
          f"{ALERTS_FROM:%d %b}, {len(year_alerts)} alerts in 2014")
    print("accuracy", out["accuracy"], "| today", out["today"], "| report all", out["report"]["allMeters"], "wins", wins)


if __name__ == "__main__":
    main()
