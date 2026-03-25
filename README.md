# Sentinel — 

A secure, asynchronous Python gateway that intercepts data-sensitive AI prompts, masks PII via Microsoft Presidio into a Redis-backed token vault, and routes queries between a local Dockerized LLM and Google Gemini, logging telemetry to a serverless SQLite database.

---

## Tech Stack

- **Frontend:** Microsoft Copilot Studio (via Ngrok HTTPS calls)
- **API Gateway:** Python 3.11, FastAPI, Uvicorn, Pydantic
- **LLM Orchestration:** LangChain (Ollama, Google Gemini)
- **PII Engine:** Microsoft Presidio + spaCy (`en_core_web_sm`)
- **State Management:** Redis (internal Docker network)
- **Telemetry:** SQLite (host-mounted volume)

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- A Google Gemini API key

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/vin-jl/sentinel.git
   cd sentinel
   ```

2. **Configure environment variables:**
   ```
   SENTINEL_API_KEY=<your-secure-random-key>
   GEMINI_API_KEY=<your-gemini-api-key>
   ```

3. **Launch services via Docker:**
   ```bash
   docker compose up --build -d
   ```

4. **Pull a local model:**
   ```bash
   docker exec -it llm-local ollama pull llama3
   ```

5. **Test the gateway:**
   ```bash
   curl -X POST http://localhost:8000/v1/chat \
     -H "Content-Type: application/json" \
     -H "X-API-Key: <your-sentinel-api-key>" \
     -d '{"session_id": "test-001", "message": "Hello, how are you?"}'
   ```

---

## Architecture

```
                        Internet
                            |
                     [ Ngrok Tunnel ]
                            |
                   +--------v--------+
                   |  gateway-api    |  Port 8000 (only exposed service)
                   |  (FastAPI)      |
                   +--+-----------+--+
                      |           |
          +-----------+-----------+-----------+
          |     sentinel_net (internal)       |
          |           |           |           |
     +----v----+ +----v----+ +---v---+
     | redis-  | | llm-    | | data/ |
     | vault   | | local   | | .db   |
     | :6379   | | :11434  | +-------+
     +---------+ +---------+
```

Redis and the local LLM are isolated on an internal Docker bridge network with zero host port exposure.

---

## API Contract

`POST /v1/chat` -- requires `X-API-Key` header.

**Request:**
```json
{
  "session_id": "unique-session-identifier",
  "message": "user prompt text"
}
```

**Response (200):**
```json
{
  "reply": "unmasked AI response",
  "metadata": {
    "routed_to": "llama-3-local | gemini-3.1-flash-lite-preview",
    "pii_entities_masked": 2,
    "latency_ms": 1205
  }
}
```

| Status | Meaning                                  |
|--------|------------------------------------------|
| `401`  | Missing or invalid `X-API-Key`           |
| `429`  | Rate limit exceeded (>10 req/min/IP)     |

---

## Project Structure

```
sentinel-gateway/
├── .env                    # API keys (not committed)
├── docker-compose.yml      # Zero-trust container orchestration
├── Dockerfile              # Gateway image build
├── requirements.txt        # Python dependencies
│
├── data/                   # Host volume for persistent storage
│   └── telemetry.db        # SQLite (auto-generated at runtime)
│
└── app/
    ├── main.py             # FastAPI entry point & endpoint orchestration
    ├── schemas.py          # Pydantic request/response models
    ├── security.py         # API key verification & rate limiting
    ├── database.py         # SQLite init & telemetry logging
    ├── vault.py            # Redis + Presidio PII masking/unmasking
    └── router.py           # LangChain LLM routing (Ollama vs Gemini)
```
