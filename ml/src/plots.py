"""Plot helpers used by the notebook. One consistent, colour-blind-safe style."""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C

INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e1e0d9", "#fcfcfb"
COLORS = {"naive_weekly": "#898781", "naive_daily": "#1baf7a", "rf": "#eb6834", "xgb": "#2a78d6"}
LABELS = {"naive_weekly": "Seasonal Naive (weekly)", "naive_daily": "Seasonal Naive (daily)",
          "rf": "Random Forest", "xgb": "XGBoost"}
ALERT = "#d03b3b"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": "#c3c2b7", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelcolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "font.size": 10, "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 150,
    "savefig.bbox": "tight"})


def save(fig, name):
    C.FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(C.FIG_DIR / f"{name}.png")
    return fig


def seasonality(y: pd.Series, meter: str):
    """Daily, weekly and yearly patterns of one meter (training period only)."""
    fig, ax = plt.subplots(1, 3, figsize=(14, 3.6))
    wk = y[y.index.dayofweek < 5].groupby(y[y.index.dayofweek < 5].index.hour).mean()
    we = y[y.index.dayofweek >= 5].groupby(y[y.index.dayofweek >= 5].index.hour).mean()
    ax[0].plot(wk.index, wk.values, color="#2a78d6", lw=2, label="Weekdays")
    ax[0].plot(we.index, we.values, color="#eb6834", lw=2, label="Weekend")
    ax[0].set(title="Daily pattern", xlabel="Hour of day", ylabel="Mean kWh per hour", xticks=range(0, 24, 3))
    ax[0].legend()
    dow = y.groupby(y.index.dayofweek).mean()
    ax[1].bar(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], dow.values, color="#2a78d6", width=0.6)
    ax[1].set(title="Weekly pattern", ylabel="Mean kWh per hour")
    mon = y.groupby(y.index.month).mean()
    ax[2].bar(mon.index, mon.values, color="#2a78d6", width=0.6)
    ax[2].set(title="Yearly pattern", xlabel="Month", ylabel="Mean kWh per hour", xticks=range(1, 13))
    for a in ax[1:]:
        a.grid(axis="x", visible=False)
    fig.suptitle(f"Seasonality of meter {meter} (training period)", x=0.01, ha="left", fontweight="bold")
    fig.tight_layout()
    return fig


def split_timeline(train, val, test):
    fig, ax = plt.subplots(figsize=(12, 2.2))
    parts = [("TRAIN\nfit the models", train, "#2a78d6"), ("VALIDATION\ntune + thresholds", val, "#eb6834"),
             ("TEST\nfinal score, used once", test, "#1baf7a")]
    for name, d, col in parts:
        a, b = d.index.min(), d.index.max()
        ax.barh(0, (b - a).days, left=a, color=col, height=0.5)
        ax.text(a + (b - a) / 2, 0, f"{name}\n{a:%b %Y} - {b:%b %Y}", ha="center", va="center", color="white",
                fontsize=9, fontweight="bold")
    ax.set(yticks=[], title="Chronological split (no shuffling)")
    ax.grid(False)
    ax.xaxis_date()
    return fig


def model_comparison(summary: pd.DataFrame):
    """summary: rows = evaluation set, columns = models, values = mean WAPE %."""
    fig, ax = plt.subplots(figsize=(11, 4))
    x, w = np.arange(len(summary)), 0.19
    for i, m in enumerate(summary.columns):
        bars = ax.bar(x + (i - 1.5) * w, summary[m], w - 0.02, color=COLORS[m], label=LABELS[m])
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.15, f"{b.get_height():.1f}", ha="center",
                    fontsize=9, color=INK)
    ax.set(xticks=x, xticklabels=summary.index, ylabel="Mean WAPE across meters (%)  - lower is better",
           title="Forecast error by model")
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.1))
    return fig


def per_meter(wape_table: pd.DataFrame, title):
    """Dumbbell: best baseline vs XGBoost for every meter."""
    t = wape_table.copy()
    t["baseline"] = t[["naive_weekly", "naive_daily"]].min(axis=1)
    t = t.sort_values("baseline")
    fig, ax = plt.subplots(figsize=(11, 0.3 * len(t) + 1.5))
    yy = np.arange(len(t))
    ax.hlines(yy, t.xgb, t.baseline, color=GRID, lw=3)
    ax.scatter(t.baseline, yy, color=MUTED, s=45, zorder=3, label="Best of the two baselines")
    ax.scatter(t.xgb, yy, color=COLORS["xgb"], s=45, zorder=3, label="XGBoost")
    ax.set(yticks=yy, yticklabels=t.index, xlabel="WAPE (%)  - lower is better", title=title)
    ax.legend(loc="lower right")
    return fig


def week_plot(df: pd.DataFrame, start, days=7, title=""):
    d = df.loc[start:pd.Timestamp(start) + pd.Timedelta(days=days)]
    fig, ax = plt.subplots(figsize=(13, 3.8))
    ax.plot(d.index, d.y, color=INK, lw=2, label="Actual")
    ax.plot(d.index, d.xgb, color=COLORS["xgb"], lw=2, label="XGBoost forecast (made 24 h earlier)")
    ax.plot(d.index, d.naive_weekly, color=MUTED, lw=1.3, ls="--", label="Seasonal Naive (weekly)")
    ax.set(ylabel="kWh per hour", title=title)
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.12))
    return fig


def error_breakdown(test: pd.DataFrame):
    """WAPE by hour of day and by month, pooled over meters (scaled errors)."""
    fig, ax = plt.subplots(1, 2, figsize=(13, 3.8))
    for key, a, lab in [(test.index.hour, ax[0], "Hour of day"), (test.index.month, ax[1], "Month")]:
        for m in ["naive_weekly", "naive_daily", "xgb"]:
            err = ((test[m] - test.y).abs() / test.scale).groupby(key).sum() / (test.y / test.scale).groupby(key).sum() * 100
            a.plot(err.index, err.values, color=COLORS[m], lw=2, marker="o", ms=4, label=LABELS[m])
        a.set(xlabel=lab, ylabel="WAPE (%)", title=f"Error by {lab.lower()} (test year)")
    ax[0].set_xticks(range(0, 24, 3))
    ax[1].set_xticks(range(1, 13))
    ax[0].legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.18))
    fig.tight_layout()
    return fig


def importance(imp: pd.DataFrame):
    t = imp.sort_values("xgb_gain")
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.barh(t.feature, t.xgb_gain * 100, color=COLORS["xgb"], height=0.6)
    ax.set(xlabel="Share of total gain (%)", title="XGBoost feature importance")
    ax.grid(axis="y", visible=False)
    return fig


def z_timeline(d: pd.DataFrame, meter):
    fig, ax = plt.subplots(figsize=(13, 3.6))
    ax.plot(d.index, d.z, color=MUTED, lw=0.6)
    f = d[d.flag_resid]
    ax.scatter(f.index, f.z, color=ALERT, s=12, zorder=3, label=f"Flagged hours ({len(f)})")
    for k in (C.ROBUST_Z_THRESHOLD, -C.ROBUST_Z_THRESHOLD):
        ax.axhline(k, color=INK, lw=1, ls="--")
    ax.set(ylabel="Robust z-score of the residual", title=f"Meter {meter}: residual z-score in the test year (dashed = +/-{C.ROBUST_Z_THRESHOLD})")
    ax.legend(loc="upper left")
    return fig


def alert_zoom(d: pd.DataFrame, start, end, pad_h=36, title=""):
    w = d.loc[pd.Timestamp(start) - pd.Timedelta(hours=pad_h):pd.Timestamp(end) + pd.Timedelta(hours=pad_h)]
    fig, ax = plt.subplots(figsize=(13, 3.8))
    ax.plot(w.index, w.y, color=INK, lw=2, label="Actual")
    ax.plot(w.index, w.expected, color=COLORS["xgb"], lw=2, label="Expected (forecast)")
    fl = w[w.flag_resid]
    ax.scatter(fl.index, fl.y, color=ALERT, s=40, zorder=4, label="Flagged hour")
    ax.fill_between(w.index, w.expected, w.y, where=(w.flag_resid & (w.y > w.expected)).values, color=ALERT,
                    alpha=0.18, step="mid", label="Energy above expected")
    ax.set(ylabel="kWh per hour", title=title)
    ax.legend(ncol=4, loc="upper left", bbox_to_anchor=(0, -0.12))
    return fig


def injection(inj: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 4))
    x, w = np.arange(len(inj)), 0.36
    for i, (col, lab, c) in enumerate([("recall_residual", "Forecast-residual thresholds", COLORS["xgb"]),
                                       ("recall_iforest", "Isolation Forest", COLORS["rf"])]):
        bars = ax.bar(x + (i - 0.5) * w, inj[col], w - 0.03, color=c, label=lab)
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1.2, f"{b.get_height():.0f}%", ha="center", fontsize=9)
    ax.set(xticks=x, xticklabels=[f"+{m}%" for m in inj.magnitude_pct], xlabel="Size of the injected 3-hour spike",
           ylabel="Injected spikes detected (%)", ylim=(0, 112), title="Controlled injection test on real test-year data")
    ax.grid(axis="x", visible=False)
    ax.legend(ncol=2, loc="upper left", bbox_to_anchor=(0, -0.16))
    return fig


def alerts_per_meter(alerts: pd.DataFrame, meters):
    n = alerts.groupby("meter").size().reindex(meters).fillna(0).sort_values()
    fig, ax = plt.subplots(figsize=(11, 3.6))
    ax.bar(n.index, n.values, color=COLORS["xgb"], width=0.6)
    ax.set(ylabel="Alerts in 2014", title="Alert volume per meter (test year)")
    ax.tick_params(axis="x", rotation=60)
    ax.grid(axis="x", visible=False)
    return fig
