# backend/db_import_extra.py
# Imports companies.csv (YC companies) and postings.csv (LinkedIn job postings)

import os
import sys
import csv
import argparse
from backend.database import get_connection

# ─────────────────────────────────────────────
# TABLE CREATION
# ─────────────────────────────────────────────

def create_yc_companies_table(cursor, is_postgres):
    ph = "%s" if is_postgres else "?"
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
    """ if not is_postgres else """
        CREATE TABLE IF NOT EXISTS yc_companies (
            id SERIAL PRIMARY KEY,
            name TEXT,
            vertical TEXT,
            year INTEGER,
            batch TEXT,
            url TEXT,
            description TEXT
        );
    """)

def create_job_postings_table(cursor, is_postgres):
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
    """ if not is_postgres else """
        CREATE TABLE IF NOT EXISTS job_postings (
            id SERIAL PRIMARY KEY,
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

# ─────────────────────────────────────────────
# IMPORTERS
# ─────────────────────────────────────────────

def import_yc_companies(csv_file_path: str):
    """Import companies.csv (YC batch companies) into yc_companies table."""
    if not os.path.exists(csv_file_path):
        print(f"Error: '{csv_file_path}' not found.")
        sys.exit(1)

    conn = get_connection()
    cursor = conn.cursor()
    is_postgres = hasattr(cursor, 'mogrify')
    ph = "%s" if is_postgres else "?"

    create_yc_companies_table(cursor, is_postgres)
    cursor.execute("DELETE FROM yc_companies;")
    conn.commit()

    success = 0
    errors = 0

    sql = f"""
        INSERT INTO yc_companies (name, vertical, year, batch, url, description)
        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph});
    """

    try:
        with open(csv_file_path, encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    year_str = row.get('year', '0') or '0'
                    year = int(float(year_str)) if year_str.strip() else 0
                    cursor.execute(sql, (
                        row.get('name', ''),
                        row.get('vertical', ''),
                        year,
                        row.get('batch', ''),
                        row.get('url', ''),
                        row.get('description', '')
                    ))
                    success += 1
                except Exception as e:
                    errors += 1
                    continue

        conn.commit()
        print(f"[OK] yc_companies: {success} rows imported, {errors} skipped.")
    except Exception as e:
        print(f"Error importing companies: {e}")
    finally:
        conn.close()


def import_job_postings(csv_file_path: str, limit: int = 50000):
    """
    Import postings.csv (LinkedIn job postings) into job_postings table.
    Limits to first `limit` rows by default to keep the DB manageable.
    """
    if not os.path.exists(csv_file_path):
        print(f"Error: '{csv_file_path}' not found.")
        sys.exit(1)

    conn = get_connection()
    cursor = conn.cursor()
    is_postgres = hasattr(cursor, 'mogrify')
    ph = "%s" if is_postgres else "?"

    create_job_postings_table(cursor, is_postgres)
    cursor.execute("DELETE FROM job_postings;")
    conn.commit()

    success = 0
    errors = 0

    sql = f"""
        INSERT INTO job_postings (
            job_id, company_name, title, description,
            min_salary, max_salary, normalized_salary,
            pay_period, location, work_type, formatted_work_type,
            formatted_experience_level, remote_allowed, applies, views,
            job_posting_url, listed_time, expiry, currency, skills_desc
        ) VALUES (
            {ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},
            {ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph}
        );
    """

    def safe_float(val):
        try:
            return float(val) if val and str(val).strip() else None
        except:
            return None

    def safe_int(val):
        try:
            return int(float(val)) if val and str(val).strip() else None
        except:
            return None

    try:
        with open(csv_file_path, encoding='utf-8', errors='replace') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= limit:
                    print(f"Reached row limit of {limit:,}. Stopping import.")
                    break
                try:
                    cursor.execute(sql, (
                        row.get('job_id', ''),
                        row.get('company_name', ''),
                        row.get('title', ''),
                        (row.get('description', '') or '')[:2000],  # truncate long descriptions
                        safe_float(row.get('min_salary')),
                        safe_float(row.get('max_salary')),
                        safe_float(row.get('normalized_salary')),
                        row.get('pay_period', ''),
                        row.get('location', ''),
                        row.get('work_type', ''),
                        row.get('formatted_work_type', ''),
                        row.get('formatted_experience_level', ''),
                        safe_int(row.get('remote_allowed')),
                        safe_int(row.get('applies')),
                        safe_int(row.get('views')),
                        row.get('job_posting_url', ''),
                        row.get('listed_time', ''),
                        row.get('expiry', ''),
                        row.get('currency', ''),
                        (row.get('skills_desc', '') or '')[:1000]
                    ))
                    success += 1

                    if success % 5000 == 0:
                        conn.commit()
                        print(f"  → {success:,} rows committed so far...")

                except Exception as e:
                    errors += 1
                    continue

        conn.commit()
        print(f"[OK] job_postings: {success:,} rows imported, {errors} skipped.")
    except Exception as e:
        print(f"Error importing postings: {e}")
    finally:
        conn.close()


# ─────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import extra Crunchbase/LinkedIn datasets into SQL database.")
    parser.add_argument("--companies", help="Path to companies.csv (YC companies)")
    parser.add_argument("--postings", help="Path to postings.csv (LinkedIn job postings)")
    parser.add_argument("--limit", type=int, default=50000, help="Max rows to import from postings.csv (default: 50,000)")
    args = parser.parse_args()

    if not args.companies and not args.postings:
        print("Please provide at least one of --companies or --postings")
        parser.print_help()
        sys.exit(1)

    if args.companies:
        print(f"\nImporting YC Companies from: {args.companies}")
        import_yc_companies(args.companies)

    if args.postings:
        print(f"\nImporting Job Postings from: {args.postings} (limit: {args.limit:,} rows)")
        import_job_postings(args.postings, limit=args.limit)

    print("\nAll imports complete.")
