import { importFixtures } from './importer';

export const publicProjection = importFixtures([
  {
    slug: 'reproducible-research',
    type: 'concept',
    title: 'Reproducible research',
    summary: 'A synthetic example of published research metadata.',
    visibility: 'public',
    sourcePath: 'concepts/reproducible-research.md',
    commitSha: '1111111111111111111111111111111111111111',
    syncedAt: '2026-09-09T00:00:00.000Z',
    topics: ['methods'],
    tags: ['evidence'],
  },
]);
