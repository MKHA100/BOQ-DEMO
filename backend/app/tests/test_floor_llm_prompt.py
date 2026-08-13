from __future__ import annotations


def test_floor_prompt_is_strict_and_geometry_safe():
    from app.floors.llm_room_prompt import ROOM_PROMPT_VERSION, build_floor_room_prompt

    prompt = build_floor_room_prompt().lower()
    assert ROOM_PROMPT_VERSION
    assert "original floor crop" in prompt
    assert "never invent" in prompt
    assert "json schema" in prompt
    assert "do not draw" in prompt
    assert "do not return area" in prompt
    assert "room_suggestion_id" in prompt
