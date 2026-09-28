from __future__ import annotations
import requests
from openai import OpenAI
from src.utils.config import get_settings

class LLMClient:
    def __init__(self):
        self.s = get_settings()

    def generate(self, user_prompt: str, system_prompt: str = "You are a careful analytics assistant.", max_output_tokens: int = 1500) -> str:
        provider = self.s.llm_provider.lower()
        if provider == "openai":
            if not self.s.openai_api_key:
                raise RuntimeError("OPENAI_API_KEY is not set. Add it to .env or set LLM_PROVIDER=ollama.")
            client = OpenAI(api_key=self.s.openai_api_key)
            r = client.responses.create(
                model=self.s.openai_model,
                instructions=system_prompt,
                input=user_prompt,
                max_output_tokens=max_output_tokens,
            )
            return r.output_text.strip()
        if provider == "ollama":
            r = requests.post(
                f"{self.s.ollama_base_url.rstrip('/')}/api/generate",
                json={"model": self.s.ollama_model, "prompt": f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}", "stream": False},
                timeout=120,
            )
            r.raise_for_status()
            return r.json()["response"].strip()
        raise ValueError(f"Unknown LLM_PROVIDER={self.s.llm_provider}")

    def embed_openai(self, texts: list[str]) -> list[list[float]]:
        if not self.s.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        client = OpenAI(api_key=self.s.openai_api_key)
        r = client.embeddings.create(model=self.s.openai_embedding_model, input=texts)
        return [x.embedding for x in r.data]
