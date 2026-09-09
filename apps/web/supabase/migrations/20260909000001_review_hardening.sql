create type public.edge_confidence as enum ('EXTRACTED', 'INFERRED', 'AMBIGUOUS');

alter table public.pages
  add column confidence text not null default 'medium'
    check (confidence in ('high', 'medium', 'low'));

create table public.tags (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  label text not null,
  visibility public.visibility not null default 'internal',
  source_path text not null,
  commit_sha text not null check (commit_sha ~ '^[0-9a-f]{40}$'),
  synced_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.page_tags (
  page_id uuid not null references public.pages(id) on delete cascade,
  tag_id uuid not null references public.tags(id) on delete cascade,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (page_id, tag_id)
);

alter table public.explicit_edges
  add column confidence public.edge_confidence not null default 'EXTRACTED';

alter table public.tags enable row level security;
alter table public.page_tags enable row level security;

create policy "anon reads public tags" on public.tags for select to anon using (visibility = 'public');
create policy "anon reads public page tags" on public.page_tags for select to anon using (
  exists (select 1 from public.pages where pages.id = page_tags.page_id and pages.visibility = 'public')
  and exists (select 1 from public.tags where tags.id = page_tags.tag_id and tags.visibility = 'public')
);

drop policy "anon reads public explicit edges" on public.explicit_edges;
create policy "anon reads public explicit edges" on public.explicit_edges for select to anon using (
  visibility = 'public'
  and exists (
    select 1 from public.pages as source_page
    where source_page.id = explicit_edges.source_page_id and source_page.visibility = 'public'
  )
  and exists (
    select 1 from public.pages as target_page
    where target_page.id = explicit_edges.target_page_id and target_page.visibility = 'public'
  )
);
