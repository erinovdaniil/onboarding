-- Migration: Add Pipeline Fields and Cleaned Transcripts Table
-- Run this SQL in your Supabase SQL Editor to update existing schema

-- Add new columns to projects table
ALTER TABLE projects
ADD COLUMN IF NOT EXISTS cleaned_script TEXT,
ADD COLUMN IF NOT EXISTS voiceover_voice VARCHAR(50) DEFAULT 'alloy',
ADD COLUMN IF NOT EXISTS avatar_config JSONB,
ADD COLUMN IF NOT EXISTS error_message TEXT,
ADD COLUMN IF NOT EXISTS processing_step VARCHAR(50);

-- Create cleaned_transcripts table
CREATE TABLE IF NOT EXISTS cleaned_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    segments JSONB NOT NULL, -- Array of {start, end, original_text, cleaned_text}
    full_cleaned_text TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for cleaned_transcripts
CREATE INDEX IF NOT EXISTS idx_cleaned_transcripts_project_id ON cleaned_transcripts(project_id);

-- Enable Row Level Security for cleaned_transcripts
ALTER TABLE cleaned_transcripts ENABLE ROW LEVEL SECURITY;

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
