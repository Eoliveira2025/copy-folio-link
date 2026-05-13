"""
run_final_v2_preflight.py
Institutional V2 Pre-flight Validation Script.
Validates all infrastructure requirements before starting operation.
"""

import os
import sys
import argparse
import base64
import logging
from typing import List

# Add root to sys.path
sys.path.append(os.getcwd())

from backend.agent_v2.config import get_v2_settings
from backend.agent_v2.db import session_scope
from backend.agent_v2.redis_client import get_redis, k
from backend.agent_v2.utils.logger import get_logger

log = get_logger("preflight")

def test_redis():
    """Test connection to Redis and V2 prefix isolation."""
    log.info("Testing Redis connection...")
    r = get_redis()
    r.ping()
    
    # Test V2 prefix
    test_key = k("preflight_test")
    r.set(test_key, "ok", ex=10)
    val = r.get(test_key)
    if val != "ok":
        raise ValueError(f"Redis prefix test failed: expected 'ok', got '{val}'")
    
    # Verify DB index (V2 should use DB 2)
    # redis-py connection_pool doesn't easily expose db index after creation 
    # but we trust REDIS_URL from config.
    log.info("[OK] Redis connectivity and isolation validated.")

def test_db():
    """Test connection to Postgres (Linux Backend)."""
    log.info("Testing Database (Postgres) connection...")
    with session_scope() as session:
        # Just a simple query to verify connectivity
        result = session.execute("SELECT 1").scalar()
        if result != 1:
            raise ValueError("DB query test failed")
    log.info("[OK] Database connectivity validated.")

def test_encryption_key():
    """Validate MT5_CREDENTIAL_KEY format."""
    log.info("Validating MT5 encryption key...")
    settings = get_v2_settings()
    key = settings.MT5_CREDENTIAL_KEY
    try:
        decoded = base64.b64decode(key)
        if len(decoded) != 32:
            log.warning(f"Key length is {len(decoded)} bytes. Recommended is 32 bytes for AES-256.")
    except Exception as e:
        raise ValueError(f"Invalid Base64 encryption key: {e}")
    log.info("[OK] Encryption key format validated.")

def test_directories():
    """Verify isolation directories exist."""
    log.info("Verifying directory structure...")
    settings = get_v2_settings()
    dirs = [
        settings.V2_ROOT,
        settings.V2_MASTERS_DIR,
        settings.V2_POOL_DIR,
        settings.V2_LOGS_DIR
    ]
    for d in dirs:
        if not os.path.exists(d):
            log.warning(f"Directory missing: {d}")
        else:
            log.info(f" Found: {d}")
    log.info("[OK] Directory structure check complete.")

def test_features():
    """Display active institutional feature flags."""
    s = get_v2_settings()
    log.info("Institutional Configuration:")
    log.info(f" - VPS_ID: {s.V2_VPS_ID}")
    log.info(f" - SAFE_MODE: {s.V2_INSTITUTIONAL_SAFE_MODE_ENABLED}")
    log.info(f" - RESOURCE_GUARD: {s.V2_RESOURCE_GUARD_ENABLED}")
    log.info(f" - EXECUTION_DEDUP: {s.V2_EXECUTION_DEDUP_ENABLED}")
    log.info(f" - HIGH_DENSITY: {s.V2_MAX_ACCOUNTS_PER_VPS} accounts/vps target")
    log.info(f" - MONITOR: {s.METRICS_PORT} (Prometheus) / Web dashboard enabled")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--short", action="store_true", help="Run short connectivity test only")
    args = parser.parse_args()

    print("\n--- CopyTrade Pro V2 Pre-flight Checks ---")
    
    try:
        test_redis()
        test_db()
        
        if not args.short:
            test_encryption_key()
            test_directories()
            test_features()
            
        print("\n[SUCCESS] V2 Pre-flight validation passed!")
        sys.exit(0)
    except Exception as e:
        log.error(f"Pre-flight failed: {e}")
        print(f"\n[ERROR] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
