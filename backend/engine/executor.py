"""
Execution Worker — pops CopyOrders from a client's Redis queue and
executes them on the client's MT5 terminal.

Each worker manages one MT5 connection (one process per client account).
The worker pool spawns these as subprocesses.
"""

from __future__ import annotations
import time
import logging
from typing import Dict, Optional
import redis
import MetaTrader5 as mt5

from engine.config import get_engine_settings
from engine.models import CopyOrder, CopyStatus, TradeAction, TradeDirection

settings = get_engine_settings()
logger = logging.getLogger("engine.executor")


class ExecutionWorker:
    """
    Connects to a client MT5 account and processes CopyOrders from its Redis queue.
    Maintains a mapping of master_ticket → client_ticket for close/modify operations.
    """

    def __init__(self, client_mt5_id: str, login: int, password: str, server: str):
        self.client_mt5_id = client_mt5_id
        self.login = login
        self.password = password
        self.server = server
        self.running = False
        self.redis_client: Optional[redis.Redis] = None
        self._queue_key = f"copytrade:execute:{client_mt5_id}"
        self._result_key = f"copytrade:results:{client_mt5_id}"
        # master_ticket → client_ticket mapping
        self.ticket_map: Dict[int, int] = {}

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

    def execute_open(self, order: CopyOrder) -> CopyOrder:
        """Send a market order to open a position."""
        order_type = mt5.ORDER_TYPE_BUY if order.direction == TradeDirection.BUY else mt5.ORDER_TYPE_SELL

        # Get current price
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
            "deviation": 20,  # slippage in points
            "magic": 123456,  # EA magic number for identification
            "comment": f"CT:{order.master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        start = time.time()
        result = mt5.order_send(request)
        latency_ms = int((time.time() - start) * 1000)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            order.status = CopyStatus.FAILED
            order.error = f"Order failed: {result.comment if result else 'no response'} (code: {result.retcode if result else 'N/A'})"
            logger.error(f"[{self.login}] OPEN failed: {order.error}")
        else:
            order.status = CopyStatus.EXECUTED
            # Map master ticket to client ticket for future close/modify
            self.ticket_map[order.master_ticket] = result.order
            logger.info(f"[{self.login}] OPEN executed: {order.symbol} vol={order.volume} ticket={result.order} latency={latency_ms}ms")

        return order

    def execute_close(self, order: CopyOrder) -> CopyOrder:
        """Close the client position that corresponds to a master ticket."""
        client_ticket = self.ticket_map.get(order.master_ticket)

        if not client_ticket:
            # Try to find by comment
            positions = mt5.positions_get(symbol=order.symbol)
            if positions:
                for pos in positions:
                    if f"CT:{order.master_ticket}" in (pos.comment or ""):
                        client_ticket = pos.ticket
                        break

        if not client_ticket:
            order.status = CopyStatus.SKIPPED
            order.error = "No matching client position found"
            logger.warning(f"[{self.login}] CLOSE skipped: no position for master ticket {order.master_ticket}")
            return order

        # Get position details
        position = None
        positions = mt5.positions_get(ticket=client_ticket)
        if positions:
            position = positions[0]

        if not position:
            order.status = CopyStatus.SKIPPED
            order.error = "Position already closed"
            return order

        # Determine close direction (opposite of position)
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
            "deviation": 20,
            "magic": 123456,
            "comment": f"CT:close:{order.master_ticket}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)

        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            order.status = CopyStatus.FAILED
            order.error = f"Close failed: {result.comment if result else 'N/A'}"
        else:
            order.status = CopyStatus.EXECUTED
            self.ticket_map.pop(order.master_ticket, None)
            logger.info(f"[{self.login}] CLOSE executed: ticket={client_ticket}")

        return order

    def execute_modify(self, order: CopyOrder) -> CopyOrder:
        """Modify SL/TP on the client position."""
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
            logger.info(f"[{self.login}] MODIFY executed: ticket={client_ticket} sl={order.sl} tp={order.tp}")

        return order

    def process_order(self, order: CopyOrder) -> CopyOrder:
        """Route order to the correct execution method with retry logic."""
        for attempt in range(1, settings.MAX_RETRY_ATTEMPTS + 1):
            order.attempt = attempt
            order.status = CopyStatus.EXECUTING

            if order.action == TradeAction.OPEN:
                order = self.execute_open(order)
            elif order.action == TradeAction.CLOSE:
                order = self.execute_close(order)
            elif order.action == TradeAction.MODIFY:
                order = self.execute_modify(order)

            if order.status == CopyStatus.EXECUTED:
                break

            if attempt < settings.MAX_RETRY_ATTEMPTS:
                logger.warning(f"[{self.login}] Retry {attempt}/{settings.MAX_RETRY_ATTEMPTS} for {order.action.value}")
                time.sleep(settings.RETRY_DELAY_MS / 1000.0)

        return order

    def run(self):
        """Main loop: pop orders from Redis queue and execute."""
        self.redis_client = redis.from_url(settings.REDIS_URL)
        self.running = True

        if not self.connect():
            logger.error(f"[{self.login}] Worker cannot start")
            return

        logger.info(f"[{self.login}] Execution worker started, listening on {self._queue_key}")

        while self.running:
            try:
                # Blocking pop with 5s timeout
                result = self.redis_client.brpop(self._queue_key, timeout=5)

                if result is None:
                    continue  # Timeout, loop again

                _, raw = result
                order = CopyOrder.from_json(raw)
                order = self.process_order(order)

                # Push result for tracking
                self.redis_client.lpush(self._result_key, order.to_json())

                # Publish result for real-time dashboard updates
                self.redis_client.publish(
                    f"copytrade:results",
                    order.to_json()
                )

            except Exception as e:
                logger.error(f"[{self.login}] Worker error: {e}", exc_info=True)
                time.sleep(1)

    def stop(self):
        self.running = False
        mt5.shutdown()
        logger.info(f"[{self.login}] Worker stopped")
