"""The single place that talks to an AI model: Anthropic (Claude) or OpenAI."""

from __future__ import annotations

import logging
import os
from typing import TypeVar

from pydantic import BaseModel

from .config import Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# provider id -> display name
PROVIDERS = {"anthropic": "Anthropic", "openai": "OpenAI"}
BILLING_HINTS = {
    "anthropic": "Add credits at platform.claude.com (Plans & Billing).",
    "openai": "Add billing or credits at platform.openai.com (Billing).",
}

# Anthropic: server-side refusal fallback re-runs a declined turn on a suitable model.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# OpenAI: the first of these the key can use is chosen when the key is checked.
OPENAI_PREFERRED_MODELS = ("gpt-5.1", "gpt-5", "gpt-4.1", "gpt-4o")


class LLMError(RuntimeError):
    """The model call failed or returned nothing usable."""


def explain_api_error(exc: Exception, provider: str = "anthropic") -> str:
    """Turn an Anthropic or OpenAI SDK error into a plain-language message for the user."""
    text = str(getattr(exc, "message", exc)).lower()
    if "credit balance" in text or "insufficient_quota" in text or "exceeded your current quota" in text:
        return f"This API key's account has no credits left. {BILLING_HINTS.get(provider, '')}".strip()
    name = type(exc).__name__
    if name == "AuthenticationError":
        return "That API key wasn't accepted. Check that you copied the whole key and chose the right platform."
    if name == "PermissionDeniedError":
        return "This API key isn't allowed to use the model ChatQuadra needs."
    if name == "NotFoundError":
        return "The model ChatQuadra needs isn't available for this key."
    if name == "RateLimitError":
        return "The model service is busy or this key hit its rate limit. Please try again shortly."
    if name in {"APIConnectionError", "APITimeoutError"}:
        return "Could not reach the model service. Check your internet connection."
    status = getattr(exc, "status_code", None)
    if status:
        return f"Model service error ({status})."
    return "Something went wrong talking to the model service."


def _pick_openai_model(client) -> str:
    override = os.environ.get("CHATQUADRA_OPENAI_MODEL")
    if override:
        return override
    available = {m.id for m in client.models.list()}
    for model in OPENAI_PREFERRED_MODELS:
        if model in available:
            return model
    raise LLMError("This OpenAI key can't use any of the models ChatQuadra supports.")


def check_api_key(provider: str, api_key: str, anthropic_model: str) -> tuple[str | None, str | None]:
    """Confirm the key works, can use a supported model, and has credits, with one tiny request.

    Returns (problem, model): problem is None when the key is good, and model is the model to use.
    """
    key = (api_key or "").strip()
    if provider == "anthropic":
        if key.startswith("sk-") and not key.startswith("sk-ant-"):
            return "That looks like an OpenAI key. Choose OpenAI as the platform, or paste an Anthropic key.", None
        if not key.startswith("sk-ant-"):
            return "That doesn't look like an Anthropic API key (it should start with sk-ant-).", None
        import anthropic

        try:
            client = anthropic.Anthropic(api_key=key, max_retries=1, timeout=45)
            client.messages.create(
                model=anthropic_model, max_tokens=16,
                messages=[{"role": "user", "content": "Hi"}], output_config={"effort": "low"},
            )
        except anthropic.APIError as exc:
            return explain_api_error(exc, provider), None
        return None, anthropic_model

    if provider == "openai":
        if key.startswith("sk-ant-"):
            return "That looks like an Anthropic key. Choose Anthropic as the platform, or paste an OpenAI key.", None
        if not key.startswith("sk-"):
            return "That doesn't look like an OpenAI API key (it should start with sk-).", None
        import openai

        try:
            client = openai.OpenAI(api_key=key, max_retries=1, timeout=45)
            model = _pick_openai_model(client)
            client.chat.completions.create(
                model=model, max_completion_tokens=16, messages=[{"role": "user", "content": "Hi"}],
            )
        except LLMError as exc:
            return str(exc), None
        except openai.APIError as exc:
            return explain_api_error(exc, provider), None
        return None, model

    return f"Unknown platform: {provider}", None


class LLM:
    def __init__(
        self,
        settings: Settings,
        api_key: str | None = None,
        provider: str = "anthropic",
        model: str | None = None,
    ):
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        self.settings = settings
        self.mock = settings.mock
        self.provider = provider
        if model:
            self.model = model
        elif provider == "anthropic":
            self.model = settings.model
        else:
            self.model = os.environ.get("CHATQUADRA_OPENAI_MODEL", OPENAI_PREFERRED_MODELS[0])
        self._client = None
        if self.mock:
            return
        if provider == "anthropic":
            import anthropic

            # The visitor's own key, or the environment's key when none is given.
            self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        else:
            import openai

            self._client = openai.OpenAI(api_key=api_key) if api_key else openai.OpenAI()

    def structured(
        self,
        *,
        system: str,
        messages: list[dict],
        output_model: type[T],
        effort: str,
        max_tokens: int = 8000,
    ) -> T | None:
        """Return a validated `output_model`, or None if the model declined.

        Raises LLMError for API failures so callers can show a graceful message.
        """
        if self._client is None:
            raise LLMError("LLM called in mock mode")
        if self.provider == "openai":
            return self._openai(system, messages, output_model, effort, max_tokens)
        return self._anthropic(system, messages, output_model, effort, max_tokens)

    def _anthropic(self, system, messages, output_model, effort, max_tokens):
        import anthropic

        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_format=output_model,
                output_config={"effort": effort},
                cache_control={"type": "ephemeral"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            if isinstance(exc, anthropic.APIStatusError):
                log.error("Claude API error %s: %s", exc.status_code, exc.message)
            raise LLMError(explain_api_error(exc, "anthropic")) from exc

        if response.stop_reason == "refusal":
            log.warning("Model declined a turn (request %s)", response._request_id)
            return None
        if response.stop_reason == "max_tokens":
            raise LLMError("The reply was cut off (max_tokens).")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError("The model returned no structured output.")
        return parsed

    def _openai(self, system, messages, output_model, effort, max_tokens):
        import openai

        # Our history is already in role/content form; OpenAI takes the system prompt as the first message.
        chat = [{"role": "system", "content": system}] + [{"role": m["role"], "content": m["content"]} for m in messages]
        extra = {}
        if self.model.startswith(("gpt-5", "o")):  # reasoning models accept an effort level
            extra["reasoning_effort"] = effort if effort in {"low", "medium", "high"} else "low"
        try:
            completion = self._client.chat.completions.parse(
                model=self.model,
                messages=chat,
                response_format=output_model,
                max_completion_tokens=max_tokens,
                **extra,
            )
        except openai.LengthFinishReasonError as exc:
            raise LLMError("The reply was cut off (max_tokens).") from exc
        except openai.ContentFilterFinishReasonError:
            log.warning("OpenAI content filter stopped a turn")
            return None
        except openai.APIError as exc:
            if isinstance(exc, openai.APIStatusError):
                log.error("OpenAI API error %s: %s", exc.status_code, exc.message)
            raise LLMError(explain_api_error(exc, "openai")) from exc

        message = completion.choices[0].message
        if message.refusal:
            log.warning("OpenAI model declined a turn")
            return None
        if message.parsed is None:
            raise LLMError("The model returned no structured output.")
        return message.parsed
