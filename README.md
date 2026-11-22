# EnergyPulse AI

Forecast the electricity consumption of a meter for every hour, 24 hours in advance, flag hours that
are far from the forecast, and let a person review each alert.

This folder holds the work for **Evaluation 2: ML model + UI/UX design**.

| Evaluation item | Where to look |
|---|---|
| Data and preprocessing | `ml/notebooks/01_preprocessing.ipynb` |
| Model training and evaluation | `ml/notebooks/02_model_training_evaluation.ipynb` |
| UI screens | `ui/design/EnergyPulse_UI_Design.pdf`, `ui/screenshots/`, or open `ui/index.html` |
| Team guide (Arabic): every step and likely questions | `docs/Team_Guide_AR.html` |

## Results (test year 2014, never used for training or for choosing settings)

20 meters, day-ahead forecast, average over the meters:

| Method | MAE (kWh) | RMSE (kWh) | WAPE |
|---|---|---|---|
| Baseline: same hour yesterday | 31.95 | 53.28 | 12.12 % |
| **XGBoost** | **29.07** | **43.33** | **10.57 %** |

XGBoost is better than the baseline on 16 of the 20 meters. Validation WAPE (10.61 %) and test WAPE
(10.57 %) are the same, so the model does not overfit.
Alerts: an hour is flagged when the error is larger than 3 x the normal error of that meter
(measured on the validation period). About 1.4 % of the hours in 2014 are flagged.

The 20 meters are chosen with the training period only (2012-01-01 to 2013-06-30), so no information
from the validation or test period is used before the final evaluation.

## Data

UCI *ElectricityLoadDiagrams20112014*: 370 real meters in Portugal, one reading every
15 minutes, 2011-2014. https://archive.ics.uci.edu/dataset/321/electricityloaddiagrams20112014

No synthetic or AI-generated data is used.

## Folder map

```
ml/notebooks/01_preprocessing.ipynb              dataset, quality checks, cleaning, split, features, scaling
ml/notebooks/02_model_training_evaluation.ipynb  baseline, XGBoost, evaluation, alerts
ml/data/hourly_kwh_20_meters.csv                 clean hourly kWh of the 20 meters
ml/data/features.csv.gz                          features ready for the model (output of notebook 1)
ml/outputs/models/xgb_forecaster.json            the trained model
ml/outputs/models/model_meta.json                features, scale per meter, alert thresholds
ml/outputs/test_results_per_meter.csv            test WAPE per meter
ml/outputs/flagged_hours_2014.csv                flagged hours in the test year
ml/export_ui_data.py                             writes the model's output for the UI (ui/assets/data.js)
ui/                                              the interface prototype (HTML, CSS, JavaScript; no Streamlit)
```

## Run it again

```
pip install -r requirements.txt
```

1. Download `LD2011_2014.txt` from the UCI page and put it next to the `EnergyPulse-AI` folder.
2. Open `ml/notebooks/01_preprocessing.ipynb` and run all cells (a few minutes).
3. Open `ml/notebooks/02_model_training_evaluation.ipynb` and run all cells.
4. Optional: `python ml/export_ui_data.py` refreshes the numbers shown in the UI.

Notebook 2 also runs without the raw file, because `ml/data/features.csv.gz` is already included.

The UI needs no install: open `ui/index.html` in a browser.

## Next evaluation

Serve `ml/outputs/models/xgb_forecaster.json` behind an API, connect the UI to it, and deploy.
