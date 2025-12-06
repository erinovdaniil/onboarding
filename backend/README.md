# Trupeer Clone - Python Backend

FastAPI backend for the Trupeer Clone application, handling all business logic separately from the Next.js frontend.

## Tech Stack

- **Framework**: FastAPI
- **Python**: 3.9+
- **AI**: OpenAI API (GPT-4, Whisper, TTS)
- **Video Processing**: FFmpeg (via ffmpeg-python)

## Setup

1. **Create a virtual environment**:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**:
```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
```

4. **Run the server**:
```bash
python main.py
# Or using uvicorn directly:
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Upload
- `POST /api/upload/` - Upload video file

### Scripts
- `POST /api/scripts/generate` - Generate AI script
- `POST /api/scripts/translate` - Translate script

### Voiceover
- `POST /api/voiceover/generate` - Generate AI voiceover

### Video
- `POST /api/video/process` - Process video with enhancements
- `GET /api/video/export/{project_id}` - Export video

### Projects
- `GET /api/projects/` - List all projects
- `DELETE /api/projects/{project_id}` - Delete project

## Environment Variables

- `OPENAI_API_KEY` - Your OpenAI API key (required)
- `BACKEND_PORT` - Backend server port (default: 8000)
- `BACKEND_HOST` - Backend server host (default: 0.0.0.0)
- `FRONTEND_URL` - Frontend URL for CORS (default: http://localhost:3000)
- `UPLOAD_DIR` - Directory for uploaded files (default: ../public/uploads)

## Development

The backend runs separately from the Next.js frontend. The Next.js API routes will proxy requests to this Python backend.

## Production

For production deployment:
1. Use a production ASGI server like Gunicorn with Uvicorn workers
2. Set up proper database (PostgreSQL)
3. Use cloud storage for video files (AWS S3, etc.)
4. Configure proper CORS settings
5. Add authentication and authorization

