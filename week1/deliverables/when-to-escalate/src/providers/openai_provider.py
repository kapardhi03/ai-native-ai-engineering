"""providers/openai_provider.py — belief from the OpenAI chat completions API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .base import Provider, ProviderError
from .json_utils import extract_json
from .prompt import SYSTEM_PROMPT, render_observation

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class OpenAIProvider(Provider):
    name = "openai"
    is_llm = True

    def model_name(self, settings: "Settings") -> str:
        return settings.openai_model

    def is_available(self, settings: "Settings") -> bool:
        return settings.has_key("openai")

    def generate_raw(self, message: str, settings: "Settings", context=None) -> dict:
        # Imported here so the package works without the SDK installed.
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                self.name,
                "the `openai` package is not installed (pip install -r requirements.txt)",
            ) from exc

        model = settings.openai_model
        logger.debug("OpenAI call (model=%s).", model)

        # Key is passed explicitly rather than read from the ambient environment,
        # so config.py stays the single place configuration resolves.
        client = OpenAI(api_key=settings.require_key("openai"))
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": render_observation(message, context)},
            ],
            response_format={"type": "json_object"},
            temperature=0,  # belief is cached, but a deterministic call still helps
        )
        return extract_json(response.choices[0].message.content)
