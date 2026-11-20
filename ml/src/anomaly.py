"""Step 4 - Anomaly detection on top of the forecast.

Run:  python ml/src/anomaly.py      (after train_forecast.py)

Method A - forecast-residual thresholds (the EnergyPulse method)
    residual = actual - expected (XGBoost day-ahead forecast), divided by the
    meter's scale. For every meter and every hour of the day we learn what a
    "normal" residual looks like from the VALIDATION period (median and MAD),
    then flag a test hour when its robust z-score is beyond +/- 3.5.

Method B - Isolation Forest (comparison)
    Unsupervised model fitted on TRAIN, with no forecast involved. Its alert
    budget is matched to method A on VALIDATION so the comparison is fair.

The dataset has NO anomaly labels, so we never report "accuracy". We report
alert volumes, agreement between the two methods, what the alerts look like,
and a controlled injection test (known artificial spikes added to real data).
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest

import config as C
import features as F

IF_FEATURES = ["y_scaled", "dev_lag_24", "dev_lag_168", "dev_same_hour", "hour", "is_weekend"]


# ------------------------------------------------------------------ method A
def fit_thresholds(val: pd.DataFrame) -> pd.DataFrame:
    """Per meter and hour of day: median and MAD of the validation residuals."""
    r = val.assign(hour=val.index.hour)
    g = r.groupby(["meter", "hour"])["rel_resid"]
    med = g.median().rename("median")
    mad = g.apply(lambda s: (s - s.median()).abs().median()).rename("mad")
    return pd.concat([med, mad], axis=1).reset_index()


def robust_z(df: pd.DataFrame, thr: pd.DataFrame) -> np.ndarray:
    """Modified z-score: 0.6745 * (x - median) / MAD  (robust to outliers)."""
    key = pd.DataFrame({"meter": df["meter"].values, "hour": df.index.hour})
    t = key.merge(thr, on=["meter", "hour"], how="left")
    return 0.6745 * (df["rel_resid"].values - t["median"].values) / t["mad"].clip(lower=1e-9).values


def add_residuals(df: pd.DataFrame, pred_col="xgb") -> pd.DataFrame:
    df = df.copy()
    df["expected"] = df[pred_col]
    df["rel_resid"] = (df["y"] - df["expected"]) / df["scale"]
    return df


# ------------------------------------------------------------------ method B
def if_table(t: pd.DataFrame) -> pd.DataFrame:
    """Scale-free description of one reading, WITHOUT using the forecast."""
    return pd.DataFrame({
        "y_scaled": t.y_scaled,
        "dev_lag_24": t.y_scaled - t.lag_24,            # vs same hour yesterday
        "dev_lag_168": t.y_scaled - t.lag_168,          # vs same hour last week
        "dev_same_hour": t.y_scaled - t.same_hour_mean_4w,
        "hour": t.hour, "is_weekend": t.is_weekend}, index=t.index)


# ------------------------------------------------------------------ alerts
def build_alerts(hourly: pd.DataFrame, flag_col="flag_resid", tariff=C.DEFAULT_TARIFF) -> pd.DataFrame:
    """Merge neighbouring flagged hours into one reviewable alert."""
    rows = []
    for meter, g in hourly[hourly[flag_col]].groupby("meter"):
        g = g.assign(direction=np.where(g.z > 0, "spike", "drop"))
        for direction, d in g.groupby("direction"):
            gap = d.index.to_series().diff() > pd.Timedelta(hours=C.MAX_EVENT_GAP_HOURS + 1)
            for _, ev in d.groupby(gap.cumsum()):
                excess = float((ev.y - ev.expected).sum())
                peak = float(ev.z.abs().max())
                rows.append({
                    "meter": meter, "start": ev.index[0], "end": ev.index[-1] + pd.Timedelta(hours=1),
                    "flagged_hours": len(ev), "direction": direction,
                    "actual_kwh": float(ev.y.sum()), "expected_kwh": float(ev.expected.sum()),
                    "excess_kwh": excess, "excess_pct": excess / float(ev.expected.sum()) * 100,
                    "estimated_cost": max(excess, 0) * tariff, "peak_z": peak,
                    "severity": "high" if peak >= 8 else "medium" if peak >= 5 else "low",
                    "is_holiday": int(ev.is_holiday.max()), "status": "needs_review"})
    return pd.DataFrame(rows).sort_values(["meter", "start"]).reset_index(drop=True)


# ------------------------------------------------------------------ injection test
def injection_test(hourly_raw, meters, model, thr, iforest, if_thr, clean_test):
    """Add artificial spikes to REAL test-year readings and count how many each
    method catches. The models are never trained on these spikes."""
    rng = np.random.default_rng(C.RANDOM_SEED)
    test_start = pd.Timestamp(C.VAL_END) + pd.Timedelta(hours=1)
    slots = {}
    for m in meters:                        # same positions for every magnitude
        idx = hourly_raw.loc[test_start:].index
        # one random 3-day block per event + a random hour inside it -> events
        # never overlap and fall on every hour of the day
        blocks = rng.choice(np.arange(48, len(idx) - 96, 72), size=C.INJECT_EVENTS_PER_METER, replace=False)
        starts = blocks + rng.integers(0, 48, size=C.INJECT_EVENTS_PER_METER)
        slots[m] = [idx[s:s + C.INJECT_DURATION_HOURS] for s in sorted(starts)]

    rows = []
    for mag in C.INJECT_MAGNITUDES:
        hit_a = hit_b = total = 0
        fa_a, fa_b = [], []
        for m in meters:
            y = hourly_raw[m].copy()
            for ev in slots[m]:
                y.loc[ev] = y.loc[ev] * (1 + mag)
            t = F.split(F.make_table(y.to_frame(m), [m]))[2].copy()
            t["xgb"] = model.predict(t[F.FEATURES]) * t.scale
            t = add_residuals(t)
            fa = robust_z(t, thr) > C.ROBUST_Z_THRESHOLD              # spikes only
            fb = iforest.score_samples(if_table(t)[IF_FEATURES]) < if_thr[m]
            fa, fb = pd.Series(fa, index=t.index), pd.Series(fb, index=t.index)
            injected = pd.DatetimeIndex(np.concatenate([e.values for e in slots[m]]))
            for ev in slots[m]:
                total += 1
                hit_a += bool(fa.loc[ev].any())
                hit_b += bool(fb.loc[ev].any())
            fa_a.append(fa.drop(injected).mean())
            fa_b.append(fb.drop(injected).mean())
        rows.append({"magnitude_pct": int(mag * 100), "events": total,
                     "recall_residual": hit_a / total * 100, "recall_iforest": hit_b / total * 100,
                     "alert_rate_other_hours_residual": np.mean(fa_a) * 100,
                     "alert_rate_other_hours_iforest": np.mean(fa_b) * 100})
    return pd.DataFrame(rows)


def main():
    hourly_raw, sel = F.load_hourly(), F.load_selection()
    meters = sel.index[sel.role == "modelled"].tolist()
    preds = pd.read_csv(C.PREDICTIONS_FILE, index_col=0, parse_dates=True)
    preds = preds[preds.role == "modelled"]

    table = F.make_table(hourly_raw, meters)
    train, val_t, test_t = F.split(table)
    extra = ["y_scaled", "lag_24", "lag_168", "same_hour_mean_4w", "hour", "is_weekend", "is_holiday"]

    def attach(split_name, t):
        p = preds[preds.split == split_name].set_index("meter", append=True)
        return p.join(t.set_index("meter", append=True)[extra]).reset_index(level="meter")

    val, test = add_residuals(attach("val", val_t)), add_residuals(attach("test", test_t))

    # ---- method A: thresholds from validation, applied to test
    thr = fit_thresholds(val)
    val["z"], test["z"] = robust_z(val, thr), robust_z(test, thr)
    val["flag_resid"] = val.z.abs() > C.ROBUST_Z_THRESHOLD
    test["flag_resid"] = test.z.abs() > C.ROBUST_Z_THRESHOLD

    # ---- method B: Isolation Forest fitted on train, budget matched on validation
    iforest = IsolationForest(n_estimators=200, max_samples=2048, random_state=C.RANDOM_SEED, n_jobs=-1)
    iforest.fit(if_table(train)[IF_FEATURES])
    val["if_score"] = iforest.score_samples(if_table(val)[IF_FEATURES])
    test["if_score"] = iforest.score_samples(if_table(test)[IF_FEATURES])
    if_thr = {m: g.if_score.quantile(max(g.flag_resid.mean(), 1e-4)) for m, g in val.groupby("meter")}
    test["flag_iforest"] = test.if_score < test.meter.map(if_thr)

    # ---- outputs
    alerts = build_alerts(test)
    both = (test.flag_resid & test.flag_iforest).sum()
    either = (test.flag_resid | test.flag_iforest).sum()
    summary = pd.DataFrame([{
        "test_hours": len(test),
        "val_alert_rate_residual_pct": val.flag_resid.mean() * 100,
        "test_alert_rate_residual_pct": test.flag_resid.mean() * 100,
        "test_alert_rate_iforest_pct": test.flag_iforest.mean() * 100,
        "flagged_by_both_hours": int(both), "jaccard_overlap_pct": both / either * 100,
        "alerts_events": len(alerts), "alerts_per_meter_per_month": len(alerts) / len(meters) / 12,
        "spike_alerts": int((alerts.direction == "spike").sum()), "drop_alerts": int((alerts.direction == "drop").sum()),
        "holiday_share_of_flagged_hours_pct": test[test.flag_resid].is_holiday.mean() * 100,
        "holiday_share_of_all_hours_pct": test.is_holiday.mean() * 100,
        "total_excess_kwh_spikes": alerts.loc[alerts.direction == "spike", "excess_kwh"].sum()}])

    model = xgb.XGBRegressor()
    model.load_model(C.MODEL_FILE)
    inj = injection_test(hourly_raw, meters, model, thr, iforest, if_thr, test)

    thr.round(6).to_csv(C.THRESHOLDS_FILE, index=False)
    test[["meter", "y", "expected", "scale", "z", "flag_resid", "if_score", "flag_iforest", "is_holiday"]].round(4).to_csv(C.ANOMALY_HOURLY_FILE)
    alerts.round({c: 3 for c in alerts.select_dtypes("float").columns}).to_csv(C.ALERTS_FILE, index=False)
    summary.round(3).to_csv(C.ANOMALY_SUMMARY_FILE, index=False)
    inj.round(2).to_csv(C.INJECTION_FILE, index=False)

    print(summary.round(2).T.to_string(header=False))
    print("\nInjection test (artificial spikes on real test data)")
    print(inj.round(1).to_string(index=False))
    print("\nseverity:", alerts.severity.value_counts().to_dict())


if __name__ == "__main__":
    main()
