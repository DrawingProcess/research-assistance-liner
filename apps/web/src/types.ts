export type PageType = 'paper' | 'concept' | 'comparison' | 'query';
export type Visibility = 'public' | 'internal';

export interface ProjectionInput {
  slug: string;
  type: PageType;
  title: string;
  summary: string;
  visibility: Visibility;
  sourcePath: string;
  commitSha: string;
  syncedAt: string;
  topics: string[];
  tags: string[];
}

export interface Provenance {
  sourcePath: string;
  commitSha: string;
  syncedAt: string;
}

export interface PublicPage {
  slug: string;
  type: PageType;
  title: string;
  summary: string;
  topics: string[];
  tags: string[];
  provenance: Provenance;
}

export interface Projection {
  pages: ProjectionInput[];
}
