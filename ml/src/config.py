"""Central configuration for the EnergyPulse AI machine-learning pipeline.

Every number that defines the experiment lives here, so the whole team
reads (and explains) the same settings.
"""
import os
from pathlib import Path

# ---------------------------------------------------------------- paths
ML_DIR = Path(__file__).resolve().parents[1]          # .../EnergyPulse-AI/ml
PROJECT_DIR = ML_DIR.parent                           # .../EnergyPulse-AI
DATA_DIR = ML_DIR / "data"
OUT_DIR = ML_DIR / "outputs"
FIG_DIR = OUT_DIR / "figures"
MODEL_DIR = OUT_DIR / "models"

# Raw UCI file (ElectricityLoadDiagrams20112014). Not committed to git (711 MB).
RAW_FILE = Path(os.environ.get("ENERGYPULSE_RAW", PROJECT_DIR.parent / "LD2011_2014.txt"))

HOURLY_FILE = DATA_DIR / "hourly_kwh_2012_2014.csv"            # all 370 meters (80 MB, git-ignored)
HOURLY_SELECTED_FILE = DATA_DIR / "hourly_kwh_selected.csv"     # 20 modelled + 10 unseen meters (small, committed)
QUALITY_FILE = DATA_DIR / "data_quality_report.csv"
SELECTED_FILE = DATA_DIR / "selected_meters.csv"

# ---------------------------------------------------------------- study period
# 2011 is excluded: 211 of the 370 meters are mostly zeros in 2011
# (they were connected later), so 2012-2014 is the common, usable period.
PERIOD_START = "2012-01-01 00:00"
PERIOD_END = "2014-12-31 23:00"

# ---------------------------------------------------------------- chronological split
# No shuffling anywhere: the past predicts the future.
TRAIN_END = "2013-06-30 23:00"   # train : 2012-01-01 -> 2013-06-30 (18 months)
VAL_END = "2013-12-31 23:00"     # val   : 2013-07-01 -> 2013-12-31 ( 6 months)
#                                  test  : 2014-01-01 -> 2014-12-31 (12 months, all seasons)

# ---------------------------------------------------------------- meter selection
MAX_ZERO_SHARE = 0.005       # at most 0.5 % zero readings in the study period
MAX_ZERO_RUN_HOURS = 3       # no outage longer than 3 hours
N_METERS = 20                # modelled meters: stratified sample across consumption levels
N_UNSEEN_METERS = 10         # extra meters NEVER used for training (generalisation check)
RANDOM_SEED = 42

# Example meter used in the plots and in the UI mock-ups (mid-size consumer).
SHOWCASE_METER = "MT_287"

# ---------------------------------------------------------------- forecasting task
HORIZON = 24                 # day-ahead: predict hour t using data up to t-24h only
LAGS = [24, 48, 72, 168, 336]            # all >= HORIZON
SAME_HOUR_WEEKS = 4                      # mean of the same hour in the previous 4 weeks
SEASONAL_PERIOD = 168                    # weekly seasonality (24 x 7)

# ---------------------------------------------------------------- anomaly detection
ROBUST_Z_THRESHOLD = 3.5     # modified z-score rule (Iglewicz & Hoaglin, 1993)
MAX_EVENT_GAP_HOURS = 1      # flagged hours separated by <= 1 normal hour form one alert
DEFAULT_TARIFF = 0.15        # currency per kWh -- USER-DEFINED in the app, example value only
INJECT_EVENTS_PER_METER = 30         # controlled test: artificial spikes added to real test data
INJECT_DURATION_HOURS = 3
INJECT_MAGNITUDES = [0.2, 0.4, 0.7, 1.0]   # +20 % ... +100 % above the real reading

PREDICTIONS_FILE = OUT_DIR / "predictions.csv.gz"
METRICS_FILE = OUT_DIR / "forecast_metrics.csv"
PARAMS_FILE = OUT_DIR / "best_params.csv"
IMPORTANCE_FILE = OUT_DIR / "feature_importance.csv"
TUNING_FILE = OUT_DIR / "tuning_log.csv"
THRESHOLDS_FILE = OUT_DIR / "anomaly_thresholds.csv"
ANOMALY_HOURLY_FILE = OUT_DIR / "anomaly_hourly.csv.gz"
ALERTS_FILE = OUT_DIR / "alerts.csv"
ANOMALY_SUMMARY_FILE = OUT_DIR / "anomaly_summary.csv"
INJECTION_FILE = OUT_DIR / "injection_results.csv"
MODEL_FILE = MODEL_DIR / "xgb_forecaster.json"
MODEL_META_FILE = MODEL_DIR / "model_meta.json"
