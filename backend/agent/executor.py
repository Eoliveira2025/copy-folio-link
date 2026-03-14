"""
Execution Worker — executes CopyOrders on client MT5 accounts.

Each client account runs its own worker in a subprocess.
Features:
  - Slippage protection
  - Exponential backoff retry
  - Dead letter queue for failed orders
  - Result publishing for audit trail
"""

from __future__ import annotations
import time
import logging
import json
from typing import Dict, Optional
import redis
import MetaTrader5 as mt5

from agent.config import get_agent_settings

settings = get_agent_settings()

try:
    import orjson
    def _dumps(d: dict) -> str:
        return orjson.dumps(d).decode()
    def _loads(s) -> dict:
        return orjson.loads(s)
except ImportError:
    _dumps = json.dumps
    _loads = json.loads


def executor_process(client_id: str, login: int, password: str, server: str):
    """
    Subprocess entry point: connects to a client MT5 account,
    dequeues CopyOrders from Redis, executes them.
    """
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format=f"%(asctime)s.%(msecs)03d [Exec-{login}] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger(f"executor.{login}")

    # Connect to MT5
    if not mt5.initialize(path=settings.MT5_TERMINAL_PATH):
        log.error(f"MT5 initialize failed: {mt5.last_error()}")
        return

    if not mt5.login(login, password=password, server=server):
        log.error(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return

    info = mt5.account_info()
    if info:
        log.info(f"Connected — Balance: {info.balance}, Server: {info.server}")

    # Connect to Redis
    redis_client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_keepalive=True,
        socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
    )

    queue_key = f"copytrade:execute:{client_id}"
    result_channel = "copytrade:results"
    ticket_map: Dict[int, int] = {}  # master_ticket → client_ticket
    orders_processed = 0

    log.info(f"Execution worker started, listening on {queue_key}")

    while True:
        try:
            # Check if trading is globally blocked (emergency stop)
            if redis_client.exists("copytrade:trading_blocked"):
                time.sleep(2)
                continue

            # Blocking pop with short timeout
            result = redis_client.brpop(queue_key, timeout=2)
            if result is None:
                # Periodic heartbeat
                redis_client.set(
                    f"copytrade:health:heartbeat:{client_id}",
                    _dumps({
                        "account_id": client_id,
                        "login": login,
                        "role": "executor",
                        "timestamp": time.time(),
                    }),
                    ex=settings.HEARTBEAT_TTL_S * 2,
                )
                continue

            _, raw = result
            order = _loads(raw)
            order["dequeued_at"] = time.time()

            # Execute with retry
            action = order.get("action", "open")

            for attempt in range(1, order.get("max_attempts", 3) + 1):
                order["attempt"] = attempt

                if action == "open":
                    order = _execute_open(order, ticket_map, log)
                elif action == "close":
                    order = _execute_close(order, ticket_map, log)
                elif action == "modify":
                    order = _execute_modify(order, ticket_map, log)

                order["executed_at"] = time.time()

                if order["status"] in ("executed", "skipped", "slippage_rejected"):
                    break

                if attempt < order.get("max_attempts", 3):
                    delay = (settings.RETRY_BASE_DELAY_MS * (2 ** (attempt - 1))) / 1000.0
                    log.warning(f"Retry {attempt}/{order['max_attempts']} in {delay*1000:.0f}ms")
                    time.sleep(delay)

            # Compute total latency
            detected_at = order.get("event_detected_at", 0)
            executed_at = order.get("executed_at", 0)
            if detected_at and executed_at:
                order["latency_total_ms"] = (executed_at - detected_at) * 1000
            else:
                order["latency_total_ms"] = 0

            order["result_at"] = time.time()
            orders_processed += 1

            # Push to DLQ if failed
            if order["status"] == "failed":
                try:
                    pipe = redis_client.pipeline(transaction=False)
                    pipe.lpush("copytrade:dead_letter", _dumps(order))
                    pipe.ltrim("copytrade:dead_letter", 0, 9999)
                    pipe.execute()
                    log.warning(f"Order {order['order_id'][:8]} → dead letter queue")
                except Exception as dlq_err:
                    log.error(f"DLQ push failed: {dlq_err}")

            # Publish result
            result_json = _dumps(order)
            pipe = redis_client.pipeline(transaction=False)
            pipe.publish(result_channel, result_json)
            pipe.lpush(f"copytrade:results:{client_id}", result_json)
            pipe.ltrim(f"copytrade:results:{client_id}", 0, 999)
            pipe.execute()

            if order.get("latency_total_ms", 0) > 0:
                log.info(
                    f"Order {order['order_id'][:8]} {order['status']} "
                    f"total={order['latency_total_ms']:.1f}ms "
                    f"slip={order.get('slippage_points', 0):.1f}pts"
                )

        except redis.ConnectionError:
            log.error("Redis connection lost, reconnecting...")
            time.sleep(1)
            try:
                redis_client = redis.Redis.from_url(settings.REDIS_URL)
            except Exception:
                pass
        except Exception as e:
            log.error(f"Worker error: {e}", exc_info=True)
            time.sleep(0.5)


def _execute_open(order: dict, ticket_map: Dict[int, int], log) -> dict:
    """Execute market order with slippage protection."""
    symbol = order["symbol"]

    # Slippage check
    if settings.SLIPPAGE_REJECT_ENABLED and order.get("master_price", 0) > 0:
        tick = mt5.symbol_info_tick(symbol)
        if tick:
            direction = order["direction"]
            current_price = tick.ask if direction == "BUY" else tick.bid
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info and symbol_info.point > 0:
                slippage = abs(current_price - order["master_price"]) / symbol_info.point
                order["slippage_points"] = slippage
                if slippage > order.get("max_slippage_points", 30):
                    order["status"] = "slippage_rejected"
                    order["error"] = f"Slippage {slippage:.1f}pts > max {order['max_slippage_points']}"
                    log.warning(f"Slippage rejected: {symbol} slip={slippage:.1f}pts")
                    return order

    order_type = mt5.ORDER_TYPE_BUY if order["direction"] == "BUY" else mt5.ORDER_TYPE_SELL

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        order["status"] = "failed"
        order["error"] = f"Symbol {symbol} not found"
        return order

    price = tick.ask if order["direction"] == "BUY" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": order["volume"],
        "type": order_type,
        "price": price,
        "sl": order.get("sl") or 0.0,
        "tp": order.get("tp") or 0.0,
        "deviation": order.get("max_slippage_points", 30),
        "magic": order.get("magic_number", 123456),
        "comment": f"CT:{order['master_ticket']}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    exec_start = time.time()
    result = mt5.order_send(request)
    exec_ms = (time.time() - exec_start) * 1000

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        order["status"] = "failed"
        order["error"] = f"Order failed: {result.comment if result else 'no response'} (code: {result.retcode if result else 'N/A'})"
        log.error(f"OPEN failed: {order['error']}")
    else:
        order["status"] = "executed"
        order["executed_price"] = result.price
        ticket_map[order["master_ticket"]] = result.order

        # Calculate actual slippage
        if order.get("master_price", 0) > 0:
            si = mt5.symbol_info(symbol)
            if si and si.point > 0:
                order["slippage_points"] = abs(result.price - order["master_price"]) / si.point

        log.info(
            f"OPEN {symbol} vol={order['volume']} ticket={result.order} "
            f"exec={exec_ms:.1f}ms slip={order.get('slippage_points', 0):.1f}pts"
        )

    return order


def _execute_close(order: dict, ticket_map: Dict[int, int], log) -> dict:
    """Close matching client position."""
    master_ticket = order["master_ticket"]
    client_ticket = ticket_map.get(master_ticket)

    if not client_ticket:
        positions = mt5.positions_get(symbol=order["symbol"])
        if positions:
            for pos in positions:
                if f"CT:{master_ticket}" in (pos.comment or ""):
                    client_ticket = pos.ticket
                    break

    if not client_ticket:
        order["status"] = "skipped"
        order["error"] = "No matching client position"
        return order

    positions = mt5.positions_get(ticket=client_ticket)
    if not positions:
        order["status"] = "skipped"
        order["error"] = "Position already closed"
        return order

    position = positions[0]
    close_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
    tick = mt5.symbol_info_tick(order["symbol"])
    price = tick.bid if position.type == 0 else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": order["symbol"],
        "volume": position.volume,
        "type": close_type,
        "position": client_ticket,
        "price": price,
        "deviation": order.get("max_slippage_points", 30),
        "magic": order.get("magic_number", 123456),
        "comment": f"CT:close:{master_ticket}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        order["status"] = "failed"
        order["error"] = f"Close failed: {result.comment if result else 'N/A'}"
    else:
        order["status"] = "executed"
        order["executed_price"] = result.price
        ticket_map.pop(master_ticket, None)
        log.info(f"CLOSE ticket={client_ticket}")

    return order


def _execute_modify(order: dict, ticket_map: Dict[int, int], log) -> dict:
    """Modify SL/TP on client position."""
    client_ticket = ticket_map.get(order["master_ticket"])
    if not client_ticket:
        order["status"] = "skipped"
        order["error"] = "No matching position to modify"
        return order

    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "symbol": order["symbol"],
        "position": client_ticket,
        "sl": order.get("sl") or 0.0,
        "tp": order.get("tp") or 0.0,
    }

    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        order["status"] = "failed"
        order["error"] = f"Modify failed: {result.comment if result else 'N/A'}"
    else:
        order["status"] = "executed"
        log.info(f"MODIFY ticket={client_ticket} sl={order.get('sl')} tp={order.get('tp')}")

    return order
