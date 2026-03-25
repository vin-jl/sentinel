# Sentinel

A secure, asynchronous Python gateway that intercepts data-sensitive AI prompts, masks PII via Microsoft Presidio into a Redis-backed token vault, and routes queries between a local Dockerized LLM and Google Gemini, logging telemetry to a serverless SQLite database.

---

## Motivation

Most enterprises want to adopt AI assistants but face a hard constraint: sensitive data (names, emails, phone numbers) cannot be sent to third-party LLM providers. The typical answer is to either ban cloud LLMs entirely or trust the provider's data handling.

Sentinel sits between the user-facing chatbot (Microsoft Copilot Studio) and the LLMs, acting as a governance layer that strips user-sensitive before any prompt leaves the network, vaults the original values in a TTL-scoped Redis store, and restores them in the response. Simple queries stay on a local Ollama instance that never touches the internet; only complex prompts that need a larger model are forwarded to Gemini, with PII already removed.

---

## Tech Stack

- **Frontend:** Microsoft Copilot Studio (via Ngrok)
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
- [Ngrok](https://ngrok.com/) account (for Copilot Studio integration)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-org>/sentinel.git
   cd sentinel
   ```

2. **Configure environment variables** -- edit `.env`:
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

## Connecting Microsoft Copilot Studio

Copilot Studio can use Sentinel as its backend by calling the `/v1/chat` endpoint through an Ngrok HTTPS tunnel.

1. **Expose the gateway via Ngrok:**

```bash
ngrok http 8000
```

2. **Create a custom connector in Copilot Studio:**

   1. Open [Copilot Studio](https://copilotstudio.microsoft.com/) and navigate to your agent.
   2. Go to **Settings > Generative AI > Dynamic chaining with generative actions**.
   3. Under **Actions**, select **Add an action > Custom connector**.
   4. Configure the connector:
      - **Base URL:** `https://abc123.ngrok-free.app`
      - **Authentication type:** API Key
      - **API key header name:** `X-API-Key`
      - **API key value:** your `SENTINEL_API_KEY`

3. **Add the chat action:**

   1. In the connector, define a **POST** action pointing to `/v1/chat`.
   2. Set the request body schema:
      ```json
      {
      "session_id": "string",
      "message": "string"
      }
      ```
   3. Set the response body schema:
      ```json
      {
      "reply": "string",
      "metadata": {
         "routed_to": "string",
         "pii_entities_masked": 0,
         "latency_ms": 0
      }
      }
      ```
4. Map the Copilot conversation turn to the `message` field, and use a unique conversation ID as the `session_id`.

### 4. Wire the action into a topic

1. Create or edit a topic in your agent.
2. Add a **Plugin action** node and select your custom connector action.
3. Pass the user's message as input and display `reply` from the response.

The agent will now route all messages through Sentinel — PII is masked before it reaches any LLM, and the user sees the full, unmasked response.

---

## Architecture

```
                         POST Request
                              |
                       [ Ngrok Tunnel ]
                              |
                   +----------v----------+
                   |     gateway-api     |  Port 8000 (only exposed service)
                   |     (FastAPI)       |
                   +--+-----+-----+--+--+
                      |     |     |  |
        sentinel_net  |     |     |  |  host volume
         (internal)   |     |     |  |  (./data:/data)
          +-----------+     |     |  +----------+
          |                 |     |             |
     +----v----+   +--------v--+  |       +-----v-----+
     | redis-  |   | llm-local |  |       | data/     |
     | vault   |   | (Ollama)  |  |       | .db       |
     | :6379   |   | :11434    |  |       +-----------+
     +---------+   +-----------+  |
                                  |  external (HTTPS)
        internal network          |  PII already stripped
        no host ports             |
                            +-----v-----+
                            |  Gemini   |
                            |  (Google) |
                            |  cloud    |
                            +-----------+
```

- **redis-vault** and **llm-local** are on an internal Docker bridge network with zero host port exposure.
- **Gemini** is called over HTTPS from the gateway container -- PII is already stripped before the request leaves.
- **data/.db** is a host volume mount (`./data:/data`), not a network service.

---

## API Contract

`POST /v1/chat` — requires `X-API-Key` header.

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

| Status | Meaning                              |
|--------|--------------------------------------|
| `401`  | Missing or invalid `X-API-Key`       |
| `429`  | Rate limit exceeded (>10 req/min/IP) |

---

## Project Structure

```
sentinel/
├── .env                    # API keys (not committed)
├── docker-compose.yml      # Zero-trust container orchestration
├── Dockerfile              # Gateway image build
├── requirements.txt        # Pinned Python dependencies
│
├── data/                   # Host volume for persistent storage
│   └── telemetry.db        # SQLite (auto-generated at runtime)
│
└── app/
    ├── config.py           # Pydantic BaseSettings (cached)
    ├── main.py             # FastAPI entry point & endpoint orchestration
    ├── schemas.py          # Pydantic request/response models
    ├── security.py         # API key verification & rate limiting
    ├── database.py         # SQLite init & telemetry logging
    ├── vault.py            # Redis + Presidio PII masking/unmasking
    └── router.py           # LangChain LLM routing (Ollama vs Gemini)
```
