# Implementation Plan: Fix Auto-Loop Trade Execution Bugs

**Branch**: `006-fix-autoloop-execution` | **Date**: February 1, 2026 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-fix-autoloop-execution/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Fix critical bugs in auto-loop execution where (1) per-strike quantity ratios are not respected, and (2) subsequent rounds start before previous round orders are confirmed filled. The fix ensures each round executes the correct quantity per strike and waits for all fills before proceeding.

**Primary Issue**: The current implementation in `executeAutoLoop` (OptionsPanel.js) and `executeOrders` (AdjustmentReviewDialog.js) calculates per-loop quantity using division but doesn't properly track original quantities per strike, leading to all strikes getting 1 lot instead of maintaining ratios like 1:2.

**Technical Approach**: 
1. Preserve original quantity per strike in order data structure
2. Calculate per-round quantity as `Math.round(originalQty / totalRounds)` for each strike individually
3. Add fill confirmation check before starting next round
4. Implement proper order status polling with timeout

## Technical Context

**Language/Version**: JavaScript (ES6+), React 17+  
**Primary Dependencies**: React, Material-UI, axios (via apiShim)  
**Storage**: React component state (useState), no persistence needed  
**Testing**: Manual testing via browser, integration tests with real API  
**Target Platform**: Web browser (Chrome, Firefox, Safari)  
**Project Type**: web (frontend React application with backend API)  
**Performance Goals**: <2s delay between rounds, <2s UI update latency  
**Constraints**: Must not break existing non-autoloop execution modes  
**Scale/Scope**: 2 frontend files affected (OptionsPanel.js, AdjustmentReviewDialog.js), ~150 lines modified


## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Constitution file not found** - proceeding without constitution constraints.

✅ **PASS** - No architectural violations detected:
- Bug fix in existing codebase (no new projects or patterns introduced)
- Changes localized to 2 frontend components
- Follows existing code structure and patterns
- No new dependencies required
- Maintains backward compatibility with non-autoloop modes

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```


### Source Code (repository root)

```text
webui/frontend/src/
├── components/
│   ├── options/
│   │   └── OptionsPanel.js           # PRIMARY FIX: executeAutoLoop function
│   └── positionAdjustment/
│       ├── AdjustmentReviewDialog.js  # PRIMARY FIX: executeOrders function
│       └── SensibullStyleAdjustmentPage.js  # Uses AdjustmentReviewDialog
├── utils/
│   └── apiShim.js                     # API wrapper (no changes needed)
└── tests/
    └── manual/
        └── autoloop-scenarios.md      # NEW: Manual test scenarios
```

**Structure Decision**: Web application structure with React frontend. Changes are isolated to two existing component files that handle auto-loop execution. No backend changes required as the API already supports the correct behavior.


## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations detected - this section is not applicable.

---

## Phase 0: Research Complete ✅

**Output**: [research.md](./research.md)

### Key Findings

1. **Root Cause Identified**: Quantity calculation uses division which loses ratio information
2. **Solution Approach**: Use GCD to maintain ratios across rounds
3. **Timing Issue**: Missing fill verification between rounds
4. **Polling Strategy**: Keep existing 2-second polls, add strict timeout handling

All NEEDS CLARIFICATION items resolved.

---

## Phase 1: Design Complete ✅

**Outputs**: 
- [data-model.md](./data-model.md) - Entity definitions and state management
- [contracts/function-contracts.md](./contracts/function-contracts.md) - Internal function APIs
- [quickstart.md](./quickstart.md) - Implementation guide

### Design Decisions

1. **Data Model**: Defined Trade, RoundOrder, ExecutionProgress, AutoLoopState entities
2. **Calculations**: Documented GCD-based ratio preservation algorithm
3. **Contracts**: Specified input/output contracts for executeOrders() and executeBatch()
4. **Testing**: Manual test scenarios with expected outcomes

Constitution re-check: ✅ PASS (no architectural changes, bug fix only)

---

## Phase 2: Task Planning (NOT DONE YET)

**Note**: Phase 2 (task breakdown) is handled by the `/speckit.tasks` command, not `/speckit.plan`.

The implementation tasks will include:
- Modify AdjustmentReviewDialog.js
- Modify OptionsPanel.js  
- Add error handling and validation
- Test with multiple scenarios
- Verify console logs
- Update UI progress indicators

Run `/speckit.tasks` to generate detailed task breakdown.

---

## Implementation Summary

This plan provides everything needed to proceed with implementation:

1. ✅ **Problem identified**: Quantity ratios not preserved, round timing incorrect
2. ✅ **Solution designed**: GCD-based ratio calculation + fill verification
3. ✅ **Files identified**: 2 frontend components need modification
4. ✅ **Test cases defined**: 5 manual test scenarios documented
5. ✅ **Quick start ready**: Step-by-step implementation guide available

**Next Step**: Run `/speckit.tasks` to generate implementation task list, then proceed with coding.

**Branch**: `006-fix-autoloop-execution`  
**Estimated Effort**: 2-4 hours (coding + testing)  
**Risk Level**: Low (isolated bug fix, no API changes)
