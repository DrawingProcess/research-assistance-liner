import { NextResponse } from 'next/server';

import { publicProjection } from '../../../src/fixtures';
import { createPublicReadModel } from '../../../src/public-read-model';

export function GET() {
  return NextResponse.json(createPublicReadModel(publicProjection).dashboard());
}
