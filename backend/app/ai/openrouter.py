import json, httpx
from .base import AIProvider, EXTRACTION_PROMPT, ProviderError
from .tools.registry import tool_schemas

class OpenRouterProvider(AIProvider):
    def capabilities(self):
        return {"structured_output": False, "tool_calling": True, "streaming": False}

    def tool_schemas(self):
        return tool_schemas()

    def chat_turn(self, messages, tools=None):
        if not self.is_configured():
            raise ProviderError("OpenRouter not configured", kind="authentication")
        try:
            wire_messages = []
            for message in messages:
                item = {key: value for key, value in message.items() if key not in ("tool_name", "result")}
                if message.get("tool_calls"):
                    item["tool_calls"] = [{
                        "id": call.get("id") or f"call_{index}",
                        "type": "function",
                        "function": {"name": call["name"], "arguments": json.dumps(call.get("arguments", {}))},
                    } for index, call in enumerate(message["tool_calls"])]
                if message.get("role") == "tool" and message.get("tool_call_id") is None:
                    item["tool_call_id"] = "call_0"
                wire_messages.append(item)
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={"model": self.model, "messages": wire_messages, "tools": tools or self.tool_schemas(), "tool_choice": "auto"},
                timeout=60,
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
        except httpx.TimeoutException as exc:
            raise ProviderError("OpenRouter request timed out", kind="timeout", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            kind = "authentication" if exc.response.status_code in (401, 403) else "rate_limit" if exc.response.status_code == 429 else "provider_error"
            raise ProviderError(f"OpenRouter request failed ({exc.response.status_code})", kind=kind, retryable=kind == "rate_limit") from exc
        calls = []
        for call in message.get("tool_calls", []) or []:
            function = call.get("function", {})
            try:
                arguments = json.loads(function.get("arguments", "{}"))
            except json.JSONDecodeError as exc:
                raise ProviderError("OpenRouter returned malformed tool arguments", kind="malformed_output", retryable=True) from exc
            calls.append({"id": call.get("id"), "name": function.get("name"), "arguments": arguments})
        return {"content": message.get("content") or "", "tool_calls": calls, "raw": response.json()}

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
