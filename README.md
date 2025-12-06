# Trupeer Clone - AI-Powered Video Creator

A full-stack application that transforms screen recordings into polished videos with AI-powered features, inspired by [Trupeer](https://www.trupeer.ai/).

## Features

- 🎥 **Screen Recording**: Record your screen directly in the browser
- 🤖 **AI Script Generation**: Automatically generate polished scripts from recordings
- 🎤 **AI Voiceovers**: Generate professional voiceovers with multiple voice options
- 🌍 **Multilingual Support**: Translate scripts into 20+ languages
- ✨ **Automated Editing**: Apply zoom effects, transitions, and highlights
- 🎨 **Brand Customization**: Add logos, colors, and branding elements
- 📤 **Export & Share**: Export videos in multiple formats

## Tech Stack

- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **Backend**: Python FastAPI (separate service)
- **AI**: OpenAI API (GPT-4, Whisper, TTS)
- **Video Processing**: FFmpeg (for production)

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn
- Python 3.9+ and pip
- OpenAI API key (for AI features)

### Installation

1. **Install frontend dependencies**:
```bash
cd "Onboarding App"
npm install
```

2. **Set up Python backend**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Set up environment variables**:

   **Frontend** (`.env.local`):
   ```bash
   cp .env.local.example .env.local
   ```
   Add: `BACKEND_URL=http://localhost:8000`

   **Backend** (`backend/.env`):
   ```bash
   cd backend
   cp .env.example .env
   ```
   Add: `OPENAI_API_KEY=your_openai_api_key_here`

4. **Start the backend server** (in one terminal):
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python main.py
# Or: uvicorn main:app --reload --port 8000
```

5. **Start the frontend server** (in another terminal):
```bash
npm run dev
```

6. Open [http://localhost:3000](http://localhost:3000) in your browser.

The Python backend will be running at [http://localhost:8000](http://localhost:8000) with API docs at [http://localhost:8000/docs](http://localhost:8000/docs)

## Usage

1. **Record**: Click "Start Recording" to capture your screen
2. **Upload**: After recording, upload the video for processing
3. **Generate Script**: Use AI to generate a polished script
4. **Add Voiceover**: Generate professional voiceovers
5. **Translate**: Translate your script into multiple languages
6. **Customize**: Add branding and customize colors
7. **Process**: Apply AI-powered editing effects
8. **Export**: Download your final video

## Project Structure

```
├── app/
│   ├── api/              # Next.js API routes (proxies to Python backend)
│   │   ├── upload/
│   │   ├── generate-script/
│   │   ├── translate/
│   │   ├── generate-voiceover/
│   │   ├── process-video/
│   │   └── projects/
│   ├── components/       # React components
│   │   ├── ScreenRecorder.tsx
│   │   ├── VideoEditor.tsx
│   │   └── ProjectList.tsx
│   ├── layout.tsx        # Root layout
│   └── page.tsx          # Main page
├── backend/              # Python FastAPI backend
│   ├── app/
│   │   └── routers/      # API route handlers
│   │       ├── upload.py
│   │       ├── scripts.py
│   │       ├── voiceover.py
│   │       ├── video.py
│   │       └── projects.py
│   ├── main.py           # FastAPI application
│   ├── requirements.txt  # Python dependencies
│   └── .env              # Backend environment variables
├── public/
│   └── uploads/          # Uploaded videos (gitignored)
└── package.json
```

## API Endpoints

All endpoints are proxied from Next.js to the Python backend:

**Next.js Frontend Routes** (proxies to Python):
- `POST /api/upload` - Upload a video file
- `POST /api/generate-script` - Generate AI script
- `POST /api/translate` - Translate text
- `POST /api/generate-voiceover` - Generate voiceover
- `POST /api/process-video` - Process video with effects
- `GET /api/export/[projectId]` - Export video
- `GET /api/projects` - List all projects
- `DELETE /api/projects/[projectId]` - Delete project

**Python Backend Routes** (direct access):
- `POST /api/upload/` - Upload endpoint
- `POST /api/scripts/generate` - Script generation
- `POST /api/scripts/translate` - Translation
- `POST /api/voiceover/generate` - Voiceover generation
- `POST /api/video/process` - Video processing
- `GET /api/video/export/{project_id}` - Video export
- `GET /api/projects/` - List projects
- `DELETE /api/projects/{project_id}` - Delete project

See [http://localhost:8000/docs](http://localhost:8000/docs) for interactive API documentation.

## Environment Variables

**Frontend** (`.env.local`):
- `BACKEND_URL` - Python backend URL (default: http://localhost:8000)
- `NEXT_PUBLIC_APP_URL` - Your app URL

**Backend** (`backend/.env`):
- `OPENAI_API_KEY` - Your OpenAI API key (required for AI features)
- `BACKEND_PORT` - Backend server port (default: 8000)
- `BACKEND_HOST` - Backend server host (default: 0.0.0.0)
- `FRONTEND_URL` - Frontend URL for CORS (default: http://localhost:3000)
- `UPLOAD_DIR` - Directory for uploaded files (default: ../public/uploads)
- `DATABASE_URL` - Optional: For production database

## Production Deployment

For production, you'll need to:

1. **Backend**:
   - Deploy Python backend (FastAPI) to a service like:
     - AWS ECS/Fargate
     - Google Cloud Run
     - Heroku
     - DigitalOcean App Platform
     - Or use Gunicorn + Uvicorn workers
   - Set up a proper database (PostgreSQL recommended)
   - Configure cloud storage for videos (AWS S3, Cloudinary, etc.)
   - Add authentication and authorization

2. **Frontend**:
   - Deploy Next.js to Vercel, Netlify, or similar
   - Update `BACKEND_URL` to point to production backend
   - Configure environment variables

3. **Video Processing**:
   - Implement proper FFmpeg video processing
   - Consider using a video processing service or queue (Celery, etc.)

## Notes

- This is a demo/educational implementation
- Video processing is simplified (uses original video in demo mode)
- For production, implement proper FFmpeg video processing
- Add database persistence for projects
- Implement proper error handling and validation
- Add user authentication

## License

MIT

## References

- [Trupeer](https://www.trupeer.ai/) - Original inspiration
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Next.js Documentation](https://nextjs.org/docs)

