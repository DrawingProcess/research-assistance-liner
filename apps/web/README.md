# Research Knowledge Web

This Next.js app can run on Cloudflare Workers through Vinext while retaining the
standard Next.js development workflow.

## Local commands

```bash
npm ci
npm run dev          # Next.js development server
npm run dev:vinext   # Cloudflare-compatible development server
npm run build        # Standard Next.js production build
npm run build:vinext # Cloudflare Workers production build
npm run preview      # Build and run the Worker locally with Wrangler
```

`npm run deploy` builds the Worker and invokes the authenticated Cloudflare
deployment command. It is intentionally a manual action; do not run it from
untrusted automation.

## Cloudflare dashboard setup

1. In the Cloudflare dashboard, create a **Workers** application connected to
   this repository.
2. Set the repository root directory to `apps/web`.
3. Set the install command to `npm ci`.
4. Set the build command to `npm run build:vinext`.
5. For a manual CLI release from this directory, authenticate with Cloudflare
   and run `npm run deploy`.

Vinext generates the deployable Worker settings in `dist/server/wrangler.json`
from the tracked `wrangler.jsonc`. The tracked configuration uses the Vinext
fetch handler and serves static assets from `dist/client`.

## Environment variables and secrets

Copy `.env.example` only for local configuration. Browser-exposed variables use
the `NEXT_PUBLIC_` prefix and must never contain credentials. Configure private
runtime credentials as Cloudflare Worker secrets (for example,
`npx wrangler secret put <NAME>`); do not add them to the dashboard public
build variables or commit them to this repository.
