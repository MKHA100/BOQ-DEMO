from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import settings
from app.specifications.schemas import extraction_model

RESPONSES_URL = "https://api.openai.com/v1/responses"

CATEGORY_PROMPTS = {
    "door_schedule": (
        "Extract every clearly supported door schedule row. Capture type code, dimensions in millimetres, "
        "material, frame material, finish, fire rating, quantity, source page and a short source text excerpt."
    ),
    "window_schedule": (
        "Extract every clearly supported window schedule row. Capture type code, dimensions in millimetres, "
        "frame material, glass type, finish, quantity, source page and a short source text excerpt."
    ),
    "wall_schedule": (
        "Extract every clearly supported wall type. Capture code, nominal thickness in millimetres, material, "
        "internal or external use, cavity information, finish, bond, mortar, source page and source text."
    ),
    "floor_schedule": (
        "Extract every clearly supported floor finish or floor type row. Capture floor type code, finish, material, "
        "room or zone, tile size, screed, skirting, source page and source text."
    ),
    "specification": (
        "Extract clearly supported specification facts grouped into useful sections. Capture brick or block type, "
        "mortar, wall finishes, floor finishes, door and window materials, glazing, paint and joinery information."
    ),
    "other": (
        "Extract useful supporting construction notes as concise titled rows. Keep only facts visible in the source."
    ),
}

COMMON_RULES = (
    "Return only values supported by the supplied page text or page images. Never calculate wall lengths, floor areas, "
    "room areas or other geometry. Do not invent missing values. Use null for unavailable optional values. "
    "Preserve the page number and a short exact source excerpt where possible."
)


class OpenAiScheduleExtractionProvider:
    def is_configured(self) -> bool:
        return bool(settings.openai_api_key and settings.openai_extraction_model)

    def extract(self, category: str, pages: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
        if not self.is_configured() or not pages:
            return None
        model_type = extraction_model(category)
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": f"{CATEGORY_PROMPTS[category]}\n\n{COMMON_RULES}\n\n{self._page_text(pages)}",
            }
        ]
        for page in pages[: settings.openai_extraction_max_pages]:
            image = page.get("image_data_url")
            if image:
                content.append({"type": "input_image", "image_url": image, "detail": "high"})
        payload = {
            "model": settings.openai_extraction_model,
            "input": [{"role": "user", "content": content}],
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": f"autoboq_{category}",
                    "strict": True,
                    "schema": self._strict_schema(model_type.model_json_schema()),
                }
            },
        }
        request = urllib.request.Request(
            RESPONSES_URL,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.openai_extraction_timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            return None
        output_text = self._output_text(response_payload)
        if not output_text:
            return None
        try:
            validated = model_type.model_validate_json(output_text)
        except Exception:
            return None
        return [row.model_dump(mode="json") for row in validated.rows]

    @classmethod
    def _strict_schema(cls, value: Any) -> Any:
        if isinstance(value, list):
            return [cls._strict_schema(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: cls._strict_schema(item) for key, item in value.items() if key != "default"}
        if result.get("type") == "object" or "properties" in result:
            properties = result.get("properties")
            if isinstance(properties, dict):
                result["required"] = list(properties.keys())
            result["additionalProperties"] = False
        return result

    @staticmethod
    def _page_text(pages: list[dict[str, Any]]) -> str:
        blocks: list[str] = []
        remaining = 120_000
        for page in pages:
            text = str(page.get("text") or "").strip()
            if not text:
                continue
            block = f"--- Page {page.get('page_number')} ---\n{text}"
            if len(block) > remaining:
                block = block[:remaining]
            blocks.append(block)
            remaining -= len(block)
            if remaining <= 0:
                break
        return "\n\n".join(blocks) or "No reliable vector text was found. Read the attached page images."

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str | None:
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct
        output = payload.get("output")
        if not isinstance(output, list):
            return None
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    return part["text"]
        return None


openai_schedule_extraction_provider = OpenAiScheduleExtractionProvider()
