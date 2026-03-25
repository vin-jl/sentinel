import asyncio
import logging
import re
from functools import partial

from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

# LLM Clients
_OLLAMA_MODEL = "llama3"
_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"
_LLM_TIMEOUT_SECONDS = 60

ollama_llm = ChatOllama(
    base_url="http://llm-local:11434",
    model=_OLLAMA_MODEL,
)

# SDK auto-reads GEMINI_API_KEY from the environment as a fallback
gemini_llm = ChatGoogleGenerativeAI(model=_GEMINI_MODEL)

# ROUTING
# A prompt must score >= _GEMINI_THRESHOLD to be routed to Gemini
_GEMINI_THRESHOLD = 3

_KEYWORD_WEIGHTS: dict[str, int] = {
    # Technical reasoning (weight 2 each)
    "code": 2, "debug": 2, "refactor": 2, "algorithm": 2, "optimize": 2,
    # Analytical tasks (weight 2 each)
    "analyze": 2, "compare": 2, "evaluate": 2, "summarize": 2, "research": 2,
    # Multi-step / complex framing (weight 1 each)
    "step-by-step": 1, "explain": 1, "translate": 1, "generate": 1, "design": 1,
}

# Length thresholds — longer prompts get incremental score
_LENGTH_TIERS: list[tuple[int, int]] = [
    (100, 3),   # very long prompts almost certainly need Gemini
    (50, 1),    # moderately long prompts get a nudge
]

# Question complexity - multiple question marks suggest multi-part reasoning
_MULTI_QUESTION_THRESHOLD = 2
_MULTI_QUESTION_SCORE = 2
_TOKEN_PATTERN = re.compile(r"[a-z0-9-]+")


def _compute_complexity_score(text: str) -> int:
    score = 0
    normalized = text.lower()
    words = set(_TOKEN_PATTERN.findall(normalized))

    # 1. Keyword scoring
    for keyword, weight in _KEYWORD_WEIGHTS.items():
        if keyword in words or re.search(rf"\b{re.escape(keyword)}\b", normalized):
            score += weight

    # 2. Length scoring
    word_count = len(text.split())
    for threshold, contribution in _LENGTH_TIERS:
        if word_count > threshold:
            score += contribution
            break  # only the highest matching tier applies

    # 3. Multi-question scoring
    if text.count("?") >= _MULTI_QUESTION_THRESHOLD:
        score += _MULTI_QUESTION_SCORE

    return score

# Invoke an LLM synchronously (run in a thread executor)
def _invoke_llm(llm, prompt: str) -> str:
    response = llm.invoke([HumanMessage(content=prompt)])
    return str(response.content)

# Route the masked prompt to the appropriate LLM based on complexity scoring
# Runs the blocking LLM call in a thread executor to avoid starving the async event loop
# Returns: Tuple of (raw_llm_response, model_name)
async def route_query(masked_prompt: str) -> tuple[str, str]:
    score = _compute_complexity_score(masked_prompt)
    use_gemini = score >= _GEMINI_THRESHOLD

    llm = gemini_llm if use_gemini else ollama_llm
    model_name = _GEMINI_MODEL if use_gemini else "llama-3-local"

    logger.info("Routing score=%d threshold=%d -> %s", score, _GEMINI_THRESHOLD, model_name)

    loop = asyncio.get_running_loop()
    text = await asyncio.wait_for(
        loop.run_in_executor(None, partial(_invoke_llm, llm, masked_prompt)),
        timeout=_LLM_TIMEOUT_SECONDS,
    )

    return text, model_name
