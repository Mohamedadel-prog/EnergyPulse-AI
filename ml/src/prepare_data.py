"""Step 1 - Load the raw UCI file, clean it, and build the hourly dataset.

Run:  python ml/src/prepare_data.py

Raw file facts (UCI ElectricityLoadDiagrams20112014):
  * 140,256 rows x 370 meters, one row every 15 minutes, 2011-2014
  * values are average kW in the 15-minute interval -> kWh = kW / 4
  * Portuguese local time, so there are two daylight-saving artefacts per year
    (see fix_daylight_saving)
"""
import numpy as np
import pandas as pd

import config as C


def load_raw(path=C.RAW_FILE) -> pd.DataFrame:
    """Read the 711 MB text file in chunks (semicolon separated, decimal comma)."""
    chunks = []
    for ch in pd.read_csv(path, sep=";", decimal=",", index_col=0, chunksize=20_000):
        ch.index = pd.to_datetime(ch.index)
        chunks.append(ch.astype("float32"))
    df = pd.concat(chunks)
    df.index.name = "timestamp"
    return df


def last_sunday(year: int, month: int) -> pd.Timestamp:
    days = pd.date_range(f"{year}-{month:02d}-01", periods=31, freq="D")
    days = days[(days.month == month) & (days.dayofweek == 6)]
    return days[-1]


def fix_daylight_saving(df: pd.DataFrame) -> pd.DataFrame:
    """Repair the two daylight-saving artefacts (verified on the raw file).

    Last Sunday of March - the clock jumps from 01:00 to 02:00, so the local
        hour 01:00-01:59 does not exist. The file still has 4 rows for it
        (01:00, 01:15, 01:30, 01:45) holding zeros or tiny placeholder values.
        They are not real consumption -> mark them as missing (NaN).
    Last Sunday of October - the hour 01:00-01:59 happens twice and the file
        stores the SUM of both -> divide the 4 rows by 2.
    """
    df = df.copy()
    for year in sorted(set(df.index.year)):
        for month in (3, 10):
            day = last_sunday(year, month)
            mask = (df.index >= day + pd.Timedelta(hours=1)) & (df.index < day + pd.Timedelta(hours=2))
            if mask.any():
                df.loc[mask] = np.nan if month == 3 else df.loc[mask] / 2
    return df


def to_hourly_kwh(df_kw: pd.DataFrame) -> pd.DataFrame:
    """15-minute kW -> hourly kWh (rows 01:00, 01:15, 01:30, 01:45 -> hour 01:00).
    An hour is kept only if all 4 quarters exist, otherwise it is missing."""
    kwh = df_kw / 4.0
    return kwh.resample("1h").sum(min_count=4)


def longest_zero_run(values: np.ndarray) -> int:
    z = (values == 0).astype(int)
    if z.sum() == 0:
        return 0
    edges = np.diff(np.concatenate([[0], z, [0]]))
    return int((np.where(edges == -1)[0] - np.where(edges == 1)[0]).max())


def quality_report(hourly: pd.DataFrame) -> pd.DataFrame:
    rep = pd.DataFrame({
        "mean_kwh": hourly.mean(),
        "zero_share": (hourly == 0).mean(),
        "missing_share": hourly.isna().mean(),
        "longest_zero_run_h": hourly.fillna(1).apply(lambda s: longest_zero_run(s.values)),
        "first_nonzero": hourly.ne(0).idxmax(),
    })
    rep["eligible"] = (rep.zero_share <= C.MAX_ZERO_SHARE) & (rep.longest_zero_run_h <= C.MAX_ZERO_RUN_HOURS)
    rep.index.name = "meter"
    return rep


def stratified_pick(pool: pd.DataFrame, n: int, seed: int) -> list:
    """Split `pool` into n consumption-level bins (quantiles of mean kWh) and
    draw one meter from each bin with a fixed seed -> small, medium and large
    consumers are all represented and the choice is reproducible."""
    bins = pd.qcut(pool.mean_kwh, n, labels=False)
    rng = np.random.default_rng(seed)
    return [rng.choice(g.index.to_numpy()) for _, g in pool.groupby(bins)]


def select_meters(rep: pd.DataFrame) -> pd.DataFrame:
    elig = rep[rep.eligible].sort_values("mean_kwh")
    train_meters = stratified_pick(elig, C.N_METERS, C.RANDOM_SEED)
    unseen_meters = stratified_pick(elig.drop(train_meters), C.N_UNSEEN_METERS, C.RANDOM_SEED + 1)
    sel = elig.loc[train_meters + unseen_meters, ["mean_kwh", "zero_share"]].copy()
    sel["role"] = ["modelled"] * len(train_meters) + ["unseen"] * len(unseen_meters)
    return sel


def main():
    print(f"Reading {C.RAW_FILE} ...")
    raw = load_raw()
    print("raw shape:", raw.shape, "|", raw.index.min(), "->", raw.index.max())
    print("missing values:", int(raw.isna().sum().sum()), "| negative values:", int((raw < 0).sum().sum()),
          "| duplicated timestamps:", int(raw.index.duplicated().sum()))

    hourly = to_hourly_kwh(fix_daylight_saving(raw)).loc[C.PERIOD_START:C.PERIOD_END]
    n_gap = int(hourly.isna().sum().sum())
    # Fill the (very few) daylight-saving gaps with the same hour of the previous day.
    # Past-only fill: it never looks at a future value.
    hourly = hourly.fillna(hourly.shift(24))
    print("hourly shape:", hourly.shape, "| daylight-saving gaps filled:", n_gap,
          "| still missing:", int(hourly.isna().sum().sum()))

    rep = quality_report(hourly)
    sel = select_meters(rep)
    print(f"eligible meters: {int(rep.eligible.sum())} of {len(rep)} | selected: {dict(sel.role.value_counts())}")
    print(sel.round(3).to_string())

    C.DATA_DIR.mkdir(parents=True, exist_ok=True)
    hourly.round(4).to_csv(C.HOURLY_FILE)
    rep.round(5).to_csv(C.QUALITY_FILE)
    sel.round(5).to_csv(C.SELECTED_FILE)
    hourly[sel.index].round(4).to_csv(C.HOURLY_SELECTED_FILE)
    print("saved:", C.HOURLY_FILE.name, C.HOURLY_SELECTED_FILE.name, C.QUALITY_FILE.name, C.SELECTED_FILE.name)


if __name__ == "__main__":
    main()
