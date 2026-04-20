"""
Ultra-Low-Latency Execution Worker

Executes CopyOrders on client MT5 accounts with:
  - Slippage protection (reject if price drifts beyond threshold)
  - Exponential backoff retry (100ms, 200ms, 400ms)
  - Per-order latency tracking at every hop
  - Batch order dequeuing for throughput
  - Heartbeat reporting for health monitoring

Target: <50ms execution latency (dequeue → order_send result)
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Optional
import redis
import MetaTrader5 as mt5

from engine.config import get_engine_settings
from engine.models import CopyOrder, CopyStatus, TradeAction, TradeDirection
from engine.metrics import get_metrics
from engine.health_monitor import send_heartbeat
from engine.recovery_reasons import classify_mt5_error

settings = get_engine_settings()
logger = logging.getLogger("engine.executor")


class ExecutionWorker:
    """
    High-performance execution worker with slippage control and retry logic.

    Execution pipeline per order:
      dequeue → slippage check → order_send → latency calc → result publish
    """

    def __init__(self, client_mt5_id: str, login: int, password: str, server: str):
        self.client_mt5_id = client_mt5_id
        self.login = login
        self.password = password
        self.server = server
        self.running = False
        self.redis_client: Optional[redis.Redis] = None
        self._queue_key = f"copytrade:execute:{client_mt5_id}"
        self._result_channel = "copytrade:results"
        self.ticket_map: Dict[int, int] = {}  # master_ticket → client_ticket
        self._metrics = get_metrics()
        self._last_heartbeat = 0.0
        self._orders_processed = 0

    def connect(self) -> bool:
        if not mt5.initialize():
            logger.error(f"[{self.login}] MT5 init failed")
            return False
        if not mt5.login(self.login, password=self.password, server=self.server):
            logger.error(f"[{self.login}] MT5 login failed: {mt5.last_error()}")
            mt5.shutdown()
            return False
        logger.info(f"[{self.login}] Connected to {self.server}")
        return True

    def _check_slippage(self, order: CopyOrder) -> bool:
        """
        Check if current price has slipped beyond acceptable range.
        Returns True if order should proceed, False if slippage exceeded.
        """
        if not settings.SLIPPAGE_REJECT_ENABLED or order.master_price <= 0:
            return True

        tick = mt5.symbol_info_tick(order.symbol)
        if not tick:
            return True  # Can't check, let order_send handle it

        current_price = tick.ask if order.direction == TradeDirection.BUY else tick.bid

        # Get symbol point value for slippage calculation
        symbol_info = mt5.symbol_info(order.symbol)
        if not symbol_info:
            return True

        point = symbol_info.point
        if point <= 0:
            return True

        slippage_points = abs(current_price - order.master_price) / point
        order.slippage_points = slippage_points

        if slippage_points > order.max_slippage_points:
            logger.warning(
                f"[{self.login}] Slippage rejected: {order.symbol} "
                f"master={order.master_price} current={current_price} "
                f"slip={slippage_points:.1f}pts > max={order.max_slippage_points}"
            )
            return False

        return True

    def execute_open(self, order: CopyOrder) -> CopyOrder:
        """Execute market order with slippage protection."""
        # ── Slippage check ──
        if order.action == TradeAction.OPEN and not self._check_slippage(order):
            order.status = CopyStatus.SLIPPAGE_REJECTED
            order.error = f"Slippage {order.slippage_points:.1f}pts exceeds max {order.max_slippage_points}"
            return order

        order_type = mt5.ORDER_TYPE_BUY if order.direction == TradeDirection.BUY else mt5.ORDER_TYPE_SELL

        tick = mt5.symbol_info_tick(order.symbol)
        if not tick:
            order.status = CopyStatus.FAILED
            order.error = f"Symbol {order.symbol} not found"
            return order

        price = tick.ask if order.direction == TradeDirection.BUY else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": order.volume,
            "type": order_type,
            "price": price,
            "sl": order.sl or 0.0,
            "tp": order.tp or 0.0,
            "deviation": order.max_slippage_points,
            "magic": order.magic_number,
            "comment": f"CT:{order.master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        exec_start = time.time()
        result = mt5.order_send(request)
        exec_ms = (time.time() - exec_start) * 1000

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            order.status = CopyStatus.FAILED
            order.error = f"Order failed: {result.comment if result else 'no response'} (code: {result.retcode if result else 'N/A'})"
            logger.error(f"[{self.login}] OPEN failed: {order.error}")
        else:
            order.status = CopyStatus.EXECUTED
            order.executed_price = result.price
            self.ticket_map[order.master_ticket] = result.order

            # Calculate actual slippage
            if order.master_price > 0:
                symbol_info = mt5.symbol_info(order.symbol)
                if symbol_info and symbol_info.point > 0:
                    order.slippage_points = abs(result.price - order.master_price) / symbol_info.point

            logger.info(
                f"[{self.login}] OPEN {order.symbol} vol={order.volume} "
                f"ticket={result.order} exec={exec_ms:.1f}ms slip={order.slippage_points:.1f}pts"
            )

        return order

    def execute_close(self, order: CopyOrder) -> CopyOrder:
        """Close matching client position."""
        client_ticket = self.ticket_map.get(order.master_ticket)

        if not client_ticket:
            positions = mt5.positions_get(symbol=order.symbol)
            if positions:
                for pos in positions:
                    if f"CT:{order.master_ticket}" in (pos.comment or ""):
                        client_ticket = pos.ticket
                        break

        if not client_ticket:
            order.status = CopyStatus.SKIPPED
            order.error = "No matching client position"
            return order

        positions = mt5.positions_get(ticket=client_ticket)
        if not positions:
            order.status = CopyStatus.SKIPPED
            order.error = "Position already closed"
            return order

        position = positions[0]
        close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(order.symbol)
        price = tick.bid if position.type == 0 else tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order.symbol,
            "volume": position.volume,
            "type": close_type,
            "position": client_ticket,
            "price": price,
            "deviation": order.max_slippage_points,
            "magic": order.magic_number,
            "comment": f"CT:close:{order.master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        exec_start = time.time()
        result = mt5.order_send(request)
        exec_ms = (time.time() - exec_start) * 1000

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            order.status = CopyStatus.FAILED
            order.error = f"Close failed: {result.comment if result else 'N/A'}"
        else:
            order.status = CopyStatus.EXECUTED
            order.executed_price = result.price
            self.ticket_map.pop(order.master_ticket, None)
            logger.info(f"[{self.login}] CLOSE ticket={client_ticket} exec={exec_ms:.1f}ms")

        return order

    def execute_modify(self, order: CopyOrder) -> CopyOrder:
        """Modify SL/TP on client position."""
        client_ticket = self.ticket_map.get(order.master_ticket)
        if not client_ticket:
            order.status = CopyStatus.SKIPPED
            order.error = "No matching position to modify"
            return order

        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": order.symbol,
            "position": client_ticket,
            "sl": order.sl or 0.0,
            "tp": order.tp or 0.0,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            order.status = CopyStatus.FAILED
            order.error = f"Modify failed: {result.comment if result else 'N/A'}"
        else:
            order.status = CopyStatus.EXECUTED
            logger.info(f"[{self.login}] MODIFY ticket={client_ticket} sl={order.sl} tp={order.tp}")

        return order

    def process_order(self, order: CopyOrder) -> CopyOrder:
        """Execute order with exponential backoff retry."""
        order.dequeued_at = time.time()

        for attempt in range(1, order.max_attempts + 1):
            order.attempt = attempt
            order.status = CopyStatus.EXECUTING

            if order.action == TradeAction.OPEN:
                order = self.execute_open(order)
            elif order.action == TradeAction.CLOSE:
                order = self.execute_close(order)
            elif order.action == TradeAction.MODIFY:
                order = self.execute_modify(order)

            order.executed_at = time.time()

            if order.status in (CopyStatus.EXECUTED, CopyStatus.SKIPPED, CopyStatus.SLIPPAGE_REJECTED):
                break

            if attempt < order.max_attempts:
                # Exponential backoff: 100ms, 200ms, 400ms
                delay = (settings.RETRY_BASE_DELAY_MS * (2 ** (attempt - 1))) / 1000.0
                logger.warning(
                    f"[{self.login}] Retry {attempt}/{order.max_attempts} "
                    f"for {order.action.value} in {delay*1000:.0f}ms"
                )
                self._metrics.record_retry()
                time.sleep(delay)

        # Compute latencies
        order.result_at = time.time()
        order.compute_latencies()

        # Record metrics
        self._metrics.record_execution(
            success=order.status == CopyStatus.EXECUTED,
            total_latency_ms=order.latency_total_ms,
            execution_latency_ms=(order.executed_at - order.dequeued_at) * 1000 if order.dequeued_at else 0,
            dist_to_exec_ms=order.latency_distribute_to_execute_ms,
            symbol=order.symbol,
            slippage_points=order.slippage_points,
            slippage_rejected=order.status == CopyStatus.SLIPPAGE_REJECTED,
        )

        return order

    def _send_heartbeat(self):
        """Send heartbeat every 5 seconds."""
        now = time.time()
        if now - self._last_heartbeat < 5:
            return
        self._last_heartbeat = now
        send_heartbeat(self.redis_client, self.client_mt5_id, self.login, role="executor")

    def run(self):
        """Main loop: dequeue and execute orders."""
        self.redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            socket_keepalive=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
        )
        self.running = True

        if not self.connect():
            logger.error(f"[{self.login}] Worker cannot start")
            return

        self._metrics.set_gauges(workers=1)  # Increment would need atomic counter
        logger.info(f"[{self.login}] Execution worker started on {self._queue_key}")

        while self.running:
            try:
                self._send_heartbeat()

                # Check if trading is globally blocked (emergency stop)
                if self.redis_client.exists("copytrade:trading_blocked"):
                    time.sleep(2)
                    continue

                # Blocking pop with short timeout for responsiveness
                result = self.redis_client.brpop(self._queue_key, timeout=2)
                if result is None:
                    continue

                _, raw = result
                order = CopyOrder.from_json(raw)
                order = self.process_order(order)
                self._orders_processed += 1

                # Push to dead letter queue if failed after all retries
                if order.status == CopyStatus.FAILED:
                    try:
                        dlq_entry = order.to_json()
                        pipe = self.redis_client.pipeline(transaction=False)
                        pipe.lpush("copytrade:dead_letter", dlq_entry)
                        pipe.ltrim("copytrade:dead_letter", 0, 9999)
                        pipe.execute()
                        logger.warning(f"[{self.login}] Order {order.order_id[:8]} moved to dead letter queue")
                    except Exception as dlq_err:
                        logger.error(f"[{self.login}] Failed to push to DLQ: {dlq_err}")

                # Publish result
                result_json = order.to_json()
                pipe = self.redis_client.pipeline(transaction=False)
                pipe.publish(self._result_channel, result_json)
                pipe.lpush(f"copytrade:results:{self.client_mt5_id}", result_json)
                pipe.ltrim(f"copytrade:results:{self.client_mt5_id}", 0, 999)
                pipe.execute()

                if order.latency_total_ms > 0:
                    logger.info(
                        f"[{self.login}] Order {order.order_id[:8]} "
                        f"status={order.status.value} "
                        f"total={order.latency_total_ms:.1f}ms "
                        f"slip={order.slippage_points:.1f}pts"
                    )

            except redis.ConnectionError:
                logger.error(f"[{self.login}] Redis connection lost, reconnecting...")
                time.sleep(1)
                try:
                    self.redis_client = redis.Redis.from_url(settings.REDIS_URL)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"[{self.login}] Worker error: {e}", exc_info=True)
                time.sleep(0.5)

    def stop(self):
        self.running = False
        try:
            mt5.shutdown()
        except Exception:
            pass
        logger.info(f"[{self.login}] Worker stopped ({self._orders_processed} orders processed)")
