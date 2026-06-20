import asyncio
import json
import logging
from typing import AsyncGenerator
import httpx
from app.config import CEO_API_KEY, CFO_API_KEY, CMO_API_KEY, LLM_PROVIDER, LLM_MODEL, RETRY_TOTAL_ATTEMPTS, RETRY_BACKOFF_BASE, DEMO_MODE

logger = logging.getLogger(__name__)
_AGENT_KEY_MAP = {"CEO": CEO_API_KEY, "CFO": CFO_API_KEY, "CMO": CMO_API_KEY}

class LLMClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)

    async def generate_stream(self, agent_id: str, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 800):
        if DEMO_MODE:
            raise RuntimeError("LLMClient called in DEMO_MODE")
        api_key = _AGENT_KEY_MAP.get(agent_id)
        if not api_key:
            raise ValueError(f"No API key configured for agent {agent_id}")

        if LLM_PROVIDER == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            data = {"model": LLM_MODEL, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        else:
            raise ValueError(f"Unsupported provider: {LLM_PROVIDER}")

        attempt = 0
        while attempt < RETRY_TOTAL_ATTEMPTS:
            try:
                async with self.client.stream("POST", url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            payload = line[6:]
                            if payload == "[DONE]": break
                            try:
                                chunk = json.loads(payload)
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                                if delta: yield delta
                            except: continue
                    return
            except Exception as e:
                attempt += 1
                if attempt < RETRY_TOTAL_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
                else: raise e

    async def close(self): await self.client.aclose()

llm_client = LLMClient()
