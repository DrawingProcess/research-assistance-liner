import { NextResponse } from 'next/server';

import { publicProjection } from '../../../../src/fixtures';
import { createPublicReadModel } from '../../../../src/public-read-model';

export function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  return params.then(({ slug }) => {
    const topic = createPublicReadModel(publicProjection).topic(slug);
    return topic
      ? NextResponse.json(topic)
      : NextResponse.json({ error: 'Topic not found' }, { status: 404 });
  });
}
