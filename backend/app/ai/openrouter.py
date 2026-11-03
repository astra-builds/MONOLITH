import json, httpx
from .base import AIProvider, EXTRACTION_PROMPT, ProviderError

class OpenRouterProvider(AIProvider):
    def capabilities(self):
        return {"structured_output": True, "tool_calling": True, "streaming": True}

    def _post(self, messages):
        try:
            r = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": messages},
                timeout=60,
            )
            r.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderError("OpenRouter request timed out", kind="timeout", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            kind = "authentication" if exc.response.status_code in (401, 403) else "rate_limit" if exc.response.status_code == 429 else "provider_error"
            raise ProviderError(f"OpenRouter request failed ({exc.response.status_code})", kind=kind, retryable=kind == "rate_limit") from exc
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
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderError("OpenRouter returned malformed structured output", kind="malformed_output", retryable=True) from exc
    def chat(self, text):
        if not self.is_configured():
            raise RuntimeError("OpenRouter not configured")
        return self._post([{"role":"user","content":text}])
