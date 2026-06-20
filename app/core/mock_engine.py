import asyncio
from typing import AsyncGenerator, Tuple
from app.config import MOCK_CHUNK_DELAY_MS, MOCK_CHUNK_SIZE

SAAS_SCRIPT = [
    "CEO: We're launching a vertical SaaS for independent pharmacies. Our initial focus will be inventory management and patient engagement. We'll target 500 pharmacies in year one, with a subscription model at $199/month.",
    "CFO: The financials show a $1.2M burn rate to reach 500 customers. At $199/month, breakeven requires 650 subscribers. We should consider a tiered pricing.",
    "CMO: The market is crowded, but our differentiator is AI-driven predictive restocking. We should highlight that in our messaging.",
    "CEO: Synthesizing: we adopt a two-tier pricing: Basic ($99) and Pro ($199). We'll focus initial sales on 100 beta pharmacies.",
    "CMO: Final convergence: Our AI predictive restocking is the killer feature. We'll partner with a major pharmacy association."
]
SAAS_INTERJECTIONS = {
    "europe": ["CEO: Great insight on Europe. We'll adapt our pricing to EUR99/EUR199 and address GDPR.", "CFO: Budget an extra $200k for legal and localization.", "CMO: We'll run a targeted LinkedIn campaign in the DACH region."],
    "default": ["CEO: Acknowledging. We'll pivot to focus on the core AI engine.", "CFO: This reduces development costs by 30%.", "CMO: We'll re-target our messaging to emphasize speed."]
}
RETAIL_SCRIPT = [
    "CEO: We're launching a direct-to-consumer sustainable fashion brand. We aim for $500k revenue in year one.",
    "CFO: Initial inventory investment is $150k, plus $50k for marketing. We project break-even at $400k revenue.",
    "CMO: The eco-conscious consumer segment is growing 25% annually. We'll use Instagram and TikTok.",
    "CEO: We'll adopt a pre-order model to reduce inventory risk.",
    "CMO: Final convergence: We'll launch with a limited drop to build hype, then expand."
]
RETAIL_INTERJECTIONS = {
    "online": ["CEO: We'll double down on online sales, investing in better UX.", "CFO: This increases marketing spend by $20k but expands reach.", "CMO: We'll run targeted ads on Pinterest."],
    "default": ["CEO: We'll shift our strategy to focus on a niche demographic.", "CFO: This reduces marketing waste.", "CMO: We'll create a dedicated content hub."]
}
FOOD_SCRIPT = [
    "CEO: We're launching a ghost kitchen concept for healthy meal delivery. We target $1M revenue in year two.",
    "CFO: Startup costs: $200k for kitchen equipment, $50k for marketing. We project a 20% net margin.",
    "CMO: The meal delivery market is saturated, but our differentiator is real-time nutrition tracking.",
    "CEO: We'll start with a limited menu to perfect operations.",
    "CFO: Final convergence: With a subscription model, we improve revenue predictability."
]
FOOD_INTERJECTIONS = {
    "delivery": ["CEO: We'll optimize delivery routes using AI.", "CFO: This could increase margins by 5%.", "CMO: We'll market our delivery efficiency."],
    "default": ["CEO: We'll pivot to a more premium positioning.", "CFO: This raises COGS but allows higher price points.", "CMO: We'll build a brand around farm-to-table."]
}
DEFAULT_SCRIPT = SAAS_SCRIPT
DEFAULT_INTERJECTIONS = SAAS_INTERJECTIONS
SCRIPT_MAP = [(["saas","software","cloud","app"], (SAAS_SCRIPT, SAAS_INTERJECTIONS)), (["retail","product","store"], (RETAIL_SCRIPT, RETAIL_INTERJECTIONS)), (["food","restaurant","meal"], (FOOD_SCRIPT, FOOD_INTERJECTIONS))]

def _select_script(concept_text):
    for keywords, script_tuple in SCRIPT_MAP:
        if any(kw in concept_text.lower() for kw in keywords): return script_tuple
    return (DEFAULT_SCRIPT, DEFAULT_INTERJECTIONS)

def _get_pivot_branch(text, interjection_map):
    for keyword, branch in interjection_map.items():
        if keyword in text.lower(): return branch
    return interjection_map["default"]

class MockEngine:
    @staticmethod
    async def generate_stream(agent_id, concept_text, turn_index, prior_transcript, interjection_directive=None, current_state=None):
        script, interjection_map = _select_script(concept_text)
        if interjection_directive:
            branch = _get_pivot_branch(interjection_directive, interjection_map)
            agent_index = {"CEO":0,"CFO":1,"CMO":2}.get(agent_id,0)
            full_text = branch[agent_index] if agent_index < len(branch) else f"{agent_id}: Acknowledging the interjection."
        else:
            full_text = script[turn_index] if turn_index < len(script) else f"{agent_id}: Final convergence."
        for i in range(0, len(full_text), MOCK_CHUNK_SIZE):
            yield full_text[i:i+MOCK_CHUNK_SIZE]
            await asyncio.sleep(MOCK_CHUNK_DELAY_MS / 1000.0)

    @staticmethod
    def get_mock_complete_turn(agent_id, turn_index, concept_text, interjection_directive=None, current_state=None):
        script, interjection_map = _select_script(concept_text)
        if interjection_directive:
            branch = _get_pivot_branch(interjection_directive, interjection_map)
            agent_index = {"CEO":0,"CFO":1,"CMO":2}.get(agent_id,0)
            return branch[agent_index] if agent_index < len(branch) else f"{agent_id}: Acknowledging.", {}
        return script[turn_index] if turn_index < len(script) else f"{agent_id}: Final.", {}
