import json, httpx
from .base import AIProvider, EXTRACTION_PROMPT, ProviderError

class GeminiProvider(AIProvider):
    def capabilities(self):
        return {"structured_output": True, "tool_calling": True, "streaming": True}

    def extract(self, text):
        if not self.is_configured():
            raise RuntimeError("Gemini not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        prompt = EXTRACTION_PROMPT + text
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            r = httpx.post(url, json=payload, timeout=60)
            r.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderError("Gemini request timed out", kind="timeout", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            kind = "authentication" if exc.response.status_code in (401, 403) else "rate_limit" if exc.response.status_code == 429 else "provider_error"
            raise ProviderError(f"Gemini request failed ({exc.response.status_code})", kind=kind, retryable=kind == "rate_limit") from exc
        data = r.json()
        txt = data["candidates"][0]["content"]["parts"][0]["text"]
        # strip code fences
        txt = txt.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.startswith("json"):
                txt = txt[4:]
        try:
            return json.loads(txt)
        except json.JSONDecodeError as exc:
            raise ProviderError("Gemini returned malformed structured output", kind="malformed_output", retryable=True) from exc
    def chat(self, text):
        if not self.is_configured():
            raise RuntimeError("Gemini not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        r = httpx.post(url, json={"contents":[{"parts":[{"text":text}]}]}, timeout=60)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
