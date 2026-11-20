"""Step 5 - Export real model output for the UI screens.

Run:  python ml/src/export_ui_data.py      (after anomaly.py)

The UI is not connected to the model yet (that is the next evaluation), so the
screens read this static file. Every consumption / forecast / alert number in
it comes from the trained model on meter SHOWCASE_METER. Only the review
decisions (who marked what) are example values, flagged with "demo": true.
"""
import json

import numpy as np
import pandas as pd

import config as C
import features as F

NOW = pd.Timestamp("2014-06-19 10:00")       # the moment the screens pretend it is
HISTORY_DAYS, ALERT_WINDOW_DAYS = 7, 60
UI_FILE = C.PROJECT_DIR / "ui" / "assets" / "data.js"
SAMPLE_CSV = C.PROJECT_DIR / "ui" / "sample" / "meter_MT_287_sample.csv"

# example review decisions for older alerts (newest alerts stay "needs_review")
DEMO_REVIEWS = ["investigate", "expected", "expected", "investigate", "expected", "expected", "expected",
                "investigate", "expected", "expected"]
DEMO_NOTES = {"investigate": "Asked the night shift to check which equipment was left running.",
              "expected": "Planned activity - nothing to follow up."}


def r(x, n=1):
    return None if pd.isna(x) else round(float(x), n)


def main():
    m = C.SHOWCASE_METER
    hourly = pd.read_csv(C.ANOMALY_HOURLY_FILE, index_col=0, parse_dates=True)
    h = hourly[hourly.meter == m].copy()
    thr = pd.read_csv(C.THRESHOLDS_FILE)
    thr = thr[thr.meter == m].set_index("hour")
    k = C.ROBUST_Z_THRESHOLD / 0.6745
    hr = h.index.hour
    h["lo"] = h.expected + h["scale"] * (thr["median"].reindex(hr).values - k * thr["mad"].reindex(hr).values)
    h["hi"] = h.expected + h["scale"] * (thr["median"].reindex(hr).values + k * thr["mad"].reindex(hr).values)

    def points(d, with_actual=True):
        return [{"t": t.strftime("%Y-%m-%dT%H:%M"), "actual": r(x.y) if with_actual else None,
                 "expected": r(x.expected), "lo": r(max(x.lo, 0)), "hi": r(x.hi),
                 "flag": bool(x.flag_resid) if with_actual else False} for t, x in d.iterrows()]

    past = h.loc[NOW - pd.Timedelta(days=HISTORY_DAYS):NOW - pd.Timedelta(hours=1)]
    future = h.loc[NOW:NOW + pd.Timedelta(hours=23)]
    today = h.loc[NOW.normalize():NOW - pd.Timedelta(hours=1)]

    alerts = pd.read_csv(C.ALERTS_FILE, parse_dates=["start", "end"])
    a = alerts[(alerts.meter == m) & (alerts.end <= NOW) & (alerts.start >= NOW - pd.Timedelta(days=ALERT_WINDOW_DAYS))]
    a = a.sort_values("start", ascending=False).reset_index(drop=True)
    out_alerts = []
    for i, x in a.iterrows():
        status = "needs_review" if i < 4 else DEMO_REVIEWS[(i - 4) % len(DEMO_REVIEWS)]
        if x.is_holiday and i >= 4:
            status = "expected"
        win = h.loc[x.start - pd.Timedelta(hours=18):min(x.end + pd.Timedelta(hours=17), NOW - pd.Timedelta(hours=1))]
        first = h.loc[x.start]
        out_alerts.append({
            "id": f"A-{x.start:%m%d}-{x.start:%H}", "start": x.start.strftime("%Y-%m-%dT%H:%M"),
            "end": x.end.strftime("%Y-%m-%dT%H:%M"), "hours": int(x.flagged_hours), "direction": x.direction,
            "actual": r(x.actual_kwh), "expected": r(x.expected_kwh), "excess": r(x.excess_kwh),
            "pct": r(x.excess_pct), "peakZ": r(x.peak_z), "severity": x.severity, "holiday": bool(x.is_holiday),
            "normalLo": r(max(first.lo, 0)), "normalHi": r(first.hi),
            "status": status, "demo": status != "needs_review",
            "note": "Public holiday." if (x.is_holiday and status == "expected") else DEMO_NOTES.get(status, ""),
            "series": points(win)})

    month = alerts[(alerts.meter == m) & (alerts.direction == "spike") & (alerts.end <= NOW)
                   & (alerts.start >= NOW.normalize().replace(day=1))]
    metrics = pd.read_csv(C.METRICS_FILE)
    mm = metrics[(metrics.meter == m) & (metrics.split == "test")].set_index("model")

    data = {
        "generated_from": "EnergyPulse ML pipeline - trained XGBoost day-ahead forecaster + residual thresholds",
        "meter": {"id": m, "name": "Main meter", "source": "UCI ElectricityLoadDiagrams20112014",
                  "interval": "hourly (aggregated from 15-minute readings)",
                  "dataFrom": "2012-01-01", "dataTo": (NOW - pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")},
        "now": NOW.strftime("%Y-%m-%dT%H:%M"),
        "tariff": {"value": C.DEFAULT_TARIFF, "currency": "EUR"},
        "sensitivity": {"threshold": C.ROBUST_Z_THRESHOLD},
        "today": {"actual": r(today.y.sum()), "expected": r(today.expected.sum()),
                  "pct": r((today.y.sum() / today.expected.sum() - 1) * 100), "hours": len(today)},
        "month": {"excessKwh": r(month.excess_kwh.sum()), "alerts": int(len(month))},
        "next24": {"total": r(future.expected.sum()), "peak": r(future.expected.max()),
                   "peakAt": future.expected.idxmax().strftime("%Y-%m-%dT%H:%M"),
                   "low": r(future.expected.min()), "lowAt": future.expected.idxmin().strftime("%Y-%m-%dT%H:%M")},
        "accuracy": {"wape": r(mm.loc["xgb", "WAPE"], 2), "mae": r(mm.loc["xgb", "MAE"], 2),
                     "baselineWape": r(min(mm.loc["naive_daily", "WAPE"], mm.loc["naive_weekly", "WAPE"]), 2),
                     "weeklyWape": r(mm.loc["naive_weekly", "WAPE"], 2), "dailyWape": r(mm.loc["naive_daily", "WAPE"], 2),
                     "period": "all of 2014 (data the model never saw in training)"},
        "history": points(past), "forecast": points(future, with_actual=False), "alerts": out_alerts}

    # numbers for the "Model report" screen - straight from the saved evaluation files
    labels = {"naive_weekly": "Same hour last week", "naive_daily": "Same hour yesterday",
              "rf": "Random Forest", "xgb": "XGBoost (in use)"}
    tm = metrics[metrics.split == "test"]
    overall = tm.groupby(["role", "model"]).WAPE.mean()
    summ = pd.read_csv(C.ANOMALY_SUMMARY_FILE).iloc[0]
    inj = pd.read_csv(C.INJECTION_FILE)
    year_alerts = alerts[alerts.meter == m]
    data["report"] = {
        "testPeriod": "1 Jan - 31 Dec 2014", "trainedOn": "1 Jan 2012 - 31 Dec 2013",
        "metersModelled": int(tm[tm.role == "modelled"].meter.nunique()),
        "metersUnseen": int(tm[tm.role == "unseen"].meter.nunique()),
        "thisMeter": [{"key": k, "label": labels[k], "mae": r(mm.loc[k, "MAE"], 2), "rmse": r(mm.loc[k, "RMSE"], 2),
                       "wape": r(mm.loc[k, "WAPE"], 2)} for k in labels],
        "allMeters": [{"key": k, "label": labels[k], "modelled": r(overall["modelled", k], 2),
                       "unseen": r(overall["unseen", k], 2)} for k in labels],
        "meanKwh": r(mm.loc["xgb", "mean_kwh"], 1),
        "alerts2014": {"total": int(len(year_alerts)), "perMonth": r(len(year_alerts) / 12, 1),
                       "above": int((year_alerts.direction == "spike").sum()),
                       "below": int((year_alerts.direction == "drop").sum())},
        "flaggedHoursPct": r(summ.test_alert_rate_residual_pct, 1),
        "holidayShareFlaggedPct": r(summ.holiday_share_of_flagged_hours_pct, 1),
        "holidayShareAllPct": r(summ.holiday_share_of_all_hours_pct, 1),
        "injection": [{"size": int(x.magnitude_pct), "caught": r(x.recall_residual, 0),
                       "caughtIsolationForest": r(x.recall_iforest, 0)} for x in inj.itertuples()],
        "features": len(F.FEATURES)}

    # how many alerts each sensitivity level would have produced for this meter in 2014
    import anomaly as A
    levels = []
    for label, z in [("Fewer alerts", 5.0), ("Standard", C.ROBUST_Z_THRESHOLD), ("More alerts", 2.5)]:
        n = len(A.build_alerts(h.assign(flag_resid=h.z.abs() > z)))
        levels.append({"label": label, "threshold": z, "alertsPerMonth": r(n / 12, 0)})
    data["sensitivity"]["levels"] = levels

    # a real sample file for the upload screen (8 weeks of hourly readings before NOW)
    raw = F.load_hourly()[m].loc[NOW - pd.Timedelta(weeks=8):NOW - pd.Timedelta(hours=1)]
    raw = raw.round(2).rename("kwh").rename_axis("timestamp")
    data["sampleCsv"] = raw.to_csv()

    UI_FILE.parent.mkdir(parents=True, exist_ok=True)
    UI_FILE.write_text("// Generated by ml/src/export_ui_data.py - do not edit by hand.\nwindow.EP_DATA = "
                       + json.dumps(data, separators=(",", ":")) + ";\n", encoding="utf-8")

    SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
    raw.to_csv(SAMPLE_CSV)
    print(f"saved {UI_FILE.name}: {len(past)} past hours, {len(future)} forecast hours, {len(out_alerts)} alerts"
          f" | sample csv rows: {len(raw)}")
    print("today:", data["today"], "| month:", data["month"], "| next24:", data["next24"], "| accuracy:", data["accuracy"])


if __name__ == "__main__":
    main()
