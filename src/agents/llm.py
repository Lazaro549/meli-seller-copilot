"""Multi-provider LLM client with a common tool-use loop.

Supported providers:
- anthropic  (native Messages API + tools)
- openai     (Chat Completions + tools)
- groq       (OpenAI-compatible)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Callable

from src.agents.errors import AgentError, LLMAuthError, map_provider_exception
from src.config import Settings

logger = logging.getLogger(__name__)

ToolHandler = Callable[[str, dict[str, Any]], str]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class LLMClient:
    """Thin multi-provider wrapper used by agents."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.llm_provider
        if self.provider == "mock":
            return
        if self.provider == "anthropic":
            self._init_anthropic()
        elif self.provider in ("openai", "groq"):
            self._init_openai_compatible()
        else:
            raise AgentError(f"Proveedor LLM no soportado: {self.provider}")

    def _init_anthropic(self) -> None:
        if not self.settings.anthropic_api_key:
            raise LLMAuthError(
                "Falta ANTHROPIC_API_KEY.",
                hint="Agregala en .env o usá LLM_PROVIDER=mock|groq|openai",
            )
        from anthropic import Anthropic

        self._anthropic = Anthropic(api_key=self.settings.anthropic_api_key)
        self._model = self.settings.anthropic_model

    def _init_openai_compatible(self) -> None:
        from openai import OpenAI

        if self.provider == "openai":
            if not self.settings.openai_api_key:
                raise LLMAuthError(
                    "Falta OPENAI_API_KEY.",
                    hint="Agregala en .env o usá LLM_PROVIDER=mock|groq",
                )
            self._openai = OpenAI(api_key=self.settings.openai_api_key)
            self._model = self.settings.openai_model
        else:  # groq
            if not self.settings.groq_api_key:
                raise LLMAuthError(
                    "Falta GROQ_API_KEY.",
                    hint="Creá una key en https://console.groq.com y ponela en .env, "
                    "o usá LLM_PROVIDER=mock",
                )
            self._openai = OpenAI(
                api_key=self.settings.groq_api_key,
                base_url=self.settings.groq_base_url,
            )
            self._model = self.settings.groq_model

    def run_tool_loop(
        self,
        *,
        system: str,
        user_message: str,
        tools: list[ToolSpec],
        tool_handler: ToolHandler,
        max_rounds: int = 5,
    ) -> str:
        if self.provider == "anthropic":
            return self._run_anthropic(system, user_message, tools, tool_handler, max_rounds)
        return self._run_openai_compatible(system, user_message, tools, tool_handler, max_rounds)

    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------

    def _run_anthropic(
        self,
        system: str,
        user_message: str,
        tools: list[ToolSpec],
        tool_handler: ToolHandler,
        max_rounds: int,
    ) -> str:
        anthropic_tools = [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in tools
        ]
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

        try:
            for round_idx in range(max_rounds):
                logger.info("LLM round %s (%s)", round_idx + 1, self.provider)
                response = self._anthropic.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=system,
                    tools=anthropic_tools,
                    messages=messages,
                )

                tool_uses = []
                text_chunks: list[str] = []
                for block in response.content:
                    if block.type == "text":
                        text_chunks.append(block.text)
                    elif block.type == "tool_use":
                        tool_uses.append(block)

                if response.stop_reason == "end_turn" or not tool_uses:
                    return "\n".join(text_chunks).strip()

                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for tu in tool_uses:
                    logger.info("Tool %s %s", tu.name, tu.input)
                    result = tool_handler(tu.name, dict(tu.input))
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": result,
                        }
                    )
                messages.append({"role": "user", "content": tool_results})

            return (
                "No pude terminar el análisis dentro del límite de pasos. "
                "Probá de nuevo o simplificá el pedido."
            )
        except AgentError:
            raise
        except Exception as exc:
            raise map_provider_exception(exc, "anthropic") from exc

    # ------------------------------------------------------------------
    # OpenAI / Groq
    # ------------------------------------------------------------------

    def _run_openai_compatible(
        self,
        system: str,
        user_message: str,
        tools: list[ToolSpec],
        tool_handler: ToolHandler,
        max_rounds: int,
    ) -> str:
        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_message},
        ]

        try:
            for round_idx in range(max_rounds):
                logger.info("LLM round %s (%s)", round_idx + 1, self.provider)
                response = self._openai.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=oai_tools,
                    tool_choice="auto",
                    temperature=0.3,
                )
                msg = response.choices[0].message
                tool_calls = msg.tool_calls or []

                if not tool_calls:
                    return (msg.content or "").strip()

                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )

                for tc in tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    logger.info("Tool %s %s", name, args)
                    result = tool_handler(name, args)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result,
                        }
                    )

            return (
                "No pude terminar el análisis dentro del límite de pasos. "
                "Probá de nuevo o simplificá el pedido."
            )
        except AgentError:
            raise
        except Exception as exc:
            raise map_provider_exception(exc, self.provider) from exc
