"""
Migration script to add zoom_config column to projects table.
Run this script once to add the column.

Usage:
    cd backend
    source venv/bin/activate
    python migrations/add_zoom_config.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# The SQL to run - you'll need to run this in Supabase SQL Editor
SQL = """
ALTER TABLE projects ADD COLUMN IF NOT EXISTS zoom_config JSONB;
"""

print("Migration: Add zoom_config column to projects table")
print("=" * 50)
print()
print("Since Supabase Python client doesn't support raw SQL,")
print("please run this SQL in your Supabase Dashboard:")
print()
print("1. Go to: https://supabase.com/dashboard")
print("2. Select your project")
print("3. Go to SQL Editor")
print("4. Run this query:")
print()
print("-" * 50)
print(SQL)
print("-" * 50)
print()

# Try to verify if column exists by attempting an update
try:
    # Try to read a project with zoom_config
    result = supabase.table("projects").select("id, zoom_config").limit(1).execute()
    print("✓ Column 'zoom_config' already exists!")
    print(f"  Sample data: {result.data}")
except Exception as e:
    if "zoom_config" in str(e).lower():
        print("✗ Column 'zoom_config' does NOT exist yet.")
        print("  Please run the SQL above to add it.")
    else:
        print(f"? Could not verify column existence: {e}")
