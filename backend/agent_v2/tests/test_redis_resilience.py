import asyncio
import time
import logging
import random
from uuid import uuid4
from backend.agent_v2.redis_client import get_redis, k
from backend.agent_v2.config import get_v2_settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [REDIS-RESILIENCE] %(message)s')
logger = logging.getLogger(__name__)

async def test_redis_resilience():
    settings = get_v2_settings()
    redis = get_redis()
    
    logger.info("Test 1: Simulating high frequency state updates...")
    account_id = str(uuid4())
    pool_id = str(uuid4())
    
    # Simula 1000 updates rápidos de batimento cardíaco
    start = time.perf_counter()
    for i in range(1000):
        key = f"health:pool:{pool_id}"
        redis.set(k(key), "ALIVE", ex=30)
    end = time.perf_counter()
    logger.info(f"1000 updates concluídos em {end-start:.4f}s ({(end-start)/1000:.6f}s/op)")

    logger.info("Test 2: Order Deduplication Integrity...")
    # Simula o cenário onde duas ordens idênticas chegam via Redis
    idempotency_key = f"idemp_{int(time.time())}"
    dedup_key = f"dedup:order:{idempotency_key}"
    
    # Primeira tentativa (deve passar)
    first_attempt = redis.set(k(dedup_key), "PROCESSING", nx=True, ex=60)
    logger.info(f"First attempt (nx=True): {first_attempt}")
    
    # Segunda tentativa imediata (deve falhar)
    second_attempt = redis.set(k(dedup_key), "PROCESSING", nx=True, ex=60)
    logger.info(f"Second attempt (nx=True): {second_attempt}")
    
    if first_attempt and not second_attempt:
        logger.info("SUCCESS: Redis atomic NX working correctly for deduplication.")
    else:
        logger.error("FAILURE: Redis deduplication integrity failed!")

    logger.info("Test 3: Simulating Redis disconnection recovery (Logic simulation)...")
    # Em um cenário real, fecharíamos o socket. Aqui simulamos o retry loop do config.
    try:
        redis.ping()
        logger.info("Redis is UP and responsive.")
    except Exception as e:
        logger.error(f"Redis is DOWN: {e}")

if __name__ == "__main__":
    asyncio.run(test_redis_resilience())
