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

    # Create yc_companies table
    if is_postgres:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS yc_companies (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                vertical VARCHAR(100),
                year INTEGER,
                batch VARCHAR(20),
                url TEXT,
                description TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_postings (
                id SERIAL PRIMARY KEY,
                job_id TEXT,
                company_name TEXT,
                title TEXT,
                description TEXT,
                min_salary NUMERIC,
                max_salary NUMERIC,
                normalized_salary NUMERIC,
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
            );
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS yc_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                vertical TEXT,
                year INTEGER,
                batch TEXT,
                url TEXT,
                description TEXT
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_postings (
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
            );
        """)

    conn.commit()

    # Check if companies table needs seeding (re-seed if db has fewer companies than COMPANIES_DB)
    cursor.execute("SELECT COUNT(*) FROM companies;")
    count = cursor.fetchone()[0]
    
    from backend.mock_db import COMPANIES_DB
    if count < len(COMPANIES_DB):
        # Clear and re-seed to pick up any new companies added to COMPANIES_DB
        cursor.execute("DELETE FROM companies;")
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

    # Seed demo YC companies if empty
    cursor.execute("SELECT COUNT(*) FROM yc_companies;")
    yc_count = cursor.fetchone()[0]
    if yc_count == 0:
        demo_yc = [
            ("Airbnb", "Consumer", 2009, "W09", "http://airbnb.com", "Airbnb is a marketplace for short-term home rentals in the US and worldwide."),
            ("Dropbox", "SaaS", 2007, "S07", "http://dropbox.com", "Dropbox is a cloud storage and file sync platform used by individuals and businesses in the US."),
            ("Stripe", "Fintech", 2010, "S10", "http://stripe.com", "Stripe is a payment processing platform for internet businesses, primarily in the US."),
            ("Reddit", "Consumer", 2005, "S05", "http://reddit.com", "Reddit is a community-based content aggregator platform. Consumer vertical."),
            ("Kiko", "Consumer", 2005, "S05", "http://kiko.com", "Kiko is an online calendar startup from YC Batch S05. Consumer vertical."),
            ("Parakey", "Consumer", 2005, "W05", "http://parakey.com", "Parakey is a web operating system startup from YC Batch W05. Consumer vertical."),
            ("Razorpay", "Fintech", 2015, "W15", "http://razorpay.com", "Razorpay is a leading payment gateway in India, serving businesses across the country."),
            ("ClearTax", "Fintech", 2011, "W11", "http://cleartax.in", "ClearTax is an India-based tax filing and financial services platform."),
            ("Meesho", "Consumer", 2015, "W15", "http://meesho.com", "Meesho is a social commerce platform in India connecting sellers and resellers."),
            ("RedCarpetUp", "Fintech", 2015, "S15", "http://redcarpetup.com", "RedCarpetUp provides credit and financial products to underserved consumers in India."),
            ("Kisan Network", "B2B", 2016, "S16", "http://kisannetwork.com", "Kisan Network connects Indian farmers to buyers directly, improving their income in India."),
            ("Innov8", "B2B", 2015, "S15", "http://innov8.work", "Innov8 is a co-working space startup based in India."),
            ("JustRide", "Consumer", 2016, "W16", "http://justride.in", "JustRide is a vehicle rental platform operating in India."),
            ("Posterous", "Consumer", 2008, "W08", "http://posterous.com", "Posterous is a blogging platform in the US that simplifies sharing content online."),
            ("Custora", "SaaS", 2010, "W10", "http://custora.com", "Custora is an AI-powered customer analytics platform for ecommerce companies in the US."),
            ("Heap", "SaaS", 2013, "W13", "http://heapanalytics.com", "Heap is an analytics platform for web and mobile products used by companies in the US."),
            ("Flexport", "B2B", 2013, "W14", "http://flexport.com", "Flexport is a modern freight forwarding and logistics platform operating in the US."),
            ("Next Caller", "SaaS", 2012, "S12", "http://nextcaller.com", "Next Caller provides real-time caller verification and fraud prevention in the US."),
            ("SimplyInsured", "Fintech", 2012, "S12", "http://simplyinsured.com", "SimplyInsured helps small businesses compare and purchase health insurance in the US."),
            ("One Month", "Consumer", 2013, "S13", "http://onemonth.com", "One Month offers online coding courses for beginners in the US."),
        ]
        ph = "%s" if is_postgres else "?"
        for row in demo_yc:
            cursor.execute(
                f"INSERT INTO yc_companies (name, vertical, year, batch, url, description) VALUES ({ph},{ph},{ph},{ph},{ph},{ph})",
                row
            )
        conn.commit()

    # Seed demo job postings if empty
    cursor.execute("SELECT COUNT(*) FROM job_postings;")
    jp_count = cursor.fetchone()[0]
    if jp_count == 0:
        demo_jobs = [
            ("1", "Mindful Health", "Mental Health Therapist/Counselor", "Provide mental health therapy and counseling services in Fort Collins.", 60000.0, 90000.0, 75000.0, "YEAR", "Fort Collins, CO", "FULL_TIME", "Full-time", "Associate", 0, 12, 125, "https://linkedin.com/jobs/view/1", "2026-05-01", "2026-06-01", "USD", "Therapy, Counseling, Mental Health"),
            ("2", "Raising Cane's", "Cashier", "Customer service and cashier role at Raising Cane's.", 15.0, 18.0, 16.5, "HOUR", "Fort Collins, CO", "PART_TIME", "Part-time", "Entry level", 0, 5, 45, "https://linkedin.com/jobs/view/2", "2026-05-05", "2026-06-05", "USD", "Customer Service, Cashiering"),
            ("3", "Stripe", "Software Engineer - AI", "Build financial infrastructure powered by AI.", 150000.0, 220000.0, 185000.0, "YEAR", "San Francisco, CA", "FULL_TIME", "Full-time", "Mid-Senior", 1, 85, 450, "https://linkedin.com/jobs/view/3", "2026-05-10", "2026-06-10", "USD", "Python, React, Stripe API, Machine Learning"),
            ("4", "Razorpay", "Product Manager", "Lead payment product lines in Bangalore.", 1200000.0, 2000000.0, 1600000.0, "YEAR", "Bangalore, India", "FULL_TIME", "Full-time", "Mid-Senior", 0, 30, 210, "https://linkedin.com/jobs/view/4", "2026-05-12", "2026-06-12", "INR", "Product Management, Fintech, SQL"),
        ]
        ph = "%s" if is_postgres else "?"
        for row in demo_jobs:
            cursor.execute(
                f"""INSERT INTO job_postings (
                    job_id, company_name, title, description, min_salary, max_salary,
                    normalized_salary, pay_period, location, work_type, formatted_work_type,
                    formatted_experience_level, remote_allowed, applies, views, job_posting_url,
                    listed_time, expiry, currency, skills_desc
                ) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
                row
            )
        conn.commit()

    conn.close()

# Auto-initialize database on import of this module
init_db()
