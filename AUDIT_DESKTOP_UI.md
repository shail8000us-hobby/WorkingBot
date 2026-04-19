# AUDIT_DESKTOP_UI
Date: 2026-04-17
Scope: Desktop Web UI

## 1. Executive Summary
The desktop UI is feature-rich but overloaded. The current shell stacks multiple always-on status surfaces, navigation contains 22 destinations, and strategy pages use different control grammars and layouts. This creates operator friction, strategy confusion, and elevated misclick risk for destructive actions.

Across the 5 strategy UIs (MMM, MMMX, Patience, SSDH, SSR Algo), control placement, confirmation depth, and information hierarchy are inconsistent. The result is a non-uniform operator experience that does not yet meet a clean professional desk standard.

## 2. Files Audited
- `webui/frontend/src/App.js`
- `webui/frontend/src/components/layout/TopBar.js`
- `webui/frontend/src/components/layout/Sidebar.js`
- `webui/frontend/src/config/navigationSections.js`
- `webui/frontend/src/components/layout/SymbolContextBar.js`
- `webui/frontend/src/components/FloatingPriceWidget.js`
- `webui/frontend/src/components/IdleIndicator.js`
- `webui/frontend/src/components/OfflineIndicator.js`
- `webui/frontend/src/components/SafetyWarningBanner.js`
- `webui/frontend/src/components/positionAdjustment/AutoloopStatusBar.js`
- `webui/frontend/src/components/mmm/MMMDashboard.js`
- `webui/frontend/src/components/mmmx/MMMXDashboard.js`
- `webui/frontend/src/components/mmmx/MMMXTopCommandStrip.js`
- `webui/frontend/src/components/mmmx/MMMXCriticalModePanel.js`
- `webui/frontend/src/components/patience/PatienceDashboard.js`
- `webui/frontend/src/components/ssdh/SSDHDashboard.js`
- `webui/frontend/src/components/ssrAlgo/SSRAlgoDashboardRefactored.js`
- `webui/frontend/src/pages/DashboardPage.js`
- `webui/frontend/src/pages/MonitoringPage.js`
- `webui/frontend/src/components/MonitoringDashboard.js`
- `webui/frontend/src/components/MonitoringPanel.js`
- `webui/frontend/src/components/ProductionMonitoringDashboard.js`

## 3. Findings
| ID | Finding | Evidence | Severity |
|---|---|---|---|
| F1 | **Navigation clutter and weak global hierarchy**. Desktop nav exposes too many primary destinations at once. | `navigationSections.js` has 22 section IDs (`id:` entries at lines 45-200). `Sidebar.js` renders all groups in one horizontal strip (`lines 46-53, 66-117`). | P2 |
| F2 | **Strategy confusion from shell-level identity mismatch**. Global header branding is fixed to one strategy context. | `TopBar.js` shows fixed label `SSR BOT` (`line 127`) while app routes include many unrelated strategies (`App.js` routes `lines 413-427`). | P2 |
| F3 | **Irrelevant controls/status surfaces shown globally**. Route-agnostic overlays compete with strategy UI. | `App.js` always mounts `AutoloopStatusBar` (`359`), `SymbolContextBar` (`383-391`), connection pill (`530-533`), `IdleIndicator` (`537`), `OfflineIndicator` (`540`), `SafetyWarningBanner` (`543`), `FloatingPriceWidget` (`554-557`). | P2 |
| F4 | **Dangerous controls are too prominent in routine action zones**. Emergency actions are co-located with normal controls across strategies. | MMM dangerous mode toggle in overview header (`MMMDashboard.js 3239-3269`, confirm dialog `4267-4347`); MMMX persistent `Kill Session` + `Global Kill` in top strip (`MMMXTopCommandStrip.js 103-128`) and critical panel (`MMMXCriticalModePanel.js 68-72`); Patience global kill button (`PatienceDashboard.js 981`) + modal (`1099-1119`); SSDH top-bar kill (`SSDHDashboard.js 370-387`). | P1 |
| F5 | **Weak operator flow due inconsistent confirmation UX**. Native prompt/confirm/alert patterns vary by strategy and break desk workflow. | MMM uses `window.confirm` and `window.prompt` (`MMMDashboard.js 4608, 4643-4645`); Patience has multiple `confirm/prompt/alert` calls (`PatienceDashboard.js 751-797, 773-775`); SSR uses browser confirms (`SSRAlgoDashboardRefactored.js 370-372`). | P2 |
| F6 | **Excessive local complexity in strategy workspaces**. Primary strategy pages have too many parallel panels/tabs. | MMM has 18+ detail tabs (`MMMDashboard.js 3132-3150`) plus separate session list/filter area (`4967-5030`); MMMX defines 18 tabs (`MMMXDashboard.js 65-69`) with additional left incident rail and right risk rail (`307-425`, `586-621`). | P2 |
| F7 | **Shared UI inconsistency across the 5 strategy dashboards**. No common interaction frame for lifecycle actions. | MMM uses card-level icon actions and advanced dialogs (`MMMDashboard.js 689-799`), MMMX uses tiered confirmation dialog (`MMMXDashboard.js 648-686`), Patience uses inline button clusters (`PatienceDashboard.js 183-195`, `976-982`), SSDH uses simple top bar actions (`SSDHDashboard.js 364-371`), SSR uses compact header action row (`SSRAlgoDashboardRefactored.js 487-497`). | P2 |
| F8 | **Monitoring overload and duplication**. Monitoring domains are spread across multiple pages/components with overlap. | `DashboardPage.js` mounts 9 collapsible sections (`48-187`) including multiple monitoring variants; `MonitoringPage.js` repeats monitoring blocks (`31-68`); monitoring components are large and dense (`MonitoringDashboard.js` 1189 LOC, `MonitoringPanel.js` 408 LOC, `ProductionMonitoringDashboard.js` 485 LOC). | P1 |

## 4. Severity (P0/P1/P2/P3)
| Severity | Count | Findings |
|---|---:|---|
| P0 | 0 | None identified in this UI-only audit |
| P1 | 2 | F4, F8 |
| P2 | 6 | F1, F2, F3, F5, F6, F7 |
| P3 | 0 | None assigned |

## 5. Why It Matters
- **Operational risk:** Exposed destructive controls in high-traffic areas increase accidental execution probability.
- **Decision latency:** Too many simultaneous status sources force operators to scan multiple competing panels.
- **Mental model breakage:** Different strategy pages require relearning controls and flow.
- **Trust erosion:** Non-uniform confirmation semantics (`dialog` vs `prompt` vs `confirm`) weaken confidence during live operations.

## 6. Suggested Fix
1. **Create a single Desktop Strategy Shell** for all 5 strategies: standardized header, action cluster, risk lane, and content region.
2. **Route-gate global overlays**: show only context-relevant widgets per route (e.g., autoloop, symbol context, floating ticker).
3. **Unify action taxonomy**: map lifecycle actions to one shared grammar (`Start/Pause/Resume/Stop/Delete`) and one shared safety model.
4. **Tier dangerous actions**: keep typed confirmation for high-risk actions and move them into a dedicated danger zone, visually separated from routine controls.
5. **Consolidate monitoring IA**: make one canonical monitoring surface; convert Dashboard monitoring cards into summary links/cards to that surface.
6. **Progressive disclosure for depth**: reduce first-view density (fewer default-open cards/tabs), move advanced analytics under explicit secondary navigation.

## 7. Safe Implementation Notes for Claude
- Treat this as a **UI architecture refactor only**; do not alter trading/monitoring backend semantics.
- Preserve existing API endpoints and action handlers; wrap them behind shared UI components instead of rewriting service logic.
- Introduce changes behind a feature flag (e.g., `desktop_ui_v2`) and migrate one strategy page at a time.
- Keep kill/stop pathways explicit and auditable; never remove confirmations on destructive actions.
- Replace `window.prompt/confirm/alert` with consistent in-app dialogs to avoid browser-level UX drift.
- If touching MMM files, follow strict before/after behavior verification of modified controls and state transitions.

## 8. Final Score /10
**4.2 / 10**

Current desktop UI is operationally capable but not yet clean, coherent, or desk-professional at the shell and cross-strategy interaction level.
