-- Migration: Assign existing projects to specific user
-- Run this SQL in your Supabase SQL Editor

-- This migration assigns all existing projects without a user_id to the specified user
-- Replace the email if needed

-- Step 1: Get the user ID for erinovdaniil@gmail.com and update projects
UPDATE projects
SET user_id = (
    SELECT id FROM auth.users WHERE email = 'erinovdaniil@gmail.com' LIMIT 1
)
WHERE user_id IS NULL;

-- Verify the update (optional - run separately to check)
-- SELECT id, name, user_id, created_at FROM projects;
