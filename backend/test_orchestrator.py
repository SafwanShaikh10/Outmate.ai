# backend/test_orchestrator.py

import json
import unittest
from backend.orchestrator import GTMOrchestrator, get_query_hash, QUERY_CACHE
from backend.mock_db import search_companies

class TestGTMOrchestrator(unittest.TestCase):
    
    def setUp(self):
        # Clear global query cache before each test
        QUERY_CACHE.clear()
        self.orchestrator = GTMOrchestrator()
        # Wait for database background seeding to complete
        import backend.database as db
        import time
        for _ in range(50):
            if db.is_seeding_complete:
                break
            time.sleep(0.1)
        # Disable live LLM calls during unit tests for deterministic testing and avoiding rate limits
        self.orchestrator.planner.use_llm = False
        self.orchestrator.retrieval.use_llm = False
        self.orchestrator.enrichment.use_llm = False
        self.orchestrator.critic.use_llm = False
        self.orchestrator.strategy.use_llm = False

    def test_mock_db_search(self):
        """Test that SQL-backed company search filtering works correctly."""
        # Ensure DB is initialized with seeded data
        from backend import database  # triggers init_db()
        
        # Search AI SaaS in US
        results = search_companies({"industry": "AI SaaS", "location": "US"})
        self.assertGreater(len(results), 0)
        ai_names = [r["name"] for r in results]
        self.assertIn("CognitiveAI", ai_names)

        # Search Fintech
        results_fintech = search_companies({"industry": "Fintech"})
        self.assertGreater(len(results_fintech), 0)
        # Should match FinFlow Technologies & PayRapid
        names = [c["name"] for c in results_fintech]
        self.assertIn("FinFlow Technologies", names)
        self.assertIn("PayRapid", names)

    def test_query_hash(self):
        """Test cache query hash functionality."""
        h1 = get_query_hash("Find AI SaaS in US")
        h2 = get_query_hash("find ai saas in us ")
        self.assertEqual(h1, h2)

    def test_orchestrator_execution_stream(self):
        """Test orchestrator execution flow and output formats."""
        query = "Find high-growth AI SaaS companies in the US and generate personalized outbound hooks for their VP Sales."
        
        events = list(self.orchestrator.execute(query))
        
        # Check that events are returned
        self.assertGreater(len(events), 0)
        
        # Verify event formatting and parsing
        parsed_events = []
        for event in events:
            self.assertIsInstance(event, str)
            payload = json.loads(event)
            parsed_events.append(payload)
            
        # Verify that we have status updates and a final result
        event_types = [p["event"] for p in parsed_events]
        self.assertIn("status", event_types)
        self.assertIn("result", event_types)
        
        # Verify final result structure
        final_result = next(p["data"] for p in parsed_events if p["event"] == "result")
        self.assertIn("plan", final_result)
        self.assertIn("results", final_result)
        self.assertIn("signals", final_result)
        self.assertIn("gtm_strategy", final_result)
        self.assertIn("confidence", final_result)
        self.assertIn("reasoning_trace", final_result)
        
        # Verify ICP scores and outbound copy
        self.assertGreater(len(final_result["results"]), 0)
        self.assertIn("icp_scores", final_result["results"][0])
        self.assertIn("fit", final_result["results"][0]["icp_scores"])
        self.assertIn("email_snippets", final_result["gtm_strategy"])
        
    def test_caching_layer(self):
        """Test memory caching of query outputs."""
        query = "Identify fintech startups hiring aggressively and suggest outreach strategies."
        
        # First execution (no cache)
        events_first = list(self.orchestrator.execute(query))
        first_result = json.loads(events_first[-1])["data"]
        self.assertFalse(first_result.get("cached", True))
        
        # Second execution (should read from cache)
        events_second = list(self.orchestrator.execute(query))
        second_result = json.loads(events_second[-1])["data"]
        self.assertTrue(second_result.get("cached", False))
        
        # Verify content matches
        self.assertEqual(first_result["results"][0]["name"], second_result["results"][0]["name"])

    def test_acquisitions_query(self):
        """Test search and parsing of acquisitions table dataset."""
        query = "Find recent acquisitions in the Fintech category"
        events = list(self.orchestrator.execute(query))
        
        # Verify that we have status updates and a final result
        parsed_events = []
        for event in events:
            parsed_events.append(json.loads(event))
            
        final_result = next(p["data"] for p in parsed_events if p["event"] == "result")
        
        self.assertGreater(len(final_result["results"]), 0)
        self.assertIn("Acquired", final_result["results"][0]["funding"])
        self.assertIn("was acquired by", final_result["results"][0]["why_this_result"])

    def test_yc_companies_query(self):
        """Test search and parsing of yc_companies table dataset."""
        query = "Find YC Batch 2005 companies in the vertical Consumer"
        events = list(self.orchestrator.execute(query))
        
        parsed_events = [json.loads(e) for e in events]
        final_result = next(p["data"] for p in parsed_events if p["event"] == "result")
        
        self.assertGreater(len(final_result["results"]), 0)
        # Check that we retrieved YC companies (2005 batch — order not guaranteed)
        names = [r["name"] for r in final_result["results"]]
        self.assertGreater(len(names), 0)
        # All results should have yc_ prefixed IDs
        self.assertTrue(final_result["results"][0]["id"].startswith("yc_"))
        # why_this_result must contain 'yc batch' (case-insensitive)
        self.assertIn("yc batch", final_result["results"][0]["why_this_result"].lower())

    def test_job_postings_query(self):
        """Test search and parsing of job_postings table dataset."""
        query = "Search LinkedIn job postings hiring for Therapist in Fort Collins"
        events = list(self.orchestrator.execute(query))
        
        parsed_events = [json.loads(e) for e in events]
        final_result = next(p["data"] for p in parsed_events if p["event"] == "result")
        
        self.assertGreater(len(final_result["results"]), 0)
        # Check that we retrieved job postings (like Mental Health Therapist/Counselor)
        self.assertIn("post_", final_result["results"][0]["id"])
        self.assertIn("hiring for", final_result["results"][0]["why_this_result"].lower())

if __name__ == "__main__":
    unittest.main()
