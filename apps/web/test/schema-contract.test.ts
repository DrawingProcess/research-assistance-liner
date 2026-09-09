import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const migrationPath = fileURLToPath(new URL('../supabase/migrations/20260909000000_public_projection.sql', import.meta.url));
const migration = [
  readFileSync(migrationPath, 'utf8'),
  readFileSync(fileURLToPath(new URL('../supabase/migrations/20260909000001_review_hardening.sql', import.meta.url)), 'utf8'),
].join(String.fromCharCode(10));

describe('public projection migration contract', () => {
  it('enables RLS on every exposed projection table', () => {
    for (const table of ['pages', 'papers', 'topics', 'tags', 'page_topics', 'page_tags', 'explicit_edges', 'sync_runs']) {
      expect(migration).toContain(`alter table public.${table} enable row level security;`);
    }
  });

  it('allows anon explicit-edge reads only when the edge and both endpoints are public', () => {
    const finalEdgePolicy = migration.slice(migration.lastIndexOf('create policy "anon reads public explicit edges"'));
    expect(finalEdgePolicy).toMatch(/visibility = 'public'[\s\S]*source_page_id[\s\S]*visibility = 'public'[\s\S]*target_page_id[\s\S]*visibility = 'public'/);
  });

  it('constrains page and edge confidence values', () => {
    expect(migration).toContain("add column confidence text not null default 'medium'");
    expect(migration).toContain("check (confidence in ('high', 'medium', 'low'))");
    expect(migration).toMatch(/create type public.edge_confidence as enum \('EXTRACTED', 'INFERRED', 'AMBIGUOUS'\)/);
    expect(migration).toMatch(/confidence public.edge_confidence not null default 'EXTRACTED'/);
  });
});
