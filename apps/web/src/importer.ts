import type { Projection, ProjectionInput } from './types';

const commitShaPattern = /^[0-9a-f]{40}$/;

function assertPublicProvenance(page: ProjectionInput): void {
  if (
    !page.sourcePath ||
    !commitShaPattern.test(page.commitSha) ||
    !page.syncedAt ||
    Number.isNaN(Date.parse(page.syncedAt))
  ) {
    throw new Error('Public projection requires sourcePath, commitSha, and syncedAt');
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
