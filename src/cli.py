"""Minimal CLI to try the Product Analyst agent.

Examples:
    python -m src.cli --item MLA1234567890
    python -m src.cli --query "auriculares bluetooth noise cancelling"
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.agents.product_analyst import ProductAnalyst
from src.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="meli-seller-copilot – Product Analyst")
    parser.add_argument("--item", help="Item ID (ej. MLA1234567890)")
    parser.add_argument("--query", help="Search query / product name")
    parser.add_argument("--context", help="Extra context from the seller", default=None)
    args = parser.parse_args()

    if not args.item and not args.query:
        parser.error("Tenés que pasar --item o --query")

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not settings.anthropic_api_key:
        print("Falta ANTHROPIC_API_KEY en el entorno / .env", file=sys.stderr)
        sys.exit(1)

    agent = ProductAnalyst()
    print("Analizando...\n")
    result = agent.analyze(item_id=args.item, query=args.query, extra_context=args.context)
    print(result)


if __name__ == "__main__":
    main()
