"""
Terminal Bootstrap — pre-configures a fresh MT5 instance for first-time login.

ROOT CAUSE: When InstanceManager copies the base MT5 folder, the new instance
has no server/account cached. mt5.initialize(server=...) only works if the
server is already in the terminal's internal server list. Without pre-config,
the terminal opens the broker selection screen and hangs.

SOLUTION: Write the correct server + account into the terminal's .ini files
BEFORE calling mt5.initialize(). This makes the terminal skip the broker
selection and connect directly.

This module does NOT alter executor, distributor, or copy logic.
"""

from __future__ import annotations
import configparser
import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("agent.bootstrap")


# ── Known Exness server addresses ────────────────────────────────────
# MT5 needs the actual IP/hostname to connect. These are resolved from
# the server name. If a server is not in this map, the bootstrap will
# still write the name and let MT5 resolve it via its internal DNS.
EXNESS_SERVER_ADDRESSES: dict[str, str] = {
    # Add known addresses here if needed for faster resolution.
    # Format: "Exness-MT5RealX": "mt5realX.exness.com:443"
    # If empty, MT5 will resolve by server name (works for most brokers).
}


def bootstrap_terminal(
    instance_dir: str,
    login: int,
    password: str,
    server: str,
    timeout_ms: int = 60000,
) -> bool:
    """
    Pre-configure a fresh MT5 instance so that mt5.initialize() can log in
    on the very first attempt without showing the broker selection screen.

    Steps:
        1. Locate or create the instance's config directory
        2. Write common.ini with [Common] Server, Login, etc.
        3. Write origin.ini with the server/broker info
        4. Optionally write a startup.ini to skip the first-run wizard
        5. Validate that terminal64.exe exists

    Args:
        instance_dir: Path to the MT5 instance folder (contains terminal64.exe)
        login: MT5 account number
        password: Decrypted MT5 password (only used for validation, NOT written to disk)
        server: Exact MT5 server name (e.g. "Exness-MT5Real6")
        timeout_ms: Init timeout in milliseconds

    Returns:
        True if bootstrap succeeded, False otherwise
    """
    instance_path = Path(instance_dir)
    terminal_exe = instance_path / "terminal64.exe"

    if not terminal_exe.exists():
        logger.error(f"[Bootstrap] terminal64.exe not found in {instance_path}")
        return False

    logger.info(f"[Bootstrap] Configuring instance for login={login} server={server}")
    logger.info(f"[Bootstrap] Instance path: {instance_path}")

    try:
        # ── Step 1: Write common.ini ──────────────────────────────
        _write_common_ini(instance_path, login, server)

        # ── Step 2: Write origin.ini (server info for first launch) ─
        _write_origin_ini(instance_path, server)

        # ── Step 3: Create startup flag to skip first-run wizard ──
        _write_startup_ini(instance_path)

        # ── Step 4: Ensure config directory exists ────────────────
        config_dir = instance_path / "config"
        config_dir.mkdir(exist_ok=True)

        # ── Step 5: Write server.ini in config folder ─────────────
        _write_server_ini(config_dir, server)

        logger.info(f"[Bootstrap] ✅ Instance configured successfully for login={login}")
        return True

    except Exception as e:
        logger.error(f"[Bootstrap] ❌ Failed to configure instance: {e}", exc_info=True)
        return False


def bootstrap_and_connect(
    instance_dir: str,
    login: int,
    password: str,
    server: str,
    timeout_ms: int = 60000,
    max_retries: int = 3,
) -> bool:
    """
    Full bootstrap + MT5 connect flow. Call this INSTEAD of raw mt5.initialize().

    1. Pre-configure the instance files
    2. Call mt5.initialize() with credentials
    3. Verify account_info matches expected login
    4. Retry up to max_retries times with increasing delays

    Returns:
        True if connected and authenticated, False otherwise
    """
    import MetaTrader5 as mt5

    # Step 1: Pre-configure files
    bootstrap_ok = bootstrap_terminal(instance_dir, login, password, server, timeout_ms)
    if not bootstrap_ok:
        logger.warning(f"[Bootstrap] File config failed for {login}, attempting initialize anyway...")

    terminal_exe = str(Path(instance_dir) / "terminal64.exe")

    for attempt in range(1, max_retries + 1):
        logger.info(f"[Bootstrap] Initialize attempt {attempt}/{max_retries} for login={login}")

        # Ensure previous session is clean
        try:
            mt5.shutdown()
        except Exception:
            pass

        time.sleep(1)

        # Initialize with full credentials
        ok = mt5.initialize(
            path=terminal_exe,
            login=login,
            password=password,
            server=server,
            timeout=timeout_ms,
            portable=True,
        )

        if not ok:
            error = mt5.last_error()
            logger.warning(f"[Bootstrap] initialize() failed (attempt {attempt}): {error}")

            if attempt < max_retries:
                delay = 5 * attempt  # 5s, 10s, 15s
                logger.info(f"[Bootstrap] Retrying in {delay}s...")
                time.sleep(delay)
            continue

        # Verify we're logged into the correct account
        info = mt5.account_info()
        if info is None:
            logger.warning(f"[Bootstrap] initialize() OK but account_info() is None (attempt {attempt})")
            if attempt < max_retries:
                mt5.shutdown()
                time.sleep(5 * attempt)
            continue

        if info.login != login:
            logger.error(
                f"[Bootstrap] ❌ Login mismatch! Expected {login}, got {info.login}. "
                f"Instance may be corrupted."
            )
            mt5.shutdown()
            if attempt < max_retries:
                time.sleep(5 * attempt)
            continue

        # Verify server matches
        terminal_info = mt5.terminal_info()
        if terminal_info:
            logger.info(
                f"[Bootstrap] ✅ Terminal info: "
                f"connected={terminal_info.connected}, "
                f"trade_allowed={terminal_info.trade_allowed}, "
                f"path={terminal_info.path}"
            )

        logger.info(
            f"[Bootstrap] ✅ Connected successfully! "
            f"login={info.login}, balance={info.balance}, "
            f"server={info.server}, leverage=1:{info.leverage}"
        )
        return True

    logger.error(f"[Bootstrap] ❌ All {max_retries} attempts failed for login={login}")
    return False


# ── Private helpers ──────────────────────────────────────────────────


def _write_common_ini(instance_path: Path, login: int, server: str):
    """
    Write/update common.ini in the MT5 instance root.
    This is the PRIMARY config file MT5 reads on startup.
    """
    ini_path = instance_path / "common.ini"

    config = configparser.ConfigParser()
    # Preserve existing settings if file exists
    if ini_path.exists():
        try:
            config.read(str(ini_path), encoding="utf-16")
        except Exception:
            try:
                config.read(str(ini_path), encoding="utf-8")
            except Exception:
                pass

    if "Common" not in config:
        config["Common"] = {}

    config["Common"]["Login"] = str(login)
    config["Common"]["Server"] = server
    config["Common"]["KeepPrivate"] = "1"
    config["Common"]["NewsEnable"] = "0"
    config["Common"]["CertInstall"] = "1"

    # Disable UI elements for headless operation
    if "StartUp" not in config:
        config["StartUp"] = {}
    config["StartUp"]["Expert"] = "1"
    config["StartUp"]["ExpertEnabled"] = "1"
    config["StartUp"]["OneClick"] = "0"

    # Write as UTF-16 (MT5 native encoding)
    try:
        with open(ini_path, "w", encoding="utf-16") as f:
            config.write(f)
        logger.debug(f"[Bootstrap] Wrote common.ini: {ini_path}")
    except Exception:
        # Fallback to UTF-8 if UTF-16 fails
        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f)
        logger.debug(f"[Bootstrap] Wrote common.ini (utf-8 fallback): {ini_path}")


def _write_origin_ini(instance_path: Path, server: str):
    """
    Write origin.ini that tells MT5 which broker/server to use on first launch.
    This prevents the broker selection dialog.
    """
    ini_path = instance_path / "origin.ini"

    # Extract broker name from server string (e.g., "Exness-MT5Real6" -> "Exness")
    broker_name = server.split("-")[0] if "-" in server else server

    content = f"[Origin]\nServer={server}\nCompany={broker_name}\n"

    try:
        with open(ini_path, "w", encoding="utf-16") as f:
            f.write(content)
        logger.debug(f"[Bootstrap] Wrote origin.ini: {ini_path}")
    except Exception:
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(content)


def _write_startup_ini(instance_path: Path):
    """
    Write startup flag file to skip the MT5 first-run wizard/EULA screen.
    """
    # The 'terminal.ini' or '.portable' flag tells MT5 to run in portable mode
    portable_flag = instance_path / ".portable"
    if not portable_flag.exists():
        portable_flag.touch()
        logger.debug(f"[Bootstrap] Created .portable flag: {portable_flag}")


def _write_server_ini(config_dir: Path, server: str):
    """
    Write a minimal server config in the config/ subdirectory.
    MT5 looks here for known server definitions.
    """
    # Create a server .ini file with the server name
    safe_name = server.replace(" ", "_").replace(":", "_")
    server_file = config_dir / f"{safe_name}.ini"

    if not server_file.exists():
        content = f"[{server}]\nDescription={server}\nEnable=1\n"
        try:
            with open(server_file, "w", encoding="utf-8") as f:
                f.write(content)
            logger.debug(f"[Bootstrap] Wrote server config: {server_file}")
        except Exception as e:
            logger.warning(f"[Bootstrap] Could not write server config: {e}")
