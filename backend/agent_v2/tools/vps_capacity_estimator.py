import psutil
import json
import logging
from backend.agent_v2.config import get_v2_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CapacityEstimator")

def estimate_capacity():
    settings = get_v2_settings()
    
    # Coleta dados do hardware
    ram_total = psutil.virtual_memory().total / (1024**2) # MB
    cpu_count = psutil.cpu_count()
    
    # Premissas institucionais (baseadas em testes prévios da V2)
    RAM_PER_TERMINAL_MB = 150  # Estimativa conservadora para terminal em background
    CPU_PER_TERMINAL_PCT = 2.0 # % de um core em idle/background
    
    # Reserva para o Sistema Operacional e Redis/Agent
    SYSTEM_RESERVE_RAM_MB = 2048
    SYSTEM_RESERVE_CPU_PCT = 20.0
    
    available_ram = ram_total - SYSTEM_RESERVE_RAM_MB
    available_cpu = (cpu_count * 100.0) - SYSTEM_RESERVE_CPU_PCT
    
    # Cálculo por RAM
    max_by_ram = int(available_ram / (RAM_PER_TERMINAL_MB / settings.POOL_CAPACITY))
    # Cálculo por CPU
    max_by_cpu = int(available_cpu / (CPU_PER_TERMINAL_PCT / settings.POOL_CAPACITY))
    
    capacity_accounts = min(max_by_ram, max_by_cpu)
    
    # Margem de segurança institucional (80% da capacidade teórica)
    safe_capacity = int(capacity_accounts * 0.8)
    
    report = {
        "vps_id": settings.V2_VPS_ID,
        "hardware": {
            "ram_total_mb": round(ram_total, 2),
            "cpu_cores": cpu_count
        },
        "assumptions": {
            "ram_per_terminal_mb": RAM_PER_TERMINAL_MB,
            "accounts_per_terminal": settings.POOL_CAPACITY
        },
        "limits": {
            "theoretical_max_accounts": capacity_accounts,
            "institutional_safe_limit": safe_capacity,
            "recommended_terminals": int(safe_capacity / settings.POOL_CAPACITY)
        }
    }
    
    print("\n" + "="*40)
    print("      VPS CAPACITY ESTIMATOR V2")
    print("="*40)
    print(f"RAM Total: {report['hardware']['ram_total_mb']} MB")
    print(f"CPU Cores: {report['hardware']['cpu_cores']}")
    print("-" * 40)
    print(f"Capacidade Teórica: {report['limits']['theoretical_max_accounts']} contas")
    print(f"LIMITE SEGURO: {report['limits']['institutional_safe_limit']} contas")
    print(f"Terminais Recomendados: {report['limits']['recommended_terminals']}")
    print("="*40 + "\n")
    
    return report

if __name__ == "__main__":
    estimate_capacity()
