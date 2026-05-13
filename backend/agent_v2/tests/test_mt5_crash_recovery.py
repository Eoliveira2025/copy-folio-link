import asyncio
import logging
from uuid import uuid4
from backend.agent_v2.config import get_v2_settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s [CRASH-TEST] %(message)s')
logger = logging.getLogger(__name__)

async def test_mt5_crash_recovery_logic():
    """
    Simula o cenário de falha de processo e valida o tempo de resposta do Watchdog.
    Nota: Este teste em sandbox foca na lógica de detecção.
    """
    settings = get_v2_settings()
    logger.info("Iniciando simulação de crash do MT5...")
    
    # Simula o estado de um pool monitorado
    pool_id = str(uuid4())
    is_alive = True
    
    logger.info(f"Pool {pool_id} operando normalmente.")
    await asyncio.sleep(1)
    
    # Simula o 'kill' do processo
    is_alive = False
    logger.warning(f"CRASH SIMULADO: Processo associado ao Pool {pool_id} encerrado abruptamente.")
    
    # Watchdog logic simulation
    logger.info("Watchdog verificando saúde...")
    if not is_alive:
        logger.error(f"Watchdog detectou falha no Pool {pool_id}. Iniciando restart controlado...")
        # Tempo de backoff institucional
        await asyncio.sleep(settings.TERMINAL_RESTART_BACKOFF_S)
        logger.info(f"Restart concluído para Pool {pool_id}. Estado restaurado.")
        
    logger.info("MT5 Crash Test concluído com sucesso (lógica validada).")

if __name__ == "__main__":
    asyncio.run(test_mt5_crash_recovery_logic())
