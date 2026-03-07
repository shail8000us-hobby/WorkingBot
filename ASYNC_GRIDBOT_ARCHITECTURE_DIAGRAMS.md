# ASYNC GRIDBOT ARCHITECTURE DIAGRAMS

**Generated:** November 14, 2025  
**Source:** Code forensic analysis  

---

## 1. COMPLETE SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                         DELTA EXCHANGE ECOSYSTEM                             │
│                                                                              │
│  ┌──────────────────────┐              ┌──────────────────────┐            │
│  │  REST API            │              │  WebSocket API        │            │
│  │  api.india.delta.ex  │              │  socket.india.delta.ex│            │
│  │                      │              │                      │            │
│  │  • Get ticker        │              │  • Mark price        │            │
│  │  • Place order       │              │  • User trades       │            │
│  │  • Cancel order      │              │  • Order updates     │            │
│  │  • Get positions     │              │  • Fills             │            │
│  └──────────┬───────────┘              └───────────┬──────────┘            │
│             │                                      │                        │
└─────────────┼──────────────────────────────────────┼─────────────────────────┘
              │                                      │
              │                                      │
┌─────────────┼──────────────────────────────────────┼─────────────────────────┐
│             │         ASYNC GRIDBOT PROCESS        │                         │
│             │                                      │                         │
│             ▼                                      ▼                         │
│   ┌──────────────────┐              ┌──────────────────────┐               │
│   │ AsyncDeltaClient │              │ AsyncWebSocketManager │               │
│   │                  │              │                       │               │
│   │ • Async HTTP     │              │ • Connection mgmt    │               │
│   │ • Retry logic    │              │ • Auto-reconnect     │               │
│   │ • Rate limiting  │              │ • Heartbeat          │               │
│   └────────┬─────────┘              └──────────┬────────────┘               │
│            │                                   │                            │
│            │                                   │                            │
│            │         ┌──────────────────────┐  │                            │
│            │         │  ASYNC GRIDBOT       │  │                            │
│            │         │  (Main Controller)   │  │                            │
│            │         │                      │  │                            │
│            │         │  • Initialization    │◄─┤                            │
│            └────────►│  • Price monitoring  │                               │
│                      │  • Safety checks     │                               │
│                      │  • Lifecycle mgmt    │                               │
│                      └───────┬──────────────┘                               │
│                              │                                              │
│               ┌──────────────┼──────────────┐                               │
│               │              │              │                               │
│               ▼              ▼              ▼                               │
│   ┌────────────────┐  ┌───────────────┐  ┌──────────────┐                 │
│   │ PositionActor  │  │  OrderActor   │  │ SagaOrchest. │                 │
│   │                │  │               │  │              │                 │
│   │ • Mailbox      │  │ • Mailbox     │  │ • Saga queue │                 │
│   │ • State mgmt   │  │ • Order API   │  │ • Execution  │                 │
│   │ • Positions    │  │ • Validation  │  │ • Compensate │                 │
│   └────────┬───────┘  └───────┬───────┘  └──────┬───────┘                 │
│            │                  │                  │                         │
│            │                  │                  │                         │
│            │         ┌────────▼──────────────────▼────┐                    │
│            │         │      SAGA PATTERNS              │                    │
│            │         │                                 │                    │
│            │         │  • create_buy_fill_saga()      │                    │
│            │         │  • create_sell_fill_saga()     │                    │
│            │         │  • create_short_entry_saga()   │                    │
│            │         │  • create_short_tp_saga()      │                    │
│            │         └─────────────────────────────────┘                    │
│            │                                                                │
│            ▼                                                                │
│   ┌─────────────────────────────────────────────┐                          │
│   │            MODULES                          │                          │
│   │                                             │                          │
│   │  ┌──────────────┐  ┌──────────────┐       │                          │
│   │  │ EventStore   │  │ GridCalc     │       │                          │
│   │  │              │  │              │       │                          │
│   │  │ • SQLite DB  │  │ • Pure logic │       │                          │
│   │  │ • Audit log  │  │ • No state   │       │                          │
│   │  └──────────────┘  └──────────────┘       │                          │
│   │                                             │                          │
│   │  ┌──────────────┐  ┌──────────────┐       │                          │
│   │  │ Monitoring   │  │ Safety       │       │                          │
│   │  │              │  │              │       │                          │
│   │  │ • 5 layers   │  │ • Volatility │       │                          │
│   │  │ • WebUI data │  │ • Limits     │       │                          │
│   │  └──────────────┘  └──────────────┘       │                          │
│   └─────────────────────────────────────────────┘                          │
│                                                                             │
│   ┌─────────────────────────────────────────────────┐                      │
│   │          OUTPUT / PERSISTENCE                   │                      │
│   │                                                  │                      │
│   │  • bot_events_LONG.db   (EventStore)           │                      │
│   │  • positions.json        (WebUI)               │                      │
│   │  • state.json            (WebUI)               │                      │
│   │  • monitoring_snapshot.json                     │                      │
│   │  • guardian_health.json                         │                      │
│   │  • .heartbeat                                   │                      │
│   └─────────────────────────────────────────────────┘                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. ORDER LIFECYCLE SEQUENCE (LONG MODE BUY FILL)

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│WebSocket │  │AsyncGrid │  │Position  │  │  Order   │  │  Saga    │  │ Exchange │
│          │  │   Bot    │  │  Actor   │  │  Actor   │  │Orchestr. │  │          │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │              │              │              │              │
     │ order_update│              │              │              │              │
     │ state=filled│              │              │              │              │
     ├────────────►│              │              │              │              │
     │             │              │              │              │              │
     │             │_process_fill │              │              │              │
     │             │──────┐       │              │              │              │
     │             │      │       │              │              │              │
     │             │◄─────┘       │              │              │              │
     │             │              │              │              │              │
     │             │create_buy_fill_saga         │              │              │
     │             │──────┐       │              │              │              │
     │             │      │       │              │              │              │
     │             │◄─────┘       │              │              │              │
     │             │              │              │              │              │
     │             │              │              │   start_saga │              │
     │             │──────────────┼──────────────┼─────────────►│              │
     │             │              │              │              │              │
     │             │              │              │              │ SAGA STEP 1  │
     │             │              │              │              │ Add Position │
     │             │              │ ADD_POSITION │              │              │
     │             │              │◄─────────────┼──────────────┤              │
     │             │              │              │              │              │
     │             │              │ reply(ok)    │              │              │
     │             │              ├──────────────┼─────────────►│              │
     │             │              │              │              │              │
     │             │              │              │              │ SAGA STEP 1.5│
     │             │              │CLEAR_PENDING │              │ Clear Pending│
     │             │              │◄─────────────┼──────────────┤              │
     │             │              │              │              │              │
     │             │              │              │              │ SAGA STEP 2  │
     │             │              │              │              │ Place TP     │
     │             │              │              │   PLACE_TP   │              │
     │             │              │              │◄─────────────┤              │
     │             │              │              │              │              │
     │             │              │              │ create_order │              │
     │             │              │              ├─────────────────────────────►│
     │             │              │              │              │              │
     │             │              │              │ order_id     │              │
     │             │              │              │◄─────────────────────────────┤
     │             │              │              │              │              │
     │             │              │              │ reply(ok)    │              │
     │             │              │              ├─────────────►│              │
     │             │              │              │              │              │
     │             │              │              │              │ SAGA STEP 3  │
     │             │              │              │              │ Next Grid    │
     │             │              │  GET_STATE   │              │              │
     │             │              │◄─────────────┼──────────────┤              │
     │             │              │              │              │              │
     │             │              │  state       │              │              │
     │             │              ├──────────────┼─────────────►│              │
     │             │              │              │              │              │
     │             │              │              │   PLACE_BUY  │              │
     │             │              │              │◄─────────────┤              │
     │             │              │              │              │              │
     │             │              │              │ create_order │              │
     │             │              │              ├─────────────────────────────►│
     │             │              │              │              │              │
     │             │              │              │ order_id     │              │
     │             │              │              │◄─────────────────────────────┤
     │             │              │              │              │              │
     │             │              │              │ reply(ok)    │              │
     │             │              │              ├─────────────►│              │
     │             │              │              │              │              │
     │             │              │              │              │ SAGA COMPLETE│
     │             │              │              │              ├──────┐       │
     │             │              │              │              │      │       │
     │             │              │              │              │◄─────┘       │
     │             │◄─────────────┼──────────────┼──────────────┤              │
     │             │              │              │              │              │
     ▼             ▼              ▼              ▼              ▼              ▼
```

---

## 3. STATE MACHINE: LONG MODE

```
                    ┌─────────────────┐
                    │   BOT STARTUP   │
                    └────────┬────────┘
                             │
                             │ _place_initial_order()
                             │ Calculate: ref - step
                             │
                             ▼
                    ┌─────────────────┐
                    │  PENDING_BUY    │◄────────────────────┐
                    │  @ Level N      │                     │
                    └────────┬────────┘                     │
                             │                              │
                             │ Price drops to N             │
                             │ Fill occurs                  │
                             │                              │
                             ▼                              │
        ┌────────────────────────────────────────┐         │
        │      SAGA: BUY FILL PROCESSING         │         │
        │                                        │         │
        │  STEP 1: ADD_POSITION                 │         │
        │    • entry = N                        │         │
        │    • tp = N + step                    │         │
        │    • open_tranches.append()           │         │
        │                                        │         │
        │  STEP 1.5: CLEAR_PENDING_BUY          │         │
        │    • pending_buy = None               │         │
        │                                        │         │
        │  STEP 2: PLACE_TP                     │         │
        │    • SELL @ N + step                  │         │
        │                                        │         │
        │  STEP 3: PLACE_GRID                   │         │
        │    • BUY @ N - step                   │         │
        │    • pending_buy = N - step           │         │
        └────────────────┬───────────────────────┘         │
                         │                                 │
                         │ Saga complete                   │
                         │                                 │
                         └─────────────────────────────────┘
                         
                    
                    ┌─────────────────┐
                    │  POSITION OPEN  │
                    │  @ N with TP    │
                    │  @ N + step     │
                    └────────┬────────┘
                             │
                             │ Price rises to N + step
                             │ TP fills
                             │
                             ▼
        ┌────────────────────────────────────────┐
        │      SAGA: SELL FILL PROCESSING        │
        │           (TP Close)                   │
        │                                        │
        │  STEP 1: FIND & REMOVE POSITION       │
        │    • GET_POSITION_BY_TP(N + step)     │
        │    • REMOVE_POSITION                  │
        │    • open_tranches.remove()           │
        │                                        │
        │  STEP 2: CLEAR_PENDING_SELL           │
        │    • pending_sell = None              │
        │                                        │
        │  STEP 3: PLACE_BUY                    │
        │    • BUY @ N - step                   │
        │    • Check duplicate                  │
        │    • pending_buy = N - step           │
        └────────────────┬───────────────────────┘
                         │
                         │ Saga complete
                         │
                         └──────────────► (Loop continues)
```

---

## 4. TICKER-DRIVEN ORDER PLACEMENT FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                  TICKER UPDATE ARRIVES                           │
│                  (WebSocket message)                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
                ┌─────────────────────────┐
                │ _handle_ticker_update() │
                │                         │
                │ • Extract price         │
                │ • Update current_price  │
                │ • Update price_monitor  │
                └───────────┬─────────────┘
                            │
                            ▼
            ┌───────────────────────────────┐
            │ _check_and_place_entry_order() │
            └───────────┬───────────────────┘
                        │
                        ▼
        ┌───────────────────────────────────────┐
        │         GUARD CHECKS                  │
        │  (All must pass to continue)          │
        │                                       │
        │  1. _initial_order_placed == True ────► FAIL → SKIP
        │  2. current_price exists ──────────────► FAIL → SKIP
        │  3. Safety limits pass ────────────────► FAIL → SKIP
        │  4. Cooldown satisfied ────────────────► FAIL → SKIP
        │  5. Price health OK ───────────────────► FAIL → SKIP
        │  6. Within grid bounds ────────────────► FAIL → SKIP
        │  7. Volatility safe ───────────────────► FAIL → SKIP
        └───────────┬───────────────────────────┘
                    │ ALL PASS
                    ▼
        ┌───────────────────────────────────────┐
        │     Get State from PositionActor      │
        │  • open_tranches                      │
        │  • pending_buy / pending_sell         │
        └───────────┬───────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────┐
        │      MODE-SPECIFIC CHECKS             │
        │                                       │
        │  LONG MODE:                           │
        │    • pending_buy exists? → SKIP       │
        │    • At max capacity? → SKIP          │
        │                                       │
        │  SHORT MODE:                          │
        │    • pending_sell exists? → SKIP      │
        │    • At max capacity? → SKIP          │
        └───────────┬───────────────────────────┘
                    │ CHECKS PASS
                    ▼
        ┌───────────────────────────────────────┐
        │      Calculate Target Level           │
        │                                       │
        │  LONG: GridCalc.compute_next_buy_level│
        │  SHORT: GridCalc.compute_next_sell_lvl│
        └───────────┬───────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────┐
        │      Pre-Order Logging                │
        │  • PreOrderDecisionLogger             │
        │  • AnomalyDetectionSystem             │
        └───────────┬───────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────┐
        │      Send to OrderActor               │
        │  • PLACE_BUY / PLACE_SELL             │
        │  • Wait for reply (20s timeout)       │
        └───────────┬───────────────────────────┘
                    │
                    ▼
        ┌───────────────────────────────────────┐
        │      Update PositionActor State       │
        │  • SET_PENDING_BUY                    │
        │  • SET_PENDING_SELL                   │
        └───────────────────────────────────────┘
```

---

## 5. ACTOR MESSAGE FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                        ACTOR MODEL                               │
│                                                                  │
│  ┌────────────────────┐              ┌────────────────────┐    │
│  │  PositionActor     │              │  OrderActor        │    │
│  │                    │              │                    │    │
│  │  ┌──────────────┐  │              │  ┌──────────────┐  │    │
│  │  │   Mailbox    │  │              │  │   Mailbox    │  │    │
│  │  │   (Queue)    │  │              │  │   (Queue)    │  │    │
│  │  │              │  │              │  │              │  │    │
│  │  │  Max: 1000   │  │              │  │  Max: 1000   │  │    │
│  │  │  FIFO        │  │              │  │  FIFO        │  │    │
│  │  └──────┬───────┘  │              │  └──────┬───────┘  │    │
│  │         │          │              │         │          │    │
│  │         ▼          │              │         ▼          │    │
│  │  ┌──────────────┐  │              │  ┌──────────────┐  │    │
│  │  │  _process()  │  │              │  │  _process()  │  │    │
│  │  │              │  │              │  │              │  │    │
│  │  │  Handle:     │  │              │  │  Handle:     │  │    │
│  │  │  • ADD_POS   │  │              │  │  • PLACE_BUY │  │    │
│  │  │  • REMOVE    │  │              │  │  • PLACE_SELL│  │    │
│  │  │  • GET_STATE │  │              │  │  • PLACE_TP  │  │    │
│  │  │  • CLEAR_*   │  │              │  │  • CANCEL    │  │    │
│  │  └──────┬───────┘  │              │  └──────┬───────┘  │    │
│  │         │          │              │         │          │    │
│  │         ▼          │              │         ▼          │    │
│  │  ┌──────────────┐  │              │  ┌──────────────┐  │    │
│  │  │    State     │  │              │  │ AsyncDelta   │  │    │
│  │  │              │  │              │  │   Client     │  │    │
│  │  │ • open_      │  │              │  │              │  │    │
│  │  │   tranches   │  │              │  │ • place()    │  │    │
│  │  │ • pending_   │  │              │  │ • cancel()   │  │    │
│  │  │   buy/sell   │  │              │  │              │  │    │
│  │  └──────────────┘  │              │  └──────────────┘  │    │
│  └────────────────────┘              └────────────────────┘    │
│                                                                  │
│  Message Types:                                                 │
│                                                                  │
│  @dataclass                                                     │
│  class Message:                                                 │
│      type: str              # "ADD_POSITION", "PLACE_BUY", etc. │
│      payload: Dict          # Message data                      │
│      reply_to: Queue        # For ask() pattern                 │
│      correlation_id: str    # For tracing                       │
│                                                                  │
│  Communication Patterns:                                        │
│                                                                  │
│  1. TELL (fire-and-forget)                                      │
│     actor.mailbox.put(Message(..., reply_to=None))             │
│                                                                  │
│  2. ASK (request-reply)                                         │
│     reply_queue = Queue()                                       │
│     actor.mailbox.put(Message(..., reply_to=reply_queue))      │
│     result = await reply_queue.get()                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. SAGA COMPENSATION FLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAGA HAPPY PATH                               │
│                                                                  │
│  Step 1 ──► Step 2 ──► Step 3 ──► ✅ SUCCESS                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 SAGA FAILURE & COMPENSATION                      │
│                                                                  │
│  Step 1 ──► Step 2 ──► Step 3 ❌ FAILS                         │
│     │          │          │                                      │
│     │          │          │                                      │
│     │          │          ▼                                      │
│     │          │     ┌─────────────────┐                        │
│     │          │     │ Compensation 3  │                        │
│     │          │     │ (if defined)    │                        │
│     │          │     └────────┬────────┘                        │
│     │          │              │                                 │
│     │          ▼              │                                 │
│     │     ┌─────────────────┐│                                 │
│     │     │ Compensation 2  ││                                 │
│     │     │ Cancel TP order ││                                 │
│     │     └────────┬────────┘│                                 │
│     │              │         │                                 │
│     ▼              ▼         ▼                                 │
│ ┌──────────────────────────────┐                               │
│ │    Compensation 1            │                               │
│ │    Remove position           │                               │
│ └──────────────┬───────────────┘                               │
│                │                                                │
│                ▼                                                │
│         ❌ SAGA FAILED                                          │
│         (All changes rolled back)                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

EXAMPLE: BUY Fill Saga Failure at Step 3

┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  STEP 1: Add Position @ 99,000 → 99,500        ✅ SUCCESS      │
│  STEP 1.5: Clear pending_buy                    ✅ SUCCESS      │
│  STEP 2: Place TP SELL @ 99,500                ✅ SUCCESS      │
│  STEP 3: Place next BUY @ 98,500               ❌ FAILS        │
│          (Exchange rejects order)                               │
│                                                                  │
│  COMPENSATION SEQUENCE:                                         │
│                                                                  │
│  1. Compensation Step 3: Cancel next BUY                        │
│     (N/A - order wasn't placed)                                 │
│                                                                  │
│  2. Compensation Step 2: Cancel TP order                        │
│     ├─► OrderActor.CANCEL_ORDER(ORD_0002)                      │
│     └─► Exchange cancels SELL @ 99,500                         │
│                                                                  │
│  3. Compensation Step 1: Remove position                        │
│     ├─► PositionActor.REMOVE_POSITION(POS_0001)                │
│     └─► open_tranches.remove({entry: 99000, tp: 99500})        │
│                                                                  │
│  RESULT: Bot state rolled back to before fill processing        │
│          Position NOT added                                     │
│          TP NOT placed                                          │
│          Next BUY NOT placed                                    │
│                                                                  │
│  ⚠️  ISSUE: Compensation uses TELL, not ASK                     │
│      No verification that compensation succeeded                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. GRID LEVEL CALCULATION LOGIC

```
┌─────────────────────────────────────────────────────────────────┐
│                  GRID CONFIGURATION                              │
│                                                                  │
│  Lower: 95,000    Upper: 110,000    Step: 500    Ref: 100,000  │
│                                                                  │
│  Grid Levels (partial):                                         │
│  95,000 | 95,500 | 96,000 | ... | 99,500 | 100,000 | 100,500  │
│  ... | 109,500 | 110,000                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              LONG MODE: BUY Level Calculation                    │
│                                                                  │
│  compute_next_buy_level(positions, current_price):              │
│                                                                  │
│  IF positions is empty:                                         │
│    IF current_price < ref:                                      │
│      lowest_entry = find_nearest_grid_below(current_price)     │
│    ELSE:                                                        │
│      lowest_entry = ref                                         │
│  ELSE:                                                          │
│    lowest_entry = min(p.entry_price for p in positions)        │
│                                                                  │
│  target = lowest_entry - step                                   │
│                                                                  │
│  IF target within bounds:                                       │
│    RETURN quantize(target)                                      │
│  ELSE:                                                          │
│    RETURN None                                                  │
│                                                                  │
│  Example:                                                       │
│    positions = [{entry: 99500}, {entry: 99000}]                │
│    lowest_entry = 99000                                         │
│    target = 99000 - 500 = 98500                                 │
│    RETURN 98,500                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              SHORT MODE: SELL Level Calculation                  │
│                                                                  │
│  compute_next_sell_level(positions, current_price):             │
│                                                                  │
│  IF positions is empty:                                         │
│    IF current_price > ref:                                      │
│      highest_entry = find_nearest_grid_above(current_price)    │
│    ELSE:                                                        │
│      highest_entry = ref                                        │
│  ELSE:                                                          │
│    highest_entry = max(p.entry_price for p in positions)       │
│                                                                  │
│  target = highest_entry + step                                  │
│                                                                  │
│  IF target within bounds:                                       │
│    RETURN quantize(target)                                      │
│  ELSE:                                                          │
│    RETURN None                                                  │
│                                                                  │
│  Example:                                                       │
│    positions = [{entry: 100500}, {entry: 101000}]              │
│    highest_entry = 101000                                       │
│    target = 101000 + 500 = 101500                               │
│    RETURN 101,500                                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                  TP Price Calculation                            │
│                                                                  │
│  LONG MODE:                                                     │
│    compute_tp_price(entry_price):                               │
│      RETURN entry_price + step                                  │
│                                                                  │
│    Example: entry = 99,000 → TP = 99,500                       │
│                                                                  │
│  SHORT MODE:                                                    │
│    compute_tp_price_short(entry_price):                         │
│      RETURN entry_price - step                                  │
│                                                                  │
│    Example: entry = 100,500 → TP = 100,000                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. MONITORING SYSTEMS (5 Layers)

```
┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 1: Price Health Monitor                  │
│                                                                  │
│  • Tracks price freshness                                       │
│  • Warns if price > 10s old                                     │
│  • Critical if > 30s old                                        │
│  • Prevents stale price orders                                  │
│                                                                  │
│  Methods:                                                       │
│    • update_price(price, source)                                │
│    • can_place_orders() → (bool, reason)                        │
│    • get_status() → dict                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 2: Pre-Order Decision Logger             │
│                                                                  │
│  • Logs every order decision before placement                   │
│  • Transparent audit trail                                      │
│  • Stores recent decisions (last 100)                           │
│                                                                  │
│  Logged Data:                                                   │
│    • side (buy/sell)                                            │
│    • price                                                      │
│    • current_price                                              │
│    • reason                                                     │
│    • positions count                                            │
│    • timestamp                                                  │
│                                                                  │
│  Methods:                                                       │
│    • log_decision(...)                                          │
│    • get_recent_decisions() → list                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 3: TP Verification System                │
│                                                                  │
│  • Detects orphaned positions (no TP order)                     │
│  • Cross-checks positions vs TP orders                          │
│  • Alerts if position lacks TP protection                       │
│                                                                  │
│  Methods:                                                       │
│    • verify_tp_orders(positions, orders)                        │
│    • get_orphaned_positions() → list                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 4: Anomaly Detection System              │
│                                                                  │
│  • Pattern detection (unusual order placement)                  │
│  • Rate monitoring (too many orders)                            │
│  • Distance checks (order far from market)                      │
│                                                                  │
│  Methods:                                                       │
│    • check_before_order(side, price, current_price)             │
│    • get_recent_anomalies() → list                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                   LAYER 5: Predictive Decision Display           │
│                                                                  │
│  • Shows next expected actions                                  │
│  • Predicts next BUY/SELL levels                                │
│  • Estimates TP prices                                          │
│  • Displays "bot is waiting for X"                              │
│                                                                  │
│  Methods:                                                       │
│    • predict_next_actions(state, current_price)                 │
│    • get_predictions() → dict                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

**END OF DIAGRAMS**

All diagrams are code-accurate representations derived from actual implementation.

For detailed analysis, see: `ASYNC_GRIDBOT_FORENSIC_ANALYSIS.md`  
For simulation, run: `python3 async_bot_simulation.py`
