# Page dependency trees

## / — Operations Overview
Entry: frontend/src/main.tsx

- frontend/src/main.tsx
  - frontend/src/App.tsx
    - react and react-dom — state, lifecycle, rendering
    - lucide-react — navigation and status icons
    - recharts — RUL and sensor charts
    - Local components in App.tsx: Badge, CardTitle, PageHeading, MetricCard, Overview, plus the other seven internal screens
    - frontend/src/styles.css — all layout and visual styles
  - frontend/src/styles.css
- frontend/index.html — document metadata, fonts, root element

## Internal screen components
All internal screens live in frontend/src/App.tsx and share the shell in App: Overview, EngineScreen, ReplayScreen, DatasetScreen, ExperimentsScreen, ExplainScreen, MonitoringScreen, and RegistryScreen. There are no additional local component files.
