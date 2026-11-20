"""Step 2 - Feature engineering for the day-ahead forecast.

LEAKAGE RULE: the model predicts hour t and may only see data that exists
24 hours earlier (t-24h or older). Therefore:
  * every lag is >= 24 hours,
  * every rolling window is computed on the series shifted by 24 hours,
  * the scaling factor of each row is also a past-only rolling mean,
  * calendar features (hour, weekday, holiday) are known in advance.
Nothing is ever "fitted" on the whole dataset (no global scaler, no global
mean), so no information from validation / test can reach the training rows.
"""
from datetime import date, timedelta

import pandas as pd
from dateutil.easter import easter

import config as C

# features measured in kWh -> divided by the meter's own recent level
LEVEL_FEATURES = ([f"lag_{l}" for l in C.LAGS]
                  + ["roll_mean_24", "roll_std_24", "roll_min_24", "roll_max_24",
                     "roll_std_168", "same_hour_mean_4w"])
CALENDAR_FEATURES = ["hour", "dayofweek", "is_weekend", "month", "is_holiday"]
FEATURES = LEVEL_FEATURES + CALENDAR_FEATURES


def portugal_holidays(years) -> set:
    """Portuguese national public holidays (the meters are in Portugal).
    Corpus Christi, 5 Oct, 1 Nov and 1 Dec were suspended in 2013-2015."""
    days = set()
    for y in years:
        e = easter(y)
        days |= {date(y, 1, 1), e - timedelta(days=2), e, date(y, 4, 25), date(y, 5, 1),
                 date(y, 6, 10), date(y, 8, 15), date(y, 12, 8), date(y, 12, 25)}
        if not 2013 <= y <= 2015:
            days |= {e + timedelta(days=60), date(y, 10, 5), date(y, 11, 1), date(y, 12, 1)}
    return days


def build_features(y: pd.Series) -> pd.DataFrame:
    """One meter -> table with target, scale and raw (kWh) features."""
    h = C.HORIZON
    df = pd.DataFrame({"y": y})

    # 1) lagged demand: same hour 1, 2, 3 days ago and 1, 2 weeks ago
    for lag in C.LAGS:
        df[f"lag_{lag}"] = y.shift(lag)

    # 2) rolling statistics of the most recent data we are allowed to see
    past = y.shift(h)                       # newest value inside every window is y[t-24]
    df["roll_mean_24"] = past.rolling(24).mean()
    df["roll_std_24"] = past.rolling(24).std()
    df["roll_min_24"] = past.rolling(24).min()
    df["roll_max_24"] = past.rolling(24).max()
    df["roll_mean_168"] = past.rolling(168).mean()
    df["roll_std_168"] = past.rolling(168).std()

    # 3) typical level of this exact hour-of-week (mean of the previous 4 weeks)
    df["same_hour_mean_4w"] = sum(y.shift(168 * k) for k in range(1, C.SAME_HOUR_WEEKS + 1)) / C.SAME_HOUR_WEEKS

    # 4) calendar / seasonality features - known in advance
    idx = df.index
    df["hour"] = idx.hour
    df["dayofweek"] = idx.dayofweek
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    df["month"] = idx.month
    holidays = portugal_holidays(range(idx.year.min(), idx.year.max() + 1))
    df["is_holiday"] = pd.Series(idx.date, index=idx).isin(holidays).astype(int)

    # 5) scale = the meter's average hourly consumption over the last visible week
    df["scale"] = df["roll_mean_168"].clip(lower=1e-6)
    df = df.drop(columns="roll_mean_168")

    return df.dropna()                      # first 4 weeks have no lag history


def scale_table(df: pd.DataFrame) -> pd.DataFrame:
    """Divide the target and all kWh features by `scale`.
    A 5 kWh shop and a 2,500 kWh factory become comparable (values around 1.0),
    so ONE model can learn from all meters and can serve a brand-new meter."""
    out = df.copy()
    for c in LEVEL_FEATURES:
        out[c] = out[c] / out["scale"]
    out["y_scaled"] = out["y"] / out["scale"]
    return out


def make_table(hourly: pd.DataFrame, meters) -> pd.DataFrame:
    """Stack the scaled feature tables of several meters into one long table."""
    parts = []
    for m in meters:
        t = scale_table(build_features(hourly[m]))
        t.insert(0, "meter", m)
        # the two baselines, kept in kWh
        t["naive_weekly"] = hourly[m].shift(C.SEASONAL_PERIOD).reindex(t.index)
        t["naive_daily"] = hourly[m].shift(C.HORIZON).reindex(t.index)
        parts.append(t)
    return pd.concat(parts)


def split(df: pd.DataFrame):
    """Chronological split - never shuffled."""
    val_start = pd.Timestamp(C.TRAIN_END) + pd.Timedelta(hours=1)
    test_start = pd.Timestamp(C.VAL_END) + pd.Timedelta(hours=1)
    train = df[df.index <= pd.Timestamp(C.TRAIN_END)]
    val = df[(df.index >= val_start) & (df.index <= pd.Timestamp(C.VAL_END))]
    test = df[df.index >= test_start]
    return train, val, test


def load_hourly() -> pd.DataFrame:
    return pd.read_csv(C.HOURLY_SELECTED_FILE, index_col=0, parse_dates=True)


def load_selection() -> pd.DataFrame:
    return pd.read_csv(C.SELECTED_FILE, index_col=0)
