"""Product Analyst agent.

Takes a Mercado Libre item ID (or title/query) and produces a structured
analysis with pricing context, competitive landscape and concrete actions.

Supports LLM providers: anthropic, openai, groq, mock.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.agents.errors import AgentError
from src.agents.llm import LLMClient, ToolSpec
from src.agents.mock_report import build_mock_report, parse_tool_json
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

TOOLS: list[ToolSpec] = [
    ToolSpec(
        name="get_item",
        description=(
            "Obtiene el detalle de una publicación de Mercado Libre a partir de su ID "
            "(ej: MLA1234567890). Devuelve título, precio, stock, ventas, condición, "
            "envío, atributos y más."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "string",
                    "description": "ID de la publicación (ej. MLA1234567890)",
                }
            },
            "required": ["item_id"],
        },
    ),
    ToolSpec(
        name="search_competitors",
        description=(
            "Busca publicaciones similares en el catálogo de Mercado Libre. "
            "Útil para entender el panorama competitivo de un producto."
        ),
        input_schema={
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
    ),
]

_ITEM_ID_RE = re.compile(r"^[A-Z]{3}\d{6,}$")


class ProductAnalyst:
    """Agent that analyzes a Mercado Libre product and its competitive context."""

    def __init__(
        self,
        meli_client: MeliClient | None = None,
        settings: Settings | None = None,
        max_tool_rounds: int = 5,
        provider_override: str | None = None,
    ):
        self.settings = settings or get_settings()
        if provider_override:
            # Allow CLI --mock / --provider without mutating global settings object deeply
            self.settings = self.settings.model_copy(update={"llm_provider": provider_override})
        self.meli = meli_client or MeliClient(self.settings)
        self.max_tool_rounds = max_tool_rounds
        self.provider = self.settings.llm_provider
        self._llm: LLMClient | None = None
        if self.provider != "mock":
            self._llm = LLMClient(self.settings)

    def _run_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        try:
            if name == "get_item":
                item_id = str(tool_input.get("item_id", "")).strip().upper()
                if not _ITEM_ID_RE.match(item_id):
                    return json.dumps(
                        {
                            "error": (
                                f"item_id inválido: '{item_id}'. "
                                "Formato esperado: MLA123456789 (3 letras + dígitos)."
                            )
                        },
                        ensure_ascii=False,
                    )
                return get_item_tool(self.meli, item_id)
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
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _analyze_mock(
        self,
        *,
        item_id: str | None,
        query: str | None,
        extra_context: str | None,
    ) -> str:
        item_data: dict[str, Any] | None = None
        competitors: dict[str, Any] | None = None

        if item_id:
            raw = self._run_tool("get_item", {"item_id": item_id})
            parsed = parse_tool_json(raw)
            if "error" not in parsed:
                item_data = parsed
                if not query and item_data.get("title"):
                    query = str(item_data["title"])[:80]

        search_q = query
        if not search_q and item_data and item_data.get("title"):
            search_q = str(item_data["title"])[:80]

        if search_q:
            raw_c = self._run_tool(
                "search_competitors", {"query": search_q, "limit": 10}
            )
            competitors = parse_tool_json(raw_c)
            if "error" in competitors:
                competitors = {"results": [], "total": 0, "query": search_q}

        return build_mock_report(
            item=item_data,
            competitors_payload=competitors,
            query=search_q,
            extra_context=extra_context,
        )

    def analyze(
        self,
        *,
        item_id: str | None = None,
        query: str | None = None,
        extra_context: str | None = None,
    ) -> str:
        """Run a full product analysis.

        Provide at least `item_id` or `query`.
        Raises AgentError with a user-friendly message on provider failures.
        """
        if not item_id and not query:
            raise ValueError("Debés pasar item_id o query")

        if item_id:
            item_id = item_id.strip().upper()
            if not _ITEM_ID_RE.match(item_id):
                raise AgentError(
                    f"item_id inválido: '{item_id}'.",
                    hint="Usá un ID real de Mercado Libre, por ejemplo MLA1234567890.",
                )

        if self.provider == "mock":
            logger.info("Running ProductAnalyst in mock mode")
            return self._analyze_mock(
                item_id=item_id, query=query, extra_context=extra_context
            )

        assert self._llm is not None

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

        return self._llm.run_tool_loop(
            system=SYSTEM_PROMPT,
            user_message="\n\n".join(user_parts),
            tools=TOOLS,
            tool_handler=self._run_tool,
            max_rounds=self.max_tool_rounds,
        )
