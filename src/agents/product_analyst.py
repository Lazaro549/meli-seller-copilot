"""Product Analyst agent.

Takes a Mercado Libre item ID (or title/query) and produces a structured
analysis with pricing context, competitive landscape and concrete actions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from anthropic import Anthropic
from anthropic.types import MessageParam, ToolParam, ToolUseBlock

from src.agents.tools import get_item_tool, search_competitors_tool
from src.config import Settings, get_settings
from src.meli.client import MeliClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sos un analista de productos experto en Mercado Libre Argentina (y sitios vecinos).

Tu trabajo es ayudar a vendedores a tomar mejores decisiones de precio, posicionamiento y competitividad.

Reglas:
- Sé concreto y accionable. Evitá generalidades.
- Usá los datos que te devuelven las herramientas. No inventes números.
- Cuando compares precios, mencioná rango, mediana aproximada y outliers si los hay.
- Terminá siempre con una sección clara de **Acciones recomendadas** (máximo 5, priorizadas).
- Respondé en español argentino, tono profesional pero directo.
- Si faltan datos importantes, pedilos o indicá qué información adicional haría falta.
"""

TOOLS: list[ToolParam] = [
    {
        "name": "get_item",
        "description": (
            "Obtiene el detalle de una publicación de Mercado Libre a partir de su ID "
            "(ej: MLA1234567890). Devuelve título, precio, stock, ventas, condición, "
            "envío, atributos y más."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "ID de la publicación (ej. MLA1234567890)",
                }
            },
            "required": ["item_id"],
        },
    },
    {
        "name": "search_competitors",
        "description": (
            "Busca publicaciones similares en el catálogo de Mercado Libre. "
            "Útil para entender el panorama competitivo de un producto."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Términos de búsqueda (título del producto o keywords clave)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Cantidad máxima de resultados (default 10, max 20)",
                    "default": 10,
                },
                "category": {
                    "type": "string",
                    "description": "Opcional: filtrar por category_id",
                },
            },
            "required": ["query"],
        },
    },
]


class ProductAnalyst:
    """Agent that analyzes a Mercado Libre product and its competitive context."""

    def __init__(
        self,
        meli_client: MeliClient | None = None,
        settings: Settings | None = None,
        max_tool_rounds: int = 5,
    ):
        self.settings = settings or get_settings()
        self.meli = meli_client or MeliClient(self.settings)
        self.anthropic = Anthropic(api_key=self.settings.anthropic_api_key)
        self.max_tool_rounds = max_tool_rounds

    def _run_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        try:
            if name == "get_item":
                return get_item_tool(self.meli, tool_input["item_id"])
            if name == "search_competitors":
                return search_competitors_tool(
                    self.meli,
                    tool_input["query"],
                    limit=min(int(tool_input.get("limit", 10)), 20),
                    category=tool_input.get("category"),
                )
            return json.dumps({"error": f"Unknown tool: {name}"})
        except Exception as exc:
            logger.exception("Tool %s failed", name)
            return json.dumps({"error": str(exc)})

    def analyze(
        self,
        *,
        item_id: str | None = None,
        query: str | None = None,
        extra_context: str | None = None,
    ) -> str:
        """Run a full product analysis.

        Provide at least `item_id` or `query`.
        """
        if not item_id and not query:
            raise ValueError("Debés pasar item_id o query")

        user_parts = []
        if item_id:
            user_parts.append(f"Analizá la publicación con ID: {item_id}")
        if query:
            user_parts.append(f"Producto / búsqueda: {query}")
        if extra_context:
            user_parts.append(f"Contexto adicional del vendedor:\n{extra_context}")

        user_parts.append(
            "Quiero un análisis que incluya:\n"
            "1. Resumen del producto\n"
            "2. Posicionamiento de precio vs competencia\n"
            "3. Fortalezas y debilidades observables\n"
            "4. Riesgos (stock, envío, título, etc.)\n"
            "5. Acciones recomendadas priorizadas"
        )

        messages: list[MessageParam] = [
            {"role": "user", "content": "\n\n".join(user_parts)}
        ]

        for round_idx in range(self.max_tool_rounds):
            logger.info("Agent round %s", round_idx + 1)
            response = self.anthropic.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            # Collect text and tool uses
            tool_uses: list[ToolUseBlock] = []
            text_chunks: list[str] = []

            for block in response.content:
                if block.type == "text":
                    text_chunks.append(block.text)
                elif block.type == "tool_use":
                    tool_uses.append(block)

            if response.stop_reason == "end_turn" or not tool_uses:
                return "\n".join(text_chunks).strip()

            # Append assistant message with tool uses
            messages.append({"role": "assistant", "content": response.content})

            # Execute tools and append results
            tool_results = []
            for tu in tool_uses:
                logger.info("Running tool %s with %s", tu.name, tu.input)
                result = self._run_tool(tu.name, tu.input)  # type: ignore[arg-type]
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu.id,
                        "content": result,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        # Fallback if we exhausted rounds
        return (
            "No pude terminar el análisis dentro del límite de pasos. "
            "Probá de nuevo o simplificá el pedido."
        )
