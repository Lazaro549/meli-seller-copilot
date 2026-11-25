"""Friendly error handling for LLM and external API failures."""

from __future__ import annotations


class AgentError(Exception):
    """Base error for agent failures with a user-facing message."""

    def __init__(self, message: str, *, hint: str | None = None):
        self.message = message
        self.hint = hint
        super().__init__(message)

    def format_for_user(self) -> str:
        lines = [f"Error: {self.message}"]
        if self.hint:
            lines.append(f"\nSugerencia: {self.hint}")
        return "\n".join(lines)


class LLMCreditsError(AgentError):
    """Raised when the provider reports insufficient credits / quota."""


class LLMAuthError(AgentError):
    """Raised when the API key is missing or invalid."""


class LLMProviderError(AgentError):
    """Generic provider-side failure."""


def map_provider_exception(exc: BaseException, provider: str) -> AgentError:
    """Convert a raw SDK exception into a friendly AgentError."""
    text = str(exc).lower()
    raw = str(exc)

    # Credits / billing
    if any(
        k in text
        for k in (
            "credit balance is too low",
            "insufficient_quota",
            "insufficient credits",
            "billing",
            "payment required",
            "exceeded your current quota",
        )
    ):
        hints = {
            "anthropic": (
                "Cargá créditos en https://console.anthropic.com → Plans & Billing, "
                "o usá otro proveedor: LLM_PROVIDER=groq|openai|mock"
            ),
            "openai": (
                "Revisá billing en https://platform.openai.com/account/billing, "
                "o usá LLM_PROVIDER=groq|mock"
            ),
            "groq": (
                "Revisá límites en https://console.groq.com, "
                "o usá LLM_PROVIDER=mock para seguir sin gastar"
            ),
        }
        return LLMCreditsError(
            f"Saldo / cuota insuficiente en {provider}.",
            hint=hints.get(provider, "Revisá el billing del proveedor o usá LLM_PROVIDER=mock"),
        )

    # Auth
    if any(
        k in text
        for k in (
            "invalid api key",
            "incorrect api key",
            "authentication",
            "unauthorized",
            "401",
            "invalid_api_key",
        )
    ):
        return LLMAuthError(
            f"API key inválida o ausente para {provider}.",
            hint=f"Revisá la key en .env (ver .env.example) para el proveedor '{provider}'.",
        )

    # Rate limit
    if "rate limit" in text or "429" in text:
        return LLMProviderError(
            f"Rate limit alcanzado en {provider}.",
            hint="Esperá unos segundos e intentá de nuevo, o cambiá de proveedor.",
        )

    return LLMProviderError(
        f"Error del proveedor {provider}: {raw[:300]}",
        hint="Revisá logs y configuración. Podés probar con LLM_PROVIDER=mock.",
    )
