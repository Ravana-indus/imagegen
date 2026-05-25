# Product Creative Generator

Hosted product-image generation app using Qwen Image Edit for scene composition
and Pillow for deterministic logo and country-flag overlays.

## Workflow

1. An administrator signs in and creates a single-image or batch project.
2. Product image(s), one background, one brand logo, and a selected country flag
   are normalized and stored privately in Supabase Storage.
3. An RQ worker sends each product/background pair to
   `qwen-image-2.0-pro`, which adjusts composition and lighting without
   generating brand marks.
4. The editor previews the Qwen base with exact logo and flag overlays,
   supports placement/size adjustments, and renders final PNG downloads.
5. Completed batches can be exported as one ZIP archive.

## Architecture

| Service | Purpose |
| --- | --- |
| `apps/web` | Next.js admin interface, intended for Vercel |
| `apps/api` | FastAPI API, Supabase private-storage adapter, Pillow exporter |
| RQ worker | Executes Qwen calls and saves durable generated images |
| Redis | Queue transport for worker jobs |
| Supabase | PostgreSQL metadata and private `editimage` asset bucket |

The browser uses same-origin `/api/v1/*` requests. Next.js proxies those
requests to `API_ORIGIN`, keeping the signed administrator session HTTP-only.
The supplied Supabase publishable key is browser-safe, but it is not sufficient
for backend storage or database writes.

## Supabase State

The supplied project `qukjfjpevpjzctrtfuse` has been migrated:

- Tables: `admin_users`, `projects`, `generation_items`, `overlay_layouts`,
  and `export_assets`.
- Row Level Security is enabled on all application tables with browser roles
  revoked; the backend performs privileged access.
- Admin passwords live in Supabase Auth. `admin_users` is now the app profile
  table used for project ownership, not the credential store.
- Storage bucket `editimage` is private and accepts supported image types and
  ZIP exports.
- Creative instructions are limited to 450 characters so the protected Qwen
  prompt stays below the provider text limit.

Migration files are in [supabase/migrations](supabase/migrations).

## Required Secrets

Configure `apps/api/.env` from [apps/api/.env.example](apps/api/.env.example).
These private values are still required before live generation can run:

- `DATABASE_URL`: Supabase PostgreSQL connection string.
- `SUPABASE_SECRET_KEY`: server-only Supabase secret key; never prefix with
  `NEXT_PUBLIC_`.
- `DASHSCOPE_API_KEY`: Alibaba Cloud Model Studio API key.
- `SESSION_SECRET`: long random secret for signed administrator cookies.
- `REDIS_URL`: deployed Redis connection for the API and worker.

Configure `apps/web/.env.local` from [apps/web/.env.example](apps/web/.env.example)
and set `API_ORIGIN` to the hosted FastAPI origin.

## Local Development

```bash
pnpm install
pnpm --filter web dev
```

In separate terminals:

```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --reload --port 8000
uv run python -m app.worker
```

Run Redis locally or provide a reachable `REDIS_URL`.
For browser sign-in on local `http://` URLs, set `SESSION_COOKIE_SECURE=false`
in `apps/api/.env`; keep it `true` in hosted HTTPS environments.

After configuring backend secrets, create or update a Supabase Auth
administrator. The script confirms the email, sets the password, and marks the
Auth user with `app_metadata.role = admin`:

```bash
cd apps/api
uv run python scripts/create_admin.py owner@example.com
```

## Verification

```bash
cd apps/api
uv run pytest -v

cd ../../
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
```

## Hosting

Deploy `apps/web` to Vercel with `API_ORIGIN` pointing to the backend HTTPS
origin. Deploy `apps/api/Dockerfile` twice on a container host: one service
uses the default API command, and one worker overrides its command with:

```bash
uv run --no-dev python -m app.worker
```

Both backend services must receive the same API environment variables and
reach the same Redis service. Only the API origin should be publicly routed.
For the configured `qwen-image-2.0-pro` model, queued jobs use a Redis-backed
31-second submission interval; a 25-image batch therefore prioritizes provider
reliability over immediate completion.
# imagegen
