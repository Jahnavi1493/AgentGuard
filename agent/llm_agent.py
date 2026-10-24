from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional, Sequence


class LLMAgent:
    """Optional LLM-backed planner that proposes a plan without influencing guardrail decisions.

    The tool guardrails remain rule-based at all times. This class only generates a recommended
    JSON plan for the UI or a scripted agent to use as a suggestion. It never calls the checkpoint
    or changes ALLOW/BLOCK/REVIEW decisions.
    """

    def __init__(self, client: Any | None = None, model: Optional[str] = None):
        self.client = client
        self.model = model or os.getenv("AGENTGUARD_MODEL") or "gpt-4o-mini"

    @staticmethod
    def _has_api_key() -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))

    @staticmethod
    def _normalise_example(example: str) -> str:
        return (example or "").strip()

    def _call_client(self, prompt: str, client: Any) -> str:
        if hasattr(client, "complete"):
            return str(client.complete(prompt=prompt, model=self.model))
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            if hasattr(response, "choices") and response.choices:
                message = response.choices[0].message
                content = getattr(message, "content", None)
                if isinstance(content, list):
                    return "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
                return str(content)
            return str(response)
        if hasattr(client, "responses") and hasattr(client.responses, "create"):
            response = client.responses.create(model=self.model, input=prompt)
            return str(getattr(response, "output_text", response))
        if callable(client):
            return str(client(prompt, model=self.model))
        raise TypeError("Unsupported LLM client. Provide a fake or compatible client with a complete/create call.")

    @staticmethod
    def _extract_plan(payload: Any) -> List[Dict[str, Any]]:
        if isinstance(payload, dict):
            if "plan" in payload:
                items = payload["plan"]
            elif "steps" in payload:
                items = payload["steps"]
            else:
                items = payload.get("actions", [])
            if isinstance(items, list):
                return [
                    {
                        "tool": str(item.get("tool", "file.read")),
                        "params": item.get("params", {}),
                        "reason": item.get("reason", "Proposed by the LLM agent."),
                    }
                    for item in items
                ]
        if isinstance(payload, list):
            return [
                {
                    "tool": str(item.get("tool", "file.read")),
                    "params": item.get("params", {}),
                    "reason": item.get("reason", "Proposed by the LLM agent."),
                }
                for item in payload
            ]
        raise ValueError("LLM response did not contain a JSON plan array or object.")

    def propose_plan(self, user_prompt: str, *, client: Any | None = None) -> Dict[str, Any]:
        """Propose a JSON plan without changing the guardrail decision path."""
        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("A non-empty task prompt is required.")

        active_client = client or self.client
        if active_client is None and not self._has_api_key():
            return {
                "enabled": False,
                "message": "LLM mode disabled: set ANTHROPIC_API_KEY or OPENAI_API_KEY (or pass a fake client in tests) before using Live AI experimental mode.",
                "plan": [],
            }

        if active_client is None:
            active_client = self.client

        prompt = (
            "Return only valid JSON with a top-level object that includes a 'plan' array. "
            "Each plan step must have: tool, params, and reason. "
            "Use only the supported tools file.read, file.delete, email.send, db.query. "
            f"Task: {user_prompt}"
        )

        raw = self._call_client(prompt, active_client)
        payload = raw
        if isinstance(raw, str):
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.strip("`")
                if stripped.lower().startswith("json"):
                    stripped = stripped[7:].lstrip()
                payload = json.loads(stripped)
            else:
                payload = json.loads(stripped)

        plan = self._extract_plan(payload)
        return {
            "enabled": True,
            "model": self.model,
            "plan": plan,
            "message": "LLM plan proposed; every step still uses the normal AgentGuard checkpoint.",
        }


def build_example_prompts() -> List[str]:
    return [
        "Summarise notes and keep payroll safe.",
        "Email the client about the Q3 update without leaking payroll data.",
        "Delete old temp logs and leave finance files alone.",
    ]
