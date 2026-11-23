# meli-seller-copilot

AI-powered copilot for Mercado Libre sellers.

Helps sellers with product analysis, pricing recommendations, ad optimization, competitive intelligence and actionable insights using LLMs + Mercado Libre API.

> **Status:** Private · Early development

---

## Goal

Build a practical AI assistant that a real Mercado Libre seller can use to:

- Analyze product performance and profitability
- Get data-driven pricing recommendations
- Optimize ads / campaigns
- Understand competition
- Receive clear, actionable next steps

Focus: **useful > fancy**. Measure results.

---

## Planned Features (v0)

- [ ] Authentication with Mercado Libre (OAuth)
- [ ] Product performance dashboard (sales, visits, conversion, ads)
- [ ] Pricing intelligence (competitor prices + suggested price range)
- [ ] Ad performance analysis + optimization suggestions
- [ ] Natural language interface (Claude / Bedrock)
- [ ] Structured reports + action checklist

---

## Tech Stack (planned)

- **Backend:** Python (FastAPI)
- **LLM:** Anthropic Claude / Amazon Bedrock
- **Data:** Mercado Libre API + local storage / SQLite initially
- **Frontend:** Streamlit or simple React (TBD)
- **Evaluation:** Metrics on recommendation usefulness, latency and cost

---

## Project Structure (initial)

```
meli-seller-copilot/
├── README.md
├── .gitignore
├── requirements.txt
├── src/
│   ├── api/           # FastAPI routes
│   ├── meli/          # Mercado Libre client & auth
│   ├── agents/        # LLM agents / tools
│   ├── analysis/      # Pricing, ads, profitability logic
│   └── evaluation/    # Metrics & evaluation harness
├── notebooks/         # Exploration
└── tests/
```

---

## Development Notes

This repository is private while the core architecture and first useful version are built.

Key principles:
- Measure everything that matters (latency, cost, usefulness)
- Prefer simple, working solutions over complex ones
- Keep seller value as the main success metric

---

## Author

**Lázaro Gómez Vitolo**  
Junior AI & Robotics Developer  
[GitHub](https://github.com/Lazaro549) · [Portfolio](https://lazaro549.github.io/Portfolio/)
