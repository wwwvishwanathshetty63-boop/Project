-- ============================================================
-- TASK 3: Database Schema Migration — API Key Validation
-- Run this in Supabase SQL Editor (Settings → SQL Editor)
-- ============================================================

-- ── 1. Add columns to api_endpoints ─────────────────────────
-- api_key and api_key_header already exist, adding new ones:

ALTER TABLE api_endpoints
  ADD COLUMN IF NOT EXISTS auth_type VARCHAR(20) DEFAULT 'header';

ALTER TABLE api_endpoints
  ADD COLUMN IF NOT EXISTS key_status VARCHAR(20) DEFAULT NULL;

ALTER TABLE api_endpoints
  ADD COLUMN IF NOT EXISTS last_validated_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;


-- ── 2. Add key_status to monitoring_logs ────────────────────
-- This column may already exist from the original schema.
-- IF NOT EXISTS avoids errors on re-run.

ALTER TABLE monitoring_logs
  ADD COLUMN IF NOT EXISTS api_key_status VARCHAR(20) DEFAULT NULL;


-- ── 3. Index for faster key_status queries ──────────────────

CREATE INDEX IF NOT EXISTS idx_endpoints_key_status
  ON api_endpoints(key_status);

CREATE INDEX IF NOT EXISTS idx_logs_api_key_status
  ON monitoring_logs(api_key_status);


-- ── 4. Update RLS policies (if using Supabase RLS) ──────────
-- The existing "Allow all" policies already cover these new columns.
-- No RLS changes needed.

-- ============================================================
-- VERIFICATION: Run these after migration to confirm
-- ============================================================
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'api_endpoints'
--   ORDER BY ordinal_position;
--
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'monitoring_logs'
--   ORDER BY ordinal_position;
-- ============================================================
