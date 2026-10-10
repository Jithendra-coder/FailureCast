# Model card: FailureCast RUL predictor

## Intended use

Research and portfolio demonstration of remaining-useful-life (RUL) regression using NASA C-MAPSS simulated turbofan trajectories or clearly labeled generated demo data. Outputs support model comparison and system engineering demonstrations only.

## Out-of-scope use

Do not use to schedule or defer real maintenance, control equipment, guarantee service life, or make safety-critical decisions. No certified aircraft or industrial data are supplied.

## Data and training

The default active version is a deterministic HistGradientBoostingRegressor trained on locally generated C-MAPSS-shaped trajectories. Imported-data candidates can use HistGradientBoostingRegressor or RandomForestRegressor. The optional PyTorch LSTM uses fixed 30-cycle windows. Training labels are derived from complete training engines with a configurable-in-code cap of 125. A seeded engine-level 80/20 holdout is used for validation.

## Features and outputs

Inputs: 3 operating settings, 21 sensor measurements, cycle index, trailing-five sensor means, and trailing sensor changes. The output is a non-negative scalar in operating cycles. The API returns its model version and prediction timestamp. No uncertainty or confidence percentage is reported because intervals have not been calibrated.

## Evaluation

Validation includes MAE, RMSE, prediction bias, and the NASA asymmetric score. Official C-MAPSS test evaluation uses the final observed cycle and the provided RUL labels, and is only available after model activation. Evaluation summaries must retain the dataset version and model ID. Do not claim a performance improvement without a same-dataset, same-protocol baseline comparison.

## Limitations

The demo trajectories are synthetic and intentionally simple. Results may not generalize across subsets, operating conditions, real equipment, or sensor systems. Drift alerts are statistical review signals; local feature perturbation is sensitivity analysis rather than causal explanation. Dataset target cap and model settings are fixed in this MVP.
