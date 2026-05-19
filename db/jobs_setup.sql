-- Jobs table for the asynchronous /generate_field_layout pipeline.
-- See polygarden-async-guide.md on the project owner's desktop for the
-- full design rationale and the technologies it relies on.
--
-- Paste into the Supabase SQL Editor (project ref: jfqtyxrbqolzbvglqnno).

create table jobs (
  id           uuid primary key,
  status       text not null,                   -- queued | running | done | failed
  request_body jsonb not null,
  result       jsonb,
  error        text,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- Internal table; no public access policies needed. Disable RLS so the
-- anon key the backend uses can insert/update/select.
alter table jobs disable row level security;
