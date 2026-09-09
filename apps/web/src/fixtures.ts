import { importFixtures } from './importer';

export const publicProjection = importFixtures([
  {
    slug: 'reproducible-research',
    type: 'concept',
    title: 'Reproducible research',
    summary: 'A synthetic example of published research metadata.',
    confidence: 'high',
    visibility: 'public',
    sourcePath: 'concepts/reproducible-research.md',
    commitSha: '1111111111111111111111111111111111111111',
    syncedAt: '2026-09-09T00:00:00.000Z',
    topics: ['methods'],
    tags: ['evidence'],
  },
  {
    slug: 'internal-methods-note',
    type: 'query',
    title: 'Internal methods note',
    summary: 'Synthetic internal metadata that public APIs must not expose.',
    confidence: 'low',
    visibility: 'internal',
    sourcePath: 'queries/internal-methods-note.md',
    commitSha: '2222222222222222222222222222222222222222',
    syncedAt: '2026-09-09T00:00:00.000Z',
    topics: ['methods'],
    tags: ['internal'],
  },
]);
