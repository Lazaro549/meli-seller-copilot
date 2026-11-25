"""Minimal CLI to try the Product Analyst agent.

Examples:
    python -m src.cli --item MLA1234567890
    python -m src.cli --query "auriculares bluetooth" --mock
    python -m src.cli --query "auriculares" --provider groq
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.agents.errors import AgentError
from src.agents.product_analyst import ProductAnalyst
from src.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="meli-seller-copilot – Product Analyst")
    parser.add_argument("--item", help="Item ID (ej. MLA1234567890)")
    parser.add_argument("--query", help="Search query / product name")
    parser.add_argument("--context", help="Extra context from the seller", default=None)
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Modo offline: datos reales de MeLi + reporte plantilla (sin LLM)",
    )
    parser.add_argument(
        "--provider",
        choices=["anthropic", "openai", "groq", "mock"],
        default=None,
        help="Override LLM_PROVIDER del .env",
    )
    args = parser.parse_args()

    if not args.item and not args.query:
        parser.error("Tenés que pasar --item o --query")

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    provider = "mock" if args.mock else (args.provider or settings.llm_provider)

    if provider != "mock":
        key_ok = {
            "anthropic": bool(settings.anthropic_api_key),
            "openai": bool(settings.openai_api_key),
            "groq": bool(settings.groq_api_key),
        }.get(provider, False)
        if not key_ok:
            print(
                f"Falta la API key para el proveedor '{provider}'.\n"
                f"Configurala en .env o usá: python -m src.cli --mock ...",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        agent = ProductAnalyst(provider_override=provider)
        print(f"Analizando (provider={provider})...\n")
        result = agent.analyze(
            item_id=args.item, query=args.query, extra_context=args.context
        )
        print(result)
    except AgentError as exc:
        print(exc.format_for_user(), file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
