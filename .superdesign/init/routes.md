# Routes

This is a single-page React + TypeScript application built with Vite. There is no router configuration; App switches among eight internal screens using the Screen state and conditional rendering.

| URL | Screen | Component |
|---|---|---|
| / | Operations Overview | Overview |
| / (internal state) | Engine Health | EngineScreen |
| / (internal state) | Live Replay | ReplayScreen |
| / (internal state) | Dataset Explorer | DatasetScreen |
| / (internal state) | Experiments | ExperimentsScreen |
| / (internal state) | Explainability | ExplainScreen |
| / (internal state) | Model Monitoring | MonitoringScreen |
| / (internal state) | Model Registry | RegistryScreen |

Entry point: frontend/src/main.tsx; shell and screens: frontend/src/App.tsx; styles: frontend/src/styles.css.
frontend/vite.config.ts proxies /api to FastAPI at 127.0.0.1:8000; it contains no routes.
