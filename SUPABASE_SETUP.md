# Supabase Setup Guide

This guide will help you set up Supabase for your application.

## Prerequisites

1. A Supabase account (sign up at https://supabase.com)
2. Your Supabase project URL: `https://cjunwcthgxdfygtjdpnk.supabase.co`

## Step 1: Get Your Supabase Keys

1. Go to your Supabase project dashboard
2. Navigate to **Settings** → **API**
3. Copy the following keys:
   - **Project URL**: `https://cjunwcthgxdfygtjdpnk.supabase.co`
   - **anon/public key**: This is your `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - **service_role key**: This is your `SUPABASE_SERVICE_ROLE_KEY` (keep this secret!)

## Step 2: Set Up Environment Variables

### Frontend (Next.js)

✅ **Already configured!** The `.env.local` file has been created with your Supabase anon key.

The frontend is ready to use. The Supabase client will automatically use:
- **Project URL**: `https://cjunwcthgxdfygtjdpnk.supabase.co`
- **Anon Key**: Already configured in `.env.local`

If you need to update it, edit `.env.local`:
```env
NEXT_PUBLIC_SUPABASE_URL=https://cjunwcthgxdfygtjdpnk.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key_here

BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### Backend (Python)

Create a `.env` file in the `backend/` directory:

```env
SUPABASE_URL=https://cjunwcthgxdfygtjdpnk.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

OPENAI_API_KEY=your_openai_api_key_here

BACKEND_PORT=8000
BACKEND_HOST=0.0.0.0
FRONTEND_URL=http://localhost:3000

SUPABASE_STORAGE_BUCKET=videos
```

## Step 3: Create Database Tables

1. Go to your Supabase dashboard
2. Navigate to **SQL Editor**
3. Copy and paste the contents of `backend/database_schema.sql`
4. Click **Run** to execute the SQL

This will create:
- `projects` table - stores project metadata
- `transcripts` table - stores video transcripts
- `video_files` table - tracks files in Supabase Storage
- Row Level Security (RLS) policies for data protection

## Step 4: Create Storage Bucket

1. Go to **Storage** in your Supabase dashboard
2. Click **New bucket**
3. Name it `videos`
4. Make it **Public** (or Private if you prefer, but you'll need to generate signed URLs)
5. Click **Create bucket**

## Step 5: Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

This will install the Supabase Python client and other dependencies.

## Step 6: Test the Connection

### Test from Python Backend

You can test the connection by running:

```python
from app.supabase_client import supabase

# Test database connection
result = supabase.table("projects").select("*").limit(1).execute()
print("Database connection:", "OK" if result else "FAILED")

# Test storage connection
buckets = supabase.storage.list_buckets()
print("Storage connection:", "OK" if buckets else "FAILED")
```

### Test from Next.js Frontend

The Supabase client is already set up in `lib/supabase.ts`. You can use it in your components:

```typescript
import { supabase } from '@/lib/supabase'

// Example: Sign up a user
const { data, error } = await supabase.auth.signUp({
  email: 'user@example.com',
  password: 'password123'
})
```

## Features Enabled

✅ **Supabase Storage** - Videos are now stored in Supabase Storage instead of local filesystem  
✅ **Supabase Database** - Project metadata, transcripts, and file tracking in PostgreSQL  
✅ **Row Level Security** - Data is protected with RLS policies (users can only see their own projects)  
✅ **Scalable** - No more local filesystem limitations  

## Next Steps

1. **Add Authentication**: Implement user sign-up/login using Supabase Auth
2. **Update Frontend**: Use Supabase client for authentication and data fetching
3. **Migrate Existing Data**: If you have existing projects, create a migration script

## Troubleshooting

### "Missing NEXT_PUBLIC_SUPABASE_ANON_KEY"
- Make sure you've created `.env.local` with the correct key
- Restart your Next.js dev server after adding environment variables

### "Storage error" or "Bucket not found"
- Make sure you've created the `videos` bucket in Supabase Storage
- Check that the bucket name matches `SUPABASE_STORAGE_BUCKET` in your backend `.env`

### "Database error" or "Table not found"
- Make sure you've run the SQL schema in the Supabase SQL Editor
- Check that all tables (`projects`, `transcripts`, `video_files`) exist

### RLS Policy Errors
- If you're using the service role key, RLS is bypassed automatically
- For client-side operations, make sure users are authenticated
- Check RLS policies in Supabase dashboard under **Authentication** → **Policies**

## Security Notes

⚠️ **Important**: 
- Never commit your `.env` or `.env.local` files to git
- The `service_role` key has admin access - keep it secret and only use it server-side
- The `anon` key is safe to expose in client-side code (it's protected by RLS)

