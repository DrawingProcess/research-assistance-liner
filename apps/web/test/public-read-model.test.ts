import { describe, expect, it } from 'vitest';

import { importFixtures } from '../src/importer';
import { createPublicReadModel } from '../src/public-read-model';

describe('public read model', () => {
  it('exposes only public pages while preserving complete Git provenance', () => {
    const projection = importFixtures([
      {
        slug: 'reproducible-research',
        type: 'concept',
        title: 'Reproducible research',
        summary: 'Synthetic public summary.',
        confidence: 'high',
        visibility: 'public',
        sourcePath: 'concepts/reproducible-research.md',
        commitSha: 'a'.repeat(40),
        syncedAt: '2026-09-09T00:00:00.000Z',
        topics: ['methods'],
        tags: ['evidence'],
      },
      {
        slug: 'unpublished-candidate',
        type: 'query',
        title: 'Unpublished candidate',
        summary: 'Must not be returned.',
        confidence: 'low',
        visibility: 'internal',
        sourcePath: 'queries/unpublished-candidate.md',
        commitSha: 'b'.repeat(40),
        syncedAt: '2026-09-09T00:00:00.000Z',
        topics: ['methods'],
        tags: ['evidence'],
      },
    ]);

    const model = createPublicReadModel(projection);

    expect(model.dashboard().pageCount).toBe(1);
    expect(model.topic('methods')?.pages).toEqual([
      expect.objectContaining({
        slug: 'reproducible-research',
        provenance: {
          sourcePath: 'concepts/reproducible-research.md',
          commitSha: 'a'.repeat(40),
          syncedAt: '2026-09-09T00:00:00.000Z',
        },
      }),
    ]);
    expect(model.page('unpublished-candidate')).toBeUndefined();
  });

  it('rejects a public projection that has incomplete source provenance', () => {
    expect(() =>
      importFixtures([
        {
          slug: 'missing-provenance',
          type: 'concept',
          title: 'Missing provenance',
          summary: 'Synthetic public summary.',
          confidence: 'medium',
          visibility: 'public',
          sourcePath: '',
          commitSha: '',
          syncedAt: '',
          topics: ['methods'],
          tags: ['evidence'],
        },
      ]),
    ).toThrow('Public projection requires sourcePath, commitSha, and syncedAt');
  });

  it.each([
    ['an unapproved source directory', 'drafts/missing-provenance.md', 'c'.repeat(40)],
    ['a traversal path', 'concepts/../private.md', 'c'.repeat(40)],
    ['an unpinned commit', 'concepts/missing-provenance.md', 'HEAD'],
    ['an uppercase commit SHA', 'concepts/missing-provenance.md', 'C'.repeat(40)],
  ])('rejects %s for a public projection', (_label, sourcePath, commitSha) => {
    expect(() =>
      importFixtures([
        {
          slug: 'missing-provenance',
          type: 'concept',
          title: 'Missing provenance',
          summary: 'Synthetic public summary.',
          confidence: 'medium',
          visibility: 'public',
          sourcePath,
          commitSha,
          syncedAt: '2026-09-09T00:00:00.000Z',
          topics: ['methods'],
          tags: ['evidence'],
        },
      ]),
    ).toThrow('Public projection requires an approved Markdown sourcePath and pinned commitSha');
  });
});
