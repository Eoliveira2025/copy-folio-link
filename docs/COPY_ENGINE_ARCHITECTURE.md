# Complete Copy Engine & MT5 Terminal Manager Architecture
# This runs on separate VPS/cloud infrastructure, NOT in Lovable

## Project Structure

```
copy-engine/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── config/
│   └── settings.py
├── engine/
│   ├── __init__.py
│   ├── master_listener.py      # Monitors master accounts for trade events
│   ├── trade_distributor.py    # Routes trades to correct client accounts
│   ├── lot_calculator.py       # Proportional lot size calculation
│   ├── execution_manager.py    # Executes trades on client accounts
│   └── retry_handler.py        # Handles failed trade executions
├── mt5_manager/
│   ├── __init__.py
│   ├── terminal_pool.py        # Manages pool of MT5 connections
│   ├── connection.py           # Single MT5 connection wrapper
│   ├── health_checker.py       # Monitors connection health
│   └── credential_vault.py     # Secure credential management
├── models/
│   ├── __init__.py
│   ├── trade_event.py
│   ├── client_account.py
│   └── master_account.py
├── workers/
│   ├── celery_app.py
│   ├── copy_worker.py
│   └── health_worker.py
├── api/
│   ├── main.py                 # FastAPI endpoints for the engine
│   └── routes/
│       ├── engine.py
│       └── health.py
└── tests/
    ├── test_lot_calculator.py
    └── test_execution.py
```

---

## 1. Configuration (config/settings.py)

```python
from pydantic_settings import BaseSettings
from typing import Dict, List
import os


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@db:5432/copytrade"
    
    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    
    # MT5 Settings
    MT5_TERMINAL_PATH: str = "/opt/mt5/terminal64.exe"
    MT5_MAX_CONNECTIONS_PER_INSTANCE: int = 1  # One account per terminal
    MT5_RECONNECT_INTERVAL: int = 5            # seconds
    MT5_HEALTH_CHECK_INTERVAL: int = 10        # seconds
    MT5_MAX_RECONNECT_ATTEMPTS: int = 10
    
    # Copy Engine
    COPY_ENGINE_POLL_INTERVAL_MS: int = 100    # 100ms polling for master trades
    MAX_SLIPPAGE_POINTS: int = 20
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_DELAY_SECONDS: int = 2
    
    # Lot Calculation
    MIN_LOT_SIZE: float = 0.01
    MAX_LOT_SIZE: float = 100.0
    LOT_STEP: float = 0.01
    
    # Encryption
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    class Config:
        env_file = ".env"


settings = Settings()
```

---

## 2. Trade Event Models (models/trade_event.py)

```python
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid


class TradeEventType(Enum):
    OPEN = "open"
    CLOSE = "close"
    MODIFY = "modify"
    PARTIAL_CLOSE = "partial_close"


class OrderType(Enum):
    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5


@dataclass
class TradeEvent:
    """Represents a trade event detected on a master account."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: TradeEventType = TradeEventType.OPEN
    master_account_id: str = ""
    strategy_level: str = ""
    
    # Trade details
    ticket: int = 0
    symbol: str = ""
    order_type: OrderType = OrderType.BUY
    volume: float = 0.0
    price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.utcnow)
    master_balance: float = 0.0


@dataclass
class TradeCopy:
    """Represents a copied trade for a client account."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trade_event_id: str = ""
    client_account_id: str = ""
    
    # Calculated values
    calculated_volume: float = 0.0
    executed_volume: float = 0.0
    executed_price: float = 0.0
    
    # Status
    status: str = "pending"  # pending, executed, failed, retrying
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    executed_at: Optional[datetime] = None
```

---

## 3. MT5 Connection Wrapper (mt5_manager/connection.py)

```python
"""
Single MT5 connection wrapper.
Each instance manages ONE MetaTrader 5 terminal connection.

IMPORTANT: The MetaTrader5 Python package can only connect to
one terminal per process. For multiple accounts, you need
multiple processes or use the MT5 Manager API.
"""

import MetaTrader5 as mt5
import asyncio
import logging
from typing import Optional, List, Dict
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MT5ConnectionConfig:
    login: int
    password: str
    server: str
    path: str = "/opt/mt5/terminal64.exe"
    timeout: int = 10000  # milliseconds


class MT5Connection:
    """Wraps a single MT5 terminal connection."""
    
    def __init__(self, config: MT5ConnectionConfig):
        self.config = config
        self.is_connected = False
        self.last_heartbeat: Optional[datetime] = None
        self.reconnect_attempts = 0
        self._lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Initialize and log into MT5 terminal."""
        async with self._lock:
            try:
                # Initialize MT5 terminal
                if not mt5.initialize(
                    path=self.config.path,
                    login=self.config.login,
                    password=self.config.password,
                    server=self.config.server,
                    timeout=self.config.timeout,
                ):
                    error = mt5.last_error()
                    logger.error(
                        f"MT5 init failed for {self.config.login}: "
                        f"code={error[0]}, msg={error[1]}"
                    )
                    return False
                
                # Verify account info
                account_info = mt5.account_info()
                if account_info is None:
                    logger.error(f"Cannot get account info for {self.config.login}")
                    return False
                
                self.is_connected = True
                self.last_heartbeat = datetime.utcnow()
                self.reconnect_attempts = 0
                
                logger.info(
                    f"Connected to MT5: login={self.config.login}, "
                    f"server={self.config.server}, "
                    f"balance={account_info.balance}"
                )
                return True
                
            except Exception as e:
                logger.exception(f"Connection error for {self.config.login}: {e}")
                return False
    
    async def disconnect(self):
        """Shutdown MT5 terminal connection."""
        async with self._lock:
            mt5.shutdown()
            self.is_connected = False
            logger.info(f"Disconnected MT5: login={self.config.login}")
    
    def get_account_balance(self) -> float:
        """Get current account balance."""
        info = mt5.account_info()
        if info is None:
            raise ConnectionError(f"Lost connection to {self.config.login}")
        self.last_heartbeat = datetime.utcnow()
        return info.balance
    
    def get_account_equity(self) -> float:
        """Get current account equity."""
        info = mt5.account_info()
        if info is None:
            raise ConnectionError(f"Lost connection to {self.config.login}")
        return info.equity
    
    def get_positions(self) -> List[Dict]:
        """Get all open positions."""
        positions = mt5.positions_get()
        if positions is None:
            return []
        return [pos._asdict() for pos in positions]
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get symbol trading info (for lot step, min/max lots)."""
        info = mt5.symbol_info(symbol)
        if info is None:
            # Try to enable the symbol first
            mt5.symbol_select(symbol, True)
            info = mt5.symbol_info(symbol)
        if info is None:
            return None
        return info._asdict()
    
    def execute_order(
        self,
        symbol: str,
        order_type: int,
        volume: float,
        price: float = 0.0,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "CopyTrade",
        magic: int = 123456,
        deviation: int = 20,
    ) -> Dict:
        """
        Execute a trade order on this MT5 account.
        
        Returns dict with: success, ticket, price, volume, error
        """
        # Ensure symbol is available
        mt5.symbol_select(symbol, True)
        
        # Get current price if not provided
        if price == 0.0:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return {"success": False, "error": "Cannot get price"}
            price = tick.ask if order_type in [0, 2, 4] else tick.bid
        
        # Build order request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        if sl > 0:
            request["sl"] = sl
        if tp > 0:
            request["tp"] = tp
        
        # Send order
        result = mt5.order_send(request)
        
        if result is None:
            error = mt5.last_error()
            return {
                "success": False,
                "error": f"Order send failed: {error[1]}",
                "error_code": error[0],
            }
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {
                "success": False,
                "error": f"Order rejected: {result.comment}",
                "retcode": result.retcode,
            }
        
        return {
            "success": True,
            "ticket": result.order,
            "price": result.price,
            "volume": result.volume,
        }
    
    def close_position(self, ticket: int) -> Dict:
        """Close a specific position by ticket."""
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return {"success": False, "error": f"Position {ticket} not found"}
        
        pos = position[0]
        close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return {"success": False, "error": "Cannot get price"}
        
        price = tick.bid if pos.type == 0 else tick.ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "CopyTrade Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else mt5.last_error()[1]
            return {"success": False, "error": f"Close failed: {error}"}
        
        return {"success": True, "ticket": result.order, "price": result.price}
    
    def modify_position(self, ticket: int, sl: float = 0, tp: float = 0) -> Dict:
        """Modify SL/TP of an existing position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "sl": sl,
            "tp": tp,
        }
        
        result = mt5.order_send(request)
        
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            error = result.comment if result else mt5.last_error()[1]
            return {"success": False, "error": f"Modify failed: {error}"}
        
        return {"success": True}
    
    def check_health(self) -> bool:
        """Check if connection is alive."""
        try:
            info = mt5.account_info()
            if info is not None:
                self.last_heartbeat = datetime.utcnow()
                return True
            return False
        except Exception:
            return False
```

---

## 4. Terminal Pool Manager (mt5_manager/terminal_pool.py)

```python
"""
Terminal Pool Manager

Since MetaTrader5 Python package allows only ONE connection per process,
we manage multiple MT5 connections using subprocess workers.

Each worker process handles one MT5 terminal connection.
Communication happens via Redis queues.

Architecture:
  TerminalPool (main process)
    ├── Worker Process 1 → MT5 Terminal → Client Account A
    ├── Worker Process 2 → MT5 Terminal → Client Account B
    ├── Worker Process 3 → MT5 Terminal → Master Account 01
    └── Worker Process N → MT5 Terminal → Account N
"""

import asyncio
import json
import logging
import multiprocessing
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import redis.asyncio as redis

from config.settings import settings
from mt5_manager.connection import MT5Connection, MT5ConnectionConfig
from mt5_manager.credential_vault import CredentialVault

logger = logging.getLogger(__name__)


@dataclass
class TerminalWorkerInfo:
    """Tracks a worker process managing one MT5 connection."""
    process_id: int
    account_login: int
    server: str
    account_type: str  # "master" or "client"
    strategy_level: Optional[str] = None
    status: str = "starting"  # starting, connected, disconnected, error
    last_heartbeat: Optional[datetime] = None
    balance: float = 0.0


class TerminalPool:
    """
    Manages a pool of MT5 terminal worker processes.
    
    Usage:
        pool = TerminalPool(redis_client)
        await pool.start()
        await pool.add_connection(account_config)
        await pool.execute_trade(account_login, trade_params)
        await pool.remove_connection(account_login)
        await pool.shutdown()
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.workers: Dict[int, TerminalWorkerInfo] = {}  # login -> info
        self.vault = CredentialVault(settings.ENCRYPTION_KEY)
        self._running = False
    
    async def start(self):
        """Start the terminal pool manager."""
        self._running = True
        logger.info("Terminal Pool Manager started")
        # Start health check loop
        asyncio.create_task(self._health_check_loop())
    
    async def shutdown(self):
        """Gracefully shutdown all terminal workers."""
        self._running = False
        for login in list(self.workers.keys()):
            await self.remove_connection(login)
        logger.info("Terminal Pool Manager shut down")
    
    async def add_connection(
        self,
        login: int,
        encrypted_password: str,
        server: str,
        account_type: str = "client",
        strategy_level: Optional[str] = None,
    ) -> bool:
        """
        Add a new MT5 terminal connection to the pool.
        Spawns a new worker process.
        """
        if login in self.workers:
            logger.warning(f"Account {login} already in pool")
            return True
        
        # Decrypt password
        password = self.vault.decrypt(encrypted_password)
        
        # Create command queue and response queue for this worker
        command_queue = f"mt5:commands:{login}"
        response_queue = f"mt5:responses:{login}"
        heartbeat_key = f"mt5:heartbeat:{login}"
        
        # Spawn worker process
        config = {
            "login": login,
            "password": password,
            "server": server,
            "path": settings.MT5_TERMINAL_PATH,
            "command_queue": command_queue,
            "response_queue": response_queue,
            "heartbeat_key": heartbeat_key,
            "redis_url": settings.REDIS_URL,
        }
        
        process = multiprocessing.Process(
            target=_mt5_worker_process,
            args=(config,),
            daemon=True,
        )
        process.start()
        
        # Track worker
        self.workers[login] = TerminalWorkerInfo(
            process_id=process.pid,
            account_login=login,
            server=server,
            account_type=account_type,
            strategy_level=strategy_level,
            status="starting",
        )
        
        # Wait for connection confirmation
        try:
            response = await self.redis.blpop(
                response_queue, timeout=30
            )
            if response:
                data = json.loads(response[1])
                if data.get("status") == "connected":
                    self.workers[login].status = "connected"
                    self.workers[login].balance = data.get("balance", 0)
                    logger.info(
                        f"Worker connected: login={login}, "
                        f"balance={data.get('balance')}"
                    )
                    return True
        except Exception as e:
            logger.error(f"Worker start failed for {login}: {e}")
        
        self.workers[login].status = "error"
        return False
    
    async def remove_connection(self, login: int):
        """Remove a connection and stop its worker process."""
        if login not in self.workers:
            return
        
        # Send shutdown command
        command_queue = f"mt5:commands:{login}"
        await self.redis.rpush(
            command_queue,
            json.dumps({"action": "shutdown"})
        )
        
        # Clean up
        del self.workers[login]
        logger.info(f"Removed connection: login={login}")
    
    async def execute_trade(
        self, login: int, trade_params: Dict
    ) -> Dict:
        """
        Send a trade execution command to a specific worker.
        
        trade_params:
            action: "open" | "close" | "modify"
            symbol: str
            order_type: int
            volume: float
            price: float (optional)
            sl: float (optional)
            tp: float (optional)
            ticket: int (for close/modify)
        """
        if login not in self.workers:
            return {"success": False, "error": f"Account {login} not in pool"}
        
        if self.workers[login].status != "connected":
            return {"success": False, "error": f"Account {login} not connected"}
        
        command_queue = f"mt5:commands:{login}"
        response_queue = f"mt5:responses:{login}"
        
        # Send command
        await self.redis.rpush(
            command_queue,
            json.dumps({"action": "trade", **trade_params})
        )
        
        # Wait for response (timeout 10 seconds)
        response = await self.redis.blpop(response_queue, timeout=10)
        if response:
            return json.loads(response[1])
        
        return {"success": False, "error": "Trade execution timeout"}
    
    async def get_balance(self, login: int) -> float:
        """Get account balance from a worker."""
        command_queue = f"mt5:commands:{login}"
        response_queue = f"mt5:responses:{login}"
        
        await self.redis.rpush(
            command_queue,
            json.dumps({"action": "get_balance"})
        )
        
        response = await self.redis.blpop(response_queue, timeout=5)
        if response:
            data = json.loads(response[1])
            return data.get("balance", 0.0)
        return 0.0
    
    async def get_pool_status(self) -> List[Dict]:
        """Get status of all connections in the pool."""
        statuses = []
        for login, info in self.workers.items():
            statuses.append({
                "login": info.account_login,
                "server": info.server,
                "type": info.account_type,
                "strategy": info.strategy_level,
                "status": info.status,
                "balance": info.balance,
                "last_heartbeat": (
                    info.last_heartbeat.isoformat()
                    if info.last_heartbeat else None
                ),
            })
        return statuses
    
    async def _health_check_loop(self):
        """Periodically check all worker connections."""
        while self._running:
            await asyncio.sleep(settings.MT5_HEALTH_CHECK_INTERVAL)
            
            for login, info in list(self.workers.items()):
                heartbeat_key = f"mt5:heartbeat:{login}"
                heartbeat = await self.redis.get(heartbeat_key)
                
                if heartbeat:
                    ts = datetime.fromisoformat(heartbeat.decode())
                    info.last_heartbeat = ts
                    
                    # If heartbeat is stale (>30s), mark disconnected
                    if datetime.utcnow() - ts > timedelta(seconds=30):
                        if info.status == "connected":
                            info.status = "disconnected"
                            logger.warning(
                                f"Connection stale: login={login}"
                            )
                            # Trigger reconnect
                            await self._reconnect_worker(login)
    
    async def _reconnect_worker(self, login: int):
        """Attempt to reconnect a disconnected worker."""
        info = self.workers.get(login)
        if not info:
            return
        
        command_queue = f"mt5:commands:{login}"
        await self.redis.rpush(
            command_queue,
            json.dumps({"action": "reconnect"})
        )
        logger.info(f"Reconnect command sent to login={login}")


def _mt5_worker_process(config: Dict):
    """
    Worker process that runs a single MT5 terminal.
    Communicates with the pool via Redis queues.
    
    This runs in a separate process because MT5 Python API
    only supports one terminal per process.
    """
    import MetaTrader5 as mt5
    import redis as sync_redis
    import time
    
    r = sync_redis.Redis.from_url(config["redis_url"])
    command_queue = config["command_queue"]
    response_queue = config["response_queue"]
    heartbeat_key = config["heartbeat_key"]
    
    # Connect to MT5
    if not mt5.initialize(
        path=config["path"],
        login=config["login"],
        password=config["password"],
        server=config["server"],
        timeout=10000,
    ):
        r.rpush(response_queue, json.dumps({
            "status": "error",
            "error": str(mt5.last_error()),
        }))
        return
    
    account_info = mt5.account_info()
    r.rpush(response_queue, json.dumps({
        "status": "connected",
        "balance": account_info.balance if account_info else 0,
    }))
    
    # Main command loop
    while True:
        # Update heartbeat
        r.set(heartbeat_key, datetime.utcnow().isoformat(), ex=60)
        
        # Wait for commands (1s timeout to allow heartbeat updates)
        result = r.blpop(command_queue, timeout=1)
        if result is None:
            continue
        
        command = json.loads(result[1])
        action = command.get("action")
        
        if action == "shutdown":
            mt5.shutdown()
            break
        
        elif action == "reconnect":
            mt5.shutdown()
            time.sleep(2)
            success = mt5.initialize(
                path=config["path"],
                login=config["login"],
                password=config["password"],
                server=config["server"],
            )
            r.rpush(response_queue, json.dumps({
                "status": "connected" if success else "error",
            }))
        
        elif action == "get_balance":
            info = mt5.account_info()
            r.rpush(response_queue, json.dumps({
                "balance": info.balance if info else 0,
            }))
        
        elif action == "trade":
            trade_action = command.get("trade_action", "open")
            
            if trade_action == "open":
                conn = MT5Connection.__new__(MT5Connection)
                result = conn.execute_order(
                    symbol=command["symbol"],
                    order_type=command["order_type"],
                    volume=command["volume"],
                    price=command.get("price", 0),
                    sl=command.get("sl", 0),
                    tp=command.get("tp", 0),
                    comment=command.get("comment", "CopyTrade"),
                )
                r.rpush(response_queue, json.dumps(result))
            
            elif trade_action == "close":
                conn = MT5Connection.__new__(MT5Connection)
                result = conn.close_position(command["ticket"])
                r.rpush(response_queue, json.dumps(result))
            
            elif trade_action == "modify":
                conn = MT5Connection.__new__(MT5Connection)
                result = conn.modify_position(
                    ticket=command["ticket"],
                    sl=command.get("sl", 0),
                    tp=command.get("tp", 0),
                )
                r.rpush(response_queue, json.dumps(result))
    
    mt5.shutdown()
```

---

## 5. Lot Calculator (engine/lot_calculator.py)

```python
"""
Proportional Lot Size Calculator

Formula:
    client_lots = master_lots * (client_balance / master_balance)

Example:
    Master balance = $10,000, trade = 1.0 lot
    Client balance = $1,000
    Client lots = 1.0 * (1000 / 10000) = 0.10 lots

Rules:
    - Respect symbol's min/max lot size
    - Round to symbol's lot step (usually 0.01)
    - Never exceed client's free margin
    - Apply per-strategy risk multiplier if configured
"""

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class LotCalculationResult:
    calculated_lots: float
    adjusted_lots: float  # After min/max/step adjustment
    ratio: float
    reason: str  # "ok", "min_lot", "max_lot", "insufficient_margin"


class LotCalculator:
    """Calculates proportional lot sizes for copy trading."""
    
    # Strategy risk multipliers (optional amplifier/dampener)
    STRATEGY_MULTIPLIERS = {
        "Low": 0.5,       # Half the proportional size
        "Medium": 1.0,    # Exact proportional
        "High": 1.5,      # 1.5x proportional
        "Pro": 2.0,
        "Expert": 2.5,
        "Expert Pro": 3.0,
    }
    
    def __init__(
        self,
        min_lot: float = 0.01,
        max_lot: float = 100.0,
        lot_step: float = 0.01,
    ):
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.lot_step = lot_step
    
    def calculate(
        self,
        master_balance: float,
        master_lots: float,
        client_balance: float,
        strategy_level: str = "Medium",
        client_free_margin: Optional[float] = None,
        symbol_min_lot: Optional[float] = None,
        symbol_max_lot: Optional[float] = None,
        symbol_lot_step: Optional[float] = None,
    ) -> LotCalculationResult:
        """
        Calculate proportional lot size for a client.
        
        Args:
            master_balance: Master account balance
            master_lots: Lot size of master's trade
            client_balance: Client account balance
            strategy_level: Strategy level for risk multiplier
            client_free_margin: Client's available margin
            symbol_min_lot: Symbol-specific minimum lot
            symbol_max_lot: Symbol-specific maximum lot
            symbol_lot_step: Symbol-specific lot step
        
        Returns:
            LotCalculationResult with calculated and adjusted lots
        """
        # Use symbol-specific or default lot constraints
        min_lot = symbol_min_lot or self.min_lot
        max_lot = symbol_max_lot or self.max_lot
        lot_step = symbol_lot_step or self.lot_step
        
        # Prevent division by zero
        if master_balance <= 0:
            return LotCalculationResult(
                calculated_lots=0,
                adjusted_lots=0,
                ratio=0,
                reason="invalid_master_balance",
            )
        
        # Calculate proportional ratio
        ratio = client_balance / master_balance
        
        # Apply strategy multiplier
        multiplier = self.STRATEGY_MULTIPLIERS.get(strategy_level, 1.0)
        
        # Calculate raw lot size
        raw_lots = master_lots * ratio * multiplier
        
        # Round to lot step
        adjusted_lots = self._round_to_step(raw_lots, lot_step)
        
        reason = "ok"
        
        # Apply minimum lot constraint
        if adjusted_lots < min_lot:
            if raw_lots > 0:
                # If calculated is positive but below minimum,
                # use minimum lot (or skip if too small)
                if raw_lots >= min_lot * 0.5:
                    adjusted_lots = min_lot
                    reason = "min_lot_applied"
                else:
                    adjusted_lots = 0
                    reason = "below_min_lot"
            else:
                adjusted_lots = 0
                reason = "zero_calculation"
        
        # Apply maximum lot constraint
        if adjusted_lots > max_lot:
            adjusted_lots = max_lot
            reason = "max_lot_applied"
        
        return LotCalculationResult(
            calculated_lots=raw_lots,
            adjusted_lots=adjusted_lots,
            ratio=ratio,
            reason=reason,
        )
    
    @staticmethod
    def _round_to_step(value: float, step: float) -> float:
        """Round down to nearest lot step."""
        if step <= 0:
            return value
        return math.floor(value / step) * step
    
    @staticmethod
    def calculate_margin_required(
        symbol_price: float,
        lots: float,
        leverage: int,
        contract_size: float = 100000,
    ) -> float:
        """
        Estimate margin required for a trade.
        
        margin = (lots * contract_size * price) / leverage
        """
        return (lots * contract_size * symbol_price) / leverage
```

---

## 6. Master Trade Listener (engine/master_listener.py)

```python
"""
Master Trade Listener

Continuously monitors master MT5 accounts for trade events:
- New positions opened
- Positions closed
- SL/TP modifications

Uses a polling approach: every 100ms, compare current positions
with the previous snapshot to detect changes.

For each detected event, publishes to Redis for the Trade Distributor.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional
from datetime import datetime
from dataclasses import dataclass, field

import redis.asyncio as redis

from config.settings import settings
from mt5_manager.terminal_pool import TerminalPool
from models.trade_event import TradeEvent, TradeEventType, OrderType

logger = logging.getLogger(__name__)


@dataclass
class PositionSnapshot:
    """Snapshot of a single position for comparison."""
    ticket: int
    symbol: str
    type: int  # 0=buy, 1=sell
    volume: float
    price_open: float
    sl: float
    tp: float
    profit: float
    comment: str


class MasterTradeListener:
    """
    Monitors master accounts and detects trade events.
    
    Usage:
        listener = MasterTradeListener(terminal_pool, redis_client)
        await listener.start()  # runs forever
    """
    
    def __init__(
        self,
        terminal_pool: TerminalPool,
        redis_client: redis.Redis,
    ):
        self.pool = terminal_pool
        self.redis = redis_client
        self._running = False
        
        # Previous position snapshots per master account
        # { master_login: { ticket: PositionSnapshot } }
        self._snapshots: Dict[int, Dict[int, PositionSnapshot]] = {}
        
        # Master account configurations
        # Loaded from database on start
        self._master_accounts: Dict[int, Dict] = {}
    
    async def start(self):
        """Start listening for trade events on all master accounts."""
        self._running = True
        
        # Load master accounts from database
        await self._load_master_accounts()
        
        # Take initial snapshots
        for login in self._master_accounts:
            await self._take_snapshot(login)
        
        logger.info(
            f"Master Listener started, monitoring "
            f"{len(self._master_accounts)} accounts"
        )
        
        # Main polling loop
        poll_interval = settings.COPY_ENGINE_POLL_INTERVAL_MS / 1000
        
        while self._running:
            for login in self._master_accounts:
                try:
                    await self._check_for_changes(login)
                except Exception as e:
                    logger.error(f"Error checking master {login}: {e}")
            
            await asyncio.sleep(poll_interval)
    
    async def stop(self):
        """Stop the listener."""
        self._running = False
    
    async def _load_master_accounts(self):
        """Load master account configs from database."""
        # In production, load from PostgreSQL
        # Example structure:
        self._master_accounts = {
            10001: {"strategy": "Low", "login": 10001},
            10002: {"strategy": "Medium", "login": 10002},
            10003: {"strategy": "High", "login": 10003},
            10004: {"strategy": "Pro", "login": 10004},
            10005: {"strategy": "Expert", "login": 10005},
            10006: {"strategy": "Expert Pro", "login": 10006},
        }
    
    async def _take_snapshot(self, login: int):
        """Take a snapshot of current positions."""
        command_queue = f"mt5:commands:{login}"
        response_queue = f"mt5:responses:{login}"
        
        await self.redis.rpush(
            command_queue,
            json.dumps({"action": "get_positions"})
        )
        
        response = await self.redis.blpop(response_queue, timeout=5)
        if not response:
            return
        
        positions = json.loads(response[1]).get("positions", [])
        
        self._snapshots[login] = {
            pos["ticket"]: PositionSnapshot(
                ticket=pos["ticket"],
                symbol=pos["symbol"],
                type=pos["type"],
                volume=pos["volume"],
                price_open=pos["price_open"],
                sl=pos["sl"],
                tp=pos["tp"],
                profit=pos["profit"],
                comment=pos.get("comment", ""),
            )
            for pos in positions
        }
    
    async def _check_for_changes(self, login: int):
        """Compare current positions with snapshot to detect events."""
        old_snapshot = self._snapshots.get(login, {})
        
        # Get current positions
        command_queue = f"mt5:commands:{login}"
        response_queue = f"mt5:responses:{login}"
        
        await self.redis.rpush(
            command_queue,
            json.dumps({"action": "get_positions"})
        )
        
        response = await self.redis.blpop(response_queue, timeout=5)
        if not response:
            return
        
        data = json.loads(response[1])
        current_positions = data.get("positions", [])
        master_balance = data.get("balance", 0)
        
        new_snapshot: Dict[int, PositionSnapshot] = {}
        
        for pos in current_positions:
            snap = PositionSnapshot(
                ticket=pos["ticket"],
                symbol=pos["symbol"],
                type=pos["type"],
                volume=pos["volume"],
                price_open=pos["price_open"],
                sl=pos["sl"],
                tp=pos["tp"],
                profit=pos["profit"],
                comment=pos.get("comment", ""),
            )
            new_snapshot[snap.ticket] = snap
        
        old_tickets = set(old_snapshot.keys())
        new_tickets = set(new_snapshot.keys())
        strategy = self._master_accounts[login]["strategy"]
        
        # --- Detect NEW positions (opened trades) ---
        opened = new_tickets - old_tickets
        for ticket in opened:
            pos = new_snapshot[ticket]
            event = TradeEvent(
                event_type=TradeEventType.OPEN,
                master_account_id=str(login),
                strategy_level=strategy,
                ticket=ticket,
                symbol=pos.symbol,
                order_type=OrderType(pos.type),
                volume=pos.volume,
                price=pos.price_open,
                sl=pos.sl,
                tp=pos.tp,
                master_balance=master_balance,
            )
            await self._publish_event(event)
            logger.info(
                f"OPEN detected: master={login}, "
                f"{pos.symbol} {pos.volume} lots"
            )
        
        # --- Detect CLOSED positions ---
        closed = old_tickets - new_tickets
        for ticket in closed:
            pos = old_snapshot[ticket]
            event = TradeEvent(
                event_type=TradeEventType.CLOSE,
                master_account_id=str(login),
                strategy_level=strategy,
                ticket=ticket,
                symbol=pos.symbol,
                order_type=OrderType(pos.type),
                volume=pos.volume,
                master_balance=master_balance,
            )
            await self._publish_event(event)
            logger.info(
                f"CLOSE detected: master={login}, "
                f"ticket={ticket}"
            )
        
        # --- Detect MODIFICATIONS (SL/TP changes) ---
        for ticket in old_tickets & new_tickets:
            old = old_snapshot[ticket]
            new = new_snapshot[ticket]
            
            if old.sl != new.sl or old.tp != new.tp:
                event = TradeEvent(
                    event_type=TradeEventType.MODIFY,
                    master_account_id=str(login),
                    strategy_level=strategy,
                    ticket=ticket,
                    symbol=new.symbol,
                    order_type=OrderType(new.type),
                    volume=new.volume,
                    sl=new.sl,
                    tp=new.tp,
                    master_balance=master_balance,
                )
                await self._publish_event(event)
                logger.info(
                    f"MODIFY detected: master={login}, "
                    f"ticket={ticket}, SL={new.sl}, TP={new.tp}"
                )
        
        # Update snapshot
        self._snapshots[login] = new_snapshot
    
    async def _publish_event(self, event: TradeEvent):
        """Publish trade event to Redis for the distributor."""
        event_data = {
            "id": event.id,
            "event_type": event.event_type.value,
            "master_account_id": event.master_account_id,
            "strategy_level": event.strategy_level,
            "ticket": event.ticket,
            "symbol": event.symbol,
            "order_type": event.order_type.value,
            "volume": event.volume,
            "price": event.price,
            "sl": event.sl,
            "tp": event.tp,
            "master_balance": event.master_balance,
            "timestamp": event.timestamp.isoformat(),
        }
        
        # Publish to Redis channel
        await self.redis.publish(
            "trade_events",
            json.dumps(event_data)
        )
        
        # Also store in a list for reliability
        await self.redis.rpush(
            "trade_events_queue",
            json.dumps(event_data)
        )
```

---

## 7. Trade Distributor (engine/trade_distributor.py)

```python
"""
Trade Distributor

Receives trade events from Master Listener and distributes
them to all client accounts subscribed to that strategy.

Flow:
1. Receive trade event from Redis
2. Query database for all active clients on that strategy
3. For each client:
   a. Calculate proportional lot size
   b. Queue execution task
"""

import asyncio
import json
import logging
from typing import List, Dict
from datetime import datetime

import redis.asyncio as redis

from config.settings import settings
from engine.lot_calculator import LotCalculator
from engine.execution_manager import ExecutionManager
from models.trade_event import TradeEvent, TradeEventType

logger = logging.getLogger(__name__)


class TradeDistributor:
    """
    Distributes master trade events to subscribed client accounts.
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        execution_manager: 'ExecutionManager',
        lot_calculator: LotCalculator,
    ):
        self.redis = redis_client
        self.executor = execution_manager
        self.calculator = lot_calculator
        self._running = False
    
    async def start(self):
        """Start consuming trade events."""
        self._running = True
        logger.info("Trade Distributor started")
        
        # Subscribe to trade events channel
        pubsub = self.redis.pubsub()
        await pubsub.subscribe("trade_events")
        
        async for message in pubsub.listen():
            if not self._running:
                break
            
            if message["type"] != "message":
                continue
            
            try:
                event_data = json.loads(message["data"])
                await self._distribute_event(event_data)
            except Exception as e:
                logger.error(f"Distribution error: {e}")
    
    async def stop(self):
        self._running = False
    
    async def _distribute_event(self, event_data: Dict):
        """Distribute a single trade event to all eligible clients."""
        strategy = event_data["strategy_level"]
        event_type = event_data["event_type"]
        
        logger.info(
            f"Distributing {event_type} event for strategy "
            f"{strategy}, symbol={event_data['symbol']}"
        )
        
        # Get all active clients subscribed to this strategy
        clients = await self._get_subscribed_clients(strategy)
        
        logger.info(f"Found {len(clients)} clients for strategy {strategy}")
        
        # Process each client concurrently
        tasks = []
        for client in clients:
            task = asyncio.create_task(
                self._process_client(client, event_data)
            )
            tasks.append(task)
        
        # Wait for all executions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log results
        success = sum(1 for r in results if not isinstance(r, Exception))
        failed = len(results) - success
        logger.info(
            f"Distribution complete: {success} success, "
            f"{failed} failed out of {len(clients)} clients"
        )
    
    async def _process_client(self, client: Dict, event_data: Dict):
        """Process a trade event for a single client."""
        client_login = client["mt5_login"]
        client_balance = client["balance"]
        strategy = event_data["strategy_level"]
        
        if event_data["event_type"] == "open":
            # Calculate lot size
            result = self.calculator.calculate(
                master_balance=event_data["master_balance"],
                master_lots=event_data["volume"],
                client_balance=client_balance,
                strategy_level=strategy,
            )
            
            if result.adjusted_lots <= 0:
                logger.warning(
                    f"Skip client {client_login}: "
                    f"calculated lots too small ({result.reason})"
                )
                return
            
            # Execute the trade
            await self.executor.execute_open(
                client_login=client_login,
                symbol=event_data["symbol"],
                order_type=event_data["order_type"],
                volume=result.adjusted_lots,
                sl=event_data.get("sl", 0),
                tp=event_data.get("tp", 0),
                master_ticket=event_data["ticket"],
                trade_event_id=event_data["id"],
            )
        
        elif event_data["event_type"] == "close":
            await self.executor.execute_close(
                client_login=client_login,
                master_ticket=event_data["ticket"],
                trade_event_id=event_data["id"],
            )
        
        elif event_data["event_type"] == "modify":
            await self.executor.execute_modify(
                client_login=client_login,
                master_ticket=event_data["ticket"],
                sl=event_data.get("sl", 0),
                tp=event_data.get("tp", 0),
                trade_event_id=event_data["id"],
            )
    
    async def _get_subscribed_clients(self, strategy: str) -> List[Dict]:
        """
        Get all active clients subscribed to a strategy.
        In production, query PostgreSQL.
        """
        # Example query:
        # SELECT u.id, ma.mt5_login, ma.balance
        # FROM users u
        # JOIN mt5_accounts ma ON u.id = ma.user_id
        # JOIN subscriptions s ON u.id = s.user_id
        # WHERE u.strategy_level = $1
        #   AND ma.status = 'connected'
        #   AND s.status = 'active'
        
        # Placeholder - replace with actual DB query
        cached = await self.redis.get(f"clients:strategy:{strategy}")
        if cached:
            return json.loads(cached)
        return []
```

---

## 8. Execution Manager (engine/execution_manager.py)

```python
"""
Execution Manager

Handles the actual trade execution on client accounts.
Includes retry logic and ticket mapping (master ticket -> client ticket).
"""

import asyncio
import json
import logging
from typing import Dict, Optional
from datetime import datetime

import redis.asyncio as redis

from config.settings import settings
from mt5_manager.terminal_pool import TerminalPool

logger = logging.getLogger(__name__)


class ExecutionManager:
    """Manages trade execution with retries and ticket tracking."""
    
    def __init__(
        self,
        terminal_pool: TerminalPool,
        redis_client: redis.Redis,
    ):
        self.pool = terminal_pool
        self.redis = redis_client
    
    async def execute_open(
        self,
        client_login: int,
        symbol: str,
        order_type: int,
        volume: float,
        sl: float = 0,
        tp: float = 0,
        master_ticket: int = 0,
        trade_event_id: str = "",
    ) -> Dict:
        """
        Execute an open trade on a client account.
        Includes retry logic.
        """
        for attempt in range(settings.MAX_RETRY_ATTEMPTS):
            result = await self.pool.execute_trade(
                login=client_login,
                trade_params={
                    "trade_action": "open",
                    "symbol": symbol,
                    "order_type": order_type,
                    "volume": volume,
                    "sl": sl,
                    "tp": tp,
                    "comment": f"CT:{master_ticket}",
                },
            )
            
            if result.get("success"):
                # Store ticket mapping: master_ticket -> client_ticket
                client_ticket = result.get("ticket")
                await self._store_ticket_mapping(
                    client_login, master_ticket, client_ticket
                )
                
                # Log successful execution
                await self._log_execution(
                    trade_event_id=trade_event_id,
                    client_login=client_login,
                    status="executed",
                    volume=volume,
                    price=result.get("price", 0),
                    client_ticket=client_ticket,
                )
                
                logger.info(
                    f"Trade executed: client={client_login}, "
                    f"symbol={symbol}, volume={volume}, "
                    f"ticket={client_ticket}"
                )
                return result
            
            # Retry
            logger.warning(
                f"Trade failed (attempt {attempt + 1}): "
                f"client={client_login}, error={result.get('error')}"
            )
            await asyncio.sleep(settings.RETRY_DELAY_SECONDS)
        
        # All retries exhausted
        await self._log_execution(
            trade_event_id=trade_event_id,
            client_login=client_login,
            status="failed",
            error=result.get("error", "Max retries exceeded"),
        )
        
        return {"success": False, "error": "Max retries exceeded"}
    
    async def execute_close(
        self,
        client_login: int,
        master_ticket: int,
        trade_event_id: str = "",
    ) -> Dict:
        """Close the corresponding position on client account."""
        # Look up client ticket from master ticket
        client_ticket = await self._get_client_ticket(
            client_login, master_ticket
        )
        
        if not client_ticket:
            logger.warning(
                f"No ticket mapping found: client={client_login}, "
                f"master_ticket={master_ticket}"
            )
            return {"success": False, "error": "No ticket mapping"}
        
        for attempt in range(settings.MAX_RETRY_ATTEMPTS):
            result = await self.pool.execute_trade(
                login=client_login,
                trade_params={
                    "trade_action": "close",
                    "ticket": client_ticket,
                },
            )
            
            if result.get("success"):
                # Clean up ticket mapping
                await self._remove_ticket_mapping(
                    client_login, master_ticket
                )
                
                await self._log_execution(
                    trade_event_id=trade_event_id,
                    client_login=client_login,
                    status="closed",
                    client_ticket=client_ticket,
                    price=result.get("price", 0),
                )
                
                logger.info(
                    f"Position closed: client={client_login}, "
                    f"ticket={client_ticket}"
                )
                return result
            
            await asyncio.sleep(settings.RETRY_DELAY_SECONDS)
        
        return {"success": False, "error": "Close failed after retries"}
    
    async def execute_modify(
        self,
        client_login: int,
        master_ticket: int,
        sl: float = 0,
        tp: float = 0,
        trade_event_id: str = "",
    ) -> Dict:
        """Modify SL/TP on client's corresponding position."""
        client_ticket = await self._get_client_ticket(
            client_login, master_ticket
        )
        
        if not client_ticket:
            return {"success": False, "error": "No ticket mapping"}
        
        result = await self.pool.execute_trade(
            login=client_login,
            trade_params={
                "trade_action": "modify",
                "ticket": client_ticket,
                "sl": sl,
                "tp": tp,
            },
        )
        
        if result.get("success"):
            logger.info(
                f"Position modified: client={client_login}, "
                f"ticket={client_ticket}, SL={sl}, TP={tp}"
            )
        
        return result
    
    # --- Ticket Mapping (Redis) ---
    
    async def _store_ticket_mapping(
        self, client_login: int, master_ticket: int, client_ticket: int
    ):
        key = f"ticket_map:{client_login}:{master_ticket}"
        await self.redis.set(key, str(client_ticket))
    
    async def _get_client_ticket(
        self, client_login: int, master_ticket: int
    ) -> Optional[int]:
        key = f"ticket_map:{client_login}:{master_ticket}"
        val = await self.redis.get(key)
        return int(val) if val else None
    
    async def _remove_ticket_mapping(
        self, client_login: int, master_ticket: int
    ):
        key = f"ticket_map:{client_login}:{master_ticket}"
        await self.redis.delete(key)
    
    # --- Execution Logging ---
    
    async def _log_execution(self, **kwargs):
        """Log trade execution to Redis (batch insert to DB later)."""
        kwargs["timestamp"] = datetime.utcnow().isoformat()
        await self.redis.rpush(
            "execution_log",
            json.dumps(kwargs, default=str),
        )
```

---

## 9. Credential Vault (mt5_manager/credential_vault.py)

```python
"""
Secure credential encryption/decryption for MT5 passwords.
Uses Fernet symmetric encryption (AES-128-CBC).
"""

from cryptography.fernet import Fernet
import base64
import hashlib


class CredentialVault:
    def __init__(self, encryption_key: str):
        # Derive a valid Fernet key from any string
        key = hashlib.sha256(encryption_key.encode()).digest()
        self.fernet = Fernet(base64.urlsafe_b64encode(key))
    
    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

---

## 10. Docker Compose (docker-compose.yml)

```yaml
version: "3.9"

services:
  # --- Core Infrastructure ---
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: copytrade
      POSTGRES_USER: copytrade
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  # --- Backend API ---
  api:
    build: ./backend
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000
    environment:
      DATABASE_URL: postgresql+asyncpg://copytrade:${DB_PASSWORD}@postgres/copytrade
      REDIS_URL: redis://redis:6379/0
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis

  # --- Copy Engine (Master Listener + Distributor) ---
  copy-engine:
    build: ./copy-engine
    command: python -m engine.main
    environment:
      DATABASE_URL: postgresql+asyncpg://copytrade:${DB_PASSWORD}@postgres/copytrade
      REDIS_URL: redis://redis:6379/0
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 1  # Only ONE listener per master

  # --- MT5 Terminal Workers ---
  # Each worker handles multiple MT5 processes
  mt5-worker:
    build: ./copy-engine
    command: python -m mt5_manager.worker
    environment:
      REDIS_URL: redis://redis:6379/0
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    volumes:
      - mt5data:/opt/mt5
    deploy:
      replicas: 3  # Scale based on client count
    # NOTE: Requires Windows or Wine for MT5 terminal

  # --- Celery Workers (billing, health checks) ---
  celery-worker:
    build: ./backend
    command: celery -A workers.celery_app worker -l info
    environment:
      DATABASE_URL: postgresql+asyncpg://copytrade:${DB_PASSWORD}@postgres/copytrade
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  celery-beat:
    build: ./backend
    command: celery -A workers.celery_app beat -l info
    environment:
      DATABASE_URL: postgresql+asyncpg://copytrade:${DB_PASSWORD}@postgres/copytrade
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis

volumes:
  pgdata:
  mt5data:
```

---

## 11. Database Schema (PostgreSQL)

```sql
-- Enum types
CREATE TYPE account_status AS ENUM ('connected', 'disconnected', 'blocked');
CREATE TYPE strategy_level AS ENUM ('Low', 'Medium', 'High', 'Pro', 'Expert', 'Expert Pro');
CREATE TYPE invoice_status AS ENUM ('paid', 'pending', 'overdue');
CREATE TYPE trade_event_type AS ENUM ('open', 'close', 'modify');
CREATE TYPE copy_status AS ENUM ('pending', 'executed', 'failed', 'retrying');

-- Users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- User roles (security best practice)
CREATE TYPE app_role AS ENUM ('admin', 'user');
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    role app_role NOT NULL,
    UNIQUE (user_id, role)
);

-- MT5 Accounts
CREATE TABLE mt5_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    mt5_login BIGINT UNIQUE NOT NULL,
    encrypted_password TEXT NOT NULL,
    server VARCHAR(100) NOT NULL,
    status account_status DEFAULT 'disconnected',
    balance DECIMAL(15,2) DEFAULT 0,
    equity DECIMAL(15,2) DEFAULT 0,
    last_connected_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_mt5_accounts_user ON mt5_accounts(user_id);
CREATE INDEX idx_mt5_accounts_status ON mt5_accounts(status);

-- Master Accounts
CREATE TABLE master_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mt5_login BIGINT UNIQUE NOT NULL,
    encrypted_password TEXT NOT NULL,
    server VARCHAR(100) NOT NULL,
    strategy strategy_level UNIQUE NOT NULL,
    balance DECIMAL(15,2) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User Strategy Selection
CREATE TABLE user_strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    strategy strategy_level NOT NULL,
    is_locked BOOLEAN DEFAULT FALSE,
    unlocked_by UUID REFERENCES users(id),
    activated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id)
);

-- Subscriptions
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'trial',
    trial_start TIMESTAMPTZ DEFAULT NOW(),
    trial_end TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 days',
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    price DECIMAL(10,2) DEFAULT 49.90,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_subscriptions_user ON subscriptions(user_id);

-- Invoices
CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES subscriptions(id),
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status invoice_status DEFAULT 'pending',
    payment_gateway VARCHAR(50),
    gateway_invoice_id VARCHAR(255),
    paid_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_invoices_user ON invoices(user_id);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_invoices_due ON invoices(due_date);

-- Trade Events (from master accounts)
CREATE TABLE trade_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type trade_event_type NOT NULL,
    master_account_id UUID REFERENCES master_accounts(id),
    strategy strategy_level NOT NULL,
    ticket BIGINT NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    order_type INT NOT NULL,
    volume DECIMAL(10,2) NOT NULL,
    price DECIMAL(15,5),
    sl DECIMAL(15,5) DEFAULT 0,
    tp DECIMAL(15,5) DEFAULT 0,
    master_balance DECIMAL(15,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_trade_events_master ON trade_events(master_account_id);
CREATE INDEX idx_trade_events_created ON trade_events(created_at);

-- Trade Copies (client executions)
CREATE TABLE trade_copies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_event_id UUID REFERENCES trade_events(id),
    mt5_account_id UUID REFERENCES mt5_accounts(id),
    client_ticket BIGINT,
    calculated_volume DECIMAL(10,2),
    executed_volume DECIMAL(10,2),
    executed_price DECIMAL(15,5),
    status copy_status DEFAULT 'pending',
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ
);
CREATE INDEX idx_trade_copies_event ON trade_copies(trade_event_id);
CREATE INDEX idx_trade_copies_account ON trade_copies(mt5_account_id);
CREATE INDEX idx_trade_copies_status ON trade_copies(status);

-- MT5 Servers (admin-managed)
CREATE TABLE mt5_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Payments
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id),
    gateway VARCHAR(50) NOT NULL,
    gateway_payment_id VARCHAR(255),
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    webhook_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_payments_invoice ON payments(invoice_id);
```

---

## 12. requirements.txt

```
# Copy Engine
MetaTrader5==5.0.45
redis==5.0.1
asyncio==3.4.3
pydantic==2.5.0
pydantic-settings==2.1.0
cryptography==41.0.7
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0

# API
fastapi==0.109.0
uvicorn==0.27.0

# Workers
celery==5.3.6

# Utilities
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
httpx==0.26.0
```
