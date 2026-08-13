from types import SimpleNamespace


def test_llm_interpreter_has_local_fallback(monkeypatch):
    from app.floors import llm_room_interpreter as module

    monkeypatch.setattr(module, "settings", SimpleNamespace(openai_api_key=None))
    result = module.llm_room_interpreter.interpret("MASTER BED ROOM 3600 3800")
    assert result["name"] == "Master Bedroom"
