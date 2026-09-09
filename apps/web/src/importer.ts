import type { Projection, ProjectionInput } from './types';

const commitShaPattern = /^[0-9a-f]{40}$/;
const approvedMarkdownPathPattern = new RegExp('^(?:entities|concepts|comparisons|queries)[/][a-z0-9]+(?:-[a-z0-9]+)*[.]md$');

function assertPublicProvenance(page: ProjectionInput): void {
  if (!page.sourcePath || !page.commitSha || !page.syncedAt || Number.isNaN(Date.parse(page.syncedAt))) {
    throw new Error("Public projection requires sourcePath, commitSha, and syncedAt");
  }

  if (!approvedMarkdownPathPattern.test(page.sourcePath) || !commitShaPattern.test(page.commitSha)) {
    throw new Error("Public projection requires an approved Markdown sourcePath and pinned commitSha");
  }
}

/**
 * Accepts already-sanitized metadata fixtures. It deliberately has no field for
 * raw Markdown, source bodies, credentials, or unpublished annotations.
 */
export function importFixtures(pages: ProjectionInput[]): Projection {
  const slugs = new Set<string>();
  for (const page of pages) {
    if (slugs.has(page.slug)) throw new Error(`Duplicate slug: ${page.slug}`);
    slugs.add(page.slug);
    if (page.visibility === 'public') assertPublicProvenance(page);
  }
  return { pages: [...pages] };
}
