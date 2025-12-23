from __future__ import annotations

import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.loader import get_config
from bot.api.delta_client import DeltaClient
from bot.utils.atomic_file import atomic_write_json


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _normalize_status(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    s = str(value).strip().lower()
    if s in {"wait", "waiting", "new"}:
        return "pending"
    if s in {"filled", "executed", "completed", "closed"}:
        return "filled"
    if s in {"cancelled"}:
        return "canceled"
    return s


def _float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str) and not value.strip():
            return None
        return float(value)
    except Exception:
        return None


@dataclass
class OrderRecord:
    id: Optional[str]
    client_order_id: Optional[str]
    side: Optional[str]
    type: Optional[str]
    status: Optional[str]
    price: Optional[float]
    qty: Optional[float]
    filled_qty: Optional[float]
    symbol: Optional[str]
    origin: str  # exchange | bot
    provenance: str  # bot | manual | unknown
    ts: Optional[str]
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "clientOrderId": self.client_order_id,
            "side": self.side,
            "type": self.type,
            "status": self.status,
            "price": self.price,
            "qty": self.qty,
            "filledQty": self.filled_qty,
            "symbol": self.symbol,
            "origin": self.origin,
            "provenance": self.provenance,
            "ts": self.ts,
        }
        if self.extra:
            payload["extra"] = self.extra
        return payload


@dataclass
class LedgerIndex:
    order_ids: set[str] = field(default_factory=set)
    client_ids: set[str] = field(default_factory=set)

    @classmethod
    def from_entries(cls, entries: Iterable[Dict[str, Any]]) -> "LedgerIndex":
        order_ids: set[str] = set()
        client_ids: set[str] = set()
        for entry in entries:
            order_id = entry.get("order_id") or entry.get("id")
            client_id = entry.get("client_order_id") or entry.get("client_id")
            if order_id:
                order_ids.add(str(order_id))
            if client_id:
                client_ids.add(str(client_id))
        return cls(order_ids=order_ids, client_ids=client_ids)


class ReconciliationV2Service:
    def __init__(
        self,
        base_dir: Path | str,
        *,
        delta_client_factory: Optional[Callable[[], DeltaClient]] = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        self.reports_dir = self.base_dir / "reports"
        self.snapshot_path = self.reports_dir / "reconciliation_status.json"
        self.delta_client_factory = delta_client_factory or DeltaClient
        self._delta_client: Optional[DeltaClient] = None
        self._product_id: Optional[int] = None
        self._lock = Lock()
        self._last_report: Optional[Dict[str, Any]] = None
        self._load_existing_snapshot()

    # ---------- Public API ----------

    def run_cycle(
        self,
        *,
        now: Optional[datetime] = None,
        lookback_days: Optional[int] = None,
        dry_run: Optional[bool] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            now = now or datetime.utcnow().replace(tzinfo=timezone.utc)
            cfg = get_config()
            mode = cfg.safety.trading_mode
            lookback = lookback_days or cfg.reconciliation.lookback_days
            dry_run_effective = dry_run if dry_run is not None else cfg.reconciliation.dry_run

            ledger_entries, ledger_index = self._load_ledger()
            positions = self._load_positions(mode)
            state_snapshot = self._load_state(mode)

            exchange_orders, exchange_error = self._fetch_exchange_orders(mode, lookback)
            exchange_positions, positions_error = self._fetch_exchange_positions(mode)

            exchange_records = [
                self._normalize_exchange_order(o, ledger_index) for o in exchange_orders
            ]

            bot_records = []
            bot_records.extend(self._normalize_ledger_entry(entry) for entry in ledger_entries)
            bot_records.extend(self._normalize_position_entry(pos) for pos in positions)
            bot_records.extend(self._normalize_state_entry(state_snapshot))

            match_result = self._match_records(
                exchange_records,
                bot_records,
                lookback_days=lookback,
            )

            report = self._build_report(
                now=now,
                mode=mode,
                lookback_days=lookback,
                dry_run=dry_run_effective,
                match_result=match_result,
                exchange_error=exchange_error,
                positions_error=positions_error,
                state_snapshot=state_snapshot,
            )

            if not dry_run_effective:
                # v2 is detection-only; still honour flag for future extension.
                pass

            atomic_write_json(self.snapshot_path, report, indent=2)
            self._last_report = json.loads(json.dumps(report))

            return report

    def get_last_report(self) -> Optional[Dict[str, Any]]:
        if self._last_report is not None:
            return json.loads(json.dumps(self._last_report))
        if self.snapshot_path.exists():
            try:
                with self.snapshot_path.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    self._last_report = data
                    return json.loads(json.dumps(data))
            except Exception:
                return None
        return None

    # ---------- Exchange helpers ----------

    def _ensure_delta_client(self) -> Optional[DeltaClient]:
        if self._delta_client is not None:
            return self._delta_client
        try:
            client = self.delta_client_factory()
        except Exception:
            return None
        self._delta_client = client
        return self._delta_client

    def _resolve_product_id(self, mode: str) -> Optional[int]:
        if self._product_id is not None:
            return self._product_id
        client = self._ensure_delta_client()
        if not client:
            return None
        cfg = get_config()
        # Check product_id from config
        if cfg.trading.product_id:
            try:
                self._product_id = int(cfg.trading.product_id)
                return self._product_id
            except Exception:
                pass
        # Fall back to resolving from symbol
        symbol = cfg.trading.symbol
        try:
            self._product_id = client.resolve_product_id(symbol)
            return self._product_id
        except Exception:
            return None

    def _fetch_exchange_orders(self, mode: str, lookback_days: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        client = self._ensure_delta_client()
        if not client:
            return [], "delta_client_unavailable"

        product_id = self._resolve_product_id(mode)
        params = {}
        if product_id is not None:
            params["product_id"] = product_id

        orders: List[Dict[str, Any]] = []
        try:
            # Fetch open and pending orders using correct API format
            response = client.list_orders(product_id=product_id, states="open,pending")
            items = response.get("result") if isinstance(response, dict) else None
            if isinstance(items, list):
                orders.extend(items)
            return orders, None
        except Exception as exc:
            return [], str(exc)

    def _fetch_exchange_positions(self, mode: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        client = self._ensure_delta_client()
        if not client:
            return [], "delta_client_unavailable"
        
        # Get product_id for the API call
        product_id = self._resolve_product_id(mode)
        
        try:
            # Use the proper get_positions method
            if product_id:
                payload = client.get_positions(product_id=product_id)
            else:
                # Fallback: get all BTC positions
                payload = client.get_positions(underlying_asset_symbol="BTC")
        except Exception as exc:
            return [], str(exc)

        positions: List[Dict[str, Any]] = []
        if isinstance(payload, dict) and isinstance(payload.get("result"), list):
            positions = payload["result"]
        elif isinstance(payload, list):
            positions = payload
        else:
            positions = []
        return positions, None

    # ---------- Bot memory loaders ----------

    def _load_ledger(self) -> Tuple[List[Dict[str, Any]], LedgerIndex]:
        audit_path = self.base_dir / "bot" / "audit" / "orders.jsonl"
        entries: List[Dict[str, Any]] = []
        if audit_path.exists():
            with audit_path.open("r", encoding="utf-8", errors="replace") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(payload, dict):
                        entries.append(payload)
                    elif isinstance(payload, list):
                        entries.extend(item for item in payload if isinstance(item, dict))
        return entries, LedgerIndex.from_entries(entries)

    def _load_positions(self, mode: str) -> List[Dict[str, Any]]:
        candidates = [
            self.base_dir / f"positions_{mode}.json",
            self.base_dir / "positions.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as fh:
                        payload = json.load(fh)
                        if isinstance(payload, dict) and isinstance(payload.get("positions"), list):
                            return payload["positions"]
                except Exception:
                    continue
        return []

    def _load_state(self, mode: str) -> Dict[str, Any]:
        candidates = [
            self.base_dir / f"state_{mode}.json",
            self.base_dir / "state.json",
            self.base_dir / "state_live.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as fh:
                        payload = json.load(fh)
                        if isinstance(payload, dict):
                            return payload
                except Exception:
                    continue
        return {}

    # ---------- Normalizers ----------

    def _normalize_exchange_order(self, order: Dict[str, Any], ledger_index: LedgerIndex) -> OrderRecord:
        oid = order.get("id") or order.get("order_id")
        client_id = order.get("client_order_id") or order.get("client_id")
        symbol = order.get("product_symbol") or order.get("symbol")
        status = _normalize_status(order.get("state") or order.get("status"))
        provenance, evidence = self._classify_provenance(oid, client_id, ledger_index)
        price = _float(order.get("limit_price") or order.get("price"))
        qty = _float(order.get("size") or order.get("quantity"))
        filled_qty = _float(order.get("filled_size") or order.get("filled"))
        record = OrderRecord(
            id=str(oid) if oid is not None else None,
            client_order_id=str(client_id) if client_id is not None else None,
            side=(order.get("side") or "").lower() or None,
            type=(order.get("order_type") or order.get("type") or "").lower() or None,
            status=status,
            price=price,
            qty=qty,
            filled_qty=filled_qty,
            symbol=symbol,
            origin="exchange",
            provenance=provenance,
            ts=order.get("updated_at") or order.get("created_at"),
            extra={
                "source": "exchange",
                "raw": {k: order.get(k) for k in ("time_in_force", "reduce_only", "commission", "average_fill_price")},
                "evidence": evidence,
            },
        )
        return record

    def _normalize_ledger_entry(self, entry: Dict[str, Any]) -> OrderRecord:
        oid = entry.get("order_id") or entry.get("id")
        client_id = entry.get("client_order_id") or entry.get("client_id")
        status = _normalize_status(
            entry.get("status") or entry.get("metadata", {}).get("status") or entry.get("state")
        )
        price = _float(
            entry.get("price")
            or entry.get("metadata", {}).get("price")
        )
        qty = _float(
            entry.get("qty")
            or entry.get("size")
            or entry.get("metadata", {}).get("qty")
            or entry.get("metadata", {}).get("size")
        )
        filled_qty = _float(
            entry.get("filled_qty")
            or entry.get("filled_size")
            or entry.get("metadata", {}).get("filled_size")
        )
        symbol = entry.get("symbol") or entry.get("metadata", {}).get("symbol")
        ts = entry.get("timestamp") or entry.get("ts")
        return OrderRecord(
            id=str(oid) if oid else None,
            client_order_id=str(client_id) if client_id else None,
            side=(entry.get("side") or entry.get("metadata", {}).get("side") or "").lower() or None,
            type=(entry.get("order_type") or entry.get("metadata", {}).get("order_type") or "").lower() or None,
            status=status,
            price=price,
            qty=qty,
            filled_qty=filled_qty,
            symbol=symbol,
            origin="bot",
            provenance="bot",
            ts=ts,
            extra={
                "source": "ledger",
                "raw": entry,
            },
        )

    def _normalize_position_entry(self, entry: Dict[str, Any]) -> OrderRecord:
        oid = entry.get("tp_order_id") or entry.get("order_id") or entry.get("id")
        side = entry.get("metadata", {}).get("side") or entry.get("side")
        if side:
            side = str(side).lower()
        qty = _float(entry.get("size"))
        price = _float(entry.get("entry_price") or entry.get("price"))
        ts = entry.get("last_update") or entry.get("timestamp")
        return OrderRecord(
            id=str(oid) if oid else None,
            client_order_id=None,
            side=side,
            type="position",
            status=entry.get("status") or "open",
            price=price,
            qty=qty,
            filled_qty=qty,
            symbol=entry.get("symbol"),
            origin="bot",
            provenance="bot",
            ts=ts,
            extra={
                "source": "positions",
                "position_id": entry.get("id"),
                "tp_order_id": entry.get("tp_order_id"),
            },
        )

    def _normalize_state_entry(self, state: Dict[str, Any]) -> List[OrderRecord]:
        ladder = state.get("LADDER") if isinstance(state, dict) else None
        if not isinstance(ladder, list):
            return []
        records: List[OrderRecord] = []
        for idx, rung in enumerate(ladder):
            try:
                entry_price = _float(rung.get("entry"))
                size = _float(rung.get("size"))
            except Exception:
                entry_price = None
                size = None
            records.append(
                OrderRecord(
                    id=str(rung.get("order_id") or rung.get("tp_id") or f"ladder_{idx}"),
                    client_order_id=None,
                    side="buy",
                    type="ladder",
                    status="open",
                    price=entry_price,
                    qty=size,
                    filled_qty=None,
                    symbol=state.get("SYMBOL"),
                    origin="bot",
                    provenance="bot",
                    ts=None,
                    extra={
                        "source": "state",
                        "ladder_index": idx,
                    },
                )
            )
        return records

    def _classify_provenance(
        self,
        order_id: Optional[str],
        client_order_id: Optional[str],
        ledger_index: LedgerIndex,
    ) -> Tuple[str, Dict[str, Any]]:
        evidence: Dict[str, Any] = {}
        normalized_order_id = str(order_id) if order_id is not None else None
        normalized_client_id = str(client_order_id) if client_order_id is not None else None

        if normalized_order_id and normalized_order_id in ledger_index.order_ids:
            evidence["matched"] = "order_id"
            return "bot", evidence

        if normalized_client_id and normalized_client_id in ledger_index.client_ids:
            evidence["matched"] = "client_id"
            return "bot", evidence

        prefixes = ("GBOT", "BOT-", "GRIDBOT")
        if normalized_client_id and normalized_client_id.upper().startswith(prefixes):
            evidence["matched"] = "client_prefix"
            evidence["prefix"] = normalized_client_id[:8]
            return "unknown", evidence

        return "manual", evidence

    # ---------- Matching ----------

    def _match_records(
        self,
        exchange_records: List[OrderRecord],
        bot_records: List[OrderRecord],
        *,
        lookback_days: int,
    ) -> Dict[str, Any]:
        bot_pool = list(bot_records)
        used_bot_indexes: set[int] = set()

        bot_by_id: Dict[str, List[int]] = {}
        bot_by_client: Dict[str, List[int]] = {}
        for idx, record in enumerate(bot_pool):
            if record.id:
                bot_by_id.setdefault(record.id, []).append(idx)
            if record.client_order_id:
                bot_by_client.setdefault(record.client_order_id, []).append(idx)

        records: List[Dict[str, Any]] = []
        counts = {"synced": 0, "stray": 0, "ghost": 0, "diverged": 0}
        provenance_counts: Dict[str, Dict[str, int]] = {
            "bot": {"synced": 0, "stray": 0, "ghost": 0, "diverged": 0},
            "manual": {"synced": 0, "stray": 0, "ghost": 0, "diverged": 0},
            "unknown": {"synced": 0, "stray": 0, "ghost": 0, "diverged": 0},
        }

        def _take_first_available(indexes: List[int]) -> Optional[int]:
            while indexes:
                candidate = indexes.pop(0)
                if candidate not in used_bot_indexes:
                    return candidate
            return None

        for exchange_record in exchange_records:
            idx = None
            if exchange_record.id and exchange_record.id in bot_by_id:
                idx = _take_first_available(bot_by_id[exchange_record.id])
            if idx is None and exchange_record.client_order_id and exchange_record.client_order_id in bot_by_client:
                idx = _take_first_available(bot_by_client[exchange_record.client_order_id])
            if idx is None:
                idx = self._find_fuzzy_match(exchange_record, bot_pool, used_bot_indexes)

            if idx is None:
                record_payload = {
                    "kind": "stray",
                    "provenance": exchange_record.provenance,
                    "exchange": exchange_record.to_dict(),
                    "bot": None,
                    "reason": "Order missing from bot memory",
                }
                records.append(record_payload)
                counts["stray"] += 1
                provenance_counts[exchange_record.provenance]["stray"] += 1
                continue

            used_bot_indexes.add(idx)
            bot_record = bot_pool[idx]
            diff = self._diff_records(exchange_record, bot_record)
            if diff:
                record_payload = {
                    "kind": "diverged",
                    "provenance": exchange_record.provenance or bot_record.provenance,
                    "exchange": exchange_record.to_dict(),
                    "bot": bot_record.to_dict(),
                    "diff": diff,
                    "reason": "Fields differ between exchange and bot",
                }
                records.append(record_payload)
                counts["diverged"] += 1
                provenance = exchange_record.provenance or bot_record.provenance
                provenance_counts[provenance]["diverged"] += 1
            else:
                record_payload = {
                    "kind": "synced",
                    "provenance": exchange_record.provenance or bot_record.provenance,
                    "exchange": exchange_record.to_dict(),
                    "bot": bot_record.to_dict(),
                }
                records.append(record_payload)
                counts["synced"] += 1
                provenance = exchange_record.provenance or bot_record.provenance
                provenance_counts[provenance]["synced"] += 1

        for idx, bot_record in enumerate(bot_pool):
            if idx in used_bot_indexes:
                continue
            record_payload = {
                "kind": "ghost",
                "provenance": bot_record.provenance,
                "exchange": None,
                "bot": bot_record.to_dict(),
                "reason": "Local record missing on exchange",
            }
            records.append(record_payload)
            counts["ghost"] += 1
            provenance_counts[bot_record.provenance]["ghost"] += 1

        totals_exchange = {"open": 0, "pending": 0, "filled_recent": 0}
        totals_bot = {"open": 0, "pending": 0, "filled_recent": 0}
        lookback_threshold = datetime.utcnow().replace(tzinfo=timezone.utc) - timedelta(days=lookback_days)

        for record in exchange_records:
            status = record.status or ""
            if status == "open":
                totals_exchange["open"] += 1
            elif status == "pending":
                totals_exchange["pending"] += 1
            elif status == "filled":
                ts = _parse_iso8601(record.ts)
                if ts and ts.replace(tzinfo=timezone.utc) >= lookback_threshold:
                    totals_exchange["filled_recent"] += 1

        for record in bot_records:
            status = (record.status or "").lower()
            if status == "open":
                totals_bot["open"] += 1
            elif status == "pending":
                totals_bot["pending"] += 1
            elif status == "filled":
                ts = _parse_iso8601(record.ts)
                if ts and ts.replace(tzinfo=timezone.utc) >= lookback_threshold:
                    totals_bot["filled_recent"] += 1

        mismatches = [r for r in records if r["kind"] in {"ghost", "stray", "diverged"}]
        return {
            "records": records,
            "mismatches": mismatches,
            "counts": counts,
            "totals": {
                "exchange": totals_exchange,
                "bot": totals_bot,
            },
            "provenance": provenance_counts,
        }

    def _find_fuzzy_match(
        self,
        exchange_record: OrderRecord,
        bot_pool: List[OrderRecord],
        used_indexes: set[int],
    ) -> Optional[int]:
        symbol = exchange_record.symbol
        side = exchange_record.side
        price = exchange_record.price
        qty = exchange_record.qty
        ts = _parse_iso8601(exchange_record.ts)

        for idx, candidate in enumerate(bot_pool):
            if idx in used_indexes:
                continue
            if symbol and candidate.symbol and candidate.symbol != symbol:
                continue
            if side and candidate.side and candidate.side != side:
                continue
            if price is not None and candidate.price is not None and abs(candidate.price - price) > 1e-2:
                continue
            if qty is not None and candidate.qty is not None and abs(candidate.qty - qty) > 1e-6:
                continue
            if ts and candidate.ts:
                c_ts = _parse_iso8601(candidate.ts)
                if c_ts and abs((c_ts - ts).total_seconds()) > 120:
                    continue
            return idx
        return None

    def _diff_records(self, exchange_record: OrderRecord, bot_record: OrderRecord) -> Dict[str, Dict[str, Any]]:
        diff: Dict[str, Dict[str, Any]] = {}
        if exchange_record.status != bot_record.status:
            diff["status"] = {"exchange": exchange_record.status, "bot": bot_record.status}
        if exchange_record.price is not None and bot_record.price is not None:
            if not math.isclose(exchange_record.price, bot_record.price, rel_tol=0, abs_tol=1e-2):
                diff["price"] = {"exchange": exchange_record.price, "bot": bot_record.price}
        elif exchange_record.price != bot_record.price:
            diff["price"] = {"exchange": exchange_record.price, "bot": bot_record.price}
        if exchange_record.qty is not None and bot_record.qty is not None:
            if not math.isclose(exchange_record.qty, bot_record.qty, rel_tol=0, abs_tol=1e-6):
                diff["qty"] = {"exchange": exchange_record.qty, "bot": bot_record.qty}
        elif exchange_record.qty != bot_record.qty:
            diff["qty"] = {"exchange": exchange_record.qty, "bot": bot_record.qty}
        if exchange_record.filled_qty is not None and bot_record.filled_qty is not None:
            if not math.isclose(exchange_record.filled_qty, bot_record.filled_qty, rel_tol=0, abs_tol=1e-6):
                diff["filledQty"] = {
                    "exchange": exchange_record.filled_qty,
                    "bot": bot_record.filled_qty,
                }
        elif exchange_record.filled_qty != bot_record.filled_qty:
            diff["filledQty"] = {
                "exchange": exchange_record.filled_qty,
                "bot": bot_record.filled_qty,
            }
        return diff

    # ---------- Reporting ----------

    def _build_report(
        self,
        *,
        now: datetime,
        mode: str,
        lookback_days: int,
        dry_run: bool,
        match_result: Dict[str, Any],
        exchange_error: Optional[str],
        positions_error: Optional[str],
        state_snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "version": 2,
            "ts": now.isoformat(),
            "mode": mode,
            "exchange_unavailable": bool(exchange_error),
            "totals": match_result["totals"],
            "counts": match_result["counts"],
            "provenance": match_result["provenance"],
            "mismatches": match_result["mismatches"],
            "records": match_result["records"],
            "meta": {
                "lookback_days": lookback_days,
                "dry_run": dry_run,
            },
        }
        if exchange_error:
            report["errors"] = {"exchange": exchange_error}
        if positions_error:
            report.setdefault("errors", {})["positions"] = positions_error
        if state_snapshot:
            report["state_snapshot"] = {
                "has_ladder": isinstance(state_snapshot.get("LADDER"), list),
                "grid_active": state_snapshot.get("GRID_ACTIVE"),
            }
        return report

    # ---------- Internal ----------

    def _load_existing_snapshot(self) -> None:
        if not self.snapshot_path.exists():
            return
        try:
            with self.snapshot_path.open("r", encoding="utf-8") as fh:
                self._last_report = json.load(fh)
        except Exception:
            self._last_report = None
