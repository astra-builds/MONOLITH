import json, httpx
from .base import AIProvider, EXTRACTION_PROMPT

class OpenRouterProvider(AIProvider):
    def _post(self, messages):
        r = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    def extract(self, text):
        if not self.is_configured():
            raise RuntimeError("OpenRouter not configured")
        content = self._post([{"role":"user","content": EXTRACTION_PROMPT + text}])
        content = content.strip()
        if content.startswith("```"):
            content = content.strip("`")
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    def chat(self, text):
        if not self.is_configured():
            raise RuntimeError("OpenRouter not configured")
        return self._post([{"role":"user","content":text}])
