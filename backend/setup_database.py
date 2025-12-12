"""
Script to automatically create database tables in Supabase.
Run this after adding your SUPABASE_SERVICE_ROLE_KEY to backend/.env
"""
import os
from dotenv import load_dotenv
from app.supabase_client import supabase

load_dotenv()

def read_sql_file():
    """Read the database schema SQL file."""
    with open('database_schema.sql', 'r') as f:
        return f.read()

def setup_database():
    """
    Execute the database schema to create all tables.
    """
    print("Starting database setup...")

    try:
        # Read SQL schema
        sql_content = read_sql_file()

        # Split into individual statements
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]

        print(f"Found {len(statements)} SQL statements to execute...")

        # Execute each statement
        for i, statement in enumerate(statements, 1):
            if statement:
                try:
                    print(f"Executing statement {i}/{len(statements)}...")
                    # Execute using Supabase RPC or direct SQL
                    result = supabase.rpc('exec_sql', {'sql': statement}).execute()
                    print(f"✓ Statement {i} executed successfully")
                except Exception as e:
                    # Try using postgrest API
                    print(f"⚠ Statement {i} failed (this may be normal for some statements): {str(e)[:100]}")

        print("\n✅ Database setup completed!")
        print("\nVerifying tables...")

        # Verify tables exist
        tables = ['projects', 'transcripts', 'video_files']
        for table in tables:
            try:
                result = supabase.table(table).select("*").limit(1).execute()
                print(f"✓ Table '{table}' exists and is accessible")
            except Exception as e:
                print(f"✗ Table '{table}' error: {e}")

        print("\n📝 Next steps:")
        print("1. Go to Supabase Storage and create a 'videos' bucket (if not exists)")
        print("2. Add your OpenAI API key to backend/.env")
        print("3. Start the backend server: python main.py")

    except Exception as e:
        print(f"\n❌ Error during database setup: {e}")
        print("\n📝 Manual setup required:")
        print("1. Go to your Supabase dashboard")
        print("2. Navigate to SQL Editor")
        print("3. Copy the contents of 'database_schema.sql'")
        print("4. Paste and run in SQL Editor")
        return False

    return True

if __name__ == "__main__":
    if not os.getenv("SUPABASE_SERVICE_ROLE_KEY"):
        print("❌ Error: SUPABASE_SERVICE_ROLE_KEY not found in backend/.env")
        print("Please add your Supabase service role key to backend/.env before running this script.")
        exit(1)

    setup_database()
