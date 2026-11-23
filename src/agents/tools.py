"""Tools exposed to the LLM agent."""

from __future__ import annotations

import json
from typing import Any

from src.meli.client import MeliClient


def _summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Reduce a full item payload to the fields useful for analysis."""
    shipping = item.get("shipping") or {}
    seller = item.get("seller") or {}
    return {
        "id": item.get("id"),
        "title": item.get("title"),
        "price": item.get("price"),
        "currency_id": item.get("currency_id"),
        "available_quantity": item.get("available_quantity"),
        "sold_quantity": item.get("sold_quantity"),
        "condition": item.get("condition"),
        "permalink": item.get("permalink"),
        "category_id": item.get("category_id"),
        "listing_type_id": item.get("listing_type_id"),
        "status": item.get("status"),
        "seller_id": seller.get("id") or item.get("seller_id"),
        "free_shipping": shipping.get("free_shipping"),
        "logistic_type": shipping.get("logistic_type"),
        "tags": item.get("tags") or [],
        "attributes": [
            {"id": a.get("id"), "name": a.get("name"), "value_name": a.get("value_name")}
            for a in (item.get("attributes") or [])[:12]
        ],
    }


def get_item_tool(client: MeliClient, item_id: str) -> str:
    """Fetch a single item and return a compact JSON summary."""
    item = client.get_item(item_id)
    return json.dumps(_summarize_item(item), ensure_ascii=False, indent=2)


def search_competitors_tool(
    client: MeliClient,
    query: str,
    *,
    limit: int = 10,
    site_id: str | None = None,
    category: str | None = None,
) -> str:
    """Search the catalog and return summarized competitor listings."""
    result = client.search(
        query,
        site_id=site_id,
        limit=limit,
        category=category,
        sort="relevance",
    )
    results = result.get("results") or []
    summarized = []
    for r in results:
        summarized.append(
            {
                "id": r.get("id"),
                "title": r.get("title"),
                "price": r.get("price"),
                "currency_id": r.get("currency_id"),
                "sold_quantity": r.get("sold_quantity"),
                "condition": r.get("condition"),
                "permalink": r.get("permalink"),
                "seller": {
                    "id": (r.get("seller") or {}).get("id"),
                    "nickname": (r.get("seller") or {}).get("nickname"),
                },
                "free_shipping": (r.get("shipping") or {}).get("free_shipping"),
                "listing_type_id": r.get("listing_type_id"),
            }
        )

    payload = {
        "query": query,
        "total": (result.get("paging") or {}).get("total"),
        "results": summarized,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def search_seller_items_tool(
    client: MeliClient,
    user_id: int | str,
    *,
    status: str = "active",
    limit: int = 20,
) -> str:
    """List items of a seller (requires authenticated client)."""
    data = client.search_seller_items(user_id, status=status, limit=limit)
    ids = data.get("results") or []
    if not ids:
        return json.dumps({"user_id": user_id, "total": 0, "items": []}, ensure_ascii=False)

    items = client.get_items(ids[:limit])
    summarized = [_summarize_item(i) for i in items]
    return json.dumps(
        {
            "user_id": user_id,
            "total": (data.get("paging") or {}).get("total", len(ids)),
            "items": summarized,
        },
        ensure_ascii=False,
        indent=2,
    )
