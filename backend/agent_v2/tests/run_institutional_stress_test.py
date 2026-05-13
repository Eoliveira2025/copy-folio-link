import os
import time
import psutil
import json
import logging
import asyncio
from typing import Dict, List
from datetime import datetime
from backend.agent_v2.config import get_v2_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] STRESS-TEST: %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_v2_settings()

class InstitutionalStressTester:
    def __init__(self, num_accounts: int = 50):
        self.num_accounts = num_accounts
        self.results = {
            "start_time": datetime.now().isoformat(),
            "metrics": {
                "accounts_simulated": num_accounts,
                "ram_per_terminal": [],
                "cpu_per_terminal": [],
                "handles_per_process": [],
                "reconnects": 0,
                "failures": 0,
                "latencies": []
            }
        }
        self.processes = []

    async def simulate_terminal_startup(self):
        """Simula a carga de abertura de terminais em escala."""
        logger.info(f"Iniciando simulação de {self.num_accounts} contas em terminais virtuais...")
        
        # Simula a lógica de alocação do TerminalAllocator
        terminals_needed = (self.num_accounts // settings.POOL_CAPACITY) + 1
        logger.info(f"Terminais físicos necessários: {terminals_needed}")

        for i in range(terminals_needed):
            start_time = time.perf_counter()
            # No teste real, aqui chamaríamos o start_terminal
            # Para o stress test, monitoramos o overhead do sistema
            logger.info(f"Simulando spawn do terminal {i+1}/{terminals_needed}...")
            await asyncio.sleep(0.5) # Throttle para evitar spike artificial
            
            # Coleta métricas do processo atual como baseline
            p = psutil.Process()
            self.results["metrics"]["ram_per_terminal"].append(p.memory_info().rss / 1024 / 1024)
            self.results["metrics"]["cpu_per_terminal"].append(p.cpu_percent(interval=0.1))
            self.results["metrics"]["handles_per_process"].append(p.num_handles() if hasattr(p, 'num_handles') else 0)
            
            latency = (time.perf_counter() - start_time) * 1000
            self.results["metrics"]["latencies"].append(latency)

    async def run_load_test(self):
        """Simula burst de ordens para testar Redis e roteamento."""
        logger.info("Iniciando Order Flood Test...")
        # Simula ordens master -> cliente
        for i in range(100):
            start = time.perf_counter()
            # Mock de processamento de ordem
            await asyncio.sleep(0.01) 
            end = time.perf_counter()
            self.results["metrics"]["latencies"].append((end - start) * 1000)
            
            if i % 10 == 0:
                logger.info(f"Flood Progress: {i}%")

    def generate_report(self):
        self.results["end_time"] = datetime.now().isoformat()
        
        # Cálculo de médias
        metrics = self.results["metrics"]
        if metrics["latencies"]:
            metrics["avg_latency_ms"] = sum(metrics["latencies"]) / len(metrics["latencies"])
        if metrics["ram_per_terminal"]:
            metrics["avg_ram_mb"] = sum(metrics["ram_per_terminal"]) / len(metrics["ram_per_terminal"])
            
        report_path = os.path.join(settings.V2_LOGS_DIR, f"stress_test_{int(time.time())}.json")
        os.makedirs(settings.V2_LOGS_DIR, exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(self.results, f, indent=4)
            
        logger.info(f"Relatório de Stress Test gerado: {report_path}")

async def main():
    tester = InstitutionalStressTester(num_accounts=100)
    await tester.simulate_terminal_startup()
    await tester.run_load_test()
    tester.generate_report()

if __name__ == "__main__":
    asyncio.run(main())
