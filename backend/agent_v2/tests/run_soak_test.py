import os
import time
import logging
import psutil
import json
import asyncio
from datetime import datetime, timedelta
from backend.agent_v2.config import get_v2_settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] SOAK-TEST: %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_v2_settings()

class InstitutionalSoakTester:
    def __init__(self, duration_hours: int = 24):
        self.duration_hours = duration_hours
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(hours=duration_hours)
        self.stats = {
            "initial_ram": psutil.virtual_memory().used / 1024 / 1024,
            "hourly_metrics": [],
            "reconnects": 0,
            "crashes": 0,
            "orphans_found": 0
        }

    async def monitor_loop(self):
        logger.info(f"Iniciando Soak Test por {self.duration_hours} horas...")
        logger.info(f"Final previsto: {self.end_time}")

        while datetime.now() < self.end_time:
            current_ram = psutil.virtual_memory().used / 1024 / 1024
            current_cpu = psutil.cpu_percent(interval=1)
            
            metric = {
                "timestamp": datetime.now().isoformat(),
                "ram_mb": current_ram,
                "cpu_pct": current_cpu,
                "process_count": len(psutil.pids())
            }
            self.stats["hourly_metrics"].append(metric)
            
            # Verifica memory leak aparente
            if len(self.stats["hourly_metrics"]) > 1:
                growth = current_ram - self.stats["hourly_metrics"][0]["ram_mb"]
                logger.info(f"Soak Status: RAM={current_ram:.2f}MB (Crescimento: {growth:.2f}MB) | CPU={current_cpu}%")

            # Sleep de 1 hora entre checks (em modo real) 
            # Para o script de exemplo/template, usamos 10 segundos
            await asyncio.sleep(10)

    def generate_soak_report(self):
        self.stats["final_ram"] = psutil.virtual_memory().used / 1024 / 1024
        self.stats["duration_actual"] = str(datetime.now() - self.start_time)
        
        report_path = os.path.join(settings.V2_LOGS_DIR, f"soak_test_report_{int(time.time())}.json")
        with open(report_path, 'w') as f:
            json.dump(self.stats, f, indent=4)
        
        logger.info(f"Relatório de Soak Test finalizado: {report_path}")

async def main():
    # Para teste rápido, definimos duration_hours pequeno ou interrompemos
    tester = InstitutionalSoakTester(duration_hours=0.01) # ~36 segundos para demo
    await tester.monitor_loop()
    tester.generate_soak_report()

if __name__ == "__main__":
    asyncio.run(main())
