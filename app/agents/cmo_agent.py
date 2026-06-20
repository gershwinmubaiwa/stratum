from .base_agent import BaseAgent
class CMOAgent(BaseAgent):
    def system_prompt(self): return "You are the CMO... market-savvy, persuasive."
    def user_prompt(self, concept, transcript, interjection=None):
        base = f"Concept: {concept}\n\nPrior debate transcript:\n" + "\n".join(transcript[-5:])
        if interjection: base += f"\n\nInterjection: {interjection}."
        return base
