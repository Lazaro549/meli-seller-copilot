# meli-seller-copilot

AI-powered copilot for Mercado Libre sellers.

Helps sellers with product analysis, pricing recommendations, competitive intelligence and actionable insights using LLMs + Mercado Libre API.

> **Status:** Private · Early development

---

## Goal

Build a practical AI assistant that a real Mercado Libre seller can use to:

- Analyze product performance and positioning
- Get data-driven pricing recommendations
- Understand competition
- Receive clear, actionable next steps

Focus: **useful > fancy**. Measure results.

---

## Current Architecture

```
meli-seller-copilot/
├── src/
│   ├── config.py              # Settings (pydantic-settings)
│   ├── cli.py                 # CLI entrypoint
│   ├── meli/
│   │   ├── client.py          # MeliClient (OAuth + items + search)
│   │   └── __init__.py
│   ├── agents/
│   │   ├── product_analyst.py # First agent (Claude + tools)
│   │   ├── tools.py           # Tool implementations
│   │   └── __init__.py
│   └── analysis/              # (next: pure analysis logic)
├── .env.example
├── requirements.txt
└── README.md
```

### Components

| Component | Description |
|-----------|-------------|
| **MeliClient** | OAuth 2.0 (auth code + refresh), `get_item`, `search`, `search_seller_items`, `get_user` |
| **ProductAnalyst** | Agent with tool-use loop (Claude). Tools: `get_item`, `search_competitors` |
| **Tools** | Thin wrappers that return compact JSON suitable for the LLM |

---

## Setup

```bash
# 1. Clone & install
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your keys
```

### Required environment variables

```env
MELI_CLIENT_ID=          # from DevCenter
MELI_CLIENT_SECRET=
MELI_ACCESS_TOKEN=       # optional if you already have one
MELI_REFRESH_TOKEN=      # recommended
MELI_SITE_ID=MLA

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-20250514
```

---

## Usage

### CLI (Product Analyst)

```bash
# Analyze a specific listing
python -m src.cli --item MLA1234567890

# Analyze by search query
python -m src.cli --query "auriculares bluetooth noise cancelling"

# With extra seller context
python -m src.cli --item MLA1234567890 --context "Costo de reposición: $18000. Quiero margen mínimo 25%."
```

### Programmatic

```python
from src.meli import MeliClient
from src.agents import ProductAnalyst

client = MeliClient()
agent = ProductAnalyst(meli_client=client)

report = agent.analyze(item_id="MLA1234567890")
print(report)
```

### OAuth (manual flow for now)

```python
from src.meli import MeliClient

client = MeliClient()
print(client.authorization_url(state="random-csrf-token"))
# → open URL, authorize, get ?code=...

tokens = client.exchange_code("THE_CODE")
# tokens["access_token"], tokens["refresh_token"], tokens["user_id"]
```

---

## Roadmap (short term)

- [x] MeliClient with OAuth + core resources
- [x] ProductAnalyst agent (first agent)
- [ ] Persist tokens securely
- [ ] Pricing / profitability pure functions in `analysis/`
- [ ] Seller items overview agent
- [ ] FastAPI thin layer + simple auth callback
- [ ] Basic evaluation (latency, token cost, usefulness)

---

## Principles

- Measure everything that matters (latency, cost, usefulness)
- Prefer simple, working solutions over complex ones
- Keep seller value as the main success metric
- No invented numbers — the agent must use tool data

---

## Author

**Lázaro Gómez Vitolo**  
Junior AI & Robotics Developer  
[GitHub](https://github.com/Lazaro549) · [Portfolio](https://lazaro549.github.io/Portfolio/)
