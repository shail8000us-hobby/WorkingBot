# Multi-Client Architecture Plan

## Context

The WorkingBot currently operates with a single set of API credentials (live/demo) loaded from
`secrets/api_keys.env`. This document captures the architectural decisions and implementation
plan for supporting multiple client accounts on the same bot stack, with all clients visible
from a single WebUI.

---

## Architectural Decisions

### Decision 1 — Credential Storage: Encrypted SQLite

**Chosen:** Encrypted SQLite table (`data/clients.db`)

**Schema (logical):**
```
clients
  client_id      TEXT PRIMARY KEY   (e.g. "ssr_main", "client_abc")
  display_name   TEXT               (human label shown in WebUI)
  exchange       TEXT               (e.g. "delta", "bybit")
  mode           TEXT               (live | demo)
  api_key        BLOB               (Fernet-encrypted)
  api_secret     BLOB               (Fernet-encrypted)
  active         INTEGER            (0 or 1)
  created_at     TEXT               (ISO timestamp)
```

**Encryption:** Fernet (AES-128-CBC + HMAC) from Python `cryptography` library.
**Master key source:** `MASTER_KEY` env var in `secrets/api_keys.env` — never stored on disk in plaintext.
**Add/remove clients:** WebUI admin page (not manual file editing).

**Why not alternatives:**
- Per-client `.env` files: no WebUI management, error-prone, hard to audit
- HashiCorp Vault / AWS Secrets Manager: significant ops overhead, overkill for <10 clients

---

### Decision 2 — Runtime Isolation: Thread-per-client (Phase 1)

**Chosen for now:** One `MMMMonitor` thread per client, inside a single Flask process.

**How it fits the current architecture:**
- MMM already runs one monitor thread. Multi-client = run N threads, one per client.
- Each client gets their own `DeltaClient` instance initialized with their decrypted keys.
- Session state is namespaced: `data/clients/{client_id}/mmm_sessions.db`
- All stale-monitor guards (gen checks, G5 guardian, `thread.join(15s)`) apply per-client independently — the guards are instance-scoped, so N threads = N independent guard sets.

**Client registry at runtime:**
```
ClientRegistry (singleton)
  └── client_id → ClientContext
        ├── credentials (decrypted, in-memory only during session)
        ├── DeltaClient instance
        ├── MMMMonitor instance (or None if stopped)
        └── session_dir: data/clients/{client_id}/
```

**Why this works at small scale (1–7 clients):**
- No new infrastructure
- WebUI aggregation is trivial (same process memory)
- Natural extension of the existing instance pattern (`BTCUSD_LONG`, `BTCUSD_SHORT`)
- Fast to build, easy to reason about

---

### Decision 2 (Phase 2) — Migrate to Subprocess-per-client when clients grow

**Trigger point:** When client count exceeds ~7, or when one client's misbehavior starts affecting
others (runaway thread, memory leak, exception storm).

**Subprocess model:**
- Each client = isolated Python subprocess running the full bot stack on its own port or socket
- A master orchestrator process manages lifecycle (start, stop, restart per client)
- WebUI backend becomes an aggregator: it holds no trading state itself, only queries each
  client subprocess or reads from a shared SQLite written by each subprocess
- Inter-process communication: shared SQLite (simplest), or HTTP (each subprocess exposes a
  local API), or Unix domain sockets

**Why defer this:**
- Subprocess lifecycle management, crash recovery, log aggregation, and WebUI aggregation
  across processes are all non-trivial engineering work
- Thread-per-client handles 1–7 clients comfortably with far less code
- Migrating from thread → subprocess later is clean: the `ClientContext` abstraction is the
  same; only the runtime backing changes

**Migration path when the time comes:**
1. Wrap each client's thread entrypoint into a standalone `__main__` script
2. Replace `threading.Thread` with `subprocess.Popen` in the `ClientRegistry`
3. Add a small health/status HTTP endpoint per subprocess
4. Update WebUI aggregation to poll subprocess endpoints instead of in-process state

---

### Decision 3 — Session & Data Isolation: Per-client directory

**Chosen:** `data/clients/{client_id}/` contains all state for that client.

**Directory layout per client:**
```
data/clients/
  ssr_main/
    mmm_sessions.db
    ic_sessions.db
    ssdh_sessions.json
    bot_events_BTCUSD_LONG.db
    logs/
  client_abc/
    mmm_sessions.db
    ...
```

**Why not a single shared DB with a `client_id` column:**
- Zero schema migration on existing DBs
- A corrupt or bloated one client's DB doesn't touch others
- Backup/restore is trivially per-client (`cp -r data/clients/client_abc/ backup/`)
- The existing code opens DBs by path — swapping the path is a one-line change per module

---

### Decision 4 — WebUI Layout: Client selector + unified position table

**Chosen:** Dropdown in the header to select the active client, with an optional "All Clients"
aggregated view showing positions across all clients in a single table.

**Details:**
- Header dropdown: `[Client: SSR Main ▾]` — switching reloads the dashboard in context of
  that client
- All existing panels (MMM, OI, positions, P&L) work unchanged — they just pull data scoped
  to the selected client
- **Unified Positions tab (new):** A single table listing all open positions across all clients.
  Columns: Client | Symbol | Side | Lots | Entry | Mark | Unrealised P&L
- No redesign of existing per-strategy panels required

---

## Implementation Plan

### Phase 0 — Groundwork (no visible change to existing behavior)

1. **Create `ClientRegistry` module** (`webui/backend/services/client_registry.py`)
   - Manages the in-memory map of `client_id → ClientContext`
   - Load/decrypt credentials from `clients.db` on startup
   - Default client = existing credentials from `secrets/api_keys.env` (so nothing breaks)

2. **Create `clients.db` + credential store** (`webui/backend/services/client_store.py`)
   - SQLite schema for the `clients` table
   - Fernet encrypt/decrypt helpers (master key from env)
   - CRUD: add client, remove client, list clients, get decrypted credentials

3. **Migrate existing credentials into `clients.db` as the default client**
   - One-time migration script: reads `secrets/api_keys.env`, inserts as `client_id = "default"`
   - Existing code keeps working unchanged — it just reads from `ClientRegistry.get("default")`

4. **Create per-client data directory structure**
   - `data/clients/default/` — move (or symlink) existing session DBs here
   - Update path resolution in MMM session loader to accept a base dir argument

---

### Phase 1 — Backend: Multi-client runtime

5. **Parameterise `DeltaClient` / `UnifiedAPIClient` initialization**
   - Currently reads credentials from global env. Change to accept explicit `api_key` / `api_secret`
   - All existing callers pass `ClientRegistry.get_credentials(client_id)` — default is transparent

6. **Parameterise `MMMMonitor` to accept a `ClientContext`**
   - `start_session_monitor(client_id)` looks up context, passes credentials + session dir
   - Each monitor thread is tagged with its `client_id` in logs and Telegram alerts
   - Stale-monitor guards are unchanged — they are already instance-scoped

7. **Add client-scoped API endpoints**
   - All existing routes continue to work against the "default" client for backwards compat
   - New routes accept optional `client_id` query param or `X-Client-ID` header
   - Or: route prefix `/api/client/{client_id}/...` (cleaner, easier to reason about)

8. **Add admin endpoints for client management**
   - `POST /api/admin/clients` — add a new client (name, exchange, mode, key, secret)
   - `DELETE /api/admin/clients/{client_id}` — remove
   - `GET /api/admin/clients` — list all (names + status, never expose decrypted keys)
   - `POST /api/admin/clients/{client_id}/start` — start monitor for that client
   - `POST /api/admin/clients/{client_id}/stop` — stop monitor for that client

---

### Phase 2 — WebUI: Client selector + unified view

9. **Add client selector to header**
   - Dropdown populated from `GET /api/admin/clients`
   - Selection stored in `localStorage` as `activeClientId`
   - All API calls from frontend include `X-Client-ID` header

10. **Add "All Clients" positions table**
    - New WebUI tab: **Clients Overview**
    - Backend endpoint: `GET /api/clients/positions/all` — aggregates across all active clients
    - Table: Client | Symbol | Side | Lots | Entry | Mark | Unrealised P&L | Strategy
    - Refresh on same polling interval as existing position panels

11. **Add WebUI admin page: Client Management**
    - Form to add a new client (name, exchange, mode, paste API key + secret)
    - List of existing clients with status (running / stopped) and start/stop buttons
    - Delete button (requires confirmation modal)
    - Keys are never shown after initial entry (write-only display)

---

### Phase 3 — Hardening

12. **Credential security audit**
    - Ensure decrypted keys are never logged, never serialised to JSON responses, never written to disk
    - Add a memory wipe after use if the client is stopped
    - Rate-limit the admin endpoints

13. **Per-client Telegram alerts**
    - Each client can optionally have their own Telegram chat ID for alerts
    - Falls back to the default chat ID if not configured

14. **Per-client P&L and audit log**
    - Each client's MMM audit trail goes to `data/clients/{client_id}/audit.jsonl`
    - WebUI reconciliation page scoped to selected client

15. **Testing**
    - Add a "demo" credential mode per client — can onboard a client with demo keys first
    - Verify stale-monitor guards fire correctly when two clients' monitors run simultaneously

---

### Phase 4 — Subprocess migration (when client count > 7)

16. Extract `ClientContext` thread entrypoint into a standalone runnable module
17. Replace `threading.Thread` launch with `subprocess.Popen`
18. Add per-subprocess health endpoint
19. Update `ClientRegistry` to use HTTP polling instead of in-process state
20. Update WebUI aggregation layer accordingly

---

## What Does NOT Change

- All existing MMM logic, stale-monitor guards, reverse mode invariants — untouched
- Existing session file formats and DB schemas — just moved under `data/clients/default/`
- Existing single-client workflow — default client is transparent, no UX change until you add a second client
- CLAUDE.md rules — all apply per client context

---

## Risk Notes

- **API key in memory:** Decrypted keys live in `ClientContext` while the monitor is running.
  If the process is core-dumped, keys are exposed. Mitigate: restrict core dumps (`ulimit -c 0`).
- **Thread contention:** At >5 simultaneous clients, GIL contention on shared Python state
  (e.g. logging, SQLite connections) may surface. Profile before adding client #6.
- **Stale monitor with multiple clients:** The generation guard checks `stored_gen` in a
  per-client session file. Ensure each client's monitor reads only its own session file.
  A cross-client session path bug would be a P0.
