# backend/agents.py

import os
import json
import random
import logging
from typing import List, Dict, Tuple, Any
from backend.mock_db import search_companies

# Load .env file if present (supports local development)
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass  # dotenv not installed, rely on system environment variables

# Set up logger
logger = logging.getLogger("gtm_agents")
logger.setLevel(logging.INFO)

# Check for LLM configuration — Priority: Grok > Gemini > OpenAI
GROK_API_KEY = os.environ.get("GROK_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Log which LLM is active
if GROK_API_KEY:
    logger.info("🤖 LLM Mode: Grok (xAI) — live agent calls enabled")
elif GEMINI_API_KEY:
    logger.info("🤖 LLM Mode: Gemini (Google) — live agent calls enabled")
elif OPENAI_API_KEY:
    logger.info("🤖 LLM Mode: OpenAI (GPT-4o-mini) — live agent calls enabled")
else:
    logger.info("🤖 LLM Mode: Simulator (no API keys found — deterministic fallback active)")

class AgentBase:
    def __init__(self, name: str):
        self.name = name
        self.use_llm = bool(GROK_API_KEY or GEMINI_API_KEY or OPENAI_API_KEY)

    def extract_location_from_query(self, query: str) -> str:
        import re
        query_lower = query.lower()
        # Check for "in the US" / "in US" / "in the USA" / "in USA" / "in United States"
        for us_term in ["united states", "usa", "us"]:
            if f"in the {us_term}" in query_lower or f"in {us_term}" in query_lower:
                return "US"
        for eu_term in ["europe", "eu"]:
            if f"in the {eu_term}" in query_lower or f"in {eu_term}" in query_lower:
                return "Europe"
                
        # Regex match for "in [Location]"
        match = re.search(r'\bin\s+([A-Z][A-Za-z0-9\s,\.\-\&]+)', query)
        if match:
            loc = match.group(1).strip()
            words = loc.split()
            cleaned_words = []
            stop_words = {"hiring", "paying", "with", "that", "having", "using", "and", "or", "for", "in", "to", "the", "a", "an"}
            for w in words:
                if w.lower() in stop_words:
                    break
                cleaned_words.append(w)
            if cleaned_words:
                loc_str = " ".join(cleaned_words)
                loc_str = re.sub(r'[,\.\s]+$', '', loc_str)
                if loc_str:
                    return loc_str
        
        match_lower = re.search(r'\bin\s+([a-z0-9\s,\.\-\&]+)', query_lower)
        if match_lower:
            loc = match_lower.group(1).strip()
            words = loc.split()
            cleaned_words = []
            stop_words = {"hiring", "paying", "with", "that", "having", "using", "and", "or", "for", "in", "to", "the", "a", "an"}
            for w in words:
                if w.lower() in stop_words:
                    break
                cleaned_words.append(w)
            if cleaned_words:
                loc_str = " ".join(cleaned_words)
                loc_str = re.sub(r'[,\.\s]+$', '', loc_str)
                if loc_str and loc_str not in ["a", "the", "recent", "high", "fast", "aggressive", "moderate"]:
                    return loc_str.title()
        return ""

    def _call_grok(self, prompt: str, json_mode: bool = False) -> str:
        """
        Call Grok via xAI API or Groq via Groq API depending on prefix.
        Fully OpenAI-compatible.
        """
        try:
            from openai import OpenAI
            api_key = GROK_API_KEY
            
            # Detect if it's a Groq key (starts with gsk_)
            if api_key and api_key.startswith("gsk_"):
                base_url = "https://api.groq.com/openai/v1"
                model_name = "llama-3.3-70b-versatile"
                logger.info(f"[{self.name}] Routing to Groq API with key prefix 'gsk_' using {model_name}")
            else:
                base_url = "https://api.x.ai/v1"
                model_name = "grok-3"
                logger.info(f"[{self.name}] Routing to xAI Grok API using {model_name}")

            client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
            messages = [{"role": "user", "content": prompt}]
            if json_mode:
                messages = [
                    {"role": "system", "content": "You are a helpful assistant. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ]
            
            response_format = {"type": "json_object"} if (json_mode and "groq" in base_url) else None
            
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.1,
                    response_format=response_format
                )
                return response.choices[0].message.content
            except Exception as e:
                # If Groq fails with llama-3.3, try llama3-70b-8192 as fallback
                if "groq.com" in base_url and model_name != "llama3-70b-8192":
                    logger.warning(f"Failed with {model_name}, trying llama3-70b-8192...")
                    response = client.chat.completions.create(
                        model="llama3-70b-8192",
                        messages=messages,
                        temperature=0.1,
                        response_format=response_format
                    )
                    return response.choices[0].message.content
                # If xAI fails with grok-3, try grok-2-1212 as fallback
                elif "x.ai" in base_url and model_name != "grok-2-1212":
                    logger.warning(f"Failed with {model_name}, trying grok-2-1212...")
                    response = client.chat.completions.create(
                        model="grok-2-1212",
                        messages=messages,
                        temperature=0.1
                    )
                    return response.choices[0].message.content
                raise e
        except Exception as e:
            logger.error(f"Error in _call_grok: {e}")
            raise e

    def _call_gemini(self, prompt: str, json_mode: bool = False) -> str:
        try:
            try:
                import google.generativeai as genai
            except ImportError:
                raise ImportError("google-generativeai is not installed. Install it with: pip install google-generativeai")
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            config = {}
            if json_mode:
                config["response_mime_type"] = "application/json"
                
            response = model.generate_content(prompt, generation_config=config)
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            raise e

    def _call_openai(self, prompt: str, json_mode: bool = False) -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            response_format = {"type": "json_object"} if json_mode else None
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format=response_format,
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling OpenAI: {e}")
            raise e

    def query_llm(self, prompt: str, json_mode: bool = False) -> str:
        """Route to the highest-priority available LLM: Grok > Gemini > OpenAI."""
        if GROK_API_KEY:
            return self._call_grok(prompt, json_mode)
        elif GEMINI_API_KEY:
            return self._call_gemini(prompt, json_mode)
        elif OPENAI_API_KEY:
            return self._call_openai(prompt, json_mode)
        else:
            raise ValueError("No API keys found for LLM invocation")


class PlannerAgent(AgentBase):
    def __init__(self):
        super().__init__("Planner Agent")

    def run(self, query: str, attempt: int = 1) -> Dict[str, Any]:
        """
        Decomposes user query into structured execution steps.
        Outputs entity_type, tasks, strategy, and confidence.
        """
        logger.info(f"[{self.name}] Decomposing query: '{query}' (Attempt {attempt})")
        
        if self.use_llm:
            prompt = f"""
            You are a GTM Planner Agent.
            Decompose the following user GTM query into a structured execution plan.
            
            Query: "{query}"
            Attempt: {attempt}
            
            Important Location Rule:
            If the query specifies a location constraint (e.g. 'in India', 'in Fort Collins', 'in US', etc.), your strategy MUST explicitly target this location and you must NOT relax it or suggest other locations, even on retry attempts. Keep it exactly as requested.
            
            You must return a JSON object with EXACTLY the following keys:
            {{
              "entity_type": "company" or "prospect",
              "tasks": ["search", "enrich", "analyze", "generate_outreach"],
              "strategy": "Your strategic approach description here",
              "confidence": 0.0-1.0
            }}
            Ensure your response is valid JSON.
            """
            try:
                raw = self.query_llm(prompt, json_mode=True)
                return json.loads(raw)
            except Exception as e:
                logger.warning(f"LLM Planner failed or not configured, falling back to simulator: {e}")

        # Deterministic simulation/fallback based on query keywords
        query_lower = query.lower()
        
        # Extract keywords dynamically to build a custom strategy
        loc_val = self.extract_location_from_query(query)
        location_str = f"in {loc_val}" if loc_val else "across target areas"
        
        # Check industry
        industries = []
        if "ai" in query_lower or "artificial intelligence" in query_lower or "llm" in query_lower:
            industries.append("AI")
        if "saas" in query_lower:
            industries.append("SaaS")
        if "fintech" in query_lower or "finance" in query_lower or "payment" in query_lower:
            industries.append("Fintech")
        if "cybersecurity" in query_lower or "security" in query_lower:
            industries.append("Cybersecurity")
        if "data" in query_lower or "infrastructure" in query_lower:
            industries.append("Data Infrastructure")
        
        industry_str = " & ".join(industries) if industries else "high-growth"
        
        # Check roles
        roles = []
        for r in ["marketing", "engineer", "therapist", "manager", "director", "developer", "designer", "coordinator", "sales", "executive"]:
            if r in query_lower:
                roles.append(r.title())
        roles_str = f" hiring for {', '.join(roles)} positions" if roles else ""
        
        # Check competitors
        comps = []
        for c in ["devai", "ledgerplus", "confluent", "stripe", "okta", "auth0"]:
            if c in query_lower:
                comps.append(c.title() if c != "devai" else "DevAI Corp")
        comps_str = f" using competitor(s) {', '.join(comps)}" if comps else ""
        
        # Check acquisitions
        is_acq = any(k in query_lower for k in ["acquisition", "acquired", "acquirer", "buyout", "purchase", "merger", "acq"])
        acq_str = " focusing on M&A history and recent acquisitions" if is_acq else ""
        
        # Check YC
        is_yc = any(k in query_lower for k in ["yc ", "yc", "ycombinator", "y-combinator", "y combinator", "batch"])
        yc_str = " from Y Combinator batches" if is_yc else ""
        
        # Build dynamic strategy
        strategy = f"Target {industry_str} companies {location_str}{roles_str}{comps_str}{acq_str}{yc_str} to tailor multi-persona GTM campaigns."
        
        # On first attempt for Fintech query, simulate a slightly over-constrained confidence/strategy to trigger Critic rejection
        # This keeps the mock self-correction demo working if the user enters the fintech preset query!
        if "fintech" in query_lower and attempt == 1:
            strategy = "Target Fintech companies in Europe with Series C funding only."
            confidence = 0.50
        else:
            confidence = 0.90
            
        tasks = ["search", "enrich", "analyze", "generate_outreach"]
        entity_type = "company"

        return {
            "entity_type": entity_type,
            "tasks": tasks,
            "strategy": strategy,
            "confidence": confidence
        }


class RetrievalAgent(AgentBase):
    def __init__(self):
        super().__init__("Retrieval Agent")

    def run(self, plan: Dict[str, Any], query: str, attempt: int = 1) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
        """
        Converts plan -> structured filters and executes SQL query on SQLite/PostgreSQL.
        Handles ambiguous queries and over-constrained filters.
        """
        logger.info(f"[{self.name}] Converting plan to SQL query parameters (Attempt {attempt})")
        strategy_lower = plan.get("strategy", "").lower()
        query_lower = query.lower()
        
        # Build filters based on the strategy & query
        filters = {}
        
        # Determine industry filter
        if "ai saas" in strategy_lower or "ai" in query_lower:
            filters["industry"] = "AI SaaS"
        elif "fintech" in strategy_lower or "fintech" in query_lower:
            filters["industry"] = "Fintech"
            
        # Determine location filter — dynamically extract from query first, then fall back to strategy keywords
        requested_location = self.extract_location_from_query(query)
        if requested_location:
            filters["location"] = requested_location
            logger.info(f"[{self.name}] Extracted location constraint from query: '{requested_location}'")
        elif "us" in strategy_lower or "us" in query_lower:
            filters["location"] = "US"
        elif "europe" in strategy_lower:
            filters["location"] = "Europe"

        # Determine competitor filter
        if "devai" in query_lower or "devai" in strategy_lower:
            filters["competitors_used"] = "DevAI Corp"
        elif "ledgerplus" in query_lower or "ledgerplus" in strategy_lower:
            filters["competitors_used"] = "LedgerPlus"
        elif "confluent" in query_lower or "confluent" in strategy_lower:
            filters["competitors_used"] = "Confluent"
        elif "competitor" in query_lower:
            filters["competitors_used"] = "DevAI Corp"

        # Simulate over-constrained filters on attempt 1 for Fintech query to trigger Critic rejection
        if "fintech" in query_lower and attempt == 1:
            filters["location"] = "Europe"
            filters["hiring"] = True
            
        logger.info(f"[{self.name}] Applying SQL parameters: {filters}")

        # Execute dynamic SQL query
        import sqlite3
        import json
        import re
        from backend.database import get_connection, fetch_all_as_dicts

        conn = get_connection()
        cursor = conn.cursor()
        
        is_sqlite = isinstance(conn, sqlite3.Connection)
        placeholder = "?" if is_sqlite else "%s"
        
        is_acquisition_query = any(k in query_lower or k in strategy_lower for k in ["acquisition", "acquired", "acquirer", "buyout", "purchase", "merger", "acq"])
        is_yc_query = any(k in query_lower or k in strategy_lower for k in ["yc ", "yc", "ycombinator", "y-combinator", "y combinator", "batch", "vertical"]) and not is_acquisition_query
        is_jobs_query = any(k in query_lower or k in strategy_lower for k in ["job", "posting", "postings", "salary", "role", "work type", "experience level", "hiring status", "work_type"]) and not is_acquisition_query and not is_yc_query

        if self.use_llm:
            prompt = f"""
            You are a GTM SQL Retrieval Agent.
            Convert the user query and planner's strategy into a structured filter dictionary and a clean SQL query.
            
            We have four tables in our database:
            1. `companies` (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT,
                industry TEXT,
                description TEXT,
                location TEXT,
                size TEXT,
                funding_stage TEXT,
                funding_amount TEXT,
                growth_rate TEXT,
                hiring_status TEXT,
                hiring_roles TEXT (JSON string list),
                tech_stack TEXT (JSON string list),
                competitors_used TEXT (JSON string list),
                current_contracts TEXT (JSON string list),
                signals TEXT (JSON string dict)
            )
            2. `acquisitions` (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_permalink TEXT,
                company_name TEXT,
                company_category_list TEXT,
                company_country_code TEXT,
                company_state_code TEXT,
                company_region TEXT,
                company_city TEXT,
                acquirer_permalink TEXT,
                acquirer_name TEXT,
                acquirer_category_list TEXT,
                acquirer_country_code TEXT,
                acquirer_state_code TEXT,
                acquirer_region TEXT,
                acquirer_city TEXT,
                acquired_at TEXT,
                acquired_month TEXT,
                acquired_quarter TEXT,
                acquired_year INTEGER,
                price_amount REAL,
                price_currency_code TEXT
            )
            3. `yc_companies` (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                vertical TEXT,
                year INTEGER,
                batch TEXT,
                url TEXT,
                description TEXT
            )
            4. `job_postings` (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT,
                company_name TEXT,
                title TEXT,
                description TEXT,
                min_salary REAL,
                max_salary REAL,
                normalized_salary REAL,
                pay_period TEXT,
                location TEXT,
                work_type TEXT,
                formatted_work_type TEXT,
                formatted_experience_level TEXT,
                remote_allowed INTEGER,
                applies INTEGER,
                views INTEGER,
                job_posting_url TEXT,
                listed_time TEXT,
                expiry TEXT,
                currency TEXT,
                skills_desc TEXT
            )
            
            User Query: "{query}"
            Planner Strategy: "{plan.get('strategy')}"
            Attempt: {attempt}
            Requested Location: "{requested_location if requested_location else 'None'}"
            
            Location Rule: If Requested Location is NOT 'None', your SQL query MUST include a filter for that location. If a table doesn't have a location column (like `yc_companies`), search for the location within other text columns like description or url (e.g. `LOWER(description) LIKE ?` or `LOWER(url) LIKE ?` with value '%{requested_location}%').
            
            Linking/Joining/Unioning Rule:
            You are allowed and encouraged to perform JOINs and UNIONs across our tables (companies, acquisitions, yc_companies, job_postings) when the query requires linking or merging the datasets. For example:
            - If finding job postings for AI/Fintech companies, join `job_postings` (jp) with `yc_companies` (yc) or `companies` (c) to filter by their vertical/industry.
            - If searching for YC companies or acquisitions in general, you can do a UNION ALL of relevant records from `yc_companies` and `companies` to provide a unified directory.
            - Make sure that when joining, the selected columns from the main entity table are retrieved and any extra filters are applied correctly.
            
            You must return a JSON object with EXACTLY the following keys:
            {{
               "table": "companies", "acquisitions", "yc_companies", "job_postings", or "joined",
               "filters": {{"industry": "...", "location": "..."}},
               "sql": "SELECT ... FROM ... LIMIT 15",
               "params": ["param1", "param2", ...]
            }}
            Use ? as placeholders in your SQL query.
            Ensure your response is valid JSON.
            """
            try:
                raw = self.query_llm(prompt, json_mode=True)
                payload = json.loads(raw)
                target_table = payload.get("table", "companies")
                filters = payload.get("filters", {})
                sql = payload.get("sql", "SELECT * FROM companies WHERE 1=1")
                params = payload.get("params", [])
                
                # Check that placeholder counts match params
                placeholder_count = sql.count("?")
                if placeholder_count != len(params):
                    raise ValueError("Placeholder count mismatch")
                    
                is_acquisition_query = (target_table == "acquisitions")
                is_yc_query = (target_table == "yc_companies")
                is_jobs_query = (target_table == "job_postings")
                if not is_sqlite:
                    sql = sql.replace("?", "%s")
            except Exception as e:
                logger.warning(f"LLM Retrieval failed, falling back to rules-based query: {e}")
        
        # Build rules-based fallback query if not LLM or if LLM failed
        if not self.use_llm or 'sql' not in locals():
            import re
            
            # Determine filters dynamically from query
            loc_val = self.extract_location_from_query(query)
            if loc_val:
                filters["location"] = loc_val
                
            # Extract industry
            industry_val = None
            for ind in ["ai", "saas", "fintech", "finance", "data", "cybersecurity", "security", "consumer", "b2b", "healthcare", "biotech", "education", "marketplace"]:
                if ind in query_lower:
                    industry_val = ind
                    filters["industry"] = ind.title() if ind != "ai" else "AI SaaS"
                    break
                    
            # Extract role
            role_val = None
            for r in ["marketing", "engineer", "therapist", "manager", "director", "developer", "designer", "coordinator", "sales", "executive"]:
                if r in query_lower:
                    role_val = r
                    filters["role"] = r.title()
                    break
            
            # Extract competitor
            comp_val = None
            for comp in ["devai", "ledgerplus", "confluent", "stripe", "okta", "auth0"]:
                if comp in query_lower:
                    comp_val = comp
                    filters["competitors_used"] = comp.title() if comp != "devai" else "DevAI Corp"
                    break
            
            # Extract YC batch & year
            year_val = None
            years = re.findall(r'\b(20\d{2}|19\d{2})\b', query)
            if years:
                year_val = int(years[0])
                filters["year"] = year_val
                
            batch_val = None
            batches = re.findall(r'\b([ws]\d{2,4})\b', query_lower)
            if batches:
                batch_val = batches[0]
                filters["batch"] = batch_val
            
            # Construct the dynamic SQL query depending on parsed intents
            params = []
            
            # Case A: Job Postings Query
            if is_jobs_query:
                # Link job_postings with yc_companies and companies to enable rich filtering by industry or location
                sql = f"""
                    SELECT jp.* 
                    FROM job_postings jp
                    LEFT JOIN yc_companies yc ON LOWER(jp.company_name) = LOWER(yc.name)
                    LEFT JOIN companies c ON LOWER(jp.company_name) = LOWER(c.name)
                    WHERE 1=1
                """
                
                # Apply location constraint
                if loc_val:
                    if loc_val.lower() == "us":
                        sql += f" AND (LOWER(jp.location) LIKE {placeholder} OR LOWER(jp.location) = 'us' OR LOWER(jp.location) = 'usa')"
                        params.append("%us%")
                    else:
                        sql += f" AND (LOWER(jp.location) LIKE {placeholder} OR LOWER(yc.description) LIKE {placeholder})"
                        params.extend([f"%{loc_val.lower()}%", f"%{loc_val.lower()}%"])
                
                # Apply industry constraint
                if industry_val:
                    sql += f" AND (LOWER(c.industry) LIKE {placeholder} OR LOWER(yc.vertical) LIKE {placeholder} OR LOWER(jp.title) LIKE {placeholder} OR LOWER(jp.description) LIKE {placeholder})"
                    params.extend([f"%{industry_val}%", f"%{industry_val}%", f"%{industry_val}%", f"%{industry_val}%"])
                
                # Apply role constraint
                if role_val:
                    sql += f" AND LOWER(jp.title) LIKE {placeholder}"
                    params.append(f"%{role_val}%")
                else:
                    # Simple text search fallback if role is mentioned
                    for title_word in ["marketing", "engineer", "therapist", "manager", "director"]:
                        if title_word in query_lower:
                            sql += f" AND LOWER(jp.title) LIKE {placeholder}"
                            params.append(f"%{title_word}%")
                            break
                            
                sql += " LIMIT 15"

            # Case B: Acquisitions Query
            elif is_acquisition_query:
                # Link acquisitions with yc_companies and companies
                sql = f"""
                    SELECT acq.* 
                    FROM acquisitions acq
                    LEFT JOIN yc_companies yc ON LOWER(acq.company_name) = LOWER(yc.name)
                    LEFT JOIN companies c ON LOWER(acq.company_name) = LOWER(c.name)
                    WHERE 1=1
                """
                
                # Apply industry constraint
                if industry_val:
                    sql += f" AND (LOWER(acq.company_category_list) LIKE {placeholder} OR LOWER(acq.acquirer_category_list) LIKE {placeholder} OR LOWER(yc.vertical) LIKE {placeholder} OR LOWER(c.industry) LIKE {placeholder})"
                    params.extend([f"%{industry_val}%", f"%{industry_val}%", f"%{industry_val}%", f"%{industry_val}%"])
                
                # Apply location constraint
                if loc_val:
                    if loc_val.lower() == "us":
                        sql += f" AND (LOWER(acq.company_country_code) = 'usa' OR LOWER(acq.company_country_code) = 'us' OR LOWER(acq.acquirer_country_code) = 'usa' OR LOWER(acq.acquirer_country_code) = 'us')"
                    else:
                        sql += f" AND (LOWER(acq.company_country_code) = LOWER({placeholder}) OR LOWER(acq.acquirer_country_code) = LOWER({placeholder}) OR LOWER(acq.company_city) LIKE {placeholder})"
                        params.extend([loc_val.lower(), loc_val.lower(), f"%{loc_val.lower()}%"])
                        
                # Apply year constraint
                if year_val:
                    sql += f" AND acq.acquired_year = {placeholder}"
                    params.append(year_val)
                    
                sql += " LIMIT 15"

            # Case C: YC Companies Query
            elif is_yc_query:
                sql = "SELECT * FROM yc_companies WHERE 1=1"
                
                # Apply location constraint (search description or URL since yc_companies has no location column)
                if loc_val:
                    sql += f" AND (LOWER(description) LIKE {placeholder} OR LOWER(url) LIKE {placeholder})"
                    params.extend([f"%{loc_val.lower()}%", f"%{loc_val.lower()}%"])
                
                # Apply industry constraint
                if industry_val:
                    sql += f" AND (LOWER(vertical) LIKE {placeholder} OR LOWER(description) LIKE {placeholder})"
                    params.extend([f"%{industry_val}%", f"%{industry_val}%"])
                
                # Apply batch constraint
                if batch_val:
                    sql += f" AND LOWER(batch) = {placeholder}"
                    params.append(batch_val)
                elif year_val:
                    sql += f" AND year = {placeholder}"
                    params.append(year_val)
                    
                sql += " LIMIT 15"

            # Case D: General Company Query (Union of companies and yc_companies)
            else:
                companies_filter = "1=1"
                companies_params = []
                yc_filter = "1=1"
                yc_params = []
                
                # Location constraint
                if loc_val:
                    companies_filter += f" AND LOWER(location) = LOWER({placeholder})"
                    companies_params.append(loc_val)
                    
                    yc_filter += f" AND (LOWER(description) LIKE {placeholder} OR LOWER(url) LIKE {placeholder})"
                    yc_params.extend([f"%{loc_val.lower()}%", f"%{loc_val.lower()}%"])
                
                # Industry constraint
                if industry_val:
                    companies_filter += f" AND LOWER(industry) LIKE {placeholder}"
                    companies_params.append(f"%{industry_val}%")
                    
                    yc_filter += f" AND (LOWER(vertical) LIKE {placeholder} OR LOWER(description) LIKE {placeholder})"
                    yc_params.extend([f"%{industry_val}%", f"%{industry_val}%"])
                
                # Competitor constraint
                if comp_val:
                    companies_filter += f" AND LOWER(competitors_used) LIKE {placeholder}"
                    companies_params.append(f"%{comp_val}%")
                    yc_filter += f" AND LOWER(description) LIKE {placeholder}"
                    yc_params.append(f"%{comp_val}%")
                
                # Compile UNION query
                sql = f"""
                    SELECT id, name, domain, industry, description, 
                           CASE 
                             WHEN LOWER(description) LIKE '%india%' OR LOWER(domain) LIKE '%.in%' THEN 'India'
                             WHEN LOWER(description) LIKE '%europe%' OR LOWER(description) LIKE '%united kingdom%' OR LOWER(description) LIKE '% london%' OR LOWER(domain) LIKE '%.uk%' OR LOWER(domain) LIKE '%.eu%' THEN 'Europe'
                             ELSE 'US' 
                           END as location, 
                           size, funding_stage, funding_amount, growth_rate, hiring_status, hiring_roles, tech_stack, competitors_used, current_contracts, signals, why_this_result
                    FROM companies
                    WHERE {companies_filter}
                    UNION ALL
                    SELECT 'yc_' || id as id, name, url as domain, vertical as industry, description, 
                           CASE 
                             WHEN LOWER(description) LIKE '%india%' OR LOWER(url) LIKE '%.in%' THEN 'India'
                             WHEN LOWER(description) LIKE '%europe%' OR LOWER(description) LIKE '%united kingdom%' OR LOWER(description) LIKE '% london%' OR LOWER(url) LIKE '%.uk%' OR LOWER(url) LIKE '%.eu%' THEN 'Europe'
                             ELSE 'US' 
                           END as location, 
                           'N/A' as size, batch as funding_stage, 'YC Seed' as funding_amount, 'N/A' as growth_rate, 'N/A' as hiring_status, '[]' as hiring_roles, '["Y Combinator"]' as tech_stack, '[]' as competitors_used, '[]' as current_contracts, '{{\"funding_recency\": \"YC Batch: ' || COALESCE(batch, 'N/A') || '\"}}' as signals, 'YC company match' as why_this_result
                    FROM yc_companies
                    WHERE {yc_filter}
                    LIMIT 15
                """
                params = companies_params + yc_params

        cursor.execute(sql, params)
        
        # Format display query by replacing placeholders with raw values for visualization
        display_query = sql
        for p in params:
            val = f"'{p}'" if isinstance(p, str) else str(p)
            display_query = display_query.replace(placeholder, val, 1)

        results = fetch_all_as_dicts(cursor)
        conn.close()

        # Parse json arrays safely (handling strings vs pre-parsed objects)
        for row in results:
            for json_col in ["hiring_roles", "tech_stack", "competitors_used", "current_contracts"]:
                if json_col in row and row[json_col]:
                    if isinstance(row[json_col], str):
                        try:
                            row[json_col] = json.loads(row[json_col])
                        except:
                            row[json_col] = []
            if "signals" in row and row["signals"]:
                if isinstance(row["signals"], str):
                    try:
                        row["signals"] = json.loads(row["signals"])
                    except:
                        row["signals"] = {}

        # Normalize acquisitions structure to mimic companies schema
        if is_acquisition_query:
            normalized_results = []
            for row in results:
                company_name = row.get("company_name", "Unknown Company")
                acquirer_name = row.get("acquirer_name", "Unknown Acquirer")
                
                domain = row.get("company_permalink", "")
                if domain and domain.startswith("/organization/"):
                    domain = domain.replace("/organization/", "") + ".com"
                else:
                    domain = company_name.lower().replace(" ", "") + ".com"

                price = row.get("price_amount", 0) or 0
                price_currency = row.get("price_currency_code", "USD") or "USD"
                price_str = f"{price_currency} {price:,.0f}" if price > 0 else "Undisclosed Price"
                
                normalized = {
                    "id": f"acq_{row.get('id')}",
                    "name": company_name,
                    "domain": domain,
                    "industry": row.get("company_category_list", "Acquisitions"),
                    "description": f"Acquired by {acquirer_name} on {row.get('acquired_at', 'N/A')}.",
                    "location": row.get("company_country_code", "US"),
                    "size": "N/A",
                    "funding_stage": "Acquired",
                    "funding_amount": price_str,
                    "growth_rate": "N/A",
                    "hiring_status": "N/A",
                    "hiring_roles": [],
                    "tech_stack": ["Acquired Stack", "SQL"],
                    "competitors_used": [],
                    "current_contracts": [],
                    "signals": {
                        "hiring_growth": "N/A",
                        "tech_adoption": "N/A",
                        "funding_recency": f"Acquired by {acquirer_name} on {row.get('acquired_at', 'N/A')}"
                    },
                    "why_this_result": f"Target company '{company_name}' was acquired by '{acquirer_name}' for {price_str} on {row.get('acquired_at')}."
                }
                if company_name.lower().strip() in ["unknown company", "unknown", ""]:
                    logger.info(f"[{self.name}] Skipping acquisition with unknown target company")
                    continue
                normalized_results.append(normalized)
            results = normalized_results

        # Normalize yc_companies structure to mimic companies schema
        elif is_yc_query:
            normalized_results = []
            for row in results:
                company_name = row.get("name", "Unknown Company")
                url = row.get("url", "")
                if not url:
                    url = f"http://{company_name.lower().replace(' ', '')}.com"
                
                normalized = {
                    "id": f"yc_{row.get('id')}",
                    "name": company_name,
                    "domain": url.replace("http://", "").replace("https://", "").split("/")[0],
                    "industry": row.get("vertical", "YC Startup"),
                    "description": row.get("description", "") or "No description available.",
                    "location": "US",
                    "size": "N/A",
                    "funding_stage": row.get("batch", "Seed"),
                    "funding_amount": "YC Seed",
                    "growth_rate": "N/A",
                    "hiring_status": "N/A",
                    "hiring_roles": [],
                    "tech_stack": ["Y Combinator", "Startup"],
                    "competitors_used": [],
                    "current_contracts": [],
                    "signals": {
                        "hiring_growth": "N/A",
                        "tech_adoption": "N/A",
                        "funding_recency": f"Y Combinator Batch: {row.get('batch')} (Year: {row.get('year')})"
                    },
                    "why_this_result": f"Target YC company '{company_name}' from YC Batch '{row.get('batch')}' (Vertical: '{row.get('vertical')}') matched."
                }
                if company_name.lower().strip() in ["unknown company", "unknown", ""]:
                    logger.info(f"[{self.name}] Skipping YC startup with unknown company name")
                    continue
                normalized_results.append(normalized)
            results = normalized_results

        # Normalize job_postings structure to mimic companies schema
        elif is_jobs_query:
            normalized_results = []
            for row in results:
                company_name = row.get("company_name", "")
                
                # If company name is missing, empty, or unknown, let's extract it!
                if not company_name or company_name.lower().strip() in ["unknown", "unknown company", "null", "none", ""]:
                    title = row.get("title", "Unknown Role")
                    description = row.get("description", "") or ""
                    
                    extracted_name = "Unknown Company"
                    
                    # 1. Regex checks (fast fallback / primary parsing)
                    import re
                    # "At Aspen Therapy and Wellness , we..." -> Aspen Therapy and Wellness
                    match_at = re.search(r'(?:At|Welcome to)\s+([A-Z][A-Za-z0-9\s&]+?)\s*(?:,|\bwe\b|\bis\b|\bhas\b|\bcommitted\b)', description)
                    # "Winger is a..." -> Winger
                    match_is = re.search(r'^([A-Z][A-Za-z0-9\s&]+?)\s+(?:is a|is seeking|is looking|hiring|announces)', description.strip())
                    
                    if match_at:
                        extracted_name = match_at.group(1).strip()
                    elif match_is:
                        extracted_name = match_is.group(1).strip()
                        
                    # Let's clean up extracted name if it looks like a sentence
                    if len(extracted_name.split()) > 5:
                        extracted_name = "Unknown Company"
                        
                    # 2. LLM check using Groq API (if configured and valid)
                    if self.use_llm and extracted_name == "Unknown Company":
                        extract_prompt = f"""
                        You are a GTM data parser. Extract the EXACT company name that is hiring from this job posting.
                        Look carefully at the job title and description.
                        
                        Job Title: {title}
                        Job Description Snippet: {description[:1000]}
                        
                        Respond with a JSON object containing exactly one key "company_name". If the company name cannot be found, return "Unknown Company".
                        Example:
                        {{
                          "company_name": "Aspen Therapy and Wellness"
                        }}
                        Ensure valid JSON.
                        """
                        try:
                            raw_llm = self.query_llm(extract_prompt, json_mode=True)
                            llm_res = json.loads(raw_llm)
                            name_val = llm_res.get("company_name", "Unknown Company").strip()
                            if name_val and name_val.lower() != "unknown company" and len(name_val.split()) <= 6:
                                extracted_name = name_val
                        except Exception as ex:
                            logger.warning(f"Failed to extract company name via LLM: {ex}")
                            
                    company_name = extracted_name
                
                # Final cleanup
                if not company_name:
                    company_name = "Unknown Company"
                    
                title = row.get("title", "Unknown Role")
                location = row.get("location", "Unknown Location")
                max_salary = row.get("max_salary")
                currency = row.get("currency", "USD") or "USD"
                pay_period = row.get("pay_period", "YEARLY") or "YEARLY"
                
                salary_str = "Undisclosed"
                if max_salary:
                    salary_str = f"{currency} {max_salary:,.0f}/{pay_period.lower()}"
                
                normalized = {
                    "id": f"post_{row.get('id')}",
                    "name": company_name,
                    "domain": f"{company_name.lower().replace(' ', '').replace('&', '')}.com",
                    "industry": "Job Posting",
                    "description": row.get("description", "") or "No job description available.",
                    "location": location,
                    "size": "N/A",
                    "funding_stage": "Hiring",
                    "funding_amount": f"Salary: {salary_str}",
                    "growth_rate": "N/A",
                    "hiring_status": "Aggressive Hiring",
                    "hiring_roles": [title],
                    "tech_stack": ["LinkedIn Posting"],
                    "competitors_used": [],
                    "current_contracts": [],
                    "signals": {
                        "hiring_growth": f"Views: {row.get('views') or 0}, Applies: {row.get('applies') or 0}",
                        "tech_adoption": f"Work Type: {row.get('formatted_work_type') or 'N/A'}",
                        "funding_recency": f"Experience Level: {row.get('formatted_experience_level') or 'N/A'}"
                    },
                    "why_this_result": f"Hiring for '{title}' in '{location}' paying up to {salary_str}."
                }
                # Skip entries where company name couldn't be resolved
                if company_name.lower().strip() in ["unknown company", "unknown", ""]:
                    logger.info(f"[{self.name}] Skipping job posting with unresolvable company name (id={row.get('id')})")
                    continue
                normalized_results.append(normalized)
            results = normalized_results

        logger.info(f"[{self.name}] SQL: {display_query}")
        logger.info(f"[{self.name}] Retrieved {len(results)} records")
        
        return results, filters, display_query


class EnrichmentAgent(AgentBase):
    def __init__(self):
        super().__init__("Enrichment Agent")

    def run(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enhances records with hiring, growth, and tech usage signals.
        Simulates noisy data, missing fields, or partial results.
        """
        logger.info(f"[{self.name}] Enriching {len(companies)} records")
        enriched_results = []
        
        for comp in companies:
            enriched = comp.copy()
            
            # Simulate noisy or partial data (missing fields dynamically in 20% of cases)
            # but keep the core data intact.
            if random.random() < 0.2:
                # Missing size or funding details
                if "size" in enriched:
                    enriched["size_missing"] = True
                    
            # Compute a custom enrichment derived insight
            signals = enriched.get("signals", {})
            hiring_status = enriched.get("hiring_status", "")
            growth_rate = enriched.get("growth_rate", "")
            
            # Generate a specific buying signal narrative
            if "aggressive" in hiring_status.lower() and "high" in signals.get("hiring_growth", "").lower():
                enriched["buying_intent_narrative"] = f"{enriched['name']} is experiencing rapid hiring growth ({growth_rate}) with key openings in engineering and leadership, showing strong intent to scale operations."
            elif "frozen" in hiring_status.lower():
                enriched["buying_intent_narrative"] = f"{enriched['name']} is currently experiencing a hiring freeze, indicating slower near-term budget expansion."
            else:
                enriched["buying_intent_narrative"] = f"{enriched['name']} displays moderate hiring activity with standard growth indicators."
                
            enriched_results.append(enriched)
            
        return enriched_results


class CriticAgent(AgentBase):
    def __init__(self):
        super().__init__("Validation / Critic Agent")

    def run(self, query: str, plan: Dict[str, Any], filters: Dict[str, Any], companies: List[Dict[str, Any]], attempt: int = 1) -> Tuple[bool, str]:
        """
        Evaluates relevance, hallucinated filters, and valid assumptions.
        Rejects bad outputs and triggers a re-execution loop if needed.
        """
        logger.info(f"[{self.name}] Validating results against user query (Attempt {attempt})")
        query_lower = query.lower()
        
        # --- Location Constraint Guard (applied before LLM and simulator) ---
        # If the user specified a location (e.g. 'in India'), and the retrieval correctly
        # applied that filter, then 0 results is a VALID answer — do NOT trigger self-correction
        # that would swap the location to somewhere else.
        requested_location = self.extract_location_from_query(query)
        if requested_location:
            filter_loc = filters.get("location", "")
            if filter_loc and filter_loc.lower() == requested_location.lower() and len(companies) == 0:
                feedback = (f"APPROVED: The query requested location '{requested_location}'. "
                            f"The retrieval correctly filtered by this location but found 0 records "
                            f"(no companies exist in the database for this location). "
                            f"This is a correct and valid result — location constraint must NOT be relaxed.")
                logger.info(f"[{self.name}] {feedback}")
                return True, feedback

        if self.use_llm:
            prompt = f"""
            You are a Validation / Critic Agent.
            Evaluate the following multi-agent outputs against the user's original query.
            
            User Query: "{query}"
            Planner Strategy: "{plan.get('strategy')}"
            Applied Filters: {json.dumps(filters)}
            Retrieved Companies: {json.dumps([c['name'] for c in companies])}
            Requested Location: "{requested_location if requested_location else 'None'}"
            
            Important: If Requested Location is NOT 'None' and Applied Filters correctly include that location, the result is VALID even if 0 companies were retrieved (the database may simply have no entries for that location). Do NOT reject the plan just because the list is empty when the location filter is correct.
            
            Is this result set valid and fully relevant to the user query?
            You must return a JSON object with:
            {{
              "is_valid": true or false,
              "feedback": "Explain why the output is valid or invalid"
            }}
            Ensure your response is valid JSON.
            """
            try:
                raw = self.query_llm(prompt, json_mode=True)
                res = json.loads(raw)
                return res.get("is_valid", True), res.get("feedback", "Looks good")
            except Exception as e:
                logger.warning(f"LLM Critic failed or not configured, falling back to simulator: {e}")

        # Deterministic simulation of Critic rejection to demo orchestration loops
        
        # Rejection Scenario: Fintech query on attempt 1 returns 0 companies because filters were over-constrained
        if "fintech" in query_lower and len(companies) == 0 and attempt == 1:
            feedback = "REJECTED: The applied filters [location: Europe, industry: Fintech] resulted in 0 matches. The query asks for fintech startups hiring aggressively, which exist in the US database (e.g. PayRapid). Recommending location relaxed to US."
            logger.warning(f"[{self.name}] {feedback}")
            return False, feedback
            
        # Rejection Scenario: Churn query matching DevAI but no results found on first try (if filters are set to Europe)
        if "churn" in query_lower and len(companies) == 0:
            feedback = "REJECTED: No competitor users retrieved. Please relax filters to search across all locations."
            logger.warning(f"[{self.name}] {feedback}")
            return False, feedback

        # Success case
        feedback = f"APPROVED: Successfully matched {len(companies)} companies with query intents. Applied filters {filters} are correct and relevant."
        logger.info(f"[{self.name}] {feedback}")
        return True, feedback


class GTMStrategyAgent(AgentBase):
    def __init__(self):
        super().__init__("GTM Strategy Agent")

    def run(self, query: str, companies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generates outreach hooks, angles, email snippets, and calculates ICP scores.
        """
        logger.info(f"[{self.name}] Generating outreach angles and ICP scores for {len(companies)} leads")
        
        results_out = []
        signals_out = []
        
        for comp in companies:
            # 1. Calculate ICP scores (Fit, Intent, Growth) dynamically based on query
            # Default scoring bases
            fit_score = 0.8
            intent_score = 0.7
            growth_score = 0.75
            
            query_lower = query.lower()
            industry = comp.get("industry", "").lower()
            location = comp.get("location", "").lower()
            hiring_status = comp.get("hiring_status", "").lower()
            funding_stage = comp.get("funding_stage", "").lower()
            
            # Adjust Fit
            if "ai" in query_lower and "ai" in industry:
                fit_score += 0.15
            if "fintech" in query_lower and "fintech" in industry:
                fit_score += 0.15
            if "us" in query_lower and "us" in location:
                fit_score += 0.05
                
            # Adjust Intent
            if "aggressive" in hiring_status:
                intent_score += 0.20
            elif "frozen" in hiring_status:
                intent_score -= 0.30
                
            if "renewal" in query_lower or "churn" in query_lower:
                contracts = comp.get("current_contracts", [])
                if contracts and contracts[0]["satisfaction"].lower() == "low":
                    intent_score += 0.25 # High intent to switch/churn
                    
            # Adjust Growth
            if "seed" in funding_stage:
                growth_score += 0.05
            elif "series a" in funding_stage or "series b" in funding_stage:
                growth_score += 0.15
                
            # Clip scores between 0.0 and 1.0
            fit_score = min(max(fit_score, 0.0), 1.0)
            intent_score = min(max(intent_score, 0.0), 1.0)
            growth_score = min(max(growth_score, 0.0), 1.0)
            
            overall_icp = round((fit_score + intent_score + growth_score) / 3, 2)
            
            # Enrich company record
            comp_record = {
                "id": comp.get("id"),
                "name": comp["name"],
                "domain": comp["domain"],
                "industry": comp["industry"],
                "location": comp["location"],
                "funding": f"{comp['funding_stage']} ({comp.get('funding_amount', 'N/A')})",
                "hiring": comp["hiring_status"],
                "icp_scores": {
                    "fit": round(fit_score, 2),
                    "intent": round(intent_score, 2),
                    "growth": round(growth_score, 2),
                    "overall": overall_icp
                },
                "why_this_result": comp.get("why_this_result") or comp.get("buying_intent_narrative", "")
            }
            results_out.append(comp_record)
            
            # Record signals
            signals_out.append({
                "company": comp["name"],
                "hiring_roles": comp.get("hiring_roles", []),
                "tech_stack": comp.get("tech_stack", []),
                "competitors_used": comp.get("competitors_used", []),
                "signals": comp.get("signals", {})
            })

        # 2. Generate multi-persona outreach content
        hooks = []
        angles = []
        email_snippets = []
        
        if self.use_llm and companies:
            # Create a structured list of target company profiles for the LLM
            companies_info = []
            for comp in companies:
                # Find matching signals
                sig = next((s for s in signals_out if s["company"] == comp["name"]), {})
                companies_info.append({
                    "name": comp["name"],
                    "industry": comp.get("industry", "Technology"),
                    "location": comp.get("location", "US"),
                    "funding": f"{comp.get('funding_stage', 'N/A')} ({comp.get('funding_amount', 'N/A')})",
                    "hiring": comp.get("hiring_status", "Hiring"),
                    "why_this_result": comp.get("why_this_result", ""),
                    "tech_stack": sig.get("tech_stack", []),
                    "hiring_roles": sig.get("hiring_roles", []),
                    "competitors_used": sig.get("competitors_used", [])
                })

            prompt = f"""
            You are a GTM Copywriting Agent.
            Create highly personalized sales hooks, email angles, and customized outreach email templates for the following target companies.
            
            Query: "{query}"
            
            Companies Data:
            {json.dumps(companies_info, indent=2)}
            
            Instructions:
            1. For EACH company listed, generate exactly three personalized email snippets: one for the "CEO", one for the "VP Sales", and one for the "CTO".
            2. The subject lines and bodies must be tailored to that specific company's name, hiring roles, tech stack, and location. Do NOT use generic text or hardcode company names across different companies.
            3. Ensure each snippet object has the "company" key set to the exact name of the company it was written for.
            
            Generate a JSON object with:
            {{
               "hooks": ["General GTM hook 1", "General GTM hook 2"],
               "angles": ["General GTM angle 1", "General GTM angle 2"],
               "email_snippets": [
                  {{
                     "company": "Exact Company Name",
                     "persona": "CEO",
                     "subject": "Tailored Subject line for CEO",
                     "body": "Hi CEO,\\n\\n[Tailored body text]\\n\\nBest,\\nOutmate Team"
                  }},
                  {{
                     "company": "Exact Company Name",
                     "persona": "VP Sales",
                     "subject": "Tailored Subject line for VP Sales",
                     "body": "Hi VP Sales,\\n\\n[Tailored body text]\\n\\nBest,\\nOutmate GTM"
                  }},
                  {{
                     "company": "Exact Company Name",
                     "persona": "CTO",
                     "subject": "Tailored Subject line for CTO",
                     "body": "Hi CTO,\\n\\n[Tailored body text]\\n\\nBest,\\nOutmate Systems"
                  }}
                  // ... Repeat for all other companies
               ]
            }}
            Ensure validity and return valid JSON.
            """
            try:
                raw = self.query_llm(prompt, json_mode=True)
                payload = json.loads(raw)
                hooks = payload.get("hooks", [])
                angles = payload.get("angles", [])
                email_snippets = payload.get("email_snippets", [])
            except Exception as e:
                logger.warning(f"LLM Strategy failed, falling back to simulator: {e}")

        # Simulator fallback / structured GTM copy engine
        if not hooks:
            for comp in companies:
                name = comp["name"]
                industry = comp.get("industry", "Technology")
                location = comp.get("location", "US")
                funding = comp.get("funding", "Seed")
                hiring_status = comp.get("hiring", "Hiring")
                why = comp.get("why_this_result", "")
                
                # Retrieve signal details from signals_out if available
                sig = next((s for s in signals_out if s["company"] == name), {})
                techs = sig.get("tech_stack", ["modern tech"])
                roles = sig.get("hiring_roles", ["specialists"])
                competitors = sig.get("competitors_used", ["legacy platforms"])
                
                tech_list_str = ", ".join(techs[:3]) if techs else "modern software stack"
                role_str = roles[0] if roles else "talented professionals"
                comp_str = competitors[0] if competitors else "manual list building"
                
                # Dynamic hooks and angles
                hooks.append(f"Leverage {name}'s active search for {role_str} in {location} to automate outbound GTM.")
                angles.append(f"Pitch Outmate's workflow integration with {tech_list_str} to optimize outbound sales.")
                
                # CEO Email Snippet
                email_snippets.append({
                    "company": name,
                    "persona": "CEO",
                    "subject": f"Strategic GTM automation for {name}",
                    "body": f"Hi CEO,\n\nI noticed {name} is expanding operations in {location} and actively hiring. To support this growth, scaling your outbound pipeline is crucial. Let's discuss a customized multi-agent GTM pilot tailored to your segment.\n\nBest,\nOutmate Team"
                })
                
                # VP Sales Email Snippet
                email_snippets.append({
                    "company": name,
                    "persona": "VP Sales",
                    "subject": f"Scaling {name}'s outbound sales pipeline",
                    "body": f"Hi VP Sales,\n\nWith {name} actively hiring for {role_str}, manual lead generation and enrichment could be slowing your sales reps down. We help sales teams automate lead lists and ICP scoring with high fidelity. Let's connect for a brief demo.\n\nBest,\nOutmate GTM"
                })
                
                # CTO Email Snippet
                email_snippets.append({
                    "company": name,
                    "persona": "CTO",
                    "subject": f"Optimizing developer GTM workflows at {name}",
                    "body": f"Hi CTO,\n\nI saw {name} is utilizing {tech_list_str} in your technology stack. We offer secure, API-first outbound orchestration to automate lead intelligence workflows and save engineering bandwidth. Let's explore an integration.\n\nBest,\nOutmate Systems"
                })

        return {
            "results": results_out,
            "signals": signals_out,
            "gtm_strategy": {
                "hooks": list(set(hooks)),
                "angles": list(set(angles)),
                "email_snippets": email_snippets
            }
        }
