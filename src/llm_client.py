"""Wrapper around the Gemini API: retries, timeouts, caching, model fallback, JSON handling."""

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from src.utils import parse_json

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM call fails after all retries and fallbacks."""


class LLMClient:
    """Small, reusable client for calling the Gemini API."""

    def __init__(self, config: dict) -> None:
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or "paste_your" in api_key or "your_api_key" in api_key:
            raise LLMError(
                "GEMINI_API_KEY is missing. Put your real key in the .env file."
            )

        llm_cfg = config["llm"]
        self.model: str = llm_cfg["model"]
        self.fallback_models: list[str] = llm_cfg.get("fallback_models", [])
        self.default_temperature: float = llm_cfg.get("temperature", 0.2)
        self.max_output_tokens: int = llm_cfg.get("max_output_tokens", 8192)
        self.max_retries: int = llm_cfg.get("max_retries", 2)
        self.retry_base_delay: float = llm_cfg.get("retry_base_delay", 2)
        self._cache: dict[str, str] = {}

        timeout_ms = int(llm_cfg.get("timeout_seconds", 45)) * 1000
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=timeout_ms),
        )

    def _call_with_retries(
        self, model: str, user_prompt: str, gen_config: types.GenerateContentConfig
    ) -> str:
        """Call one model, retrying with exponential backoff on temporary errors."""
        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Calling %s (attempt %d/%d)", model, attempt, self.max_retries)
                response = self._client.models.generate_content(
                    model=model, contents=user_prompt, config=gen_config
                )
                text = (response.text or "").strip()
                if not text:
                    raise ValueError("The model returned an empty response.")
                return text
            except errors.ClientError as exc:
                # 429 = rate limit (worth retrying). Other 4xx = our mistake (bad key, bad model).
                if exc.code != 429:
                    raise LLMError(f"{model} rejected the request ({exc.code}): {exc.message}") from exc
                last_error = exc
            except Exception as exc:  # server errors, timeouts, empty replies
                last_error = exc

            if attempt < self.max_retries:
                delay = self.retry_base_delay * (2 ** (attempt - 1))
                logger.warning("Call failed (%s). Retrying in %.0fs...", last_error, delay)
                time.sleep(delay)

        raise LLMError(f"{model} failed after {self.max_retries} attempts: {last_error}")

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> str:
        """Send a prompt to the model and return the reply text.

        Tries the main model first, then each fallback model in order.
        Identical requests are served from an in-memory cache.
        """
        temp = self.default_temperature if temperature is None else temperature
        models_to_try = [self.model, *self.fallback_models]

        cache_key = hashlib.sha256(
            f"{models_to_try}|{temp}|{json_mode}|{system_prompt}|{user_prompt}".encode()
        ).hexdigest()
        if cache_key in self._cache:
            logger.info("Cache hit - skipping API call")
            return self._cache[cache_key]

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temp,
            max_output_tokens=self.max_output_tokens,
            response_mime_type="application/json" if json_mode else "text/plain",
        )

        last_error: Optional[Exception] = None
        for model in models_to_try:
            try:
                text = self._call_with_retries(model, user_prompt, gen_config)
                self._cache[cache_key] = text
                return text
            except LLMError as exc:
                last_error = exc
                logger.warning("Model %s failed. Trying next model if available.", model)

        raise LLMError(f"All models failed. Last error: {last_error}")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        parse_retries: int = 1,
    ) -> Any:
        """Call the model in JSON mode and return parsed JSON.

        If the reply is not valid JSON, asks the model once more to fix it.
        """
        prompt = user_prompt
        for _ in range(parse_retries + 1):
            raw = self.generate(system_prompt, prompt, temperature, json_mode=True)
            try:
                return parse_json(raw)
            except json.JSONDecodeError:
                logger.warning("Reply was not valid JSON. Asking the model to retry.")
                prompt = (
                    user_prompt
                    + "\n\nYour previous reply was not valid JSON. "
                    "Return ONLY valid JSON that matches the structure above."
                )
        raise LLMError("The model did not return valid JSON.")