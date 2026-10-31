import json, httpx
from .base import AIProvider, EXTRACTION_PROMPT

class GeminiProvider(AIProvider):
    def extract(self, text):
        if not self.is_configured():
            raise RuntimeError("Gemini not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        prompt = EXTRACTION_PROMPT + text
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        r = httpx.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        txt = data["candidates"][0]["content"]["parts"][0]["text"]
        # strip code fences
        txt = txt.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.startswith("json"):
                txt = txt[4:]
        return json.loads(txt)
    def chat(self, text):
        if not self.is_configured():
            raise RuntimeError("Gemini not configured")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        r = httpx.post(url, json={"contents":[{"parts":[{"text":text}]}]}, timeout=60)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
