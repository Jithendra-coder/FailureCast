# Model card: FailureCast RUL predictor

## Intended use

Research and portfolio demonstration of remaining-useful-life (RUL) regression using NASA C-MAPSS simulated turbofan trajectories or clearly labeled generated demo data. Outputs support model comparison and system engineering demonstrations only.

## Out-of-scope use

Do not use to schedule or defer real maintenance, control equipment, guarantee service life, or make safety-critical decisions. No certified aircraft or industrial data are supplied.

## Data and training

The default active version is a deterministic HistGradientBoostingRegressor trained on locally generated C-MAPSS-shaped trajectories. Imported-data candidates can use HistGradientBoostingRegressor, an operating-condition-aware HistGradientBoostingRegressor, or RandomForestRegressor. The condition-aware pipeline fits operating-setting clusters and sensor normalization on training rows only while retaining raw features. The optional PyTorch LSTM uses fixed 30-cycle windows. Training labels are derived from complete training engines with a configurable-in-code cap of 125. A seeded engine-level 80/20 holdout evaluates one observation at 80% of each held-out training trajectory; the final artifact is then refit on all official training engines. This approximates the censored endpoint task but does not reproduce arbitrary in-service censoring.

## Features and outputs

Inputs: 3 operating settings, 21 sensor measurements, cycle index, trailing-five sensor means, and trailing sensor changes. The output is a non-negative scalar in operating cycles. The API returns its model version and prediction timestamp. No uncertainty or confidence percentage is reported because intervals have not been calibrated.

## Evaluation

Validation includes MAE, RMSE, prediction bias, and the NASA asymmetric score. Official C-MAPSS test evaluation uses the final observed cycle and the provided RUL labels, and is only available after model activation. A fixed four-model benchmark with five train-only engine holdout seeds was run on all four official subsets; results and exact protocol are in [the benchmark report](evaluation/nasa-cmapss-benchmark-2026-10.md). Evaluation summaries must retain the dataset version and model ID. Do not claim a performance improvement without a same-dataset, same-protocol baseline comparison.

Inference, promotion, rollback, and final test evaluation require the model's content-derived dataset version to match the selected dataset exactly. Changing the selected dataset pauses forecasts until a compatible version is activated.

## Limitations

The demo trajectories are synthetic and intentionally simple. Results may not generalize across subsets, operating conditions, real equipment, or sensor systems. The fixed benchmark does not establish best-in-class accuracy. FD002 and FD004 have materially higher test error than FD001 and FD003. The optional LSTM was not benchmarked in this environment. Drift alerts are statistical review signals; local feature perturbation is sensitivity analysis rather than causal explanation. Dataset target cap and model settings are fixed.
