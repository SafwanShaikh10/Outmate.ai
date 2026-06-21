# backend/db_import.py

import os
import sys
import csv
import argparse
from backend.database import get_connection

def import_acquisitions(csv_file_path: str):
    """
    Imports acquisitions from Kaggle Crunchbase CSV (acq.csv) to SQL database.
    """
    if not os.path.exists(csv_file_path):
        print(f"Error: File '{csv_file_path}' does not exist.")
        sys.exit(1)

    print(f"Starting import from '{csv_file_path}'...")
    
    conn = get_connection()
    cursor = conn.cursor()

    is_postgres = hasattr(cursor, 'mogrify')  # heuristic to identify postgres connection cursor

    # We will read with 'latin1' or 'utf-8-sig' to support potential Excel formatting and special characters
    try:
        with open(csv_file_path, mode='r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            
            # Verify columns
            required_cols = ['company_permalink', 'company_name', 'company_category_list', 'acquirer_name', 'price_amount']
            first_row = reader.fieldnames
            if not first_row:
                print("Error: Empty CSV file.")
                return

            missing_cols = [c for c in required_cols if c not in first_row]
            if missing_cols:
                print(f"Error: CSV is missing required columns: {missing_cols}")
                print(f"Available columns: {first_row}")
                return

            print("Schema validation successful. Importing rows...")

            # Clear existing acquisitions
            cursor.execute("DELETE FROM acquisitions;")
            
            success_count = 0
            error_count = 0

            # SQL query
            sql_query = """
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
            """

            for row in reader:
                try:
                    # Clean and parse numeric values
                    price_str = row.get('price_amount', '0')
                    price_amount = float(price_str) if price_str and price_str.strip() else 0.0
                    
                    year_str = row.get('acquired_year', '0')
                    acquired_year = int(float(year_str)) if year_str and year_str.strip() else 0

                    cursor.execute(sql_query, (
                        row.get('company_permalink', ''),
                        row.get('company_name', ''),
                        row.get('company_category_list', ''),
                        row.get('company_country_code', ''),
                        row.get('company_state_code', ''),
                        row.get('company_region', ''),
                        row.get('company_city', ''),
                        row.get('acquirer_permalink', ''),
                        row.get('acquirer_name', ''),
                        row.get('acquirer_category_list', ''),
                        row.get('acquirer_country_code', ''),
                        row.get('acquirer_state_code', ''),
                        row.get('acquirer_region', ''),
                        row.get('acquirer_city', ''),
                        row.get('acquired_at', ''),
                        row.get('acquired_month', ''),
                        row.get('acquired_quarter', ''),
                        acquired_year,
                        price_amount,
                        row.get('price_currency_code', 'USD')
                    ))
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    # Skip rows that fail to parse
                    continue

            conn.commit()
            print(f"Import completed successfully. Loaded {success_count} rows, skipped {error_count} bad rows.")

    except Exception as e:
        print(f"Database/File operation failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Crunchbase acquisitions CSV data into SQL database.")
    parser.add_argument("--file", required=True, help="Path to acq.csv file")
    args = parser.parse_args()

    import_acquisitions(args.file)
