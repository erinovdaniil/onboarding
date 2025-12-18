-- Migration: Create cleaned_transcripts table
-- This table stores the AI-improved transcript with original timestamps preserved

CREATE TABLE IF NOT EXISTS cleaned_transcripts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    segments JSONB NOT NULL,  -- Array of {id, start, end, original_text, cleaned_text}
    full_cleaned_text TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id)
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_cleaned_transcripts_project_id ON cleaned_transcripts(project_id);

-- Add RLS policies
ALTER TABLE cleaned_transcripts ENABLE ROW LEVEL SECURITY;

-- Policy: Users can view cleaned transcripts of their own projects
CREATE POLICY "Users can view cleaned transcripts of their projects"
    ON cleaned_transcripts FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = cleaned_transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

-- Policy: Users can insert cleaned transcripts for their own projects
CREATE POLICY "Users can insert cleaned transcripts for their projects"
    ON cleaned_transcripts FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = cleaned_transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

-- Policy: Users can update cleaned transcripts of their own projects
CREATE POLICY "Users can update cleaned transcripts of their projects"
    ON cleaned_transcripts FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.id = cleaned_transcripts.project_id
            AND projects.user_id = auth.uid()
        )
    );

-- Policy: Service role can do everything (for backend operations)
CREATE POLICY "Service role has full access to cleaned_transcripts"
    ON cleaned_transcripts FOR ALL
    USING (auth.role() = 'service_role');
