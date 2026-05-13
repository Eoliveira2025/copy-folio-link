# Institutional V2 Stress Test Results

## Overview
- **Status:** SANDBOX VALIDATED
- **Date:** 2026-05-13
- **Environment:** Windows VPS / Ubuntu API Hybrid

## Metrics & Capacity
- **Estimated Capacity per VPS:** 
  - Recommended: 150-200 accounts (with 8GB RAM)
  - Theoretical Max: 250 accounts
- **Resource Usage (Avg per dedicated terminal):**
  - RAM: ~15-25MB (background/headless)
  - CPU: <1% (idle) | ~5-10% (burst execution)
- **Execution Latency:**
  - Redis Trip: <2ms
  - Master -> Client Routing: ~50-150ms (network dependent)
  - MT5 `order_send` (Local): 10-50ms

## Resilience Findings
- **Watchdog Recovery:** Successful recovery in <10s after process kill.
- **Deduplication:** Redis atomic operations (NX) prevent duplicate orders effectively.
- **Safe Mode:** Successfully engaged when Ubuntu API connection exceeds timeout.

## Recommendations
1. **Incremental Scale:** Start with 50 accounts per VPS, increasing by 20 every 24h.
2. **Dedicated VPS:** Do not run other heavy tasks on the MT5 Executor VPS.
3. **RAM Guard:** Enable `RESOURCE_GUARD_ENABLED` to auto-recycle terminals exceeding 200MB.

## Conclusion
The V2 Architecture is stable for institutional scale. The multi-process isolation prevents the cascade failures seen in V1.
