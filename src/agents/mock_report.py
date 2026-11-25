"""Build a structured product analysis report without calling an LLM.

Uses real Mercado Libre data from tools and produces a deterministic,
actionable template. Useful for development when credits are low.
"""

from __future__ import annotations

import json
import statistics
from typing import Any


def _prices(competitors: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for c in competitors:
        p = c.get("price")
        if isinstance(p, (int, float)) and p > 0:
            out.append(float(p))
    return out


def build_mock_report(
    *,
    item: dict[str, Any] | None = None,
    competitors_payload: dict[str, Any] | None = None,
    query: str | None = None,
    extra_context: str | None = None,
) -> str:
    """Generate a Spanish report from tool payloads."""
    lines: list[str] = []
    lines.append("# Análisis de producto (modo mock — sin LLM)\n")
    lines.append(
        "> Este reporte se generó con datos reales de Mercado Libre y una plantilla determinística. "
        "No usa un modelo de lenguaje.\n"
    )

    if extra_context:
        lines.append(f"**Contexto del vendedor:** {extra_context}\n")

    # --- Product summary ---
    lines.append("## 1. Resumen del producto\n")
    if item:
        title = item.get("title") or "(sin título)"
        price = item.get("price")
        currency = item.get("currency_id") or "ARS"
        sold = item.get("sold_quantity")
        stock = item.get("available_quantity")
        condition = item.get("condition") or "—"
        free_ship = item.get("free_shipping")
        item_id = item.get("id") or "—"
        lines.append(f"- **ID:** {item_id}")
        lines.append(f"- **Título:** {title}")
        lines.append(f"- **Precio:** {currency} {price}")
        lines.append(f"- **Vendidos:** {sold}")
        lines.append(f"- **Stock disponible:** {stock}")
        lines.append(f"- **Condición:** {condition}")
        lines.append(f"- **Envío gratis:** {'sí' if free_ship else 'no'}")
        if item.get("permalink"):
            lines.append(f"- **Link:** {item['permalink']}")
    else:
        lines.append(f"- No se obtuvo detalle de un ítem específico.")
        if query:
            lines.append(f"- Búsqueda usada: `{query}`")
    lines.append("")

    # --- Pricing vs competition ---
    lines.append("## 2. Posicionamiento de precio vs competencia\n")
    competitors = (competitors_payload or {}).get("results") or []
    total = (competitors_payload or {}).get("total")
    price_list = _prices(competitors)

    if price_list:
        price_list_sorted = sorted(price_list)
        median = statistics.median(price_list_sorted)
        low, high = price_list_sorted[0], price_list_sorted[-1]
        lines.append(f"- Resultados de competencia considerados: **{len(price_list)}** "
                     f"(total catálogo ~{total})")
        lines.append(f"- Rango de precios: **{low:,.0f} – {high:,.0f}**")
        lines.append(f"- Mediana aprox.: **{median:,.0f}**")

        own_price = item.get("price") if item else None
        if isinstance(own_price, (int, float)):
            if own_price < low:
                pos = "por debajo del rango observado (muy agresivo)"
            elif own_price > high:
                pos = "por encima del rango observado (caro vs muestra)"
            elif own_price <= median:
                pos = "en la mitad inferior (competitivo)"
            else:
                pos = "en la mitad superior (premium relativo)"
            lines.append(f"- Tu precio ({own_price:,.0f}) está **{pos}**.")
    else:
        lines.append("- No hay suficientes precios de competencia para comparar.")
        if query:
            lines.append(f"- Query usada: `{query}`")
    lines.append("")

    # --- Strengths / weaknesses ---
    lines.append("## 3. Fortalezas y debilidades observables\n")
    strengths: list[str] = []
    weaknesses: list[str] = []

    if item:
        sold = item.get("sold_quantity") or 0
        stock = item.get("available_quantity")
        title = (item.get("title") or "")
        if sold and sold >= 50:
            strengths.append(f"Historial de ventas visible ({sold} vendidos).")
        if item.get("free_shipping"):
            strengths.append("Ofrece envío gratis.")
        if isinstance(stock, int) and stock == 0:
            weaknesses.append("Stock en 0: no se puede vender hasta reponer.")
        elif isinstance(stock, int) and stock <= 2:
            weaknesses.append(f"Stock bajo ({stock} unidades).")
        if len(title) < 40:
            weaknesses.append("Título corto: podría mejorar con más keywords relevantes.")
        if len(title) > 60:
            strengths.append("Título relativamente descriptivo.")
        if not strengths:
            strengths.append("Datos básicos de la publicación disponibles para análisis.")
        if not weaknesses:
            weaknesses.append("Sin señales críticas obvias en los campos evaluados.")
    else:
        strengths.append("Se pudo consultar el catálogo de competencia.")
        weaknesses.append("Sin ítem propio cargado: el análisis es solo de mercado.")

    lines.append("**Fortalezas**")
    for s in strengths:
        lines.append(f"- {s}")
    lines.append("\n**Debilidades**")
    for w in weaknesses:
        lines.append(f"- {w}")
    lines.append("")

    # --- Risks ---
    lines.append("## 4. Riesgos\n")
    risks: list[str] = []
    if item and (item.get("available_quantity") or 0) <= 2:
        risks.append("Ruptura de stock cercana.")
    if price_list and item and isinstance(item.get("price"), (int, float)):
        if item["price"] > max(price_list):
            risks.append("Precio por encima de toda la muestra competitiva.")
    if not risks:
        risks.append("Riesgos limitados con la información actual; validar fotos, reputación y costos reales.")
    for r in risks:
        lines.append(f"- {r}")
    lines.append("")

    # --- Actions ---
    lines.append("## 5. Acciones recomendadas (priorizadas)\n")
    actions: list[str] = []
    if item and (item.get("available_quantity") or 0) <= 2:
        actions.append("Reponer stock antes de invertir en visibilidad o ads.")
    if price_list and item and isinstance(item.get("price"), (int, float)):
        med = statistics.median(sorted(price_list))
        if item["price"] > med * 1.15:
            actions.append(
                f"Revisar precio: estás ~15%+ por encima de la mediana ({med:,.0f}). "
                "Evaluá margen real vs conversión."
            )
        elif item["price"] < med * 0.85:
            actions.append(
                f"Precio agresivo vs mediana ({med:,.0f}). Confirmá que el margen siga siendo sano."
            )
    if item and len(item.get("title") or "") < 50:
        actions.append("Mejorar el título con marca, modelo y 1–2 atributos clave de búsqueda.")
    actions.append("Comparar las 3–5 publicaciones más vendidas de la competencia (fotos, ficha, envío).")
    actions.append("Registrar costo de reposición y comisión MeLi para calcular piso de precio rentable.")
    for i, a in enumerate(actions[:5], 1):
        lines.append(f"{i}. {a}")

    lines.append("\n---\n*Modo mock activo. Para análisis con LLM: configurá LLM_PROVIDER=anthropic|openai|groq y la API key correspondiente.*")
    return "\n".join(lines)


def parse_tool_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
