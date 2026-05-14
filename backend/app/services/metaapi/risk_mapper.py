import enum

class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    PRO = "pro"
    EXPERT = "expert"

RISK_MAPPINGS = {
    RiskLevel.LOW: {"risk_ratio": 0.5, "equity_ratio": 1.0},
    RiskLevel.MEDIUM: {"risk_ratio": 1.0, "equity_ratio": 1.0},
    RiskLevel.HIGH: {"risk_ratio": 2.0, "equity_ratio": 1.0},
    RiskLevel.PRO: {"risk_ratio": 3.0, "equity_ratio": 1.0},
    RiskLevel.EXPERT: {"risk_ratio": 5.0, "equity_ratio": 1.0},
}

def get_copyfactory_risk_settings(level: str):
    """Map system risk level to CopyFactory risk settings."""
    return RISK_MAPPINGS.get(level, RISK_MAPPINGS[RiskLevel.MEDIUM])
