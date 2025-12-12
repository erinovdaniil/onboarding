import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://cjunwcthgxdfygtjdpnk.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_KEY:
    print("Warning: SUPABASE_SERVICE_ROLE_KEY not set. Some features may not work.")

# Create Supabase client with service role key for backend operations
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)




