import { NextResponse } from 'next/server';

import { publicProjection } from '../../../../src/fixtures';
import { createPublicReadModel } from '../../../../src/public-read-model';

export function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  return params.then(({ slug }) => {
    const page = createPublicReadModel(publicProjection).page(slug);
    return page
      ? NextResponse.json(page)
      : NextResponse.json({ error: 'Page not found' }, { status: 404 });
  });
}
