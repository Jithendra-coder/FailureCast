# Extractable UI components

All UI is currently colocated in frontend/src/App.tsx; no existing shared layout modules are available.

## Layout components

### AppShell
- Source: frontend/src/App.tsx (App render branch)
- Category: layout
- Description: Shared sidebar, workspace switcher, status bar, page frame, mobile scrim, and toast container for all eight screens.
- Extractable props: activeScreen (string, default: overview), openAlertCount (number, default: 0), apiStatus (string, default: online).
- Hardcoded: FailureCast logo mark, section labels, navigation icon names, workspace identity, footer copy, all CSS classes.

### Sidebar
- Source: frontend/src/App.tsx (nav JSX)
- Category: layout
- Description: Brand, workspace selector, grouped eight-screen navigation, research-mode panel, and user identity.
- Extractable props: activeScreen (string, default: overview), openAlertCount (number, default: 0), isMobileOpen (boolean, default: false).
- Hardcoded: Brand name, workspace and user labels, navigation text and icons, CSS classes.

## Basic components

### Badge
- Source: frontend/src/App.tsx (Badge)
- Category: basic
- Description: Compact semantic status label with optional indicator dot.
- Extractable props: tone (string, default: neutral), showDot (boolean, default: false).
- Hardcoded: Type styles and CSS classes.

### MetricCard
- Source: frontend/src/App.tsx (MetricCard)
- Category: basic
- Description: KPI card with icon, value, unit, trend, and supporting detail.
- Extractable props: none; its content should remain representative in a static design.
- Hardcoded: Icon, labels, visual treatment, CSS classes.
