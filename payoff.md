# Payoff Graph Inline Adjustment - Implementation Audit (May 2026)

This document outlines the architectural changes, state management strategies, and file modifications applied to implement the "Inline Adjustment Mode" within the Options Payoff Graph. This log is specifically structured for secondary AI code auditing and verification.

## 1. Architectural Strategy: The Orchestrator Pattern

Instead of bloating the core `OptionsPanel.js` or `OptionsPayoffDiagram.js` with complex layout state and API hooks for proposed trades, we introduced an Orchestrator component: `InlineAdjustmentWrapper.js`.

### The `InlineAdjustmentWrapper` Component
- **Location**: `webui/frontend/src/components/positionAdjustment/InlineAdjustmentWrapper.js`
- **Role**: Acts as a state container and layout manager. When active, it splits the UI into a 60/40 Flexbox grid. The left side (60%) holds the `OptionsPayoffDiagram`, and the right side (40%) mounts the `SlidingOptionsChainPanel` in `inline={true}` mode.
- **State Management**:
  - Manages `proposedTrades` (array of selected option legs to add/remove).
  - Uses the `usePayoffCalculation` hook to dynamically compute the combined payoff matrix (`currentPositions` + `proposedTrades`).
- **Render Props**: It passes the computed `adjustmentOverlay` object down to its children using a render-prop pattern:
  ```javascript
  {(adjustmentOverlay) => (
    <OptionsPayoffDiagram adjustmentOverlay={adjustmentOverlay} ... />
  )}
  ```

## 2. Payoff Chart Data Interpolation

### Context
Recharts `ComposedChart` requires a unified data array where all lines share the same X-axis `price` points. The `usePayoffCalculation` hook returns its own dynamically generated price range (`adjustmentOverlay.chartData`) which may not perfectly align with the `chartData.data` generated natively by `OptionsPayoffDiagram`.

### The Implementation
- **Location**: `webui/frontend/src/components/options/OptionsPayoffDiagram.js`
- **The Fix**: Added the `adjustmentEnrichedData` `useMemo` block. This maps over the existing X-axis domain (`enrichedData`) and finds the closest matching price point from `adjustmentOverlay.chartData` using a nearest-neighbor approach.
- **Resulting Data Keys**: Injects `adjustmentCurrent` and `adjustmentCombined` into the data points so Recharts can natively plot the overlay lines without scale mismatch errors.

### Visual Rendering
- When `adjustmentOverlay` is present:
  - The standard "On Target Date" `<Line>` stroke is muted from `#3b82f6` (blue) to `#475569` (grey) and set to a `4 4` dash array.
  - A new `<Line>` mapping to `adjustmentCombined` is rendered as a solid cyan line (`#00e5ff`, strokeWidth: 3).

## 3. UI and State Integration

### `OptionsPanel.js` Modification
- Added `const [inlineAdjustmentMode, setInlineAdjustmentMode] = useState(false);`.
- Wrapped the existing `OptionsPayoffDiagram` component call with `<InlineAdjustmentWrapper>`.
- Preserved all existing props (e.g., `selectedPositionsForPayoff`, `manualPnL`, `futuresPositions`) inside the wrapped child to ensure no regression in existing features.

### `OptionsPayoffDiagram.js` Controls
- Added the `adjustmentOverlay` and `onAdjustmentClick` props to the component signature.
- Added a dynamic `ADJUSTMENT` toggle button to the chart header (`Box` containing "Payoff Graph").
- Button UI relies on the presence of the `adjustmentOverlay` prop to determine if it should render in an "Exit Adjustment" (active/cyan) or "Adjustment" (inactive/outlined) state.

## 4. Sub-components Built

1. **`MetricsDiffStrip`**: Rendered inside the wrapper beneath the chart. It compares the `currentMetrics` and `combinedMetrics` from the payoff engine, highlighting the mathematical delta (Δ Max Profit, Δ Delta, Δ PoP) in green/red tones.
2. **`ProposedTradesStrip`**: A compact table rendered at the bottom of the left pane, allowing users to modify quantities or remove proposed legs dynamically before execution.

## Verification Checklist for Auditor AI

Please review the following files to verify mathematical and architectural soundness:
1. `webui/frontend/src/components/options/OptionsPanel.js`: Check lines `~4760-4840` to ensure `InlineAdjustmentWrapper` correctly wraps `OptionsPayoffDiagram` without losing vital props like `batchOrderSection` and `futuresPositions`.
2. `webui/frontend/src/components/options/OptionsPayoffDiagram.js`: Check the `adjustmentEnrichedData` interpolation logic (lines `~175-195`) to ensure the nearest-neighbor logic correctly maps the secondary chart data onto the primary X-axis. Check the `<Line>` declarations (lines `~1640-1660`) for conditional rendering.
3. `webui/frontend/src/components/positionAdjustment/InlineAdjustmentWrapper.js`: Verify that the layout CSS handles the 60/40 split cleanly and that `usePayoffCalculation` handles empty `proposedTrades` gracefully.
