# EnergyPulse AI

Forecast the next 24 hours of electricity consumption for a meter, flag readings that are
outside what was expected, and let a person review each alert.

This folder holds the work for **Evaluation 2: ML model + UI/UX design**.

| Evaluation item | Where to look |
|---|---|
| Trained and evaluated model | `ml/notebooks/EnergyPulse_ML.ipynb` (already executed; `EnergyPulse_ML.html` opens in any browser) |
| UI screens | `ui/design/EnergyPulse_UI_Design.pdf`, `ui/screenshots/`, or open `ui/index.html` |
| Explanation for the team (Arabic) | `docs/Team_Guide_AR.html` |

## Results (test year 2014, never used for training or tuning)

Day-ahead forecast, mean WAPE across meters (lower is better):

| Method | 20 modelled meters | 10 unseen meters |
|---|---|---|
| Seasonal Naive, same hour last week (baseline) | 11.52 % | 13.64 % |
| Seasonal Naive, same hour yesterday (baseline) | 9.31 % | 14.21 % |
| Random Forest | 7.85 % | 13.39 % |
| **XGBoost (selected on validation)** | **7.91 %** | 13.84 % |

XGBoost beats both baselines on 20 of 20 modelled meters (MAE, RMSE and WAPE). On unseen
meters the gain is small and not on every meter; the notebook discusses this openly.

Anomaly detection: forecast-residual thresholds flag 3.1 % of test hours (about 9 alerts per
meter per month), compared with Isolation Forest. The dataset has no fault labels, so no
"accuracy" is claimed.

## Data

UCI *ElectricityLoadDiagrams20112014*: 370 real meters in Portugal, one reading every
15 minutes, 2011-2014. https://archive.ics.uci.edu/dataset/321/electricityloaddiagrams20112014

No synthetic or AI-generated data is used for training.

## Folder map

```
ml/src/config.py           every setting of the experiment (dates, lags, thresholds)
ml/src/prepare_data.py     step 1  raw file -> clean hourly kWh, meter selection
ml/src/features.py         step 2  leak-free features, scaling, chronological split
ml/src/train_forecast.py   step 3  baselines, Random Forest, XGBoost, tuning, test scores
ml/src/anomaly.py          step 4  residual thresholds, Isolation Forest, alerts
ml/src/export_ui_data.py   step 5  real model output for the UI screens
ml/src/plots.py            figures used by the notebook
ml/data/                   cleaned hourly data (small files only)
ml/outputs/                metrics, predictions, alerts, figures, trained model
ml/notebooks/              the notebook shown in the evaluation
ui/                        the interface prototype (HTML, CSS, JavaScript; no Streamlit)
docs/                      team guide
```

## Run it again

```
pip install -r requirements.txt

# the raw file LD2011_2014.txt must sit next to the EnergyPulse-AI folder
python ml/src/prepare_data.py      # each step takes a few minutes
python ml/src/train_forecast.py
python ml/src/anomaly.py
python ml/src/export_ui_data.py

# notebook
cd ml/notebooks
jupyter notebook EnergyPulse_ML.ipynb
```

The UI needs no install: open `ui/index.html` in a browser.

## Next evaluation

Serve `ml/outputs/models/xgb_forecaster.json` behind FastAPI, connect the UI to it through
the ASP.NET Core API, and deploy with Docker.
