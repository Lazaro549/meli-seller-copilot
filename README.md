# meli-seller-copilot
<img width="1600" height="900" alt="image" src="https://github.com/user-attachments/assets/58e4d703-59b8-439e-86a3-cf87bb8c664e" />

AI-powered copilot for Mercado Libre sellers.

Helps sellers with product analysis, pricing recommendations, competitive intelligence and actionable insights using LLMs + Mercado Libre API.

> **Status:** Private · Early development  
> **License:** [MIT](LICENSE)

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
│   ├── config.py                 # Settings (pydantic-settings)
│   ├── cli.py                    # CLI entrypoint
│   ├── meli/
│   │   └── client.py             # MeliClient (OAuth + items + search)
│   ├── agents/
│   │   ├── product_analyst.py    # Agent principal
│   │   ├── llm.py                # Multi-LLM (Anthropic / OpenAI / Groq)
│   │   ├── mock_report.py        # Reporte offline sin LLM
│   │   ├── errors.py             # Errores amigables
│   │   └── tools.py              # Tools MeLi
│   └── analysis/                 # (próximo: pricing determinístico)
├── .env.example
├── requirements.txt
├── LICENSE
└── README.md
```

### Components

| Component | Description |
|-----------|-------------|
| **MeliClient** | OAuth 2.0, `get_item`, `search`, `search_seller_items`, `get_user` |
| **ProductAnalyst** | Agent con tools + multi-LLM o modo mock |
| **LLMClient** | Anthropic / OpenAI / Groq con tool-use loop |
| **Mock report** | Datos reales de MeLi + plantilla (sin gastar créditos) |

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### Variables de entorno relevantes

```env
LLM_PROVIDER=mock          # anthropic | openai | groq | mock

ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GROQ_API_KEY=              # recomendado para desarrollo (barato/gratis)

MELI_SITE_ID=MLA
```

Por defecto en `.env.example` está `LLM_PROVIDER=mock` para que puedas probar sin créditos.

---

## Usage

### Modo mock (sin LLM, recomendado si no hay créditos)

```bash
python -m src.cli --query "auriculares bluetooth" --mock
python -m src.cli --item MLA1234567890 --mock
```

Usa la API pública de Mercado Libre y genera un reporte estructurado determinístico.

### Con LLM

```bash
# Anthropic
LLM_PROVIDER=anthropic python -m src.cli --query "auriculares bluetooth"

# Groq
python -m src.cli --query "auriculares bluetooth" --provider groq

# OpenAI
python -m src.cli --item MLA1234567890 --provider openai

# Con contexto del vendedor
python -m src.cli --item MLA1234567890 --context "Costo $18000, margen mínimo 25%"
```

### Errores amigables

Si el proveedor falla por créditos, auth o rate limit, el CLI muestra un mensaje claro + sugerencia (por ejemplo cambiar a `--mock` o cargar créditos), en lugar de un traceback largo.

### Programmatic

```python
from src.agents import ProductAnalyst, AgentError

agent = ProductAnalyst(provider_override="mock")
try:
    print(agent.analyze(query="auriculares bluetooth"))
except AgentError as e:
    print(e.format_for_user())
```

---

## Roadmap (short term)

- [x] MeliClient with OAuth + core resources
- [x] ProductAnalyst agent
- [x] Friendly API/LLM errors
- [x] Mock / offline mode
- [x] Multi-LLM (Anthropic, OpenAI, Groq)
- [ ] Persist tokens securely
- [ ] Pricing / profitability pure functions in `analysis/`
- [ ] Seller items overview agent
- [ ] FastAPI + OAuth callback
- [ ] Basic evaluation (latency, token cost, usefulness)

---

## Principles

- Measure everything that matters (latency, cost, usefulness)
- Prefer simple, working solutions over complex ones
- Keep seller value as the main success metric
- No invented numbers — the agent must use tool data

---

## License

MIT License — see [LICENSE](LICENSE).

---

## Author

**Lázaro Gómez Vitolo**  
Junior AI & Robotics Developer  
[GitHub](https://github.com/Lazaro549) · [Portfolio](https://lazaro549.github.io/Portfolio/)
