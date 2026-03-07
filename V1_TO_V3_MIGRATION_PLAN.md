# V1 to V3 Migration Plan - Complete Feature Replication

**Goal:** Replicate ALL functionality from v1 (localhost:5555) to v3 (localhost:3003)  
**Status:** Starting systematic migration  
**Date:** January 3, 2026

---

## 📊 Current Status Assessment

### V1 Sections (from App.js):
1. **dashboard** - Trading overview & telemetry
2. **portfolio** - Multi-symbol overview
3. **config** - Bot parameters and reconciliation tools  
4. **risk** - Risk analytics and protection systems
5. **rsi** - RSI safety monitor
6. **positions** - Active grids & execution state
7. **botmanagement** - tmux control, process management
8. **guardian** - WebUI robustness monitor (feature flag)
9. **actions** - Bot Actions (real-time decisions)
10. **brain_flow** - Visual decision flowchart
11. **intelligence** - AI insights, documentation
12. **logs_panel** - Live log streaming
13. **file_editor** - Edit code with AI assistance
14. **strategy_editor** - Visual strategy builder
15. **config_visual_editor** - Edit configuration with forms/YAML
16. **mode_switcher** - Auto LONG/SHORT switching
17. **system_health** - Real-time system monitoring
18. **instance_manager** - Run multiple bots
19. **todos** - Todo list panel

### V3 Current Pages (Next.js App Router):
- `/` - Dashboard (page.tsx)
- `/brain` - Bot Brain (page.tsx)
- `/grid` - Grid Trading (page.tsx)
- `/instances` - Instances (page.tsx)
- `/orders` - Orders (page.tsx)
- `/positions` - Positions (page.tsx)
- `/guardian` - Guardian (page.tsx) ✅ JUST CREATED
- `/health` - Health (page.tsx) ✅ JUST CREATED
- `/dashboard/[panel]` - Dynamic panel routing
- `/test-api` - API Test (page.tsx)

---

## 🎯 Migration Strategy

### Phase 1: Critical Missing Pages/Sections
Create top-level pages for v1 sections that don't have equivalents:

1. **Portfolio Page** (`/portfolio`) - Multi-symbol overview
2. **Config Page** (`/config`) - Configuration editing
3. **Risk Page** (`/risk`) - Risk & Safety dashboard
4. **RSI Page** (`/rsi`) - RSI monitoring
5. **Bot Management Page** (`/bot-management`) - Process management
6. **Actions Page** (`/actions`) - Bot Actions panel
7. **Brain Flow Page** (`/brain-flow`) - Decision flowchart
8. **Intelligence Page** (`/intelligence`) - AI insights
9. **Logs Page** (`/logs`) - Log streaming
10. **File Editor Page** (`/file-editor`) - Code editor
11. **Strategy Editor Page** (`/strategy-editor`) - Strategy builder
12. **Config Visual Editor Page** (`/config-visual-editor`) - Visual config editor
13. **Mode Switcher Page** (`/mode-switcher`) - Auto mode switching
14. **System Health Page** (`/system-health`) - System monitoring (exists as `/health`)
15. **Instance Manager Page** (`/instance-manager`) - Multi-instance management
16. **Todos Page** (`/todos`) - Todo list

### Phase 2: Component Migration
For each missing component from WEBUI_V1_COMPLETE_INVENTORY.md, create TypeScript version in v3.

### Phase 3: Route Mapping & Integration
Ensure all v1 routes work in v3 with proper navigation.

---

## 🚀 Implementation Priority

Based on usage and criticality:

**TIER 1: Core Operations (Already Complete)**
- ✅ Bot Control
- ✅ Emergency Controls  
- ✅ Symbol Switching
- ✅ Grid Mode Toggle
- ✅ Order Management

**TIER 2: Essential Pages (HIGH PRIORITY)**
1. Portfolio Page - Multi-symbol overview
2. Config Page - Configuration editing
3. Risk Page - Risk & Safety dashboard
4. Bot Actions Page - Next predicted actions
5. System Health - Already exists

**TIER 3: Monitoring & Analysis**
6. RSI Page - RSI monitoring
7. Brain Flow Page - Decision flowchart
8. Intelligence Page - AI insights
9. Logs Page - Log streaming

**TIER 4: Advanced Features**
10. File Editor Page
11. Strategy Editor Page
12. Config Visual Editor Page
13. Mode Switcher Page
14. Instance Manager Page
15. Todos Page

---

## 📋 Next Steps

1. **Create missing top-level pages** - Start with TIER 2
2. **Migrate components** - Convert v1 components to TypeScript
3. **Update navigation** - Ensure sidebar links to all pages
4. **Test functionality** - Verify each feature works
5. **API integration** - Ensure all endpoints work

---

**Estimated Total Time:** 40-60 hours for full migration
**Current Progress:** ~20% (based on roadmap document)

