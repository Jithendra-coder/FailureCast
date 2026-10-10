# FailureCast engineering readiness report

**Assessment date:** 2026-10-10
**Branch:** `main`
**Scope:** repository and API workflow, four-subset NASA C-MAPSS benchmark, local Compose deployment configuration, frontend production build, defensive checks, tests, and documentation. No production deployment or real-equipment data was used.

## 1. Project overview

- **Purpose:** forecast remaining useful life (RUL) from engine sensor trajectories and demonstrate a controlled, reproducible model lifecycle.
- **Problem and users:** researchers, engineers, and reviewers need to inspect simulated degradation data, compare model evidence, and trace an estimate through a candidate, approval, monitoring, and replay workflow.
- **Essential outcome:** a non-negative RUL estimate in cycles with dataset/model provenance and reviewable evaluation evidence.
- **Technologies:** React, TypeScript, Vite, Recharts, FastAPI, Pydantic, scikit-learn, optional PyTorch, SQLite/WAL, a separate Python worker, local MLflow, and self-hosted Docker Compose.
- **Status:** the simulated-data workflow is implemented and its backend journey is integration-tested. The default dashboard uses generated sample data. NASA C-MAPSS support is an explicit operator-import path; the system does not connect to equipment.

## 2. Initial readiness score

**Initial verified score: 74/100.** The read-only review began with 25 passing backend tests and a built frontend, but no run on official C-MAPSS files. Important differences between validation and the official final-cycle task were not represented in the validation metric. Restored source files were not rechecked against their stored checksums, and test RUL labels could be associated with sorted rather than file-order engine IDs. Artifact validity also needed to be checked before promotion and on a warm inference cache.

| Category | Initial | Evidence and deductions |
| --- | ---: | --- |
| Core purpose & functionality | 24/30 | Broad dashboard and API lifecycle existed; imported-data correctness and dataset/model boundaries still needed stronger checks. |
| AI/ML accuracy & evaluation | 14/25 | Engine-level split existed, but validation scored many windows rather than the final-cycle-like task; no official benchmark had been run. |
| Architecture & code quality | 12/15 | Clear API/worker/storage split; some cross-dataset snapshot and recovery boundaries needed tightening. |
| Security & reliability | 8/10 | Sessions, origin checks, bounded uploads, and recovery existed; restore integrity and artifact promotion checks were incomplete. |
| Testing & reproducibility | 8/10 | 25 backend tests; limited end-to-end failure coverage and no authentic C-MAPSS evaluation evidence. |
| Portfolio & demonstration | 8/10 | Useful architecture and demo materials existed, but evaluation claims and one hard-coded narrated value were stale. |
| **Total** | **74/100** | |

At the initial checkpoint, imported-dataset results, full Compose runtime behavior, and optional LSTM behavior were unverified.

## 3. Core goal verification

**Does it accomplish its purpose? Yes, for simulated C-MAPSS RUL research and demonstration.** It does not validate predictions for real equipment or authorize maintenance decisions.

Evidence now includes:

- A fixed MeanBaseline vs HistGradientBoosting comparison on NASA FD001–FD004, using final-cycle test rows and provided RUL labels. The default HGB has lower test MAE than the mean baseline on all four subsets; details are in the [benchmark report](evaluation/nasa-cmapss-benchmark-2026-10.md).
- API workflow coverage for dataset import, incompatible-model blocking, durable training queue, worker completion, explicit promotion, same-dataset test evaluation, replay, drift review, and rollback.
- The real C-MAPSS test-engine label-order regression case and persisted-import corruption checks.
- Production authentication/origin checks and a test proving a disallowed origin cannot revoke a valid session.

The Playwright browser suite covers the welcome and sign-in path, engine detail, historical replay, candidate training, explicit promotion, simulated test-set evaluation, and rollback. CI runs it against an isolated Compose API/worker stack, then creates a checksummed backup, restores it to a new path, cold-starts a second stack, and verifies the active model and simulated workspace. Dataset import remains covered by backend/API tests rather than a browser upload fixture.

## 4. Architecture assessment

The system is a single-host deployment: React assets are served by one FastAPI process; API state, registry, audit, and durable training jobs use SQLite/WAL; a separate lock-protected worker trains candidates; versioned model and experiment files share local storage; MLflow is optional and best-effort. Dataset/model IDs scope predictions, replay, alerts, and evaluation.

This is an appropriate, small architecture for a local research demonstration. SQLite and local files intentionally rule out horizontal replicas and network filesystems. No broker, hosted database, LLM, vector store, or external NASA API is needed for the defined workflow. Multi-host deployment would require shared transactional state, a distributed queue, shared artifact storage, and a stronger identity boundary.

Updated diagrams:

- [System architecture (SVG)](portfolio-diagrams/system-architecture.svg) · [PNG](portfolio-diagrams/system-architecture.png) · [Mermaid source](portfolio-diagrams/system-architecture.mmd)
- [Execution flow (SVG)](portfolio-diagrams/execution-flow.svg) · [PNG](portfolio-diagrams/execution-flow.png) · [Mermaid source](portfolio-diagrams/execution-flow.mmd)

The execution diagram now distinguishes 80%-life censored validation from the official final-cycle test and shows the full-training-data refit. Both SVGs were re-rendered to 2400 px PNGs and visually checked for clipping.

## 5. AI/ML accuracy report

The [benchmark report](evaluation/nasa-cmapss-benchmark-2026-10.md) records the official archive source and SHA-256, five fixed validation seeds, per-seed and summary metrics for four CPU estimators, test counts, final-cycle test metrics, and reproduction command. The optional condition-aware features are fit on training rows only. Official test labels are reported only after the estimator set and protocol are fixed; no test result was used to tune models.

The default HGB test MAE is 14.181, 20.237, 12.958, and 21.715 cycles on FD001–FD004, respectively. The fixed mean-baseline MAE is 35.900, 45.636, 38.003, and 46.753. HGB macro-mean MAE is 17.273 vs 41.573 for the mean baseline. FD002 and FD004 remain harder and show underprediction bias; HGB bias is -8.149 and -6.913 cycles respectively.

The validation change addresses a metric/task mismatch: each held-out training engine contributes one point at 80% of its trajectory, and the final artifact then uses all official training engines. Five fixed seeds report split variability, but this does not model arbitrary operational censoring or establish a statistical confidence interval. Across FD001–FD004, condition-aware HGB improves macro final-cycle MAE modestly (17.123 vs 17.273 cycles) with subset-level tradeoffs; RandomForest is close on validation but worse on macro test MAE (17.513). HGB remains the default. The optional LSTM remains unbenchmarked.

## 6. Cleanup and simplification

| Component | Problem or status | Decision | Reason | Verification |
| --- | --- | --- | --- | --- |
| SQLite queue and one worker | More infrastructure is unnecessary for one host | Keep | Durable jobs and process separation meet the local research scope | Queue/worker integration tests; Compose check |
| C-MAPSS data | Restore checksums and engine-to-RUL association needed stronger integrity | Improve | Prevent silent data corruption and label swaps | Restore-corruption and file-order regression tests |
| Validation protocol | Previous window metric did not match final-cycle use | Replace protocol | Endpoint-like validation gives a more relevant measure without test leakage | Four-subset official final-cycle benchmark |
| HGB and mean baseline | Fixed comparison gives an interpretable baseline | Keep | HGB wins on MAE in every tested subset | Reproducible CLI benchmark |
| RandomForest and LSTM | RandomForest has benchmark evidence but no macro test advantage; optional LSTM remains unbenchmarked | Keep RandomForest benchmark-only; defer LSTM claims | Avoid presenting close or unverified candidates as better | Four-model fixed-protocol report; LSTM is explicitly optional and unbenchmarked |
| MLflow | Local tracking is useful but non-critical | Keep optional | Failure is explicitly a warning and does not fail completed training | Source review and worker tests |
| Generated demo data | Convenient for first-run UI but not real sensor evidence | Keep with explicit label | Enables a local demo without external data | API and UI source review; model card boundary |
| Diagrams and demo narration | Some protocol details and a displayed estimate could become stale | Update | Keep presentation claims tied to verified behavior | Re-rendered PNG dimensions and visual inspection; script no longer hard-codes an estimate |

## 7. End-to-end test results

| Check | Result |
| --- | --- |
| Backend unit/API/worker/CLI/backup suite | **35 passed**, 0 failed, 0 skipped; no deprecation warnings |
| Frontend TypeScript + production Vite build | Passed; 2,166 modules transformed |
| Python compilation | Passed |
| Python dependency consistency (`pip check`) | Passed; no broken requirements |
| Compose configuration parse | Passed |
| Frontend dependency audit | `npm audit --audit-level=moderate`: 0 vulnerabilities; included in CI |
| Python dependency audit | `pip-audit -r requirements-dev.txt -r requirements-deep-learning.txt --strict`: no known vulnerabilities |
| Four-subset C-MAPSS benchmark | Completed; results and archive checksum recorded in the benchmark report |
| Compose container startup and API smoke | Passed in isolated Podman Compose project; health/readiness, static page HTTP 200, production login, and overview verified |
| Browser journeys | Playwright: 2 passed; welcome/sign-in, engine inspection, replay start/restart, candidate training, promotion, simulated evaluation, and rollback |
| Demo video | Captioned silent 1080p recording generated from the actual app workflow (75.9 seconds, VP9 WebM); narration copy is maintained separately |
| Compose API/worker release journey | Passed: HGB job completed, candidate promoted, generated test engines evaluated (`simulation_only=true`), rollback completed |
| Backup and recovery | Passed: 11 files archived and checksummed, restored into a separate path, SQLite integrity checked, Compose cold-start retained the active model, 3 completed jobs, and simulated-data flag |

Reproduce the main checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Set-Location frontend
npm ci
npm run build
Set-Location ..
python -m backend.app.cli benchmark --subset FD001 --train .\train_FD001.txt --test .\test_FD001.txt --rul .\RUL_FD001.txt
```

Long-running soak, concurrent-host, and external penetration tests were not run. All 35 backend tests pass without deprecation warnings after migrating the test client to `httpx2`. The browser suite does not exercise dataset file upload; that route has backend/API coverage. Temporary credentials and the test backup archive were removed after verification; ignored isolated demo directories remain available for local reproduction.

## 8. Security and reliability

Improvements protect the trust boundaries between imported bytes, dataset versions, model artifacts, active model state, and sessions. Restores recompute file and combined fingerprints and fail closed on corruption. Promotion validates the candidate artifact before changing active state. Artifact path containment/existence is rechecked even with a warm cache. Mutating requests enforce the configured origin, and dataset/model snapshots are captured consistently for evaluation, replay, drift, and alerts. Missing compatible models and damaged stored data produce explicit unavailable responses rather than stale estimates.

Verified controls include signed expiring admin sessions, login throttling, origin enforcement, bounded request/file sizes, schema and numeric validation, explicit model approval, transactional promotion, worker recovery, preserved rollback state, a passing strict Python dependency audit, and a tested backup/restore cold start. No critical defect was confirmed in this scoped review. It was not an exhaustive penetration test; TLS termination is deployment-owner responsibility, and multi-host fault and sustained-load tests remain unverified.

## 9. Improvements implemented

| Problem and root cause | Change | Evidence / benefit | Remaining limitation |
| --- | --- | --- | --- |
| Final-cycle labels could pair with sorted rather than source-order engine IDs | Map RUL labels to engine IDs in source first-seen order | Regression test with non-sorted engine order | Assumes the C-MAPSS file's first-seen engine sequence is the label sequence, as the format specifies |
| Validation evaluated many windows rather than a final-cycle-like endpoint | One 80%-life censored observation per held-out engine; refit artifact on all training engines | Fixed split metrics plus official final-cycle test results on FD001–FD004 | Single split, fixed censor fraction; no uncertainty estimate |
| Restored dataset bytes were trusted after import | Recompute per-file SHA-256 and combined fingerprint; fail closed on mismatch | Corrupted persisted source rejected in API test | Hash integrity is not authentication against a malicious host administrator |
| Candidate could be promoted without a working artifact; cached artifacts could bypass path checks | Validate containment and file existence on load and before activation | Missing-artifact promotion regression test | Does not add signed artifact attestations |
| Concurrent dataset changes could mismatch labels/model or scope alerts across data versions | Capture dataset snapshots across evaluation/replay/drift and scope duplicate alert suppression | Full dataset/model API workflow tests | Deployment stays single-process/single-host by design |
| No reproducible fixed baseline CLI | Add a read-only benchmark command | Tested no model-registry writes; benchmark across four official subsets | Optional LSTM remains unbenchmarked |
| No estimate of split variability or condition-aware comparison | Add five fixed engine-level seeds and benchmark condition-aware HGB and RandomForest without changing the default | Per-seed metrics and final-cycle reporting for FD001–FD004 | Five seeds are not confidence intervals; condition-aware gain is small and mixed by subset |
| Portfolio script contained a hard-coded estimate | Narration now reads the visible current estimate | Stale numeric claim removed | Recording itself remains a human task |
| Reviewer journey and restore behavior were not exercised in a browser or cold-start drill | Add Playwright journeys and a checksummed backup/restore CI workflow | Two browser journeys pass; restored Compose cold start preserves model and demo state | Browser file import, soak, and multi-host recovery are not covered |
| Completed replay was presented as resumable | Show “Restart replay” and reset the completed sequence | Browser journey covers starting and restarting replay | Replays remain local to the single-host deployment |

## 10. Final scorecard

| Category | Maximum | Initial | Final verified |
| --- | ---: | ---: | ---: |
| Core purpose & functionality | 30 | 24 | 28 |
| AI/ML accuracy & evaluation | 25 | 14 | 21 |
| Architecture & code quality | 15 | 12 | 13 |
| Security & reliability | 10 | 8 | 9 |
| Testing & reproducibility | 10 | 8 | 10 |
| Portfolio & demonstration | 10 | 8 | 9 |
| **Total** | **100** | **74** | **90** |

The 10-point deduction reflects the remaining validation uncertainty and FD002/FD004 error, unbenchmarked optional LSTM, single-host state/storage, lack of sustained-load and exhaustive security testing, and the absence of real-equipment or operational validation. Scores assess a research portfolio and its local demo workflow, not readiness to make maintenance decisions.

## 11. Remaining work for a legitimate 95+

| Priority | Impact | Recommended fix | Verification | Completion criteria |
| --- | --- | --- | --- | --- |
| P1 | Confidence in model generalization | Add predeclared grouped bootstrap or nested validation analysis for uncertainty and censor-point sensitivity; keep final test untouched | Re-run fixed protocol with uncertainty summaries | Reproducible uncertainty analysis and no held-out-test tuning |
| P1 | Stronger FD002/FD004 results | Continue condition-aware feature research using training/validation only; current gain is small and mixed | Predeclare candidates, tune on validation, evaluate final test once | Stable validation benefit with no test-driven selection |
| P1 | External security and operations | Validate reverse-proxy TLS, rate limits, restore procedures, and sustained-load behavior in the target self-hosted environment | Threat-model review, penetration test, load/soak and recovery drills | Documented evidence against deployment-specific acceptance targets |
| P2 | Browser upload coverage | Add an isolated-file C-MAPSS import journey with invalid-file recovery | Run Playwright in CI with temporary fixtures | Valid import and malformed upload paths pass through the UI |
| P2 | Optional model credibility | Keep LSTM unbenchmarked and out of recommendation claims, or compare it under the same predeclared protocol | Record accuracy, runtime, memory, and hardware requirements | Evidence-backed comparative value, or continued explicit deferral |
| P2 | Portfolio delivery | Add a narrated voiceover to the captioned recording using the updated demo script | Review voiceover timing and every factual claim against the recording | Narration matches the verified simulated-data workflow and avoids unsupported claims |

## 12. Final readiness verdict

**PORTFOLIO READY — 90/100.** The project now has a repeated-seed four-subset benchmark, stronger dataset/model integrity boundaries, browser-covered demo and model lifecycle journeys, a captioned video recording, dependency scans, and a verified checksummed restore followed by a cold Compose start. It is not **HIGH-CONFIDENCE PORTFOLIO READY (95+)** because uncertainty analysis, sustained-load and external security evidence, browser upload coverage, and a narrated voiceover remain incomplete. It is not an operational maintenance system: data is simulated or imported C-MAPSS research data, and deployment is intentionally single-host.

**Final runtime verification:** Podman Compose built and started the current branch with isolated data. The bundled UI returned HTTP 200; readiness and production login passed; the separate worker completed HGB training; a candidate was promoted, evaluated on generated sample data, and rolled back. Both Playwright journeys passed. A checksummed archive was restored to a fresh path, and a separate Compose instance authenticated and returned the restored active model, completed jobs, and `simulation_only=true`. Test containers were stopped and temporary credentials/archive removed.
