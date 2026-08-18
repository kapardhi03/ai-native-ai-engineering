"""providers/google_provider.py — belief from the Google Gemini API.

VERSION-SENSITIVE. Uses the newer unified `google-genai` SDK. The older
`google-generativeai` package exposes a different client surface and will not
work against this code unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import Provider, ProviderError
from .json_utils import extract_json
from .prompt import SYSTEM_PROMPT

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class GoogleProvider(Provider):
    name = "google"
    is_llm = True

    def model_name(self, settings: "Settings") -> str:
        return settings.google_model

    def is_available(self, settings: "Settings") -> bool:
        return settings.has_key("google")

    def generate_raw(self, message: str, settings: "Settings") -> dict:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProviderError(
                self.name,
                "the `google-genai` package is not installed "
                "(pip install -r requirements.txt)",
            ) from exc

        model = settings.google_model
        logger.debug("Google call (model=%s).", model)

        client = genai.Client(api_key=settings.require_key("google"))
        response = client.models.generate_content(
            model=model,
            contents=f"{SYSTEM_PROMPT}\n\nInbound message:\n{message}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
        return extract_json(response.text)
