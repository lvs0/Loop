# LLM Proxy

Unified API pour multiples providers LLM avec fallback automatique, caching et analytics.

## Fonctionnalites

- **Multi-provider**: OpenAI, Anthropic, MiniMax, Ollama
- **Fallback automatique**: Si un provider echoue, bascule vers le suivant
- **Caching**: Reponses cachees avec Redis
- **Rate limiting**: Limites par tier (free/pro/enterprise)
- **Analytics**: Suivi d'utilisation et de couts
- **Optimisation de cout**: Route vers le provider le moins cher

## Installation

```bash
# Cloner le projet
cd llm-proxy

# Installer les dependances
pip install -r requirements.txt

# Configurer les variables d'environnement
cp .env.example .env
# Editer .env avec vos API keys
```

## Variables d'environnement

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MINIMAX_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
REDIS_URL=redis://localhost:6379
CACHE_TTL=3600
```

## Utilisation

### Demarrer le serveur

```bash
python app.py
```

Le serveur demarre sur http://localhost:5000

### Creer une API key

```bash
curl -X POST http://localhost:5000/v1/keys \
  -H "Content-Type: application/json" \
  -d '{"tier": "pro"}'
```

### Faire une requete

```bash
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Authorization: Bearer VOTRE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o-mini",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### Lister les models disponibles

```bash
curl http://localhost:5000/v1/models
```

## Tarification

| Tier | Requests/min | Prix |
|------|--------------|------|
| Free | 10 | Gratuit |
| Pro | 100 | 29 EUR/mois |
| Enterprise | 1000 | 299 EUR/mois |

## Architecture

```
Client -> LLM Proxy -> [Redis Cache]
                      |
                      v
              [Fallback Router]
                      |
        +-------------+-------------+
        |             |             |
        v             v             v
    [OpenAI]     [Anthropic]    [Ollama]
```

## API Reference

| Endpoint | Methode | Description |
|----------|---------|-------------|
| / | GET | Info API |
| /health | GET | Health check |
| /v1/models | GET | Liste models |
| /v1/keys | POST | Creer API key |
| /v1/keys/:key | GET | Info API key |
| /v1/chat/completions | POST | Completion |
| /v1/usage | GET | Statistiques |

## Licence

MIT
