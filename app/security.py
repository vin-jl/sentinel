import secrets
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

# Validate the X-API-Key header against the configured secret
async def verify_api_key(api_key: Annotated[str, Security(api_key_header)]) -> str:
    settings = get_settings()
    if not secrets.compare_digest(api_key, settings.sentinel_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
