# FailureCast demo video

## Format

- 16:9 landscape, 1080p, about 76 seconds in the recorded run. Training duration can vary by host.
- Record the app at full browser width; keep the cursor deliberate and pause on the key evidence.
- The checked-in recording is captioned and silent. Use the narration below as an optional voiceover track.
- Keep the simulated-data disclosure on screen at the opening and close.
- Do not describe RUL estimates as certain failure dates or maintenance instructions.

Recorded file: [FailureCast demo video](demo-video/failurecast-demo.webm).

## Storyboard and narration

| Time | Screen action | Voiceover |
| --- | --- | --- |
| 0:00–0:05 | Hold on the welcome page and research-demo label. | “FailureCast is a remaining-useful-life research workflow. This demo uses generated simulated telemetry and does not connect to live equipment.” |
| 0:05–0:10 | Select **Get started** and let the fleet overview settle. | “The workspace brings fleet context, the active model, and review priorities together.” |
| 0:10–0:15 | Inspect the engine history and visible estimate. | “Review observed sensor history alongside an estimate. It is a model output, not a guaranteed service-life reading.” |
| 0:15–0:23 | Start or restart a historical replay, show a few observations, then pause. | “Replay sends simulated observations through the selected model and records the resulting estimate and alert state.” |
| 0:23–0:48 | Queue candidate training and wait for completion. | “Training uses an engine-level holdout on the selected dataset version. The candidate stays separate until a reviewer checks its validation evidence.” |
| 0:48–1:04 | Promote the candidate, run the simulated evaluation, and show the audit entry. | “Activation is explicit. This evaluation uses generated demo data; it is not an official NASA test result or live equipment evidence.” |
| 1:04–1:16 | Roll back and end on the overview. | “The previous approved model remains available for rollback. FailureCast makes the data, estimate, and model history easier to review.” |

## Recording checklist

- Use the app’s current demo values only if they still match the visible workspace when recording.
- Keep the browser session free of unrelated tabs, notifications, credentials, and personal information.
- Run `npm run demo:record` from `frontend` against an isolated, disposable demo workspace; the recording flow queues a training job and changes model lifecycle state.
- Confirm the intro and the **Get started** transition before recording.
- Re-read the dataset source label before stating where the data came from.
