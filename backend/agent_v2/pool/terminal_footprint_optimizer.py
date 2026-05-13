"""TerminalFootprintOptimizer — Force minimal MT5 footprint."""

import os
import shutil
from pathlib import Path
from ..utils.logger import get_logger

_HEAVY_DIRS = (
    "Bases", 
    "MQL5/Experts", 
    "MQL5/Indicators",
    "MQL5/Scripts", 
    "Templates", 
    "Profiles",
    "MQL5/Logs",
    "logs"
)

def optimize_terminal_folder(terminal_path: str):
    """Deep cleaning of MT5 folder to minimize disk and memory usage."""
    log = get_logger("footprint_optimizer")
    root = Path(terminal_path)
    
    if not root.exists():
        return

    # 1. Remove unnecessary directories
    for d in _HEAVY_DIRS:
        target = root / d
        if target.exists():
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            except Exception as e:
                log.warning(f"Failed to remove {d}", exc_info=e)
                
    # 2. Re-create essential empty dirs
    for sub in ("config", "MQL5", "Bases", "logs"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    # 3. Optimize common.ini for "Ultra Light" mode
    write_ultra_light_ini(root / "config" / "common.ini")
    
    log.info("Terminal footprint optimized", path=terminal_path)

def write_ultra_light_ini(path: Path):
    """Writes a common.ini that disables almost everything non-essential."""
    # UTF-16 LE is required for MT5 .ini files
    content = (
        "[Common]\n"
        "Login=0\n"
        "ProxyEnable=0\n"
        "CertInstall=0\n"
        "NewsEnable=0\n"
        "ChartsEnable=0\n"
        "EventsEnable=0\n"
        "SoundsEnable=0\n"
        "[Experts]\n"
        "AllowLiveTrading=1\n"
        "AllowDllImport=0\n"
        "Enabled=0\n"
        "Account=0\n"
        "Profile=0\n"
        "[Charts]\n"
        "ProfileLast=Default\n"
        "MaxBars=100\n"
        "PrintColor=0\n"
        "SaveOffline=0\n"
        "[StartUp]\n"
        "Expert=\n"
        "Symbol=\n"
        "Period=\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-16-le")
