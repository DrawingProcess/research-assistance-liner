create type public.visibility as enum ('public', 'internal');
create type public.page_type as enum ('paper', 'concept', 'comparison', 'query');

create table public.pages (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  type public.page_type not null,
  title text not null,
  summary text not null,
  visibility public.visibility not null default 'internal',
  source_path text not null,
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  synced_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (visibility <> 'public' or (source_path <> '' and commit_sha <> '' and synced_at is not null))
);

create table public.papers (
  page_id uuid primary key references public.pages(id) on delete cascade,
  publisher_url text not null,
  published_on date,
  visibility public.visibility not null default 'internal',
  source_path text not null,
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  synced_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.topics (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  visibility public.visibility not null default 'internal',
  source_path text not null,
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  synced_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.page_topics (
  page_id uuid not null references public.pages(id) on delete cascade,
  topic_id uuid not null references public.topics(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (page_id, topic_id)
);

create table public.explicit_edges (
  id uuid primary key default gen_random_uuid(),
  source_page_id uuid not null references public.pages(id) on delete cascade,
  target_page_id uuid not null references public.pages(id) on delete cascade,
  kind text not null,
  provenance_path text not null,
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  synced_at timestamptz not null,
  visibility public.visibility not null default 'internal',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.sync_runs (
  id uuid primary key default gen_random_uuid(),
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  status text not null check (status in ('running', 'succeeded', 'failed')),
  synced_at timestamptz not null,
  visibility public.visibility not null default 'internal',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.pages enable row level security;
alter table public.papers enable row level security;
alter table public.topics enable row level security;
alter table public.page_topics enable row level security;
alter table public.explicit_edges enable row level security;
alter table public.sync_runs enable row level security;

create policy "anon reads public pages" on public.pages for select to anon using (visibility = 'public');
create policy "anon reads public papers" on public.papers for select to anon using (visibility = 'public');
create policy "anon reads public topics" on public.topics for select to anon using (visibility = 'public');
create policy "anon reads public page topics" on public.page_topics for select to anon using (
  exists (select 1 from public.pages where pages.id = page_topics.page_id and pages.visibility = 'public')
  and exists (select 1 from public.topics where topics.id = page_topics.topic_id and topics.visibility = 'public')
);
create policy "anon reads public explicit edges" on public.explicit_edges for select to anon using (visibility = 'public');

-- sync_runs are operational metadata; no anon policy means no public access.
