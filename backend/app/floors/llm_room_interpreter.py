from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.floors.llm_room_cache import llm_room_cache
from app.floors.llm_room_context_service import llm_room_context_service
from app.floors.llm_room_prompt import ROOM_PROMPT_VERSION, build_floor_room_prompt
from app.floors.llm_room_schema import FloorRoomInterpretation, floor_room_response_schema
from app.floors.room_result_validator import room_result_validator
from app.floors.room_semantics import room_semantics


class LLMRoomInterpreter:
    """One multimodal, structured interpretation per floor.

    The request has no open database transaction. It may label supplied room
    suggestions and match printed evidence, but it cannot supply quantity
    geometry or area.
    """

    endpoint = "https://api.openai.com/v1/responses"

    def should_run(self, room: dict[str, Any]) -> bool:
        """Backward-compatible room ambiguity helper used by older callers."""
        if not getattr(settings, "room_llm_enabled", True) or not getattr(
            settings, "openai_api_key", None
        ):
            return False
        if not getattr(settings, "room_llm_only_when_ambiguous", False):
            return True
        name = str(room.get("name") or "")
        return not name or name.lower().startswith("room ") or bool(
            re.search(r"\d{3,}|\b[AB]\b", name)
        )

    def interpret(self, text: str) -> dict[str, Any]:
        """Keep the original local text API for existing integrations/tests."""
        local = room_semantics.classify(text)
        return {
            **local,
            "source": "local",
        }

    def interpret_floor(self, project_id: str, floor_id: str) -> dict[str, Any]:
        if not getattr(settings, "room_llm_enabled", True) or not getattr(
            settings, "room_llm_background_enabled", True
        ):
            return {"status": "disabled", "floor_id": floor_id, "rooms": []}
        if not getattr(settings, "openai_api_key", None):
            return {"status": "not_configured", "floor_id": floor_id, "rooms": []}

        prepared = llm_room_context_service.build(project_id, floor_id)
        context = prepared["context"]
        if not context.get("room_suggestions"):
            return {
                "status": "not_needed",
                "floor_id": floor_id,
                "rooms": [],
                "warning": "No current room suggestions require interpretation.",
            }
        if getattr(settings, "room_llm_only_when_ambiguous", False):
            rooms = context.get("rooms") or []
            if rooms and not any(self.should_run(room) for room in rooms):
                return {
                    "status": "not_needed",
                    "floor_id": floor_id,
                    "rooms": [],
                }
        versions = prepared["versions"]
        model = getattr(settings, "room_llm_model", "gpt-5.5")
        identity = {
            "project_id": project_id,
            "floor_id": floor_id,
            "crop_version": int(versions.get("crop_version") or 0),
            "wall_version": int(versions.get("wall_version") or 0),
            "scale_version": int(versions.get("scale_version") or 0),
            "prompt_version": ROOM_PROMPT_VERSION,
            "model": model,
        }
        exact = llm_room_cache.get_exact(**identity)
        if exact and exact.get("status") == "ready":
            return self._cached_result(exact, "cached")
        if (
            exact
            and exact.get("status") == "failed"
            and int(exact.get("attempt_count") or 0)
            >= int(getattr(settings, "room_llm_max_floor_calls", 1))
        ):
            return {
                "status": "failed",
                "floor_id": floor_id,
                "run_id": exact.get("id"),
                "rooms": [],
                "warning": exact.get("error_message") or "Room interpretation was unavailable.",
                "cached": True,
            }
        reusable = llm_room_cache.find_reusable(
            project_id=project_id,
            floor_id=floor_id,
            crop_version=identity["crop_version"],
            wall_version=identity["wall_version"],
            prompt_version=ROOM_PROMPT_VERSION,
            model=model,
        )
        if reusable:
            return self._cached_result(reusable, "cached_scale_reuse")

        run = llm_room_cache.begin(**identity, input_hash=prepared["input_hash"])
        if not run.get("claimed"):
            if run.get("status") == "ready":
                return self._cached_result(run, "cached")
            return {
                "status": "processing",
                "floor_id": floor_id,
                "run_id": run.get("id"),
                "rooms": [],
            }

        run_id = str(run["id"])
        raw: dict[str, Any] = {}
        try:
            parsed, raw = self._request(
                context,
                prepared["image_url"],
                model,
                prepared.get("room_crop_urls") or [],
            )
            validated = room_result_validator.validate(parsed, context)
            results = self._attach_room_ids(validated["rooms"], context)
            saved = llm_room_cache.complete(
                run_id,
                raw_response=raw,
                validated_response=validated["response"],
                results=results,
            )
            return {
                "status": "ready",
                "floor_id": floor_id,
                "run_id": saved.get("id") or run_id,
                "rooms": results,
                "warnings": validated["warnings"],
                "rejected": validated["rejected"],
                "cached": False,
            }
        except Exception as exc:
            llm_room_cache.fail(run_id, str(exc), raw)
            return {
                "status": "failed",
                "floor_id": floor_id,
                "run_id": run_id,
                "rooms": [],
                "warning": str(exc),
            }

    def _request(
        self, context: dict[str, Any], image_url: str, model: str,
        room_crop_urls: list[str] | None = None,
    ) -> tuple[FloorRoomInterpretation, dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": "Coordinate-aligned evidence for the selected floor:\n"
                + json.dumps(context, separators=(",", ":"), ensure_ascii=False, default=str),
            },
            {"type": "input_image", "image_url": image_url, "detail": "high"},
        ]
        content.extend(
            {"type": "input_image", "image_url": value, "detail": "high"}
            for value in (room_crop_urls or [])
        )
        payload: dict[str, Any] = {
            "model": model,
            "instructions": build_floor_room_prompt(),
            "input": [{"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "floor_room_interpretation",
                    "strict": True,
                    "schema": floor_room_response_schema(),
                }
            },
        }
        last_raw: dict[str, Any] = {}
        last_error: Exception | None = None
        for attempt in range(2):
            if attempt:
                payload["input"] = [
                    *payload["input"],
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": "The prior output was invalid. Return one valid JSON value matching the schema exactly.",
                            }
                        ],
                    },
                ]
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=float(getattr(settings, "room_llm_timeout_seconds", 60)),
            )
            if response.status_code == 429 and attempt == 0:
                # A temporary provider quota spike must not permanently turn
                # every room into "Room N". Honour a short Retry-After value,
                # then make the second and final floor-level attempt.
                retry_after = response.headers.get("Retry-After", "1")
                try:
                    delay = max(0.0, min(float(retry_after), 5.0))
                except (TypeError, ValueError):
                    delay = 1.0
                if delay:
                    time.sleep(delay)
                continue
            response.raise_for_status()
            value = response.json()
            last_raw = value if isinstance(value, dict) else {"response": value}
            try:
                output_text = self._output_text(last_raw)
                return FloorRoomInterpretation.model_validate_json(
                    self._json_value(output_text)
                ), last_raw
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = exc
        raise ValueError(f"Room interpretation returned invalid structured JSON: {last_error}")

    @staticmethod
    def _output_text(data: dict[str, Any]) -> str:
        direct = data.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        parts: list[str] = []
        for output in data.get("output") or []:
            if not isinstance(output, dict):
                continue
            for content in output.get("content") or []:
                if not isinstance(content, dict):
                    continue
                if content.get("type") in {"output_text", "text"} and isinstance(
                    content.get("text"), str
                ):
                    parts.append(content["text"])
        if not parts:
            raise ValueError("Responses API returned no output text.")
        return "\n".join(parts)

    @staticmethod
    def _json_value(value: str) -> str:
        text = value.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start:
            raise ValueError("No JSON object was returned.")
        return text[start : end + 1]

    @staticmethod
    def _attach_room_ids(
        results: list[dict[str, Any]], context: dict[str, Any]
    ) -> list[dict[str, Any]]:
        suggestions = {
            str(item.get("id")): item for item in context.get("room_suggestions") or []
        }
        output: list[dict[str, Any]] = []
        for result in results:
            suggestion = suggestions.get(str(result.get("room_suggestion_id"))) or {}
            room_id = suggestion.get("matched_room_id")
            if not room_id:
                suggestion_polygon = room_result_validator_polygon(suggestion)
                best_score = 0.0
                for room in context.get("rooms") or []:
                    polygon = room_result_validator_polygon(
                        {"polygon": room.get("model_polygon") or room.get("wall_corrected_polygon")}
                    )
                    score = room_polygon_builder_iou(suggestion_polygon, polygon)
                    if score > best_score:
                        best_score, room_id = score, room.get("id")
                if best_score < 0.15:
                    room_id = None
            output.append({**result, "room_id": room_id})
        return output

    @staticmethod
    def _cached_result(run: dict[str, Any], status: str) -> dict[str, Any]:
        results = llm_room_cache.results(str(run["id"]))
        rooms = [item.get("result") or {} for item in results]
        return {
            "status": status,
            "floor_id": run.get("floor_id"),
            "run_id": run.get("id"),
            "rooms": rooms,
            "warnings": (run.get("validated_response") or {}).get("warnings") or [],
            "cached": True,
        }


def room_result_validator_polygon(item: dict[str, Any]):
    from app.floors.polygon_builder import room_polygon_builder

    return room_polygon_builder.points_to_polygon(
        ((item.get("polygon") or {}).get("points") or item.get("points") or [])
    )


def room_polygon_builder_iou(first: Any, second: Any) -> float:
    from app.floors.polygon_builder import room_polygon_builder

    if first.is_empty or second.is_empty:
        return 0.0
    return room_polygon_builder.iou(first, second)


llm_room_interpreter = LLMRoomInterpreter()

__all__ = ["LLMRoomInterpreter", "llm_room_interpreter"]
