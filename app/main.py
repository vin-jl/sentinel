import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Security, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.database import init_db, log_telemetry
from app.router import route_query
from app.schemas import ChatRequest, ChatResponse, ChatMetadata
from app.security import verify_api_key
from app.vault import mask_pii, unmask_pii

logger = logging.getLogger(__name__)

# Rate Limiter
limiter = Limiter(key_func=get_remote_address)


# Application Lifespan
@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize resources on startup."""
    init_db()
    logger.info("Telemetry database initialized")
    yield


app = FastAPI(
    title="Sentinel",
    description="Secure LLM router with PII governance",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.state.limiter = limiter

# Return 429 when the per-IP rate limit is exceeded
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Try again later."},
    )


# ENDPOINTS

# Basic healthcheck
@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Primary gateway endpoint
@app.post("/v1/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request: Request, payload: ChatRequest, background_tasks: BackgroundTasks, api_key: str = Security(verify_api_key)):
    # Flow: Start timer -> mask PII -> route to LLM -> unmask PII
    #       -> log telemetry in background -> return response

    start = time.perf_counter()
    masked_text, pii_count = mask_pii(payload.message, payload.session_id)

    try:
        raw_response, model_name = await route_query(masked_text)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Upstream model request timed out",
        ) from exc
    unmasked_response = unmask_pii(raw_response, payload.session_id)

    latency_ms = int((time.perf_counter() - start) * 1000)
    input_tokens = len(payload.message.split())
    background_tasks.add_task(
        log_telemetry,
        session_id=payload.session_id,
        model_routed_to=model_name,
        input_tokens=input_tokens,
        pii_entities_masked=pii_count,
        latency_ms=latency_ms,
    )

    return ChatResponse(
        reply=unmasked_response,
        metadata=ChatMetadata(
            routed_to=model_name,
            pii_entities_masked=pii_count,
            latency_ms=latency_ms,
        ),
    )
