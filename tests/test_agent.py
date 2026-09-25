import json

import agent


class FakeFunction:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = json.dumps(arguments)


class FakeCall:
    def __init__(self, call_id, name, arguments):
        self.id = call_id
        self.function = FakeFunction(name, arguments)

    def model_dump(self):
        return {"id": self.id, "type": "function", "function": {"name": self.function.name, "arguments": self.function.arguments}}


class FakeMessage:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class FakeCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return type("Completion", (), {"choices": [type("Choice", (), {"message": FakeMessage(tool_calls=[FakeCall("1", "get_stock_alerts", {})])})()]})()
        return type("Completion", (), {"choices": [type("Choice", (), {"message": FakeMessage("Hay una alerta revisada.")})()]})()


class FakeClient:
    def __init__(self):
        self.chat = type("Chat", (), {"completions": FakeCompletions()})()


def test_agent_returns_tool_result_to_next_llm_iteration(monkeypatch):
    monkeypatch.setattr(agent, "get_stock_alerts", lambda threshold=10: {"low_stock": [], "out_of_stock": []})
    result = agent.Agent(FakeClient(), [{"role": "system", "content": "test"}]).respond("¿Cómo está el stock?")
    assert result == "Hay una alerta revisada."
