import csv

import agent


def test_log_is_append_only_and_has_exact_fields(tmp_path, monkeypatch):
    log_file = tmp_path / "conversation_log.csv"
    monkeypatch.setattr(agent, "LOG_FILE", log_file)
    agent.log_event("user", "Primera sesión")
    agent.log_event("agent", "Respuesta", "list_inventory")
    first_content = log_file.read_text(encoding="utf-8")
    agent.log_event("tool", "[]", "list_inventory")
    second_content = log_file.read_text(encoding="utf-8")
    assert second_content.startswith(first_content)
    with log_file.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert list(rows[0]) == ["actor", "message", "tool_call", "timestamp"]
    assert len(rows) == 3
    assert rows[1]["tool_call"] == "list_inventory"
    assert "T" in rows[0]["timestamp"]
