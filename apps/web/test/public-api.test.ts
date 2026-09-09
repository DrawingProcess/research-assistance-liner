import { describe, expect, it } from 'vitest';

import { GET as dashboard } from '../app/api/dashboard/route';
import { GET as page } from '../app/api/pages/[slug]/route';
import { GET as topic } from '../app/api/topics/[slug]/route';

describe('public APIs', () => {
  it('returns public dashboard totals', async () => {
    const response = dashboard();

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({ pageCount: 1, topicCount: 1 });
  });

  it('returns provenance for a public page and hides unknown pages', async () => {
    const visible = await page(new Request('https://example.test'), {
      params: Promise.resolve({ slug: 'reproducible-research' }),
    });
    const missing = await page(new Request('https://example.test'), {
      params: Promise.resolve({ slug: 'unpublished-candidate' }),
    });

    expect(visible.status).toBe(200);
    await expect(visible.json()).resolves.toMatchObject({
      provenance: { sourcePath: 'concepts/reproducible-research.md' },
    });
    expect(missing.status).toBe(404);
  });

  it('returns only public pages for a public topic', async () => {
    const response = await topic(new Request('https://example.test'), {
      params: Promise.resolve({ slug: 'methods' }),
    });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toMatchObject({
      slug: 'methods',
      pages: [{ slug: 'reproducible-research' }],
    });
  });
});
