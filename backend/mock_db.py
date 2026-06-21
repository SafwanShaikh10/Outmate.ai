# backend/mock_db.py

import json
COMPANIES_DB = [
    {
        "id": "1",
        "name": "CognitiveAI",
        "domain": "cognitive.ai",
        "industry": "AI SaaS",
        "description": "Enterprise generative AI tools for developer productivity.",
        "location": "US",
        "size": "50-100",
        "funding_stage": "Series A",
        "funding_amount": "$12M",
        "growth_rate": "150% YoY",
        "hiring_status": "Aggressive hiring",
        "hiring_roles": ["AI Engineers", "VP of Sales", "Fullstack Developers"],
        "tech_stack": ["React", "Python", "PyTorch", "OpenAI API", "AWS"],
        "competitors_used": ["DevAI Corp", "CodeFlow Solutions"],
        "current_contracts": [
            {"provider": "DevAI Corp", "renewal_date": "2026-10-15", "satisfaction": "Low"}
        ],
        "signals": {
            "hiring_growth": "High",
            "tech_adoption": "Leading edge",
            "funding_recency": "Recent (3 months ago)"
        }
    },
    {
        "id": "2",
        "name": "FinFlow Technologies",
        "domain": "finflow.io",
        "industry": "Fintech",
        "description": "Automated ledger reconciliation for scaling marketplaces.",
        "location": "US",
        "size": "100-250",
        "funding_stage": "Series B",
        "funding_amount": "$28M",
        "growth_rate": "80% YoY",
        "hiring_status": "Moderate hiring",
        "hiring_roles": ["Backend Engineers", "Account Executive"],
        "tech_stack": ["Next.js", "Go", "PostgreSQL", "Kubernetes", "GCP"],
        "competitors_used": ["LedgerPlus", "Stripe Systems"],
        "current_contracts": [
            {"provider": "LedgerPlus", "renewal_date": "2026-08-01", "satisfaction": "Medium"}
        ],
        "signals": {
            "hiring_growth": "Medium",
            "tech_adoption": "Modern",
            "funding_recency": "1 year ago"
        }
    },
    {
        "id": "3",
        "name": "ApexData",
        "domain": "apexdata.com",
        "industry": "Data Infrastructure",
        "description": "Real-time stream processing and vector indexing databases.",
        "location": "US",
        "size": "20-50",
        "funding_stage": "Seed",
        "funding_amount": "$3M",
        "growth_rate": "300% YoY",
        "hiring_status": "Aggressive hiring",
        "hiring_roles": ["Systems Engineer", "Founding Sales Representative", "Developer Advocate"],
        "tech_stack": ["Rust", "C++", "AWS", "Terraform"],
        "competitors_used": ["Confluent", "Pinecone Inc"],
        "current_contracts": [
            {"provider": "Confluent", "renewal_date": "2026-12-31", "satisfaction": "Low"}
        ],
        "signals": {
            "hiring_growth": "High",
            "tech_adoption": "State of the art",
            "funding_recency": "Recent (1 month ago)"
        }
    },
    {
        "id": "4",
        "name": "SecureVault",
        "domain": "securevault.net",
        "industry": "Cybersecurity",
        "description": "Zero-trust identity access management for remote workforces.",
        "location": "Europe",
        "size": "250-500",
        "funding_stage": "Series C",
        "funding_amount": "$65M",
        "growth_rate": "45% YoY",
        "hiring_status": "Frozen",
        "hiring_roles": [],
        "tech_stack": ["Java", "Spring Boot", "React", "Azure"],
        "competitors_used": ["Okta Inc", "Auth0"],
        "current_contracts": [
            {"provider": "Okta Inc", "renewal_date": "2026-07-15", "satisfaction": "High"}
        ],
        "signals": {
            "hiring_growth": "Low",
            "tech_adoption": "Conservative",
            "funding_recency": "2 years ago"
        }
    },
    {
        "id": "5",
        "name": "PayRapid",
        "domain": "payrapid.com",
        "industry": "Fintech",
        "description": "Instant cross-border B2B payments infrastructure.",
        "location": "US",
        "size": "50-100",
        "funding_stage": "Series A",
        "funding_amount": "$10M",
        "growth_rate": "120% YoY",
        "hiring_status": "Aggressive hiring",
        "hiring_roles": ["VP of Marketing", "Growth Engineer", "DevOps Engineer"],
        "tech_stack": ["Node.js", "React", "AWS", "Redis"],
        "competitors_used": ["TransferWise", "Payoneer"],
        "current_contracts": [
            {"provider": "Payoneer", "renewal_date": "2026-09-30", "satisfaction": "Low"}
        ],
        "signals": {
            "hiring_growth": "High",
            "tech_adoption": "Modern",
            "funding_recency": "Recent (6 months ago)"
        }
    },
    {
        "id": "6",
        "name": "NeuralStream",
        "domain": "neuralstream.io",
        "industry": "AI SaaS",
        "description": "AI-powered real-time video editing and transcription tools.",
        "location": "US",
        "size": "10-20",
        "funding_stage": "Seed",
        "funding_amount": "$1.5M",
        "growth_rate": "200% YoY",
        "hiring_status": "Aggressive hiring",
        "hiring_roles": ["AI Researchers", "Frontend Developer"],
        "tech_stack": ["React", "Python", "FastAPI", "AWS", "PyTorch"],
        "competitors_used": ["Descript", "Adobe Premiere"],
        "current_contracts": [
            {"provider": "Descript", "renewal_date": "2026-11-20", "satisfaction": "Medium"}
        ],
        "signals": {
            "hiring_growth": "High",
            "tech_adoption": "Leading edge",
            "funding_recency": "Recent (2 months ago)"
        }
    }
]

def search_companies(filters: dict) -> list:
    """
    Search SQL database by filters.
    Supports industry, location, competitor filtering, and hiring status.
    """
    import sqlite3
    from backend.database import get_connection, fetch_all_as_dicts
    
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM companies WHERE 1=1"
    params = []
    
    # Check if database is SQLite or PostgreSQL
    is_sqlite = isinstance(conn, sqlite3.Connection)
    placeholder = "?" if is_sqlite else "%s"
    
    if "industry" in filters and filters["industry"]:
        query += f" AND LOWER(industry) LIKE LOWER({placeholder})"
        params.append(f"%{filters['industry']}%")
        
    if "location" in filters and filters["location"]:
        query += f" AND LOWER(location) = LOWER({placeholder})"
        params.append(filters["location"])
        
    if "competitors_used" in filters and filters["competitors_used"]:
        query += f" AND LOWER(competitors_used) LIKE LOWER({placeholder})"
        params.append(f"%{filters['competitors_used']}%")
        
    if "hiring" in filters and filters["hiring"]:
        query += f" AND LOWER(hiring_status) = LOWER({placeholder})"
        params.append("aggressive hiring")
        
    cursor.execute(query, params)
    rows = fetch_all_as_dicts(cursor)
    conn.close()
    
    # De-serialize the JSON columns in rows back to lists/dicts for compatibility
    for row in rows:
        for json_col in ["hiring_roles", "tech_stack", "competitors_used", "current_contracts"]:
            if json_col in row and row[json_col]:
                try:
                    row[json_col] = json.loads(row[json_col])
                except:
                    row[json_col] = []
        if "signals" in row and row["signals"]:
            try:
                row["signals"] = json.loads(row["signals"])
            except:
                row["signals"] = {}
                
    return rows
