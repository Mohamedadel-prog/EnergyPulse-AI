"""Step 3 - Train, tune and evaluate the day-ahead forecasting models.

Run:  python ml/src/train_forecast.py

Models compared
  * Seasonal Naive (weekly)  : y_hat[t] = y[t-168]   <- baseline from the proposal
  * Seasonal Naive (daily)   : y_hat[t] = y[t-24]    <- second, stronger baseline
  * Random Forest            : one model for all meters, scaled features
  * XGBoost                  : one model for all meters, scaled features

Protocol (no leakage)
  1. fit on TRAIN only, compare hyper-parameters on VALIDATION
  2. refit the chosen configuration on TRAIN + VALIDATION
  3. score ONCE on TEST (2014) - the test year is never used for any decision
"""
import json
import time

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestRegressor

import config as C
import features as F

RF_GRID = [
    {"min_samples_leaf": 5, "max_features": 0.33},
    {"min_samples_leaf": 5, "max_features": 0.5},
    {"min_samples_leaf": 20, "max_features": 0.33},
    {"min_samples_leaf": 20, "max_features": 0.5},
]
RF_FIXED = {"n_estimators": 100, "max_samples": 0.5, "n_jobs": -1, "random_state": C.RANDOM_SEED}

XGB_GRID = [{"max_depth": d, "min_child_weight": w} for d in (6, 8, 10) for w in (5, 20)]
XGB_FIXED = {"learning_rate": 0.03, "subsample": 0.8, "colsample_bytree": 0.8,
             "tree_method": "hist", "n_jobs": -1, "random_state": C.RANDOM_SEED}
XGB_MAX_ROUNDS, XGB_PATIENCE = 4000, 100

MODEL_COLS = ["naive_weekly", "naive_daily", "rf", "xgb"]


# ------------------------------------------------------------------ metrics
def mae(y, p):
    return float(np.mean(np.abs(y - p)))


def rmse(y, p):
    return float(np.sqrt(np.mean((y - p) ** 2)))


def wape(y, p):
    """Weighted Absolute Percentage Error = sum|error| / sum|actual| (in %).
    Unlike MAPE it does not explode when a single reading is close to zero,
    and it is comparable between a small and a large meter."""
    return float(np.abs(y - p).sum() / np.abs(y).sum() * 100)


def score_table(df: pd.DataFrame, cols=MODEL_COLS) -> pd.DataFrame:
    """MAE / RMSE / WAPE for every meter and every model (errors in kWh)."""
    rows = []
    for meter, g in df.groupby("meter"):
        for c in cols:
            rows.append({"meter": meter, "model": c, "MAE": mae(g.y, g[c]),
                         "RMSE": rmse(g.y, g[c]), "WAPE": wape(g.y, g[c]), "mean_kwh": g.y.mean()})
    return pd.DataFrame(rows)


def mean_wape(df: pd.DataFrame, col: str) -> float:
    return float(np.mean([wape(g.y, g[col]) for _, g in df.groupby("meter")]))


# ------------------------------------------------------------------ training
def predict_kwh(model, df: pd.DataFrame) -> np.ndarray:
    """The models predict the SCALED target; multiply by scale to get kWh back."""
    return model.predict(df[F.FEATURES]) * df["scale"].values


def tune_random_forest(train: pd.DataFrame, val: pd.DataFrame, verbose=True):
    """Fit every RF configuration on TRAIN, score it on VALIDATION, keep the best."""
    best, log = None, []
    for p in RF_GRID:
        m = RandomForestRegressor(**RF_FIXED, **p).fit(train[F.FEATURES], train.y_scaled)
        pred = pd.Series(predict_kwh(m, val), index=val.index)
        s = mean_wape(val.assign(_p=pred), "_p")
        log.append({"model": "rf", **p, "val_mean_WAPE": round(s, 3)})
        if verbose:
            print(f"  RF  {p}  val WAPE={s:.3f}")
        if best is None or s < best[0]:
            best = (s, p, pred)
    return best[1], best[2], log


def tune_xgboost(train: pd.DataFrame, val: pd.DataFrame, verbose=True):
    """Same for XGBoost. Early stopping watches VALIDATION only (never test);
    the number of trees it finds is stored and reused for the final refit."""
    best, log = None, []
    for p in XGB_GRID:
        m = xgb.XGBRegressor(**XGB_FIXED, **p, n_estimators=XGB_MAX_ROUNDS, early_stopping_rounds=XGB_PATIENCE)
        m.fit(train[F.FEATURES], train.y_scaled, eval_set=[(val[F.FEATURES], val.y_scaled)], verbose=False)
        pred = pd.Series(predict_kwh(m, val), index=val.index)
        s = mean_wape(val.assign(_p=pred), "_p")
        log.append({"model": "xgb", **p, "n_trees": m.best_iteration + 1, "val_mean_WAPE": round(s, 3)})
        if verbose:
            print(f"  XGB {p}  trees={m.best_iteration + 1}  val WAPE={s:.3f}")
        if best is None or s < best[0]:
            best = (s, {**p, "n_estimators": m.best_iteration + 1}, pred)
    return best[1], best[2], log


def fit_final(train_val: pd.DataFrame, rf_params: dict, xgb_params: dict):
    """Refit the chosen configurations on TRAIN + VALIDATION (more recent data)."""
    rf = RandomForestRegressor(**RF_FIXED, **rf_params).fit(train_val[F.FEATURES], train_val.y_scaled)
    xg = xgb.XGBRegressor(**XGB_FIXED, **xgb_params).fit(train_val[F.FEATURES], train_val.y_scaled)
    return rf, xg


def main():
    t0 = time.time()
    hourly, sel = F.load_hourly(), F.load_selection()
    modelled = sel.index[sel.role == "modelled"].tolist()
    unseen = sel.index[sel.role == "unseen"].tolist()

    table = F.make_table(hourly, modelled)
    train, val, test = F.split(table)
    val, test = val.copy(), test.copy()
    print(f"rows  train={len(train):,}  val={len(val):,}  test={len(test):,}  features={len(F.FEATURES)}")
    assert train.index.max() < val.index.min() <= val.index.max() < test.index.min(), "splits overlap!"

    # 1) tune on validation
    rf_params, val["rf"], rf_log = tune_random_forest(train, val)
    xgb_params, val["xgb"], xgb_log = tune_xgboost(train, val)

    # 2) refit on train + validation
    rf, xg = fit_final(pd.concat([train, val]), rf_params, xgb_params)

    # 3) single evaluation on the untouched test year
    test["rf"], test["xgb"] = predict_kwh(rf, test), predict_kwh(xg, test)

    # 4) generalisation: meters the models have never seen (same test year)
    un = F.split(F.make_table(hourly, unseen))[2].copy()
    un["rf"], un["xgb"] = predict_kwh(rf, un), predict_kwh(xg, un)

    # ---- save everything
    C.OUT_DIR.mkdir(parents=True, exist_ok=True)
    C.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    keep = ["meter", "y", "scale"] + MODEL_COLS
    preds = pd.concat([val[keep].assign(split="val", role="modelled"),
                       test[keep].assign(split="test", role="modelled"),
                       un[keep].assign(split="test", role="unseen")])
    preds.round(3).to_csv(C.PREDICTIONS_FILE)

    metrics = pd.concat([score_table(val).assign(split="val", role="modelled"),
                         score_table(test).assign(split="test", role="modelled"),
                         score_table(un).assign(split="test", role="unseen")])
    metrics.round(4).to_csv(C.METRICS_FILE, index=False)
    pd.DataFrame(rf_log + xgb_log).to_csv(C.TUNING_FILE, index=False)

    imp = pd.DataFrame({"feature": F.FEATURES, "xgb_gain": xg.feature_importances_,
                        "rf_importance": rf.feature_importances_}).sort_values("xgb_gain", ascending=False)
    imp.round(5).to_csv(C.IMPORTANCE_FILE, index=False)

    xg.save_model(C.MODEL_FILE)
    json.dump({"features": F.FEATURES, "horizon_hours": C.HORIZON, "target": "y / scale",
               "scale": "mean hourly kWh of the last visible week (t-191h .. t-24h)",
               "trained_on": f"{C.PERIOD_START} -> {C.VAL_END}", "meters": modelled,
               "xgb_params": {**XGB_FIXED, **xgb_params}, "rf_params": {**RF_FIXED, **rf_params}},
              open(C.MODEL_META_FILE, "w"), indent=2)

    for name, part in [("VALIDATION (used for tuning)", val), ("TEST 2014 - modelled meters", test),
                       ("TEST 2014 - unseen meters", un)]:
        print(f"\n{name}")
        for c in MODEL_COLS:
            print(f"  {c:13s} mean WAPE = {mean_wape(part, c):6.2f} %")
    print(f"\nbest RF  : {rf_params}\nbest XGB : {xgb_params}\ndone in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
