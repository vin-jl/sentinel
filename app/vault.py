import logging
import re

import redis
from presidio_analyzer import AnalyzerEngine

logger = logging.getLogger(__name__)

# Redis Connection (internal Docker network)
redis_client = redis.Redis(host="redis-vault", port=6379, decode_responses=True)

# Presidio Engine
analyzer = AnalyzerEngine()

_PII_TTL_SECONDS = 3600
_SUPPORTED_ENTITIES = ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS"]
_TOKEN_PATTERN = re.compile(r"\[([A-Z_]+_\d+)\]")


# Detect PII entities, replace with bracketed tokens, and vault originals in Redis
# Returns: Tuple of (masked_text, pii_count)
def mask_pii(text: str, session_id: str) -> tuple[str, int]:

    results = analyzer.analyze(
        text=text,
        entities=_SUPPORTED_ENTITIES,
        language="en",
    )

    if not results:
        return text, 0

    # Sort by start index descending so replacements don't shift offsets
    results.sort(key=lambda r: r.start, reverse=True)

    # Track per-entity-type counters for unique token names
    entity_counters: dict[str, int] = {}
    masked_text = text

    for result in results:
        entity_type = result.entity_type
        entity_counters[entity_type] = entity_counters.get(entity_type, 0) + 1
        token = f"[{entity_type}_{entity_counters[entity_type]}]"

        original_value = text[result.start : result.end]

        # Store mapping in Redis with TTL
        redis_key = f"{session_id}:{token}"
        redis_client.setex(redis_key, _PII_TTL_SECONDS, original_value)

        # Replace in the text
        masked_text = masked_text[: result.start] + token + masked_text[result.end :]

    logger.info("Masked %d PII entities for session %s", len(results), session_id)
    return masked_text, len(results)

# Restore bracketed PII tokens in the LLM response with original values from Redis
# Tokens that have expired or are not found are left as-is
def unmask_pii(masked_text: str, session_id: str) -> str:

    def _replace_token(match: re.Match) -> str:
        full_token = match.group(0)  # e.g. [PERSON_1]
        redis_key = f"{session_id}:{full_token}"
        original = redis_client.get(redis_key)
        return str(original) if original is not None else full_token

    return _TOKEN_PATTERN.sub(_replace_token, masked_text)
