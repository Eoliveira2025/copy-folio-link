"""SymbolDiscoveryService — resolves raw symbols (EURUSD) to broker symbols (EURUSDm)."""

from __future__ import annotations
import time
from typing import Optional, List
from uuid import UUID
from .logger import get_logger
from ..pool import repo

def _safe_import_mt5():
    try:
        import MetaTrader5 as mt5
        return mt5
    except ImportError:
        return None

class SymbolDiscoveryService:
    _log = get_logger("symbol_discovery")

    @classmethod
    def resolve(cls, account_id: UUID, raw_symbol: str) -> str:
        """Resolves a raw symbol to the actual broker symbol for this account."""
        log = cls._log.bind(account_id=str(account_id), raw_symbol=raw_symbol)
        
        # 1. Check cache/db first
        mapping = repo.get_symbol_map(account_id, raw_symbol)
        if mapping:
            # Quick check if it still works (mt5 must be initialized by caller/AccountSession)
            mt5 = _safe_import_mt5()
            if mt5 and mt5.symbol_select(mapping["broker_symbol"], True):
                return mapping["broker_symbol"]
        
        # 2. Discovery logic
        mt5 = _safe_import_mt5()
        if not mt5:
            return raw_symbol # Fallback
            
        all_symbols = mt5.symbols_get()
        if not all_symbols:
            log.warning("could not get symbols from mt5")
            return raw_symbol
            
        # Common suffixes/prefixes in brokers like Exness, IC Markets, etc.
        # Examples: EURUSDm, EURUSDz, EURUSD.ecn, #EURUSD, EURUSD+, EURUSD..
        candidates = []
        raw_upper = raw_symbol.upper()
        
        for s in all_symbols:
            name = s.name
            name_upper = name.upper()
            
            # Match if raw is contained or name starts/ends with raw
            # Focus on names that are basically the raw symbol with some noise
            is_match = False
            if name_upper == raw_upper:
                is_match = True
            elif raw_upper in name_upper:
                # Check if it's a real match (e.g. EURUSDm is match for EURUSD, but EURUSDJPY is not)
                # We normalize by removing common noise
                clean = name_upper.replace("M", "").replace("Z", "").replace(".", "").replace("#", "").replace("+", "").replace("ECN", "").replace("PRO", "")
                if clean == raw_upper:
                    is_match = True
            
            if is_match:
                # Check if it's visible and tradeable
                candidates.append({
                    "name": name,
                    "visible": s.visible,
                    "trade_mode": s.trade_mode, # 0 = disabled
                    "path": s.path
                })

        if not candidates:
            log.error("SYMBOL_NOT_FOUND", candidates=[s.name for s in all_symbols[:10]])
            return raw_symbol

        # Prioritize visible and tradeable
        # Sort: visible first, then trade_mode > 0
        candidates.sort(key=lambda x: (x["visible"], x["trade_mode"] > 0), reverse=True)
        
        broker_symbol = candidates[0]["name"]
        
        # 3. Persistence
        try:
            repo.upsert_symbol_map(
                account_id=account_id,
                raw_symbol=raw_symbol,
                broker_symbol=broker_symbol,
                source="auto_discovery"
            )
            # Ensure it is selected
            mt5.symbol_select(broker_symbol, True)
            log.info("symbol resolved and saved", broker_symbol=broker_symbol)
        except Exception as e:
            log.error("failed to save symbol mapping", exc_info=e)
            
        return broker_symbol

    @classmethod
    def list_all_for_account(cls, account_id: UUID) -> List[str]:
        mt5 = _safe_import_mt5()
        if not mt5: return []
        symbols = mt5.symbols_get()
        return [s.name for s in symbols] if symbols else []
