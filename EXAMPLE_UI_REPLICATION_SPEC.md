# 📋 Example: Using Spec Kit to Replicate UI Layout

**Goal**: Create a specification for your coding AI to build the exact UI shown in your screenshot

**Screenshot**: Options trading interface with positions, payoff graph, and metrics

---

## 🎯 Step-by-Step: How to Use Spec Kit for This

### **Step 1: Open VS Code & Copilot Chat**

```bash
cd /Users/ssr/Projects/WorkingBot
code .
```

Press `Cmd+I` to open GitHub Copilot Chat

---

### **Step 2: Create the Specification**

**Copy this ENTIRE command and paste into Copilot Chat:**

```
/speckit.specify Create options trading WebUI layout matching production interface:

LAYOUT STRUCTURE:
The interface should be a 3-column responsive layout:

LEFT PANEL - Positions Management (30% width):
1. Header section:
   - Symbol display: "BANKNIFTY 58417.20" with -2.00% change indicator
   - Chart icon and Info button
   - Settings gear icon
   
2. Positions summary bar:
   - "BANKNIFTY Positions" title
   - "Clear Positions" button (right-aligned)
   - Quick actions: "Exit Positions (1)" button, "Add New Trade" button
   - Date filters: "Show All" / "24 Feb" toggle

3. P&L Summary row:
   - Booked: +31,353 (green text)
   - Unbooked: +180 (green text)
   - Total P&L: +31,533 (green text)

4. Active Positions table with columns:
   - Checkbox for selection
   - Instrument (e.g., "NRML 24th Feb 64000 CE")
   - Qty (e.g., 90)
   - Avg (e.g., 28.30)
   - LTP (e.g., 26.30)
   - Row shows: "Booked 0 | Unbooked +180 | P&L +180"

5. Closed Positions section (collapsible):
   - Header: "Closed Positions (10)" with Booked P&L: +31,353
   - List of closed trades showing:
     - Checkbox
     - Instrument (NRML date strike type)
     - P&L in red (losses) or green (profits)
     - Examples: -2,171, -2,065, +15,949, -14,539, etc.

CENTER PANEL - Metrics & Payoff Graph (45% width):
1. Top metrics card with light background:
   - Profit left: +2,367 (+0.59%) in green
   - Loss left: Unlimited in orange/red
   - Max Profit: +33,900 (+8%) in small text
   - Max Loss: Unlimited with info icon
   - Breakeven: 64377 (+10.2%) with Target and Expiry chips

2. Tab navigation:
   - "Payoff Graph" (active, blue highlight)
   - "P&L Table"
   - "Greeks"
   - "Strategy Chart"

3. Payoff Graph visualization:
   - Sub-tabs: "Payoff Graph" | "Payoff Table"
   - Dropdown: "SD Dynamic" with down arrow
   - Dropdown: "Open Interest" with down arrow
   - Toggle: "Add Booked P&L" switch (blue)
   
4. Graph components:
   - X-axis: Price range (56,000 to 64,000)
   - Y-axis: Profit/Loss in thousands (-80,000 to 60,000)
   - Green horizontal line: "On Expiry" profit line
   - Blue diagonal line: "On Target Date" profit line
   - Shaded green area above zero
   - Vertical bars showing position Greeks/delta
   - Black vertical line: "Current price: 58417.20"
   - OI data label: "OI data at 58400 | Call OI 30,360 | Put OI 54,540"
   - Pink spike at current price showing max profit zone
   - Profit projection: "Projected profit: 31,533 (+8%)" in green chip at bottom
   - "Zoom Out" button top right

5. Target adjustment controls:
   - "BANKNIFTY Target" label with 0.0% value
   - Minus/Plus buttons for adjustment
   - Reset button
   - Current target: 58417.2
   - Date slider: "Date: 230 to expiry" with time "Sun, 1 Feb 8:30 PM"
   - Reset button for date

RIGHT PANEL - Settings & Risk Management (25% width):
1. Reward/Risk display:
   - "Reward / Risk" ratio: "1/x"
   - POP (Probability of Profit): 98%
   - Time Value: -2,367
   - Intrinsic Value: 0

2. Funds & Margins card:
   - "Standalone Funds" with value (dash if not set)
   - "Margin Used": 3.99L
   - "Margin Available": 49,65,905
   - Settings gear icon

VISUAL DESIGN REQUIREMENTS:
- Dark theme: Black (#000000) or very dark gray background
- Card-based layout with subtle borders/shadows
- Color scheme:
  - Profits: Bright green (#00FF00 or similar)
  - Losses: Bright red (#FF0000 or similar)
  - Neutral: White/light gray text
  - Accent: Blue for active elements (#0066FF)
  - Background cards: Dark gray (#1a1a1a or #2a2a2a)
- Typography:
  - Headers: Bold, slightly larger
  - Numbers: Monospace font for alignment
  - Percentages in parentheses after values
- Spacing: Consistent 12-16px padding in cards
- Borders: Subtle 1px borders in dark gray
- Buttons:
  - Primary actions: Blue background
  - Danger actions: Red/orange outline
  - Secondary: Gray outline
- Interactive elements:
  - Hover states on all clickable items
  - Checkbox selection for positions
  - Smooth transitions (200ms ease)

RESPONSIVE BEHAVIOR:
- On desktop (>1200px): 3-column layout as described
- On tablet (768-1200px): Stack right panel below center panel
- On mobile (<768px): Single column, collapsible sections

FUNCTIONAL REQUIREMENTS:
1. Real-time P&L updates (WebSocket connection to backend)
2. Graph should redraw when positions change
3. Target slider should update graph in real-time
4. Position selection should update "Exit Positions" count
5. Date slider should show different payoff curves
6. All numeric values should format with commas (e.g., 31,533)
7. Percentages should show 2 decimal places
8. Graph should support zoom/pan interactions

USER STORIES:
Priority P1 - Core Visualization:
- User can see all open positions in left panel
- User can view payoff graph showing profit/loss at different price points
- User can see current P&L (booked + unbooked)
- User can view risk metrics (max profit, max loss, breakeven)

Priority P1 - Interactive Graph:
- User can adjust target price to see P&L at different levels
- User can move date slider to see time decay effect
- User can zoom in/out on payoff graph
- User can toggle "Add Booked P&L" to include/exclude closed positions

Priority P2 - Position Management:
- User can select multiple positions via checkboxes
- User can exit selected positions via "Exit Positions" button
- User can expand/collapse closed positions section
- User can filter positions by date

Priority P3 - Advanced Features:
- User can switch between Payoff Graph, P&L Table, Greeks, Strategy Chart tabs
- User can view Open Interest data overlaid on graph
- User can see probability of profit (POP) calculation
- User can adjust target using +/- buttons or manual input

ACCEPTANCE CRITERIA:
1. Given user has open positions
   When page loads
   Then all positions display in left panel with correct Qty, Avg, LTP
   And Total P&L matches sum of all position P&Ls

2. Given user views payoff graph
   When current price is at 58417.20
   Then vertical line appears at this price on graph
   And projected profit displays correctly

3. Given user moves target slider
   When target changes from 58417.2 to 60000
   Then blue "On Target Date" line adjusts on graph
   And projected profit recalculates

4. Given user has mixed profit/loss positions
   When viewing closed positions
   Then profits display in green
   And losses display in red
   And total booked P&L is accurate

5. Given user selects positions via checkboxes
   When 3 positions selected
   Then "Exit Positions (3)" button shows count
   And clicking exits selected positions only

EDGE CASES:
- What happens when no positions exist? (Show empty state)
- What if P&L is exactly 0? (Show neutral color)
- How to handle very large position counts? (Pagination or virtual scrolling)
- What if graph data fails to load? (Show error state with retry)
- How to display when max loss is "Unlimited"? (Special label, no numeric value)
- What if margin available is negative? (Warning color/icon)

TECHNICAL NOTES:
- Use existing webui/frontend-v3/ React components
- Backend API endpoints in webui/backend/routes/
- Real-time updates via Delta Exchange WebSocket
- Graph rendering: Consider Chart.js, Recharts, or D3.js
- State management: Existing Redux/Context pattern
- Position data from: bot/strategy/position_tracker.py
- P&L calculations: bot/orders/pnl_calculator.py (if exists)
```

---

### **Step 3: Create Technical Plan**

After Copilot generates the spec, paste this:

```
/speckit.plan

Technical implementation details:

TECHNOLOGY STACK:
- Frontend: React 18+ (webui/frontend-v3/)
- UI Framework: Already using Material-UI or TailwindCSS (check existing)
- Charting: Recharts or Chart.js (recommend Recharts for React)
- State: Redux or Context API (use existing pattern)
- Backend: Flask (webui/backend/)
- Real-time: WebSocket connection to Delta Exchange
- Styling: CSS Modules or styled-components

FILE STRUCTURE:
```
webui/frontend-v3/
├── src/
│   ├── components/
│   │   ├── PositionsPanel/
│   │   │   ├── PositionsPanel.tsx
│   │   │   ├── PositionRow.tsx
│   │   │   ├── ClosedPositions.tsx
│   │   │   └── PositionsPanel.module.css
│   │   ├── PayoffGraph/
│   │   │   ├── PayoffGraph.tsx
│   │   │   ├── PayoffChart.tsx
│   │   │   ├── TargetSlider.tsx
│   │   │   ├── DateSlider.tsx
│   │   │   └── PayoffGraph.module.css
│   │   ├── MetricsPanel/
│   │   │   ├── MetricsCard.tsx
│   │   │   ├── RiskMetrics.tsx
│   │   │   └── MetricsPanel.module.css
│   │   └── TradingDashboard/
│   │       ├── TradingDashboard.tsx  ← Main layout container
│   │       └── TradingDashboard.module.css
│   ├── hooks/
│   │   ├── usePositions.ts          ← Fetch positions data
│   │   ├── usePayoffCalculation.ts  ← Calculate payoff curve
│   │   ├── useWebSocket.ts          ← Real-time updates
│   │   └── usePnL.ts                ← P&L calculations
│   ├── utils/
│   │   ├── payoffCalculator.ts      ← Payoff math
│   │   ├── formatters.ts            ← Number/currency formatting
│   │   └── chartHelpers.ts          ← Chart data transformation
│   └── types/
│       └── positions.ts             ← TypeScript interfaces
```

webui/backend/routes/
├── positions_api.py        ← GET /api/positions
├── payoff_api.py          ← POST /api/calculate-payoff
└── metrics_api.py         ← GET /api/risk-metrics
```

BACKEND API ENDPOINTS:
1. GET /api/positions - Fetch all positions (open + closed)
2. POST /api/calculate-payoff - Calculate payoff curve for given target/date
3. GET /api/risk-metrics - Get max profit, max loss, breakeven, POP
4. POST /api/exit-positions - Exit selected positions
5. WebSocket /ws/positions - Real-time position updates

IMPLEMENTATION PHASES:
Phase 1: Layout & Static UI (2 days)
- Create 3-column responsive grid layout
- Build PositionsPanel component with dummy data
- Build MetricsPanel with static values
- Build PayoffGraph container (no chart yet)

Phase 2: Data Integration (2 days)
- Connect to backend API endpoints
- Implement usePositions hook
- Wire up real position data to PositionsPanel
- Wire up real metrics to MetricsPanel

Phase 3: Payoff Graph Implementation (3 days)
- Implement payoff calculation logic
- Build Recharts-based PayoffChart component
- Add current price vertical line
- Add profit/loss areas
- Add OI data overlay

Phase 4: Interactive Features (2 days)
- Implement target price slider
- Implement date slider
- Add zoom/pan to graph
- Wire up "Add Booked P&L" toggle

Phase 5: Position Actions (1 day)
- Implement checkbox selection
- Wire up "Exit Positions" button
- Add confirmation dialog

Phase 6: Polish & Responsive (1 day)
- Test responsive breakpoints
- Add loading states
- Add error states
- Smooth animations
```

---

### **Step 4: Generate Tasks**

Then paste:

```
/speckit.tasks
```

This will break it into specific tasks like:
- [ ] T001: Create TradingDashboard layout component with CSS Grid
- [ ] T002: Build PositionsPanel component structure
- [ ] T003: Implement position row with P&L coloring
- [ ] T004: Create PayoffGraph container
- [ ] T005: Integrate Recharts library
- etc.

---

### **Step 5: Implement**

Finally:

```
/speckit.implement
```

Copilot will now build the entire UI matching your screenshot!

---

## 🎨 What You'll Get

After running these commands, your coding AI will:

1. ✅ Create the exact 3-column layout
2. ✅ Build all UI components (Positions Panel, Payoff Graph, Metrics)
3. ✅ Implement the dark theme with your color scheme
4. ✅ Add the interactive payoff graph
5. ✅ Wire up real-time data
6. ✅ Make it responsive
7. ✅ Add all the features you see in the screenshot

---

## 💡 Pro Tips

1. **Attach your screenshot**: In Copilot Chat, you can attach the image when you run `/speckit.specify` for even better context

2. **Iterate if needed**: If the first result isn't perfect, you can refine:
   ```
   /speckit.specify Update the payoff graph to match exactly: [describe differences]
   ```

3. **Reference existing code**: Your WebUI already exists in `webui/frontend-v3/`, so mention:
   ```
   Use existing React components from webui/frontend-v3/src/components/
   Match the existing dark theme and styling patterns
   ```

---

## ⚡ Quick Version (Copy & Paste)

If you want to start RIGHT NOW, just:

1. Open VS Code: `code /Users/ssr/Projects/WorkingBot`
2. Press `Cmd+I`
3. Copy the entire "Step 2" command above
4. Paste and press Enter
5. Follow with Steps 3, 4, 5

Your coding AI will build the UI!

---

## 🎯 Why This Works

Spec Kit gives your AI:
- **Exact layout specifications** (3-column grid, percentages)
- **Visual design details** (colors, spacing, typography)
- **Functional requirements** (real-time updates, interactions)
- **Component structure** (which files to create)
- **Acceptance criteria** (how to test it works)

**Result**: AI knows EXACTLY what to build - no guessing!

---

**Ready to try it?** Copy the command from Step 2 above and paste into Copilot Chat!
