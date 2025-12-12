-- Supabase Database Schema
-- Run this SQL in your Supabase SQL Editor to create the necessary tables

-- Projects table
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    video_url TEXT,
    processed_video_url TEXT,
    cleaned_script TEXT,
    voiceover_voice VARCHAR(50) DEFAULT 'alloy',
    avatar_config JSONB,
    error_message TEXT,
    processing_step VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Transcripts table
CREATE TABLE IF NOT EXISTS transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    segments JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Video files table (for tracking all video files in Supabase Storage)
CREATE TABLE IF NOT EXISTS video_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    file_type TEXT NOT NULL, -- 'original', 'processed', 'audio', 'avatar'
    storage_path TEXT NOT NULL, -- Path in Supabase Storage bucket
    file_size BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Cleaned transcripts table (for AI-cleaned transcript with preserved timestamps)
CREATE TABLE IF NOT EXISTS cleaned_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    segments JSONB NOT NULL, -- Array of {start, end, original_text, cleaned_text}
    full_cleaned_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transcripts_project_id ON transcripts(project_id);
CREATE INDEX IF NOT EXISTS idx_video_files_project_id ON video_files(project_id);
CREATE INDEX IF NOT EXISTS idx_cleaned_transcripts_project_id ON cleaned_transcripts(project_id);

-- Enable Row Level Security (RLS)
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE cleaned_transcripts ENABLE ROW LEVEL SECURITY;

-- RLS Policies for projects
-- Users can only see their own projects
CREATE POLICY "Users can view their own projects"
    ON projects FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own projects"
    ON projects FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own projects"
    ON projects FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own projects"
    ON projects FOR DELETE
    USING (auth.uid() = user_id);

-- RLS Policies for transcripts
CREATE POLICY "Users can view transcripts of their projects"
    ON transcripts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert transcripts for their projects"
    ON transcripts FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update transcripts of their projects"
    ON transcripts FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

-- RLS Policies for video_files
CREATE POLICY "Users can view video files of their projects"
    ON video_files FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = video_files.project_id
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert video files for their projects"
    ON video_files FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = video_files.project_id
            AND projects.user_id = auth.uid()
        )
    );

-- RLS Policies for cleaned_transcripts
CREATE POLICY "Users can view cleaned transcripts of their projects"
    ON cleaned_transcripts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = cleaned_transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert cleaned transcripts for their projects"
    ON cleaned_transcripts FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = cleaned_transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update cleaned transcripts of their projects"
    ON cleaned_transcripts FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = cleaned_transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

-- Note: For service role operations (backend), you may need to bypass RLS
-- or use the service role key which has admin access

