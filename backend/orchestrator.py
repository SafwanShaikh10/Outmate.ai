# backend/orchestrator.py

import json
import time
import hashlib
from typing import Generator, Dict, Any, List
from backend.agents import (
    PlannerAgent,
    RetrievalAgent,
    EnrichmentAgent,
    CriticAgent,
    GTMStrategyAgent
)

# Global query cache in-memory (Simple memory/cache system)
QUERY_CACHE: Dict[str, Dict[str, Any]] = {}
SHORT_TERM_MEMORY: List[Dict[str, Any]] = []

def get_query_hash(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()

class GTMOrchestrator:
    def __init__(self):
        self.planner = PlannerAgent()
        self.retrieval = RetrievalAgent()
        self.enrichment = EnrichmentAgent()
        self.critic = CriticAgent()
        self.strategy = GTMStrategyAgent()

    def execute(self, query: str, force_refresh: bool = False) -> Generator[str, None, None]:
        """
        Executes the multi-agent GTM intelligence process.
        Yields status dictionaries matching EventSourceResponse spec.
        """
        query_hash = get_query_hash(query)
        
        # 1. Cache Layer check (Memory system requirement)
        if not force_refresh and query_hash in QUERY_CACHE:
            yield self._format_sse("status", {
                "agent": "Memory/Cache System",
                "message": "Found query in cache. Retrieving stored results...",
                "status": "success",
                "time": time.time()
            })
            time.sleep(0.5)
            
            cached_result = QUERY_CACHE[query_hash]
            
            yield self._format_sse("result", {
                "plan": cached_result["plan"],
                "results": cached_result["results"],
                "signals": cached_result["signals"],
                "gtm_strategy": cached_result["gtm_strategy"],
                "confidence": cached_result["confidence"],
                "reasoning_trace": cached_result["reasoning_trace"],
                "cached": True
            })
            return

        # 2. Add to short term session memory
        SHORT_TERM_MEMORY.append({"query": query, "timestamp": time.time()})

        # Start agent execution loop
        max_attempts = 3
        attempt = 1
        reasoning_trace = []
        
        plan = {}
        filters = {}
        enriched_companies = []
        critic_approved = False
        critic_feedback = ""

        try:
            # Timeline generator loop
            while attempt <= max_attempts and not critic_approved:
                # Step A: Planner Agent
                yield self._format_sse("status", {
                    "agent": "Planner Agent",
                    "message": f"Analyzing GTM intent and planning execution (Attempt {attempt})...",
                    "status": "running",
                    "attempt": attempt
                })
                time.sleep(1.0)
                
                plan = self.planner.run(query, attempt=attempt)
                reasoning_trace.append(f"Attempt {attempt}: Planner generated strategy targeting {plan.get('entity_type', 'entity')}s. Confidence: {plan.get('confidence')}")
                
                yield self._format_sse("status", {
                    "agent": "Planner Agent",
                    "message": f"Strategy formed: {plan.get('strategy')}",
                    "status": "completed",
                    "attempt": attempt,
                    "payload": plan
                })
                time.sleep(0.8)

                # Step B: Retrieval Agent
                yield self._format_sse("status", {
                    "agent": "Retrieval Agent",
                    "message": "Translating plan to database filters and query parameters...",
                    "status": "running",
                    "attempt": attempt
                })
                time.sleep(1.0)
                
                companies, filters, sql_query = self.retrieval.run(plan, query, attempt=attempt)
                reasoning_trace.append(f"Attempt {attempt}: SQL Query: {sql_query}. Retrieved {len(companies)} records.")
                
                yield self._format_sse("status", {
                    "agent": "Retrieval Agent",
                    "message": f"SQL: {sql_query} → {len(companies)} result(s)",
                    "status": "completed",
                    "attempt": attempt,
                    "payload": {"sql_query": sql_query, "filters": filters, "count": len(companies)}
                })
                time.sleep(0.8)

                # Step C: Enrichment Agent
                yield self._format_sse("status", {
                    "agent": "Enrichment Agent",
                    "message": "Enriching company profiles with hiring signals and tech stack cues...",
                    "status": "running",
                    "attempt": attempt
                })
                time.sleep(1.0)
                
                enriched_companies = self.enrichment.run(companies)
                reasoning_trace.append(f"Attempt {attempt}: Enrichment added tech signals and buying intent narratives.")
                
                yield self._format_sse("status", {
                    "agent": "Enrichment Agent",
                    "message": "Successfully enriched candidate records and detected buying signals.",
                    "status": "completed",
                    "attempt": attempt
                })
                time.sleep(0.8)

                # Step D: Critic Agent (Very Important)
                yield self._format_sse("status", {
                    "agent": "Validation / Critic Agent",
                    "message": "Reviewing data constraints and verifying result relevance...",
                    "status": "running",
                    "attempt": attempt
                })
                time.sleep(1.2)
                
                critic_approved, critic_feedback = self.critic.run(
                    query=query,
                    plan=plan,
                    filters=filters,
                    companies=enriched_companies,
                    attempt=attempt
                )
                
                reasoning_trace.append(f"Attempt {attempt}: Critic evaluation -> Approved: {critic_approved}. Feedback: {critic_feedback}")
                
                if not critic_approved:
                    yield self._format_sse("status", {
                        "agent": "Validation / Critic Agent",
                        "message": f"Critic Rejected Plan: {critic_feedback}",
                        "status": "failed",
                        "attempt": attempt,
                        "feedback": critic_feedback
                    })
                    # Trigger Orchestrator self-correction trigger
                    yield self._format_sse("status", {
                        "agent": "Orchestrator",
                        "message": "Self-correction triggered: Re-routing execution path to correct search parameters.",
                        "status": "correcting",
                        "attempt": attempt
                    })
                    time.sleep(1.5)
                    attempt += 1
                else:
                    yield self._format_sse("status", {
                        "agent": "Validation / Critic Agent",
                        "message": f"Critic Approved Plan: {critic_feedback}",
                        "status": "completed",
                        "attempt": attempt
                    })
                    time.sleep(0.8)

            # 3. Check if we failed after max retries
            if not critic_approved:
                yield self._format_sse("error", {
                    "message": "Agent execution failed: Critic refused to approve strategy after maximum attempts.",
                    "reasoning_trace": reasoning_trace
                })
                return

            # Step E: GTM Strategy Agent (Runs on approved data)
            yield self._format_sse("status", {
                "agent": "GTM Strategy Agent",
                "message": "Generating ICP scores and tailoring multi-persona outreach hooks...",
                "status": "running"
            })
            time.sleep(1.2)
            
            strategy_out = self.strategy.run(query, enriched_companies)
            reasoning_trace.append("Orchestrator: GTM Strategy Agent completed. Generated ICP scoring sheets and multi-persona outreach strategies.")
            
            # Calculate dynamic final confidence
            avg_confidence = (plan.get("confidence", 0.8) + (1.0 if critic_approved else 0.5)) / 2
            
            final_payload = {
                "plan": plan,
                "results": strategy_out["results"],
                "signals": strategy_out["signals"],
                "gtm_strategy": strategy_out["gtm_strategy"],
                "confidence": round(avg_confidence, 2),
                "reasoning_trace": reasoning_trace,
                "cached": False
            }
            
            # Save to Cache (only if seeding is complete to avoid caching empty/incomplete data)
            from backend.database import is_seeding_complete
            if is_seeding_complete:
                QUERY_CACHE[query_hash] = final_payload
            
            yield self._format_sse("status", {
                "agent": "Orchestrator",
                "message": "Execution complete. Formulating final output payload.",
                "status": "completed"
            })
            time.sleep(0.5)

            yield self._format_sse("result", final_payload)

        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            import logging
            logging.getLogger("gtm_orchestrator").error(
                f"Unhandled exception in GTMOrchestrator.execute: {exc}\n{tb}"
            )
            # Yield a structured error event instead of crashing with HTTP 500
            yield self._format_sse("error", {
                "message": f"Internal orchestrator error: {str(exc)}",
                "reasoning_trace": reasoning_trace
            })

    def _format_sse(self, event_type: str, data: Dict[str, Any]) -> str:
        # Return the JSON string directly — sse_starlette will wrap it in 'data: ...\n\n'
        # via ensure_bytes -> ServerSentEvent(str(data)).encode()
        return json.dumps({
            "event": event_type,
            "data": data
        })
