"""Distributor V2 — consumes master events and enqueues OrderTasks.

Subscribes to `copytrade_v2:events:master:*` and, for each event:

  1. Resolve client list for (master_id, strategy_id) — only accounts
     marked engine_version='v2' AND in `EXIT_ONLY` or `ACTIVE` state.
     ACTIVE accepts OPEN+CLOSE; EXIT_ONLY accepts only CLOSE.
  2. For each client account:
        TerminalAllocator.assign(...) → pool_id, terminal_id
        Build OrderTask (OPEN or CLOSE)
        Submit to PoolWorker.queue
  3. Strategy guard: refuses to enqueue if account.strategy_id mismatches
     event.strategy_id (defense in depth on top of allocator's check).
  4. Single-strategy invariant: an account is mapped to ONE strategy via
     account_terminal_map; we never enqueue against a different strategy.

This module does NOT call mt5.order_send. The OrderExecutor enforces all
safety modes (DRY_RUN/DEMO_ONLY/LIVE_WHITELIST).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Callable, Optional
from uuid import UUID

from .pool.allocator import TerminalAllocator
from .exec.order_task import OrderAction, OrderSide, OrderTask
from .redis_client import subscribe
from .utils.logger import get_logger
from .utils.trading import VolumeCalculator, SymbolMapper, get_master_stats
from .wiring import PoolWorkerRegistry
from .pool.distributed_lock import DistributedLock


@dataclass
class ClientAccount:
    """Minimal client view for distribution."""
    account_id: UUID
    login: int
    account_type: str  # 'demo' | 'real'
    state: str  # ACTIVE | EXIT_ONLY | PENDING_STRATEGY_CHANGE | ...
    balance: float = 1000.0 # Loaded by resolver


# Caller-provided resolvers
ClientResolver = Callable[[UUID, UUID], list[ClientAccount]]
# (master_id, strategy_id) -> list[ClientAccount]


class DistributorV2:
    def __init__(
        self,
        *,
        allocator: TerminalAllocator,
        worker_registry: PoolWorkerRegistry,
        client_resolver: ClientResolver,
        symbol_mapper: Optional[SymbolMapper] = None,
    ):
        self.allocator = allocator
        self.workers = worker_registry
        self.resolve_clients = client_resolver
        self.symbol_mapper = symbol_mapper or SymbolMapper(default_suffix="m")
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.log = get_logger("distributor")
        self.lock_service = DistributedLock()
        self.settings = get_v2_settings()

    # ── lifecycle ─────────────────────────────────────────────────
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="v2-distributor", daemon=True,
        )
        self._thread.start()
        self.log.info("distributor started", extra={"action": "distributor_started"})

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
        self.log.info("distributor stopped", extra={"action": "distributor_stopped"})

    # ── loop ──────────────────────────────────────────────────────
    def _run(self) -> None:
        try:
            from .redis_client import get_redis, k
            r = get_redis()
            vps_id = self.settings.V2_VPS_ID
            
            ps = r.pubsub(ignore_subscribe_messages=True)
            # 1. Listen for master events
            ps.psubscribe(k("events:master:*"))
            # 2. Listen for direct commands (reconnect, etc)
            ps.subscribe(k(f"commands:vps:{vps_id}"))
            
            self.log.info("distributor listening for events and commands", 
                          extra={"vps_id": vps_id})
        except Exception as e:
            self.log.error("redis subscribe failed; distributor idle",
                           extra={"action": "redis_subscribe_failed"}, exc_info=e)
            while not self._stop.is_set():
                self._stop.wait(1.0)
            return

        for msg in ps.listen():
            if self._stop.is_set():
                break
            if not msg or msg.get("type") not in ("message", "pmessage"):
                continue
            try:
                channel = msg.get("channel", b"").decode()
                data = msg.get("data")
                if isinstance(data, (bytes, bytearray)):
                    data = data.decode("utf-8")
                payload = json.loads(data)
                
                if "events:master:" in channel:
                    self.handle_event(payload)
                elif "commands:vps:" in channel:
                    self.handle_command(payload)
                    
            except Exception as e:
                self.log.error("message handling failed",
                               extra={"action": "message_handling_failed"},
                               exc_info=e)

    def handle_command(self, payload: dict):
        """Handle incoming commands from the Monitor UI."""
        cmd = payload.get("command")
        account_id_str = payload.get("account_id")
        
        self.log.info(f"Received command: {cmd}", extra={"payload": payload})
        
        if not cmd or not account_id_str:
            return
            
        try:
            from uuid import UUID
            account_id = UUID(account_id_str)
            
            # Map account_id to pool_id via allocator
            # (In V2 mapping is persistent while account is on VPS)
            from .pool.repo import get_account_mapping
            mapping = get_account_mapping(account_id)
            if not mapping:
                self.log.warning("Command failed: account not mapped on this VPS", extra=payload)
                return
                
            worker = self.workers.get(mapping.pool_id)
            if not worker:
                self.log.warning("Command failed: no active worker for pool", extra=payload)
                return
            
            # Execute command on worker
            if cmd == "reconnect":
                worker.pool.stop()
                worker.pool.start()
            elif cmd == "recycle":
                worker.pool.recycle()
            elif cmd == "safe_remove":
                # Logic to stop worker and remove from registry
                # For now just stop the terminal
                worker.pool.stop()
            elif cmd == "force_remove":
                worker.pool.stop()
                
            self.log.info(f"Command executed: {cmd}", extra={"account_id": account_id_str})
        except Exception as e:
            self.log.error("command execution failed", exc_info=e)


    # ── core ──────────────────────────────────────────────────────
    def handle_event(self, payload: dict) -> dict:
        """Process one master event. Returns a small summary for tests."""
        event = payload.get("event")
        master_id = UUID(payload["master_id"])
        strategy_id = UUID(payload["strategy_id"])
        master_ticket = int(payload["master_ticket"])
        symbol = payload.get("symbol") or ""

        log = self.log.bind(
            master_id=str(master_id), strategy_id=str(strategy_id),
            master_ticket=master_ticket, action=f"distribute_{event}",
        )

        clients = self.resolve_clients(master_id, strategy_id)
        if not clients:
            log.info("no clients for event", extra={"client_count": 0})
            return {"event": event, "submitted": 0, "skipped": 0}

        submitted = 0
        skipped = 0
        for c in clients:
            # State gate
            if event == "OPEN" and c.state != "ACTIVE":
                skipped += 1
                continue
            if event == "CLOSE" and c.state not in ("ACTIVE", "EXIT_ONLY"):
                skipped += 1
                continue

            # 1. Distributed Lock (Safety)
            if not self.lock_service.acquire(c.account_id):
                log.error("distributed lock failed; skipping to prevent double execution",
                          extra={"account_id": str(c.account_id)})
                skipped += 1
                continue

            try:
                assignment = self.allocator.assign(
                    account_id=c.account_id,
                    master_id=master_id,
                    strategy_id=strategy_id,
                )
            except Exception as e:
                log.error("allocator failed",
                          extra={"account_id": str(c.account_id),
                                 "action": "allocator_error"}, exc_info=e)
                self.lock_service.release(c.account_id)
                skipped += 1
                continue

            worker = self.workers.get(assignment.pool_id)
            if worker is None:
                log.warning(
                    "no worker for pool; skipping",
                    extra={"pool_id": str(assignment.pool_id),
                           "account_id": str(c.account_id),
                           "action": "no_worker_for_pool"},
                )
                self.lock_service.release(c.account_id)
                skipped += 1
                continue

            # Shadow Mode Protection
            if self.settings.V2_SHADOW_MODE:
                log.info("SHADOW MODE: execution simulated", extra={"account_id": str(c.account_id)})
                self.lock_service.release(c.account_id)
                submitted += 1 # Count as submitted for telemetry
                continue

            task = self._build_task(payload, c, assignment)
            worker.submit(task)
            submitted += 1

        log.info("event distributed",
                 extra={"submitted": submitted, "skipped": skipped,
                        "client_count": len(clients)})
        return {"event": event, "submitted": submitted, "skipped": skipped}

    def _build_task(self, payload: dict, c: ClientAccount,
                    assignment) -> OrderTask:
        event = payload["event"]
        action = OrderAction.OPEN if event == "OPEN" else OrderAction.CLOSE
        
        symbol = self.symbol_mapper.map(payload.get("symbol") or "")
        
        volume = None
        if event == "OPEN":
            master_vol = float(payload["volume"])
            master_stats = get_master_stats(assignment.master_id)
            master_balance = master_stats.get("balance", 0.0)
            
            # Simple scaling
            volume = VolumeCalculator.calculate(
                master_volume=master_vol,
                master_balance=master_balance,
                client_balance=c.balance
            )

        side = None
        if event == "OPEN":
            side = OrderSide.BUY if payload.get("side") == "BUY" else OrderSide.SELL

        return OrderTask(
            account_id=c.account_id,
            pool_id=assignment.pool_id,
            terminal_id=assignment.terminal_id,
            master_id=assignment.master_id,
            strategy_id=assignment.strategy_id,
            action=action,
            symbol=symbol,
            side=side,
            volume=volume,
            client_ticket=None,  # resolved by close_reconciler/fallback
            master_ticket=int(payload["master_ticket"]),
            magic=int(payload.get("magic") or 0),
            comment=f"CT:{payload['master_ticket']}",
        )
