# NASA C-MAPSS benchmark

**Run date:** 2026-10-10
**Purpose:** reproducible research comparison of fixed RUL estimators. This is not maintenance validation.

## Dataset and protocol

The archive was downloaded from the [NASA C-MAPSS dataset listing](https://catalog.data.gov/dataset/cmapss-jet-engine-simulated-data), which links to NASA's public archive. NASA describes C-MAPSS as simulated turbofan degradation data in its [Prognostics Center of Excellence repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/). The downloaded archive was 12,425,978 bytes; SHA-256: `74BEF434A34DB25C7BF72E668EA4CD52AFE5F2CF8E44367C55A82BFD91A5A34F`.

Dataset acknowledgment: A. Saxena and K. Goebel (2008), “Turbofan Engine Degradation Simulation Data Set,” NASA Prognostics Data Repository, NASA Ames Research Center, Moffett Field, California. NASA PCoE requests acknowledgment of the repository and dataset contributors when its data are used. The raw archive is not redistributed in this repository.

The fixed candidates were MeanBaseline, HistGradientBoostingRegressor, a condition-aware HistGradientBoosting pipeline, and RandomForestRegressor. Each candidate was scored on five predeclared 80/20 engine-ID holdouts (seeds 41–45) using training trajectories only. Every held-out engine contributes one observation at 80% of its training trajectory; target RUL is capped at 125. The condition-aware transform clusters operating settings and computes sensor residual features from the training fold only; original features are retained. For final-cycle reporting, each estimator is refit on all official training engines, then evaluated once on the official test engines' final observed rows and supplied RUL labels. No test result was used to tune estimators or parameters. Subsets are independent; macro means are unweighted across the four subsets.

The [machine-readable CLI output](nasa-cmapss-repeated-seeds-2026-10.json) includes per-seed validation metrics, summary means and standard deviations, final-cycle test metrics, and source fingerprints.

## Results

Errors are cycles. Lower is better for MAE, RMSE, and NASA score. Bias is prediction minus true RUL; negative bias means underprediction. Validation values show mean ± population standard deviation across five engine-level splits; they are not confidence intervals.

| Subset | Estimator | Validation MAE | Validation RMSE | Final-cycle MAE | Final-cycle RMSE | Bias | NASA score |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| FD001 | MeanBaseline | 44.421 ± 2.820 | 45.289 ± 2.519 | 35.900 | 43.067 | 11.309 | 33,629.23 |
| FD001 | HistGradientBoosting | 16.998 ± 1.591 | 23.261 ± 1.422 | 14.181 | 19.400 | -1.025 | 693.64 |
| FD001 | Condition-aware HGB | 16.525 ± 1.811 | 22.608 ± 1.524 | 14.327 | 19.513 | -1.212 | 694.61 |
| FD001 | RandomForest | 16.339 ± 2.119 | 22.211 ± 1.592 | 14.391 | 19.369 | -1.101 | 675.90 |
| FD002 | MeanBaseline | 45.374 ± 1.992 | 46.288 ± 1.792 | 45.636 | 54.083 | 5.728 | 153,229.25 |
| FD002 | HistGradientBoosting | 16.683 ± 2.261 | 21.004 ± 2.540 | 20.237 | 28.243 | -8.149 | 10,121.31 |
| FD002 | Condition-aware HGB | 16.427 ± 1.974 | 20.596 ± 2.182 | 19.722 | 27.932 | -7.104 | 9,543.39 |
| FD002 | RandomForest | 15.970 ± 2.339 | 20.156 ± 2.671 | 19.783 | 27.952 | -7.610 | 9,751.14 |
| FD003 | MeanBaseline | 44.747 ± 2.937 | 47.428 ± 2.700 | 38.003 | 45.070 | 17.823 | 57,949.64 |
| FD003 | HistGradientBoosting | 17.098 ± 4.179 | 21.511 ± 4.794 | 12.958 | 17.532 | 1.893 | 663.75 |
| FD003 | Condition-aware HGB | 17.004 ± 3.634 | 20.913 ± 4.220 | 13.191 | 17.517 | 2.226 | 621.63 |
| FD003 | RandomForest | 16.645 ± 4.001 | 21.110 ± 5.002 | 14.121 | 18.608 | 1.703 | 779.43 |
| FD004 | MeanBaseline | 43.324 ± 1.408 | 45.483 ± 1.401 | 46.753 | 54.902 | 6.433 | 189,682.81 |
| FD004 | HistGradientBoosting | 20.371 ± 2.567 | 25.114 ± 2.789 | 21.715 | 28.977 | -6.913 | 6,021.49 |
| FD004 | Condition-aware HGB | 18.773 ± 2.446 | 23.185 ± 3.071 | 21.251 | 28.753 | -7.446 | 5,983.71 |
| FD004 | RandomForest | 19.186 ± 2.156 | 23.745 ± 2.562 | 21.756 | 29.330 | -7.064 | 6,872.44 |

Macro-mean final-cycle MAE is 41.573 for MeanBaseline, 17.273 for HistGradientBoosting, 17.123 for condition-aware HGB, and 17.513 for RandomForest. The condition-aware candidate lowers final-cycle MAE on FD002 by 0.515 cycles and FD004 by 0.464, while increasing it on FD001 by 0.146 and FD003 by 0.233 versus default HGB. That is a small targeted tradeoff, not evidence to replace the default globally. RandomForest's slightly lower validation MAE did not translate to the best macro test MAE; the default remains HGB. FD002 and FD004 still have negative bias and materially higher error. These results establish benchmark signal, not best-in-class accuracy or field readiness.

## Reproduction

Extract the public archive outside the repository, install the documented Python dependencies, and run once per subset:

```powershell
python -m backend.app.cli benchmark --subset FD001 --train .\train_FD001.txt --test .\test_FD001.txt --rul .\RUL_FD001.txt
```

Change `FD001` and all three filenames together to `FD002`, `FD003`, or `FD004`. The command validates filenames, schema, and label counts; it writes neither registry nor MLflow records. Dataset files are not committed; verify the archive SHA-256 above before use.

## Scope and limitations

- C-MAPSS is simulated turbofan data, not live equipment data. No live sensors, aircraft, or maintenance workflow were involved.
- Five split seeds describe validation variability; they are not statistical confidence intervals and do not represent arbitrary in-service censoring.
- The estimators and settings were fixed for this comparison. The optional PyTorch LSTM remains unbenchmarked.
- No calibrated uncertainty interval is available. Results do not authorize operational or safety-critical maintenance decisions.
