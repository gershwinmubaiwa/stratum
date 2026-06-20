from pydantic import BaseModel, Field
from typing import List

class TelemetryScores(BaseModel):
    market_validation: float = Field(ge=0, le=100)
    capital_efficiency: float = Field(ge=0, le=100)
    execution_risk: float = Field(ge=0, le=100)

def compute_telemetry(prior_scores, agent_id, turn_index, transcript, concept_text):
    if prior_scores is None:
        return TelemetryScores(market_validation=50.0, capital_efficiency=50.0, execution_risk=50.0)
    base = prior_scores.dict()
    if agent_id == "CEO":
        base["capital_efficiency"] = min(100, base["capital_efficiency"] + 5)
        base["execution_risk"] = min(100, base["execution_risk"] + 3)
    elif agent_id == "CFO":
        base["capital_efficiency"] = min(100, base["capital_efficiency"] + 8)
        base["market_validation"] = max(0, base["market_validation"] - 5)
    elif agent_id == "CMO":
        base["market_validation"] = min(100, base["market_validation"] + 10)
        base["execution_risk"] = max(0, base["execution_risk"] - 5)
    if turn_index > 3:
        base["market_validation"] = (base["market_validation"] + 60) / 2
        base["capital_efficiency"] = (base["capital_efficiency"] + 60) / 2
        base["execution_risk"] = (base["execution_risk"] + 40) / 2
    for key in ["market_validation", "capital_efficiency", "execution_risk"]:
        base[key] = max(0, min(100, base[key]))
    return TelemetryScores(**base)
