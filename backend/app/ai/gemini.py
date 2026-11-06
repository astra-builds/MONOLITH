import json, httpx
from .base import AIProvider, EXTRACTION_PROMPT, ProviderError
from .tools.registry import tool_schemas

class GeminiProvider(AIProvider):
    def capabilities(self):
        return {"structured_output": False, "tool_calling": True, "streaming": False}

    def tool_schemas(self):
        return tool_schemas()

    def chat_turn(self, messages, tools=None):
        if not self.is_configured():
            raise ProviderError("Gemini not configured", kind="authentication")
        contents = []
        for message in messages:
            role = "model" if message["role"] == "assistant" else "user"
            parts = []
            if message.get("content"):
                parts.append({"text": message["content"]})
            for call in message.get("tool_calls", []):
                parts.append({"functionCall": {"name": call["name"], "args": call.get("arguments", {})}})
            if message.get("tool_name"):
                result = message.get("result", {})
                if message.get("content"):
                    try:
                        result = json.loads(message["content"])
                    except json.JSONDecodeError:
                        result = {"content": message["content"]}
                parts.append({"functionResponse": {"name": message["tool_name"], "response": result}})
            contents.append({"role": role, "parts": parts})
        declarations = [{"name": item["function"]["name"], "description": item["function"]["description"], "parameters": item["function"]["parameters"]} for item in (tools or self.tool_schemas())]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        try:
            response = httpx.post(url, json={"contents": contents, "tools": [{"function_declarations": declarations}]}, timeout=60)
            response.raise_for_status()
            parts = response.json()["candidates"][0]["content"]["parts"]
        except httpx.TimeoutException as exc:
            raise ProviderError("Gemini request timed out", kind="timeout", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            kind = "authentication" if exc.response.status_code in (401, 403) else "rate_limit" if exc.response.status_code == 429 else "provider_error"
            raise ProviderError(f"Gemini request failed ({exc.response.status_code})", kind=kind, retryable=kind == "rate_limit") from exc
        calls = []
        text_parts = []
        for part in parts:
            if part.get("text"):
                text_parts.append(part["text"])
            if part.get("functionCall"):
                call = part["functionCall"]
                calls.append({"name": call["name"], "arguments": call.get("args", {})})
        return {"content": "\n".join(text_parts), "tool_calls": calls, "raw": response.json()}

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
