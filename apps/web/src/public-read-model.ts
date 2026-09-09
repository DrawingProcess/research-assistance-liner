import type { Projection, PublicPage } from './types';

function toPublicPage(page: Projection['pages'][number]): PublicPage {
  return {
    slug: page.slug,
    type: page.type,
    title: page.title,
    summary: page.summary,
    topics: [...page.topics],
    tags: [...page.tags],
    provenance: {
      sourcePath: page.sourcePath,
      commitSha: page.commitSha,
      syncedAt: page.syncedAt,
    },
  };
}

export function createPublicReadModel(projection: Projection) {
  const publicPages = projection.pages
    .filter((page) => page.visibility === 'public')
    .map(toPublicPage);

  return {
    dashboard() {
      return {
        pageCount: publicPages.length,
        topicCount: new Set(publicPages.flatMap((page) => page.topics)).size,
        lastSyncedAt: publicPages.reduce<string | undefined>(
          (latest, page) => (!latest || page.provenance.syncedAt > latest ? page.provenance.syncedAt : latest),
          undefined,
        ),
      };
    },
    page(slug: string) {
      return publicPages.find((page) => page.slug === slug);
    },
    topic(slug: string) {
      const pages = publicPages.filter((page) => page.topics.includes(slug));
      return pages.length === 0 ? undefined : { slug, pages };
    },
  };
}
