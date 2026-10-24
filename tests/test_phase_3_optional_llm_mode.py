from agent.llm_agent import LLMAgent


class FakeClient:
    def __init__(self):
        self.calls = []

    def complete(self, *, prompt, model):
        self.calls.append((prompt, model))
        return '{"plan": [{"tool": "file.read", "params": {"path": "notes/q3.txt"}, "reason": "Read the notes to summarise them."}]}'


def test_llm_agent_proposes_json_plan_without_touching_guardrails(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = FakeClient()
    agent = LLMAgent(client=client, model="fake-model")
    result = agent.propose_plan("Read the Q3 notes.", client=client)

    assert result["enabled"] is True
    assert result["model"] == "fake-model"
    assert result["plan"][0]["tool"] == "file.read"
    assert client.calls


def test_llm_agent_is_disabled_with_clear_message_when_no_key_or_client(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = LLMAgent().propose_plan("Read the Q3 notes.")

    assert result["enabled"] is False
    assert "LLM mode disabled" in result["message"]
