# Feature Specification: Fix Auto-Loop Trade Execution Bugs

**Feature Branch**: `006-fix-autoloop-execution`  
**Created**: February 1, 2026  
**Status**: Draft  
**Input**: User description: "I used the auto loop function but when executed the trade it places 1 lot of each strike and it didn't respect the original intent in that new strategy i had to put 1 lot of a strike and 2 lots of other strike but it executed 1 lot of each strike. Other issue is auto loop round 2 started before confirming the trades of 1 autoloop"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Respect Per-Strike Quantity Ratios (Priority: P1)

As a trader using auto-loop execution, I want the system to execute trades with the exact quantity ratios I specified (e.g., 1 lot of strike A and 2 lots of strike B), so that my strategy maintains the correct position sizing across multiple rounds.

**Why this priority**: This is the core functional bug that breaks the intended trading strategy. Without correct quantity ratios, the trader's risk/reward profile is completely wrong, potentially leading to significant losses.

**Independent Test**: Configure a strategy with 1 lot of 50000 CE and 2 lots of 51000 CE, execute 3 rounds of auto-loop, and verify each round places exactly this 1:2 ratio.

**Acceptance Scenarios**:

1. **Given** a strategy configured with 1 lot of strike A and 2 lots of strike B, **When** I execute 3 rounds of auto-loop, **Then** each round should place 1 lot of strike A and 2 lots of strike B
2. **Given** a strategy with 3:1:2 quantity ratio across three strikes, **When** I execute auto-loop, **Then** each round maintains the exact 3:1:2 ratio
3. **Given** a single round execution with different quantities per strike, **When** I execute, **Then** the quantities match my configured values exactly

---

### User Story 2 - Wait for Round Completion Before Starting Next Round (Priority: P1)

As a trader using auto-loop execution, I need each round to complete and have all orders filled before the next round starts, so that I don't accidentally double my position or create race conditions.

**Why this priority**: Starting round 2 before round 1 completes can lead to doubled positions, failed orders due to insufficient margin, and complete chaos in position tracking. This is a critical safety issue.

**Independent Test**: Execute 2 rounds of auto-loop with pending limit orders, monitor logs to confirm round 2 only starts after all round 1 orders are confirmed filled.

**Acceptance Scenarios**:

1. **Given** round 1 with pending limit orders, **When** orders are still pending, **Then** round 2 should not start
2. **Given** round 1 completes with all orders filled, **When** round completion is confirmed, **Then** round 2 should start after a brief delay
3. **Given** round 1 has a failed order, **When** failure is detected, **Then** auto-loop should stop and not proceed to round 2

---

### User Story 3 - Clear Progress Indicators (Priority: P2)

As a trader monitoring auto-loop execution, I want to see clear status for each order in each round (placing, pending, filled, failed), so that I can understand what's happening and intervene if needed.

**Why this priority**: Visibility into execution status helps traders make informed decisions about whether to stop the loop, modify parameters, or let it continue.

**Independent Test**: Execute auto-loop and verify the UI shows real-time status updates for each symbol in each round.

**Acceptance Scenarios**:

1. **Given** an executing auto-loop, **When** viewing the UI, **Then** I should see current round number and status for each symbol
2. **Given** an order is pending, **When** it transitions to filled, **Then** the UI should update within 2 seconds
3. **Given** an order fails, **When** failure occurs, **Then** the UI should show error message and stop further rounds

---

### Edge Cases

- What happens when one order in a round fills but another fails?
- How does the system handle partial fills (e.g., asked for 2 lots, only got 1)?
- What happens if network connection drops between rounds?
- How does the system handle different execution types (market vs limit) in the same batch?
- What if the user clicks "Stop" while orders are pending?
- What happens when margin is insufficient for the next round?


## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST preserve the exact quantity ratio between different strikes when executing auto-loop rounds (e.g., if user specifies 1 lot of strike A and 2 lots of strike B, each round must execute exactly 1 and 2, not 1 and 1)
- **FR-002**: System MUST wait for ALL orders in round N to be confirmed as filled before starting round N+1
- **FR-003**: System MUST track fill status for each individual order (placing, pending, filled, failed) and update UI in real-time
- **FR-004**: System MUST stop auto-loop execution if any order in a round fails, and display clear error message
- **FR-005**: System MUST prevent race conditions where round N+1 starts while round N orders are still pending
- **FR-006**: System MUST calculate per-round quantities correctly: `perRoundQty = originalQty / totalRounds` (not hardcoded to 1)
- **FR-007**: System MUST display current round number and total rounds during execution (e.g., "Round 2/5")
- **FR-008**: System MUST provide a "Stop" button that gracefully halts execution after the current round completes
- **FR-009**: System MUST log detailed execution flow for debugging (round start, orders placed, fills detected, round complete)
- **FR-010**: System MUST handle both immediate fills (market orders) and pending fills (limit orders) correctly

### Non-Functional Requirements

- **NFR-001**: Order status updates should appear in UI within 2 seconds of backend confirmation
- **NFR-002**: Auto-loop execution should have a maximum of 2-second delay between rounds (for polling and coordination)
- **NFR-003**: Error messages should be specific enough to identify which symbol and round failed
- **NFR-004**: System should maintain execution state in case of browser refresh (for recovery)

### Key Entities *(include if feature involves data)*

- **AutoLoopRound**: Represents a single execution round with orderIds, symbols, quantities, and fill status
- **OrderProgress**: Tracks status of individual order (placing → pending → filled/failed)
- **ExecutionConfig**: Stores original quantities per symbol, total rounds, execution mode
- **RoundResult**: Contains fill prices, timestamps, order IDs for completed round
- **[Entity 2]**: [What it represents, relationships to other entities]

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: [Measurable metric, e.g., "Users can complete account creation in under 2 minutes"]
- **SC-002**: [Measurable metric, e.g., "System handles 1000 concurrent users without degradation"]
- **SC-003**: [User satisfaction metric, e.g., "90% of users successfully complete primary task on first attempt"]
- **SC-004**: [Business metric, e.g., "Reduce support tickets related to [X] by 50%"]
