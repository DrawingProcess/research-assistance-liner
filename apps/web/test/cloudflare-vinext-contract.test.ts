import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const projectRoot = fileURLToPath(new URL('..', import.meta.url));

function readProjectFile(relativePath: string): string {
  return readFileSync(new URL(`../${relativePath}`, import.meta.url), 'utf8');
}

describe('Cloudflare Workers Vinext configuration contract', () => {
  it('defines module-aware Vinext build, preview, and deployment commands', () => {
    const manifest = JSON.parse(readProjectFile('package.json')) as {
      type?: string;
      scripts?: Record<string, string>;
    };

    expect(manifest.type).toBe('module');
    expect(manifest.scripts).toMatchObject({
      'build:vinext': 'vinext build',
      preview: 'npm run build:vinext && npm run start:vinext',
      deploy: 'npm run build:vinext && npm run deploy:vinext -- --skip-build',
    });
    expect(manifest.scripts?.['deploy:vinext']).toContain('dist/server/wrangler.json');
  });

  it('includes a Workers configuration targeting Vinext output', () => {
    const wranglerPath = new URL('../wrangler.jsonc', import.meta.url);
    expect(existsSync(wranglerPath)).toBe(true);

    const wrangler = readFileSync(wranglerPath, 'utf8');
    expect(wrangler).toContain('"main": "vinext/server/fetch-handler"');
    expect(wrangler).toContain('"directory": "dist/client"');
    expect(wrangler).toContain('"compatibility_date"');
  });

  it('documents the Cloudflare Builds root, install, build, and deploy commands without public service keys', () => {
    const readme = readProjectFile('README.md');
    const envExample = readProjectFile('.env.example');

    expect(readme).toContain('apps/web');
    expect(readme).toContain('npm ci');
    expect(readme).toContain('npm run build:vinext');
    expect(readme).toContain('npm run deploy:vinext -- --skip-build');
    expect(readme).toContain('Workers');
    expect(readme).not.toMatch(/SUPABASE_SERVICE_ROLE_KEY/);
    expect(envExample).not.toMatch(/SUPABASE_SERVICE_ROLE_KEY/);
  });
});
