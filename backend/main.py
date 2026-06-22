# backend/main.py

import logging
import time
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from backend.orchestrator import GTMOrchestrator, QUERY_CACHE

# Setup logging (observability requirement)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("gtm_api")

app = FastAPI(title="Outmate.ai GTM Intelligence API")

# Configure CORS for React frontend (default Vite port is 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory Rate Limiting (rate limiting requirement)
# 10 requests per minute per client IP
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 10
client_requests = defaultdict(list)

def check_rate_limit(client_ip: str):
    now = time.time()
    # Remove timestamps older than window
    client_requests[client_ip] = [t for t in client_requests[client_ip] if now - t < RATE_LIMIT_WINDOW]
    
    if len(client_requests[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        logger.warning(f"Rate limit exceeded for client: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute before querying again."
        )
    client_requests[client_ip].append(now)

@app.get("/api/query")
async def stream_query(
    request: Request,
    query: str = Query(..., min_length=3),
    refresh: bool = Query(False)
):
    """
    Core GTM query endpoint. Uses SSE to stream agent execution timeline and final results.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)
    
    logger.info(f"Received query: '{query}' from IP: {client_ip} (force_refresh={refresh})")
    
    orchestrator = GTMOrchestrator()
    
    # We return an EventSourceResponse which streams the generator
    return EventSourceResponse(
        orchestrator.execute(query, force_refresh=refresh),
        ping=15  # Send a ping event every 15 seconds to keep the connection alive
    )

@app.get("/api/cache")
async def get_cache_status():
    """
    Read cache status (memory system observability).
    """
    return {
        "cached_queries_count": len(QUERY_CACHE),
        "cached_keys": list(QUERY_CACHE.keys())
    }

@app.post("/api/cache/clear")
async def clear_cache():
    """
    Clear the query cache.
    """
    QUERY_CACHE.clear()
    logger.info("Query cache cleared by user request.")
    return {"status": "success", "message": "Query cache cleared"}

@app.get("/api/health")
async def health_check():
    """
    Check if the API server is alive and report LLM configuration.
    """
    import os
    from backend.database import is_seeding_complete
    
    grok_key = os.environ.get("GROK_API_KEY", "")
    gemini_key = os.environ.get("GEMINI_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    if grok_key:
        llm_mode = "xAI Grok (grok-3)" if not grok_key.startswith("gsk_") else "Groq (llama-3.3-70b)"
    elif gemini_key:
        llm_mode = "Gemini"
    elif openai_key:
        llm_mode = "OpenAI (gpt-4o-mini)"
    else:
        llm_mode = "Simulator (no key)"

    return {
        "status": "healthy",
        "timestamp": time.time(),
        "llm_mode": llm_mode,
        "database_seeding_complete": is_seeding_complete,
        "has_keys": {
            "grok": bool(grok_key),
            "gemini": bool(gemini_key),
            "openai": bool(openai_key),
        }
    }
