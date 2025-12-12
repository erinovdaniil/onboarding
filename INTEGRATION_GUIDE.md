# Auto Transcription & Supabase Integration Guide

## Current Status

✅ **Backend Infrastructure** - Complete
✅ **Database Schema** - Ready to deploy
✅ **Supabase Client Setup** - Configured
✅ **Auto Transcription** - Implemented with Whisper API
✅ **Transcript Segmentation** - Ready to use
⚠️ **API Keys** - Need to be added
⚠️ **Database Tables** - Need to be created in Supabase

## Step 1: Add API Keys

### Get Your Supabase Service Role Key

1. Go to your Supabase dashboard: https://supabase.com/dashboard/project/cjunwcthgxdfygtjdpnk
2. Navigate to **Settings** → **API**
3. Copy the **service_role** key (keep it secret!)
4. Open `backend/.env` and replace `your_service_role_key_here` with your actual key

### Get Your OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Create a new API key if you don't have one
3. Copy the key
4. Open `backend/.env` and replace `your_openai_api_key_here` with your actual key

**Your backend/.env should look like this:**
```env
SUPABASE_URL=https://cjunwcthgxdfygtjdpnk.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...your_actual_key
OPENAI_API_KEY=sk-proj-...your_actual_key
BACKEND_PORT=8000
BACKEND_HOST=0.0.0.0
FRONTEND_URL=http://localhost:3000
SUPABASE_STORAGE_BUCKET=videos
UPLOAD_DIR=../public/uploads
```

## Step 2: Create Database Tables

1. Go to your Supabase dashboard
2. Navigate to **SQL Editor**
3. Click **New Query**
4. Copy the entire contents of `backend/database_schema.sql`
5. Paste it into the SQL Editor
6. Click **Run** to execute

This will create:
- `projects` table
- `transcripts` table
- `video_files` table
- All necessary indexes and RLS policies

## Step 3: Create Storage Bucket

1. In Supabase dashboard, go to **Storage**
2. Click **New bucket**
3. Name it: `videos`
4. Make it **Public**
5. Click **Create bucket**

## Step 4: Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

Or if using Python 3:
```bash
cd backend
pip3 install -r requirements.txt
```

## Step 5: Start the Backend Server

```bash
cd backend
python main.py
```

Or:
```bash
cd backend
python3 main.py
```

The backend should start on http://localhost:8000

You can test it by visiting http://localhost:8000 in your browser - you should see:
```json
{"message": "Trupeer Clone API", "status": "running"}
```

## Step 6: Test the Integration

With both servers running:
- Frontend: http://localhost:3000 (already running)
- Backend: http://localhost:8000 (just started)

### Test Video Upload with Auto Transcription

1. Go to http://localhost:3000
2. Upload a video (record or upload a file)
3. The backend will automatically:
   - Upload video to Supabase Storage
   - Extract audio using FFmpeg
   - Transcribe using OpenAI Whisper API
   - Save transcript with timestamps to database
   - Return transcript to frontend

## How It Works

### Backend Flow

1. **Upload** (`POST /api/upload/`)
   - Receives video file
   - Uploads to Supabase Storage
   - Extracts audio with FFmpeg
   - Transcribes with Whisper API
   - Saves transcript to database
   - Returns project with transcript

2. **Get Transcript** (`GET /api/transcripts/{project_id}`)
   - Fetches transcript from database
   - Returns full text and segments

3. **Segment Transcript** (`POST /api/transcripts/segment`)
   - Takes transcript and segment duration
   - Returns time-based segments for document steps

### Frontend Integration (Next Steps)

The following frontend updates need to be made:

1. **Upload Component** - Update to handle transcript response
2. **Editor Page** - Fetch transcript and generate steps from segments
3. **Document View** - Already supports step display with screenshots

## Features Enabled

✅ **Automatic Transcription** - Videos are transcribed on upload
✅ **Segment Timestamps** - Transcript includes start/end times
✅ **Supabase Storage** - Videos stored in cloud
✅ **PostgreSQL Database** - Metadata and transcripts stored
✅ **Row Level Security** - Data protected by RLS policies

## Troubleshooting

### "SUPABASE_SERVICE_ROLE_KEY not set"
- Make sure you added the key to `backend/.env`
- The key should start with `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- Restart the backend server after adding the key

### "OPENAI_API_KEY not set"
- Make sure you added the key to `backend/.env`
- The key should start with `sk-proj-...` or `sk-...`
- Check that you have credits in your OpenAI account

### "Module not found" errors
- Make sure you ran `pip install -r requirements.txt`
- Try using `pip3` instead of `pip`
- Make sure you're in the `backend` directory

### FFmpeg not found
- Install FFmpeg on your system:
  - **macOS**: `brew install ffmpeg`
  - **Ubuntu/Debian**: `sudo apt-get install ffmpeg`
  - **Windows**: Download from https://ffmpeg.org/download.html

### "Table not found" or "Bucket not found"
- Make sure you ran the SQL schema in Supabase SQL Editor
- Make sure you created the `videos` bucket in Supabase Storage

## Security Notes

⚠️ **Important:**
- Never commit `backend/.env` to git (it's already in .gitignore)
- The service_role key has admin access - keep it secret
- Only use service_role key in the backend, never in frontend
- The anon key in frontend is safe to expose (protected by RLS)

## Next Steps After Setup

Once you have the backend running with valid API keys:

1. **Test video upload with transcription**
2. **Integrate transcript display in editor**
3. **Generate document steps from transcript segments**
4. **Add avatar integration (optional)**
5. **Test end-to-end workflow**
