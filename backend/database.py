# backend/database.py

import os
import sqlite3
import json

DATABASE_URL = os.getenv("DATABASE_URL", "")

def get_connection():
    """
    Returns a connection to the database.
    If DATABASE_URL environment variable is set to a postgresql:// connection,
    it uses psycopg2, otherwise it defaults to local SQLite.
    """
    if DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://"):
        try:
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except ImportError:
            raise ImportError(
                "psycopg2 is not installed but a PostgreSQL DATABASE_URL was provided. "
                "Please run: pip install psycopg2-binary"
            )
    else:
        # SQLite local database
        db_path = os.path.join(os.path.dirname(__file__), "gtm_database.db")
        conn = sqlite3.connect(db_path)
        return conn

def fetch_all_as_dicts(cursor) -> list:
    """
    Convert cursor output to a list of dicts.
    """
    if not cursor.description:
        return []
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def init_db():
    """
    Creates tables if they do not exist and auto-seeds companies.
    """
    conn = get_connection()
    cursor = conn.cursor()

    is_postgres = DATABASE_URL.startswith("postgresql://") or DATABASE_URL.startswith("postgres://")

    # Create companies table
    if is_postgres:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id VARCHAR(50) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                domain VARCHAR(100),
                industry VARCHAR(100),
                description TEXT,
                location VARCHAR(100),
                size VARCHAR(50),
                funding_stage VARCHAR(50),
                funding_amount VARCHAR(50),
                growth_rate VARCHAR(50),
                hiring_status VARCHAR(50),
                hiring_roles TEXT,
                tech_stack TEXT,
                competitors_used TEXT,
                current_contracts TEXT,
                signals TEXT,
                why_this_result TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acquisitions (
                id SERIAL PRIMARY KEY,
                company_permalink VARCHAR(255),
                company_name VARCHAR(255),
                company_category_list TEXT,
                company_country_code VARCHAR(10),
                company_state_code VARCHAR(10),
                company_region VARCHAR(100),
                company_city VARCHAR(100),
                acquirer_permalink VARCHAR(255),
                acquirer_name VARCHAR(255),
                acquirer_category_list TEXT,
                acquirer_country_code VARCHAR(10),
                acquirer_state_code VARCHAR(10),
                acquirer_region VARCHAR(100),
                acquirer_city VARCHAR(100),
                acquired_at VARCHAR(50),
                acquired_month VARCHAR(50),
                acquired_quarter VARCHAR(50),
                acquired_year INTEGER,
                price_amount NUMERIC,
                price_currency_code VARCHAR(10)
            );
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
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
                hiring_roles TEXT,
                tech_stack TEXT,
                competitors_used TEXT,
                current_contracts TEXT,
                signals TEXT,
                why_this_result TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS acquisitions (
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
            );
        """)

    conn.commit()

    # Check if companies table is empty
    cursor.execute("SELECT COUNT(*) FROM companies;")
    count = cursor.fetchone()[0]
    
    if count == 0:
        # Seed default dataset
        from backend.mock_db import COMPANIES_DB
        for c in COMPANIES_DB:
            # We serialize list/dict structures into JSON strings for database compatibility
            hiring_roles_json = json.dumps(c.get("hiring_roles", []))
            tech_stack_json = json.dumps(c.get("tech_stack", []))
            competitors_used_json = json.dumps(c.get("competitors_used", []))
            current_contracts_json = json.dumps(c.get("current_contracts", []))
            signals_json = json.dumps(c.get("signals", {}))

            cursor.execute("""
                INSERT INTO companies (
                    id, name, domain, industry, description, location, size,
                    funding_stage, funding_amount, growth_rate, hiring_status,
                    hiring_roles, tech_stack, competitors_used, current_contracts, signals, why_this_result
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """ if not is_postgres else """
                INSERT INTO companies (
                    id, name, domain, industry, description, location, size,
                    funding_stage, funding_amount, growth_rate, hiring_status,
                    hiring_roles, tech_stack, competitors_used, current_contracts, signals, why_this_result
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                c["id"], c["name"], c["domain"], c["industry"], c["description"],
                c["location"], c["size"], c["funding_stage"], c["funding_amount"],
                c["growth_rate"], c["hiring_status"], hiring_roles_json, tech_stack_json,
                competitors_used_json, current_contracts_json, signals_json, c.get("why_this_result", "")
            ))
        
        # Seed some dummy acquisitions to match acq.csv structure
        dummy_acqs = [
            {
                "company_permalink": "/organization/cognitive-ai",
                "company_name": "CognitiveAI",
                "company_category_list": "AI|SaaS|Enterprise",
                "company_country_code": "USA",
                "company_state_code": "CA",
                "company_region": "SF Bay Area",
                "company_city": "San Francisco",
                "acquirer_permalink": "/organization/outmate-corp",
                "acquirer_name": "Outmate Corp",
                "acquirer_category_list": "B2B|Marketing|Sales",
                "acquirer_country_code": "USA",
                "acquirer_state_code": "NY",
                "acquirer_region": "New York City",
                "acquirer_city": "New York",
                "acquired_at": "2026-05-10",
                "acquired_month": "2026-05",
                "acquired_quarter": "2026-Q2",
                "acquired_year": 2026,
                "price_amount": 150000000.0,
                "price_currency_code": "USD"
            }
        ]
        for a in dummy_acqs:
            cursor.execute("""
                INSERT INTO acquisitions (
                    company_permalink, company_name, company_category_list, company_country_code,
                    company_state_code, company_region, company_city, acquirer_permalink, acquirer_name,
                    acquirer_category_list, acquirer_country_code, acquirer_state_code, acquirer_region,
                    acquirer_city, acquired_at, acquired_month, acquired_quarter, acquired_year,
                    price_amount, price_currency_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """ if not is_postgres else """
                INSERT INTO acquisitions (
                    company_permalink, company_name, company_category_list, company_country_code,
                    company_state_code, company_region, company_city, acquirer_permalink, acquirer_name,
                    acquirer_category_list, acquirer_country_code, acquirer_state_code, acquirer_region,
                    acquirer_city, acquired_at, acquired_month, acquired_quarter, acquired_year,
                    price_amount, price_currency_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                a["company_permalink"], a["company_name"], a["company_category_list"], a["company_country_code"],
                a["company_state_code"], a["company_region"], a["company_city"], a["acquirer_permalink"], a["acquirer_name"],
                a["acquirer_category_list"], a["acquirer_country_code"], a["acquirer_state_code"], a["acquirer_region"],
                a["acquirer_city"], a["acquired_at"], a["acquired_month"], a["acquired_quarter"], a["acquired_year"],
                a["price_amount"], a["price_currency_code"]
            ))

        conn.commit()

    conn.close()

# Auto-initialize database on import of this module
init_db()
