# Research Knowledge Web Platform Design

## Goal

Build a public research-discovery website with an authenticated operator console.
The site visualizes published research knowledge while preserving Markdown/Git as
the durable source of truth. Operators can propose, review, and approve backlog
and gap records without granting public visitors write access.

## Architecture

```text
Git Markdown (source of truth)
  -> import worker -> Supabase Postgres projection -> Next.js public UI
  <- approved PR / sync worker <- operator review workflow
```

The web database is a query projection, not canonical evidence. Raw text, API
responses, secrets, private notes, and unpublished candidates never enter public
tables. Every projection row retains source path, commit SHA, and sync timestamp.

## Product Surfaces

### Public

- Dashboard: corpus totals, active topics, accepted gaps, update time
- Topic, paper, concept, comparison, and query browsing
- Search/filter by topic, tag, confidence, date, and gap status
- Interactive graph built from explicit `sources`, wikilinks, tags, and topics
- Gap pages that show status, evidence links, review rationale, and provenance
- Source links to publisher/arXiv URLs; do not redistribute paper bodies/PDFs

### Operator Console

- Sign-in restricted to allowlisted reviewers/admins
- Backlog topic create/edit/priority/status
- Gap candidate review: accept, contest, defer, reject
- Required decision reason and evidence references
- Audit timeline with actor, timestamp, prior state, and decision
- Sync health, import errors, and a manually triggered import request

## Data Model

- `papers`: public metadata and structured extraction safe for publication
- `canonical_pages`: slug, type, title, summary, confidence, source path, commit
- `explicit_edges`: source/target/kind/provenance/confidence=`EXTRACTED`
- `topics`, `tags`, `page_topics`
- `gaps`: candidate, accepted, contested, deferred, rejected
- `gap_evidence`, `gap_reviews`
- `backlog_topics`, `backlog_events`
- `sync_runs`, `import_errors`

Every mutable workflow table carries `created_at`, `updated_at`, and actor
identity. Approval does not write Markdown directly; it creates a reviewable
change request that is merged through Git, then re-imported.

## Authorization

Use Supabase Auth and Postgres RLS.

- `anon`: SELECT only rows with `visibility = 'public'`
- `reviewer`: reads internal candidates; creates reviews and backlog proposals
- `admin`: changes visibility/status and triggers imports
- `worker`: server-only service role; imports Git and writes projections

RLS is enabled on every exposed table. The browser uses only a publishable key;
the service role and Git credentials remain in server/worker secrets.

## Sync and Review Flow

1. A GitHub webhook or protected scheduled worker imports a known commit.
2. The worker parses Markdown, validates sources/links, and writes a projection
   transaction; it never edits source Markdown.
3. Operators create or review gap/backlog records in the console.
4. Approved changes create a Git change request/PR with provenance fields.
5. A human merges the PR; the next import makes the public projection current.

## Deployment

- Next.js App Router on Vercel
- Supabase for Postgres, Auth, Storage, and RLS
- Separate server-side import worker; Vercel Cron only invokes a protected
  endpoint and is not the source of truth
- Environment secrets: Supabase service role, GitHub App private credentials,
  cron secret; none are exposed to the browser
- Staging database/project before production

## Non-goals for v1

- Publishing raw paper bodies/PDFs
- Public account creation or public writes
- Automatic canonical promotion from LLM/Graphify inference
- Real-time collaborative editing
- Replacing Git/Markdown with the database

## Acceptance Criteria

- Public users can explore only explicitly public projections.
- Operators can manage backlog and review gap lifecycle with an audit trail.
- Every visible claim resolves to Git/Markdown provenance.
- Inferred edges are visibly distinct and never auto-promoted.
- A failed import leaves the previously published projection intact.
- Secrets and raw/private source data are absent from client bundles and public tables.

