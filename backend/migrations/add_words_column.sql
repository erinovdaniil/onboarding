-- Add words column to transcripts table for word-level timestamps
-- This enables precise voiceover synchronization

ALTER TABLE transcripts
ADD COLUMN IF NOT EXISTS words JSONB;

-- Add comment explaining the column
COMMENT ON COLUMN transcripts.words IS 'Word-level timestamps from Whisper API for precise voiceover sync';
