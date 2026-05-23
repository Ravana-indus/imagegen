# Product Creative Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hosted admin-only product creative generator that creates single or shared-input batch composites with DashScope Qwen Image Edit, stores data and private assets in Supabase, enables logo/flag positioning, and exports downloadable PNG and ZIP results.

**Architecture:** A Next.js app in `apps/web` communicates only with a FastAPI service in `apps/api`. FastAPI uses SQLAlchemy against Supabase Postgres for transactional records, Supabase Storage with a server-only service credential for private assets, Redis/RQ for independent generation jobs, DashScope behind a provider adapter, and Pillow/CairoSVG for authoritative export rendering.

**Tech Stack:** TypeScript, Next.js App Router, TanStack Query, `react-konva`, Vitest, Playwright; Python 3.12, FastAPI, SQLAlchemy 2, Supabase CLI SQL migrations, psycopg, `supabase-py`, RQ/Redis, HTTPX, Pillow, CairoSVG, pwdlib/Argon2, pytest; Supabase Postgres and private Storage; Alibaba Cloud Model Studio `qwen-image-2.0-pro`.

---

## Implementation Decisions

- Use a `pnpm` workspace for the Next.js app and shared scripts, with the Python service managed independently by `uv`.
- Initialize Git before implementation because the greenfield workspace is currently not a repository and the workflow relies on small verified commits.
- Use Supabase Postgres through server-only `DATABASE_URL` from FastAPI/worker code. The browser does not call the Supabase Data API.
- Proxy browser API calls from Next.js `/api/v1/*` to FastAPI so the secure session cookie remains same-origin in hosted and local web use.
- Use `SUPABASE_SECRET_KEY` only in FastAPI and the worker for private Storage operations. It must never be declared as `NEXT_PUBLIC_*`; the supplied publishable key does not authorize this work.
- Use the existing private `editimage` bucket with `sources/`, `generated/`, and `exports/` object prefixes.
- Store normalized overlay coordinates in PostgreSQL and render final PNG output on the server.
- Use RQ jobs keyed by `generation_item_id`; run multiple worker processes only when the configured DashScope concurrency permits it.
- Bundle ISO country metadata and flag SVG artwork in the repository; convert the selected SVG to a PNG snapshot when a project is created so re-exporting uses the same flag asset.

## Target File Map

| Path | Responsibility |
| --- | --- |
| `package.json`, `pnpm-workspace.yaml` | Workspace orchestration and frontend commands. |
| `apps/web/` | Next.js interface, API client, login, dashboard, create form, progress page, and overlay editor. |
| `apps/web/src/lib/api.ts` | Typed fetch wrapper for the FastAPI cookie-authenticated API. |
| `apps/web/src/lib/countries.ts` | Supported country dropdown values. |
| `apps/web/src/components/editor/OverlayEditor.tsx` | `react-konva` drag/resize editor emitting normalized layout. |
| `apps/api/pyproject.toml` | Backend runtime/test dependencies and pytest configuration. |
| `apps/api/app/config.py` | Environment validation and constants. |
| `apps/api/app/db.py`, `apps/api/app/models.py` | SQLAlchemy engine/session and record mappings. |
| `apps/api/app/security.py` | Argon2 password verification and signed HTTP-only admin session cookie. |
| `apps/api/app/storage.py` | Supabase private `editimage` bucket upload/download/signed URL adapter. |
| `apps/api/app/services/projects.py` | Input validation, source persistence, item creation, and project status rollup. |
| `apps/api/app/services/qwen.py` | DashScope prompt and request/response adapter. |
| `apps/api/app/services/render.py` | Flag snapshot creation and final Pillow compositing. |
| `apps/api/app/services/exports.py` | PNG export records and batch ZIP generation. |
| `apps/api/app/jobs.py`, `apps/api/app/worker.py` | RQ enqueue and generation execution. |
| `apps/api/app/routes/` | Auth, projects, items, layouts, exports, and downloads API routes. |
| `apps/api/scripts/create_admin.py` | One-time secure admin credential creation. |
| `supabase/migrations/` | Tables, RLS restrictions, private `editimage` bucket, and storage restrictions. |
| `shared/flags/4x3/` | Versioned country flag SVG artwork copied from the selected licensed asset package. |
| `tests/e2e/` | Browser verification for single and batch workflows. |

## API Contract

The frontend consumes these FastAPI endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | Establish admin session cookie. |
| `POST` | `/api/v1/auth/logout` | Remove session cookie. |
| `GET` | `/api/v1/auth/me` | Resolve logged-in administrator. |
| `GET` | `/api/v1/projects` | List saved single and batch projects. |
| `POST` | `/api/v1/projects` | Upload common inputs and one or many product images; create jobs. |
| `GET` | `/api/v1/projects/{project_id}` | Load project, items, statuses, and signed previews. |
| `POST` | `/api/v1/items/{item_id}/retry` | Queue only a failed item again. |
| `PUT` | `/api/v1/items/{item_id}/layout` | Save normalized logo/flag layer layout. |
| `GET` | `/api/v1/items/{item_id}/previews` | Return short-lived signed base/logo/flag preview URLs. |
| `POST` | `/api/v1/items/{item_id}/export` | Flatten current layout into a stored final PNG. |
| `POST` | `/api/v1/projects/{project_id}/exports/zip` | Create ZIP of exported PNGs. |
| `GET` | `/api/v1/downloads/{export_id}` | Return a short-lived signed download URL. |

## Task 1: Bootstrap The Monorepo And Test Runners

**Files:**
- Create: `.gitignore`
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/next-env.d.ts`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/globals.css`
- Create: `apps/web/src/components/Providers.tsx`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/src/app/page.test.tsx`
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: Initialize source control and create workspace manifests**

Run:

```bash
git init
pnpm init
mkdir -p apps/web/src/app apps/api/app apps/api/tests
```

Expected: Git reports an initialized repository and the application directories exist.

Create these root manifests:

```json
// package.json
{
  "name": "product-creative-generator",
  "private": true,
  "scripts": {
    "dev:web": "pnpm --filter web dev",
    "test:web": "pnpm --filter web test",
    "lint:web": "pnpm --filter web lint"
  }
}
```

```yaml
# pnpm-workspace.yaml
packages:
  - apps/web
```

```gitignore
# .gitignore
.env
.env.local
.venv/
__pycache__/
.pytest_cache/
.next/
node_modules/
coverage/
playwright-report/
test-results/
```

- [ ] **Step 2: Add frontend dependencies and a failing landing-page test**

Create `apps/web/package.json`:

```json
{
  "name": "web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "next lint",
    "test": "vitest run"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.0.0",
    "konva": "^9.0.0",
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-konva": "^19.0.0",
    "use-image": "^1.1.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/react": "^16.0.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "jsdom": "^26.0.0",
    "typescript": "^5.0.0",
    "vitest": "^3.0.0"
  }
}
```

Create `apps/web/src/app/page.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HomePage from "./page";

describe("HomePage", () => {
  it("directs the admin to start creating branded images", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { name: "Product Creative Generator" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login");
  });
});
```

Run:

```bash
pnpm install
pnpm --filter web test
```

Expected: FAIL because `apps/web/src/app/page.tsx` does not yet export the tested page.

- [ ] **Step 3: Implement the minimal Next.js shell**

Create `apps/web/src/app/page.tsx`:

```tsx
import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <h1>Product Creative Generator</h1>
      <p>Create single images or consistent product batches.</p>
      <Link href="/login">Sign in</Link>
    </main>
  );
}
```

Create `apps/web/src/app/layout.tsx`:

```tsx
import "./globals.css";
import { Providers } from "../components/Providers";

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><Providers>{children}</Providers></body>
    </html>
  );
}
```

Create `apps/web/src/components/Providers.tsx`:

```tsx
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient());
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
```

Create `apps/web/tsconfig.json` and `apps/web/next-env.d.ts`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["dom", "dom.iterable", "esnext"],
    "strict": true,
    "noEmit": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "plugins": [{ "name": "next" }]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"]
}
```

```ts
/// <reference types="next" />
/// <reference types="next/image-types/global" />
```

Create `apps/web/src/app/globals.css`:

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: Arial, sans-serif; color: #1b1b1b; background: #f5f6f7; }
main { max-width: 1120px; margin: 0 auto; padding: 32px; }
button, input, select, textarea { font: inherit; }
```

Create `apps/web/next.config.ts`:

```ts
import type { NextConfig } from "next";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${process.env.API_ORIGIN}/api/v1/:path*` }];
  }
};

export default config;
```

Create `apps/web/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"]
  }
});
```

Create `apps/web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Add backend health check with a failing test, then implement it**

Create `apps/api/pyproject.toml`:

```toml
[project]
name = "product-creative-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.34,<1"
]

[dependency-groups]
dev = [
  "httpx>=0.28,<1",
  "pytest>=8,<9",
  "pytest-asyncio>=0.25,<1"
]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Create `apps/api/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_ok() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Run:

```bash
cd apps/api
uv sync
uv run pytest tests/test_health.py -v
```

Expected: FAIL because `app.main` does not exist.

Create `apps/api/app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="Product Creative API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Run:

```bash
cd apps/api
uv run pytest tests/test_health.py -v
cd ../..
pnpm --filter web test
```

Expected: Both test suites PASS.

- [ ] **Step 5: Commit the bootstrapped workspace**

```bash
git add .gitignore package.json pnpm-workspace.yaml apps
git commit -m "chore: bootstrap product creative generator workspace"
```

## Task 2: Define Supabase Schema, RLS Restrictions, And Private Buckets

**Files:**
- Create: `supabase/config.toml`
- Create: `supabase/migrations/<timestamp>_create_product_creative_schema.sql`
- Create: `apps/api/tests/integration/test_supabase_security.py`

- [ ] **Step 1: Initialize the Supabase directory and create a migration using the CLI**

Run:

```bash
supabase init
supabase migration new create_product_creative_schema
```

Expected: `supabase/config.toml` and a timestamped migration file are created by the CLI.

- [ ] **Step 2: Write an integration test that specifies anonymous denial**

Create `apps/api/tests/integration/test_supabase_security.py`:

```python
import os

import pytest
from supabase import create_client


@pytest.mark.integration
def test_anon_cannot_read_projects_or_source_assets() -> None:
    anon = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
    service = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])
    service.storage.from_("editimage").upload("sources/security/private-probe.png", b"private", {"content-type": "image/png", "upsert": "true"})

    with pytest.raises(Exception):
        anon.table("projects").select("id").execute()

    with pytest.raises(Exception):
        anon.storage.from_("editimage").download("sources/security/private-probe.png")
```

Run:

```bash
cd apps/api
uv add supabase
uv run pytest tests/integration/test_supabase_security.py -v
```

Expected: FAIL until the Supabase test project has tables and the private `editimage` bucket.

- [ ] **Step 3: Implement relational tables and server-only access restrictions in the generated migration**

Write the following SQL into the generated `supabase/migrations/<timestamp>_create_product_creative_schema.sql` file:

```sql
create extension if not exists pgcrypto;

create table public.admin_users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 1 and 120),
  mode text not null check (mode in ('single', 'batch')),
  status text not null default 'queued'
    check (status in ('draft', 'queued', 'processing', 'completed', 'partially_failed', 'failed')),
  background_asset_key text not null,
  logo_asset_key text not null,
  country_code char(2) not null,
  flag_asset_key text not null,
  optional_instruction text check (optional_instruction is null or char_length(optional_instruction) <= 300),
  prompt_version text not null default 'product-composite-v1',
  created_by uuid not null references public.admin_users(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.generation_items (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  source_product_asset_key text not null,
  status text not null default 'queued'
    check (status in ('queued', 'processing', 'generated', 'exported', 'failed')),
  provider_model text not null default 'qwen-image-2.0-pro',
  provider_request_id text,
  provider_error_code text,
  provider_error_message text,
  attempt_count integer not null default 0 check (attempt_count >= 0),
  base_composite_asset_key text,
  thumbnail_asset_key text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.overlay_layouts (
  generation_item_id uuid primary key references public.generation_items(id) on delete cascade,
  revision integer not null default 1 check (revision >= 1),
  logo_x numeric(6,5) not null default 0.05000 check (logo_x between 0 and 1),
  logo_y numeric(6,5) not null default 0.05000 check (logo_y between 0 and 1),
  logo_width numeric(6,5) not null default 0.22000 check (logo_width between 0 and 1),
  logo_height numeric(6,5) not null default 0.12000 check (logo_height between 0 and 1),
  logo_visible boolean not null default true,
  flag_x numeric(6,5) not null default 0.82000 check (flag_x between 0 and 1),
  flag_y numeric(6,5) not null default 0.05000 check (flag_y between 0 and 1),
  flag_width numeric(6,5) not null default 0.13000 check (flag_width between 0 and 1),
  flag_height numeric(6,5) not null default 0.09000 check (flag_height between 0 and 1),
  flag_visible boolean not null default true,
  updated_at timestamptz not null default now()
);

create table public.export_assets (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  generation_item_id uuid references public.generation_items(id) on delete cascade,
  asset_type text not null check (asset_type in ('final_png', 'batch_zip')),
  storage_key text not null,
  layout_revision integer,
  created_at timestamptz not null default now(),
  check (
    (asset_type = 'final_png' and generation_item_id is not null and layout_revision is not null)
    or (asset_type = 'batch_zip' and generation_item_id is null and layout_revision is null)
  )
);

alter table public.admin_users enable row level security;
alter table public.projects enable row level security;
alter table public.generation_items enable row level security;
alter table public.overlay_layouts enable row level security;
alter table public.export_assets enable row level security;

revoke all on public.admin_users, public.projects, public.generation_items, public.overlay_layouts, public.export_assets from anon, authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('editimage', 'editimage', false, 104857600, array['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml', 'application/zip'])
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
```

- [ ] **Step 4: Apply locally and verify security assertions**

Run:

```bash
supabase start
supabase db reset
cd apps/api
uv run pytest tests/integration/test_supabase_security.py -v
```

Expected: PASS; anonymous access is denied for both creative records and private source assets.

- [ ] **Step 5: Commit database and Storage foundations**

```bash
git add supabase apps/api/pyproject.toml apps/api/uv.lock apps/api/tests/integration
git commit -m "feat: define supabase creative data and private storage"
```

## Task 3: Implement Backend Configuration, Records, And Admin Authentication

**Files:**
- Create: `apps/api/app/config.py`
- Create: `apps/api/app/db.py`
- Create: `apps/api/app/models.py`
- Create: `apps/api/app/schemas.py`
- Create: `apps/api/app/security.py`
- Create: `apps/api/app/routes/__init__.py`
- Create: `apps/api/app/routes/auth.py`
- Create: `apps/api/scripts/create_admin.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/pyproject.toml`
- Test: `apps/api/tests/test_auth.py`

- [ ] **Step 1: Write authentication tests before implementation**

Create `apps/api/tests/test_auth.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_login_sets_http_only_session_cookie(monkeypatch) -> None:
    monkeypatch.setattr("app.routes.auth.verify_admin", lambda email, password, db=None: {"id": "admin-1", "email": email})
    response = TestClient(app).post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json() == {"email": "owner@example.com"}
    assert "session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_me_requires_signed_session() -> None:
    response = TestClient(app).get("/api/v1/auth/me")

    assert response.status_code == 401
```

Run:

```bash
cd apps/api
uv run pytest tests/test_auth.py -v
```

Expected: FAIL because the auth router and security dependencies do not exist.

- [ ] **Step 2: Add typed settings and SQLAlchemy mappings**

Add dependencies:

```bash
cd apps/api
uv add pydantic-settings sqlalchemy "psycopg[binary]" "pwdlib[argon2]" itsdangerous
```

Create `apps/api/app/config.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_url: str
    supabase_secret_key: str
    session_secret: str
    redis_url: str = "redis://localhost:6379/0"
    dashscope_api_key: str
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/api/v1"
    dashscope_model: str = "qwen-image-2.0-pro"
    signed_url_ttl_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `apps/api/app/db.py`:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

Create model classes in `apps/api/app/models.py` matching the migration:

```python
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AdminUser(Base):
    __tablename__ = "admin_users"
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(String, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    background_asset_key: Mapped[str] = mapped_column(Text)
    logo_asset_key: Mapped[str] = mapped_column(Text)
    country_code: Mapped[str] = mapped_column(String(2))
    flag_asset_key: Mapped[str] = mapped_column(Text)
    optional_instruction: Mapped[str | None] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class GenerationItem(Base):
    __tablename__ = "generation_items"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    source_product_asset_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    provider_model: Mapped[str] = mapped_column(String)
    provider_request_id: Mapped[str | None] = mapped_column(Text)
    provider_error_code: Mapped[str | None] = mapped_column(Text)
    provider_error_message: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer)
    base_composite_asset_key: Mapped[str | None] = mapped_column(Text)
    thumbnail_asset_key: Mapped[str | None] = mapped_column(Text)


class OverlayLayout(Base):
    __tablename__ = "overlay_layouts"
    generation_item_id: Mapped[UUID] = mapped_column(ForeignKey("generation_items.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    logo_x: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    logo_y: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    logo_width: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    logo_height: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    logo_visible: Mapped[bool] = mapped_column(Boolean)
    flag_x: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    flag_y: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    flag_width: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    flag_height: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    flag_visible: Mapped[bool] = mapped_column(Boolean)


class ExportAsset(Base):
    __tablename__ = "export_assets"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    generation_item_id: Mapped[UUID | None] = mapped_column(ForeignKey("generation_items.id"))
    asset_type: Mapped[str] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(Text)
    layout_revision: Mapped[int | None] = mapped_column(Integer)
```

- [ ] **Step 3: Implement signed-cookie authentication endpoints**

Create `apps/api/app/security.py`:

```python
from fastapi import Cookie, HTTPException
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pwdlib import PasswordHash

from app.config import get_settings

password_hash = PasswordHash.recommended()


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().session_secret, salt="admin-session")


def create_session(user_id: str, email: str) -> str:
    return serializer().dumps({"sub": user_id, "email": email})


def require_admin(session: str | None = Cookie(default=None)) -> dict[str, str]:
    if session is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return serializer().loads(session, max_age=60 * 60 * 12)
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc
```

Create `apps/api/app/schemas.py`:

```python
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AdminResponse(BaseModel):
    email: EmailStr
```

Create `apps/api/app/routes/auth.py`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AdminUser
from app.schemas import AdminResponse, LoginRequest
from app.security import create_session, password_hash, require_admin

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def verify_admin(email: str, password: str, db: Session | None = None) -> dict[str, str] | None:
    if db is None:
        return None
    user = db.scalar(select(AdminUser).where(AdminUser.email == email))
    if user is None or not password_hash.verify(password, user.password_hash):
        return None
    return {"id": str(user.id), "email": user.email}


@router.post("/login", response_model=AdminResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AdminResponse:
    admin = verify_admin(payload.email, payload.password, db)
    if admin is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    response.set_cookie("session", create_session(admin["id"], admin["email"]), httponly=True, secure=True, samesite="lax")
    return AdminResponse(email=admin["email"])


@router.get("/me", response_model=AdminResponse)
def me(admin: dict[str, str] = Depends(require_admin)) -> AdminResponse:
    return AdminResponse(email=admin["email"])


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie("session")
```

Register the router in `apps/api/app/main.py`:

```python
from fastapi import FastAPI

from app.routes.auth import router as auth_router

app = FastAPI(title="Product Creative API")
app.include_router(auth_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Add the one-admin creation script and verify auth tests**

Create `apps/api/scripts/create_admin.py`:

```python
import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.models import AdminUser
from app.security import password_hash


def main() -> None:
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password: ")
    with SessionLocal.begin() as db:
        if db.scalar(select(AdminUser).where(AdminUser.email == email)):
            raise SystemExit("Admin already exists")
        db.add(AdminUser(email=email, password_hash=password_hash.hash(password)))
    print("Admin created")


if __name__ == "__main__":
    main()
```

Run:

```bash
cd apps/api
uv run pytest tests/test_auth.py tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit backend foundation**

```bash
git add apps/api
git commit -m "feat: add backend configuration and admin sessions"
```

## Task 4: Store Validated Inputs And Create Single Or Batch Projects

**Files:**
- Create: `shared/flags/README.md`
- Create: `shared/flags/LICENSE.flag-icons`
- Create: `scripts/sync-flags.mjs`
- Create: `apps/api/app/storage.py`
- Create: `apps/api/app/services/assets.py`
- Create: `apps/api/app/services/projects.py`
- Create: `apps/api/app/jobs.py`
- Create: `apps/api/app/routes/projects.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/pyproject.toml`
- Test: `apps/api/tests/test_projects.py`
- Test: `apps/api/tests/test_assets.py`

- [ ] **Step 1: Specify upload validation and batch item creation in tests**

Create `apps/api/tests/test_assets.py`:

```python
from io import BytesIO

from PIL import Image
import pytest

from app.services.assets import validate_raster_upload


def png_bytes(width: int = 384, height: int = 384) -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_valid_png_returns_dimensions() -> None:
    assert validate_raster_upload(png_bytes(), "image/png") == (384, 384)


def test_non_image_payload_is_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid image"):
        validate_raster_upload(b"not-an-image", "image/png")
```

Create `apps/api/tests/test_projects.py`:

```python
from app.services.projects import ProjectCreateInput, build_item_names


def test_batch_creates_one_item_for_each_product() -> None:
    payload = ProjectCreateInput(
        name="Summer launch",
        mode="batch",
        country_code="LK",
        optional_instruction="Warm afternoon lighting",
        product_filenames=["serum.png", "cleanser.png"],
    )

    assert build_item_names(payload) == ["serum.png", "cleanser.png"]
```

Run:

```bash
cd apps/api
uv add pillow python-multipart cairosvg pycountry
uv run pytest tests/test_assets.py tests/test_projects.py -v
```

Expected: FAIL because services have not been created.

- [ ] **Step 2: Implement deterministic asset validation and private Storage operations**

Create `apps/api/app/storage.py`:

```python
from supabase import Client, create_client

from app.config import get_settings


class PrivateStorage:
    def __init__(self) -> None:
        settings = get_settings()
        self.client: Client = create_client(settings.supabase_url, settings.supabase_secret_key)

    def upload(self, bucket: str, key: str, payload: bytes, content_type: str) -> str:
        self.client.storage.from_(bucket).upload(
            key,
            payload,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return key

    def download(self, bucket: str, key: str) -> bytes:
        return self.client.storage.from_(bucket).download(key)

    def signed_url(self, bucket: str, key: str, expires_in: int) -> str:
        result = self.client.storage.from_(bucket).create_signed_url(key, expires_in)
        return result["signedURL"]
```

Create `apps/api/app/services/assets.py`:

```python
from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image, UnidentifiedImageError

MAX_INPUT_BYTES = 10 * 1024 * 1024
MIN_DIMENSION = 384
MAX_DIMENSION = 3072
ALLOWED_RASTER_MIMES = {"image/png", "image/jpeg", "image/webp"}


def validate_raster_upload(payload: bytes, content_type: str) -> tuple[int, int]:
    if content_type not in ALLOWED_RASTER_MIMES or len(payload) > MAX_INPUT_BYTES:
        raise ValueError("Unsupported image upload")
    try:
        with Image.open(BytesIO(payload)) as image:
            image.verify()
        with Image.open(BytesIO(payload)) as image:
            width, height = image.size
    except UnidentifiedImageError as exc:
        raise ValueError("Invalid image") from exc
    if not (MIN_DIMENSION <= width <= MAX_DIMENSION and MIN_DIMENSION <= height <= MAX_DIMENSION):
        raise ValueError("Image dimensions out of range")
    return width, height


def normalized_png(payload: bytes, content_type: str) -> bytes:
    validate_raster_upload(payload, content_type)
    with Image.open(BytesIO(payload)) as image:
        output = BytesIO()
        image.convert("RGBA").save(output, "PNG")
        return output.getvalue()


def flag_png(country_code: str, flags_root: Path) -> bytes:
    svg_path = flags_root / f"{country_code.lower()}.svg"
    if not svg_path.exists():
        raise ValueError("Unsupported country")
    return cairosvg.svg2png(url=str(svg_path), output_width=320)
```

- [ ] **Step 3: Add versioned country flag artwork pipeline**

Create `scripts/sync-flags.mjs`:

```js
import { cp, mkdir } from "node:fs/promises";
import { join } from "node:path";

const source = join("node_modules", "flag-icons", "flags", "4x3");
const target = join("shared", "flags", "4x3");
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });
await cp(join("node_modules", "flag-icons", "LICENSE"), join("shared", "flags", "LICENSE.flag-icons"));
console.log("Synced flag SVG artwork into shared/flags/4x3");
```

Create `shared/flags/README.md`:

```markdown
# Flag Assets

The files in `4x3/` are synchronized from the `flag-icons` package for deterministic country overlay exports. Run `pnpm sync:flags` after updating that package and retain `LICENSE.flag-icons` with the committed SVG files.
```

Add the dependency and sync command to root `package.json`:

```json
{
  "name": "product-creative-generator",
  "private": true,
  "scripts": {
    "dev:web": "pnpm --filter web dev",
    "test:web": "pnpm --filter web test",
    "lint:web": "pnpm --filter web lint",
    "sync:flags": "node scripts/sync-flags.mjs"
  },
  "devDependencies": {
    "flag-icons": "^7.0.0"
  }
}
```

Run:

```bash
pnpm install
pnpm sync:flags
```

Expected: `shared/flags/4x3/lk.svg` and the rest of the supported country artwork exist and can be snapshotted by the backend.

- [ ] **Step 4: Implement project creation service, queue adapter, and multipart route**

Create `apps/api/app/services/projects.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from rq import Queue
from sqlalchemy.orm import Session

from app.jobs import generate_item
from app.models import GenerationItem, OverlayLayout, Project
from app.services.assets import flag_png, normalized_png
from app.storage import PrivateStorage


@dataclass(frozen=True)
class ProjectCreateInput:
    name: str
    mode: str
    country_code: str
    optional_instruction: str | None
    product_filenames: list[str]


@dataclass(frozen=True)
class SourceUpload:
    filename: str
    content_type: str
    content: bytes


def build_item_names(payload: ProjectCreateInput) -> list[str]:
    if payload.mode == "single" and len(payload.product_filenames) != 1:
        raise ValueError("Single projects require one product image")
    if payload.mode == "batch" and not 1 <= len(payload.product_filenames) <= 25:
        raise ValueError("Batch projects require between 1 and 25 product images")
    return payload.product_filenames


def create_project_records(
    db: Session,
    storage: PrivateStorage,
    queue: Queue,
    admin_id: UUID,
    payload: ProjectCreateInput,
    background: SourceUpload,
    logo: SourceUpload,
    products: list[SourceUpload],
    flags_root: Path,
) -> Project:
    build_item_names(payload)
    project_id = uuid4()
    root = f"projects/{project_id}"
    background_key = storage.upload("editimage", f"sources/{root}/background.png", normalized_png(background.content, background.content_type), "image/png")
    logo_key = storage.upload("editimage", f"sources/{root}/logo.png", normalized_png(logo.content, logo.content_type), "image/png")
    flag_key = storage.upload("editimage", f"sources/{root}/flag.png", flag_png(payload.country_code, flags_root), "image/png")
    project = Project(
        id=project_id,
        name=payload.name,
        mode=payload.mode,
        status="queued",
        background_asset_key=background_key,
        logo_asset_key=logo_key,
        country_code=payload.country_code,
        flag_asset_key=flag_key,
        optional_instruction=payload.optional_instruction,
        prompt_version="product-composite-v1",
        created_by=admin_id,
    )
    db.add(project)
    item_ids: list[UUID] = []
    for upload in products:
        item_id = uuid4()
        item_ids.append(item_id)
        source_key = storage.upload("editimage", f"sources/{root}/products/{item_id}.png", normalized_png(upload.content, upload.content_type), "image/png")
        db.add(GenerationItem(id=item_id, project_id=project_id, source_product_asset_key=source_key, status="queued", provider_model="qwen-image-2.0-pro", attempt_count=0))
        db.add(OverlayLayout(generation_item_id=item_id, revision=1, logo_x=0.05, logo_y=0.05, logo_width=0.22, logo_height=0.12, logo_visible=True, flag_x=0.82, flag_y=0.05, flag_width=0.13, flag_height=0.09, flag_visible=True))
    db.commit()
    for item_id in item_ids:
        queue.enqueue(generate_item, str(item_id), job_id=f"generation:{item_id}")
    return project
```

Create `apps/api/app/jobs.py`:

```python
from redis import Redis
from rq import Queue

from app.config import get_settings


def generation_queue() -> Queue:
    return Queue("generations", connection=Redis.from_url(get_settings().redis_url))


def generate_item(item_id: str) -> None:
    from app.services.worker_runtime import execute_generation
    execute_generation(item_id)
```

Create `apps/api/app/routes/projects.py`:

```python
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from rq import Queue
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.jobs import generation_queue
from app.models import GenerationItem, Project
from app.security import require_admin
from app.services.projects import ProjectCreateInput, SourceUpload, create_project_records
from app.storage import PrivateStorage

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])
FLAGS_ROOT = Path(__file__).parents[4] / "shared" / "flags" / "4x3"


@router.post("", status_code=202)
async def create_project(
    name: str = Form(...),
    mode: str = Form(...),
    country_code: str = Form(...),
    optional_instruction: str | None = Form(default=None),
    background: UploadFile = File(...),
    logo: UploadFile = File(...),
    products: list[UploadFile] = File(...),
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(PrivateStorage),
    queue: Queue = Depends(generation_queue),
) -> dict[str, object]:
    payload = ProjectCreateInput(name, mode, country_code.upper(), optional_instruction, [item.filename or "product.png" for item in products])
    source_products = [SourceUpload(item.filename or "product.png", item.content_type or "", await item.read()) for item in products]
    project = create_project_records(
        db,
        storage,
        queue,
        UUID(admin["sub"]),
        payload,
        SourceUpload(background.filename or "background.png", background.content_type or "", await background.read()),
        SourceUpload(logo.filename or "logo.png", logo.content_type or "", await logo.read()),
        source_products,
        FLAGS_ROOT,
    )
    return {"id": str(project.id), "name": project.name, "mode": project.mode, "item_count": len(source_products), "status": project.status}


@router.get("")
def list_projects(admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict[str, object]]:
    projects = list(db.scalars(select(Project).order_by(Project.created_at.desc())))
    return [
        {
            "id": str(project.id),
            "name": project.name,
            "status": project.status,
            "itemCount": len(list(db.scalars(select(GenerationItem).where(GenerationItem.project_id == project.id)))),
        }
        for project in projects
    ]


@router.get("/{project_id}")
def project_detail(project_id: str, admin: dict[str, str] = Depends(require_admin), db: Session = Depends(get_db)) -> dict[str, object]:
    project = db.get(Project, UUID(project_id))
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    items = list(db.scalars(select(GenerationItem).where(GenerationItem.project_id == project.id)))
    return {
        "id": str(project.id),
        "name": project.name,
        "status": project.status,
        "itemCount": len(items),
        "items": [{"id": str(item.id), "status": item.status} for item in items],
    }
```

Run:

```bash
cd apps/api
uv run pytest tests/test_assets.py tests/test_projects.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit project input storage**

```bash
git add package.json pnpm-lock.yaml scripts shared apps/api
git commit -m "feat: validate inputs and create creative projects"
```

## Task 5: Implement The DashScope Qwen Adapter And Independent Worker Jobs

**Files:**
- Create: `apps/api/app/services/qwen.py`
- Create: `apps/api/app/services/worker_runtime.py`
- Modify: `apps/api/app/jobs.py`
- Create: `apps/api/app/worker.py`
- Modify: `apps/api/app/services/projects.py`
- Modify: `apps/api/pyproject.toml`
- Test: `apps/api/tests/test_qwen.py`
- Test: `apps/api/tests/test_jobs.py`

- [ ] **Step 1: Write adapter tests for the protected prompt and temporary output retrieval**

Create `apps/api/tests/test_qwen.py`:

```python
import httpx

from app.services.qwen import QwenImageEditor


def test_edit_sends_product_background_and_protected_prompt() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode()
        assert "Keep the product identity" in body
        assert "Do not add logos, flags" in body
        assert "Warm afternoon lighting" in body
        return httpx.Response(
            200,
            json={
                "output": {"choices": [{"message": {"content": [{"image": "https://result.example/base.png"}]}}]},
                "request_id": "request-123",
            },
        )

    editor = QwenImageEditor("key", "https://dashscope.example/api/v1", "qwen-image-2.0-pro", httpx.Client(transport=httpx.MockTransport(handler)))
    result = editor.edit("data:image/png;base64,product", "data:image/png;base64,bg", "Warm afternoon lighting")

    assert result.image_url == "https://result.example/base.png"
    assert result.request_id == "request-123"
```

Run:

```bash
cd apps/api
uv add httpx
uv run pytest tests/test_qwen.py -v
```

Expected: FAIL because `QwenImageEditor` is not yet defined.

- [ ] **Step 2: Implement the provider adapter as the sole DashScope integration point**

Create `apps/api/app/services/qwen.py`:

```python
from dataclasses import dataclass

import httpx

BASE_PROMPT = (
    "Keep the product identity, label, shape, and colors faithful to Image 1. "
    "Place that product naturally into the setting from Image 2. "
    "Harmonize lighting, reflections, contact shadows, and perspective for a premium product advertisement. "
    "Do not add logos, flags, badges, promotional text, or unrelated objects."
)


@dataclass(frozen=True)
class QwenResult:
    request_id: str
    image_url: str


class QwenImageEditor:
    def __init__(self, api_key: str, base_url: str, model: str, client: httpx.Client | None = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = client or httpx.Client(timeout=120)

    def edit(self, product_image: str, background_image: str, optional_instruction: str | None) -> QwenResult:
        prompt = BASE_PROMPT
        if optional_instruction:
            prompt = f"{prompt} Additional direction: {optional_instruction}"
        response = self.client.post(
            f"{self.base_url}/services/aigc/multimodal-generation/generation",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "input": {"messages": [{"role": "user", "content": [{"image": product_image}, {"image": background_image}, {"text": prompt}]}]},
                "parameters": {"n": 1, "prompt_extend": True, "watermark": False},
            },
        )
        response.raise_for_status()
        payload = response.json()
        image_url = payload["output"]["choices"][0]["message"]["content"][0]["image"]
        return QwenResult(request_id=payload["request_id"], image_url=image_url)
```

- [ ] **Step 3: Write worker state-transition and failure-isolation tests**

Create `apps/api/tests/test_jobs.py`:

```python
from app.jobs import generation_failure_fields, generation_success_fields


def test_success_persists_provider_trace_and_base_key() -> None:
    fields = generation_success_fields("provider-1", "projects/p1/items/i1/base.png")
    assert fields == {
        "status": "generated",
        "provider_request_id": "provider-1",
        "base_composite_asset_key": "projects/p1/items/i1/base.png",
        "provider_error_code": None,
        "provider_error_message": None,
    }


def test_failure_keeps_item_retryable() -> None:
    fields = generation_failure_fields("RateLimitExceeded", "Provider is busy")
    assert fields["status"] == "failed"
    assert fields["provider_error_code"] == "RateLimitExceeded"
```

- [ ] **Step 4: Implement the queued job execution and store provider output immediately**

Extend `apps/api/app/jobs.py` while retaining `generation_queue()`:

```python
from typing import Any

from redis import Redis
from rq import Queue

from app.config import get_settings


def generation_queue() -> Queue:
    return Queue("generations", connection=Redis.from_url(get_settings().redis_url))


def generation_success_fields(request_id: str, base_key: str) -> dict[str, Any]:
    return {
        "status": "generated",
        "provider_request_id": request_id,
        "base_composite_asset_key": base_key,
        "provider_error_code": None,
        "provider_error_message": None,
    }


def generation_failure_fields(code: str, message: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "provider_error_code": code,
        "provider_error_message": message[:500],
    }


def generate_item(item_id: str) -> None:
    """Load item/project, call Qwen, download its temporary PNG, store it, and update that one item."""
    from app.services.worker_runtime import execute_generation

    execute_generation(item_id)
```

Add the project rollup function to `apps/api/app/services/projects.py`:

```python
def aggregate_project_status(statuses: list[str]) -> str:
    if all(status in {"generated", "exported"} for status in statuses):
        return "completed"
    if all(status == "failed" for status in statuses):
        return "failed"
    if "failed" in statuses and any(status in {"generated", "exported"} for status in statuses):
        return "partially_failed"
    if "processing" in statuses:
        return "processing"
    return "queued"
```

Create `apps/api/app/services/worker_runtime.py`:

```python
import base64
from uuid import UUID

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.jobs import generation_failure_fields, generation_success_fields
from app.models import GenerationItem, Project
from app.services.projects import aggregate_project_status
from app.services.qwen import QwenImageEditor
from app.storage import PrivateStorage


def data_url(png_bytes: bytes) -> str:
    value = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{value}"


def execute_generation(
    item_id: str,
    storage: PrivateStorage | None = None,
    editor: QwenImageEditor | None = None,
    session_factory=SessionLocal,
    output_get=httpx.get,
) -> None:
    storage = storage or PrivateStorage()
    if editor is None:
        settings = get_settings()
        editor = QwenImageEditor(settings.dashscope_api_key, settings.dashscope_base_url, settings.dashscope_model)
    with session_factory() as db:
        item = db.get(GenerationItem, UUID(item_id))
        if item is None:
            raise ValueError("Unknown generation item")
        project = db.get(Project, item.project_id)
        if project is None:
            raise ValueError("Unknown generation project")
        item.status = "processing"
        item.attempt_count += 1
        project.status = "processing"
        db.commit()
        try:
            product = storage.download("editimage", item.source_product_asset_key)
            background = storage.download("editimage", project.background_asset_key)
            result = editor.edit(data_url(product), data_url(background), project.optional_instruction)
            response = output_get(result.image_url, timeout=30)
            response.raise_for_status()
            base_key = f"generated/projects/{project.id}/items/{item.id}/base.png"
            storage.upload("editimage", base_key, response.content, "image/png")
            fields = generation_success_fields(result.request_id, base_key)
        except httpx.HTTPError as exc:
            fields = generation_failure_fields("ProviderHttpError", str(exc))
        except Exception as exc:
            fields = generation_failure_fields("GenerationFailed", str(exc))
        for key, value in fields.items():
            setattr(item, key, value)
        statuses = list(db.scalars(select(GenerationItem.status).where(GenerationItem.project_id == project.id)))
        project.status = aggregate_project_status(statuses)
        db.commit()
```

Add to `apps/api/tests/test_jobs.py`:

```python
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import AdminUser, GenerationItem, Project
from app.services.worker_runtime import execute_generation


class MemoryStorage:
    def __init__(self) -> None:
        self.files = {"product.png": b"product", "background.png": b"background"}
        self.uploaded: list[str] = []

    def download(self, bucket: str, key: str) -> bytes:
        return self.files[key]

    def upload(self, bucket: str, key: str, payload: bytes, content_type: str) -> str:
        self.uploaded.append(key)
        return key


def test_generation_downloads_temporary_result_into_private_storage() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    admin_id, project_id, item_id = uuid4(), uuid4(), uuid4()
    with Session(engine) as db:
        db.add(AdminUser(id=admin_id, email="owner@example.com", password_hash="hash"))
        db.add(Project(id=project_id, name="Launch", mode="single", status="queued", background_asset_key="background.png", logo_asset_key="logo.png", country_code="LK", flag_asset_key="flag.png", optional_instruction=None, prompt_version="product-composite-v1", created_by=admin_id, created_at=datetime.now(timezone.utc)))
        db.add(GenerationItem(id=item_id, project_id=project_id, source_product_asset_key="product.png", status="queued", provider_model="qwen-image-2.0-pro", attempt_count=0))
        db.commit()
    storage = MemoryStorage()
    editor = SimpleNamespace(edit=lambda product, background, instruction: SimpleNamespace(request_id="req-1", image_url="https://temporary.example/base.png"))
    get_output = lambda url, timeout: httpx.Response(200, content=b"generated-png")

    execute_generation(str(item_id), storage=storage, editor=editor, session_factory=lambda: Session(engine), output_get=get_output)

    assert storage.uploaded == [f"projects/{project_id}/items/{item_id}/base.png"]
    with Session(engine) as db:
        assert db.get(GenerationItem, item_id).status == "generated"
```

Create `apps/api/app/worker.py`:

```python
from redis import Redis
from rq import Worker

from app.config import get_settings


def main() -> None:
    connection = Redis.from_url(get_settings().redis_url)
    Worker(["generations"], connection=connection).work()


if __name__ == "__main__":
    main()
```

Run:

```bash
cd apps/api
uv run pytest tests/test_qwen.py tests/test_jobs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit generation worker behavior**

```bash
git add apps/api
git commit -m "feat: generate base composites through dashscope worker"
```

## Task 6: Render Exact Overlays And Persist Per-Item Layouts

**Files:**
- Create: `apps/api/app/services/render.py`
- Create: `apps/api/app/routes/items.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_render.py`
- Test: `apps/api/tests/test_layout_routes.py`

- [ ] **Step 1: Write a pixel-position rendering test**

Create `apps/api/tests/test_render.py`:

```python
from io import BytesIO

from PIL import Image

from app.services.render import Layer, render_final_png


def image_bytes(color: tuple[int, int, int, int], size: tuple[int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGBA", size, color).save(output, "PNG")
    return output.getvalue()


def test_render_places_logo_and_flag_using_normalized_coordinates() -> None:
    result = render_final_png(
        image_bytes((255, 255, 255, 255), (100, 100)),
        image_bytes((255, 0, 0, 255), (10, 10)),
        image_bytes((0, 0, 255, 255), (10, 10)),
        Layer(0.10, 0.10, 0.20, 0.20, True),
        Layer(0.70, 0.10, 0.20, 0.20, True),
    )
    image = Image.open(BytesIO(result))

    assert image.getpixel((15, 15)) == (255, 0, 0, 255)
    assert image.getpixel((75, 15)) == (0, 0, 255, 255)
```

Run:

```bash
cd apps/api
uv run pytest tests/test_render.py -v
```

Expected: FAIL because the renderer is not defined.

- [ ] **Step 2: Implement deterministic Pillow composition**

Create `apps/api/app/services/render.py`:

```python
from dataclasses import dataclass
from io import BytesIO

from PIL import Image


@dataclass(frozen=True)
class Layer:
    x: float
    y: float
    width: float
    height: float
    visible: bool


def render_final_png(base_bytes: bytes, logo_bytes: bytes, flag_bytes: bytes, logo: Layer, flag: Layer) -> bytes:
    canvas = Image.open(BytesIO(base_bytes)).convert("RGBA")
    for content, layer in ((logo_bytes, logo), (flag_bytes, flag)):
        if not layer.visible:
            continue
        overlay = Image.open(BytesIO(content)).convert("RGBA")
        width = max(1, round(canvas.width * layer.width))
        height = max(1, round(canvas.height * layer.height))
        overlay.thumbnail((width, height), Image.Resampling.LANCZOS)
        x = round(canvas.width * layer.x)
        y = round(canvas.height * layer.y)
        canvas.alpha_composite(overlay, (x, y))
    output = BytesIO()
    canvas.save(output, "PNG")
    return output.getvalue()
```

- [ ] **Step 3: Write route tests for layout validation and revision increments**

Create `apps/api/tests/test_layout_routes.py`:

```python
from pydantic import ValidationError
import pytest

from app.routes.items import LayoutUpdate


def test_layout_accepts_normalized_layers() -> None:
    payload = LayoutUpdate(
        logo={"x": 0.05, "y": 0.05, "width": 0.2, "height": 0.1, "visible": True},
        flag={"x": 0.8, "y": 0.05, "width": 0.13, "height": 0.09, "visible": True},
    )
    assert payload.flag.x == 0.8


def test_layout_rejects_layer_outside_canvas() -> None:
    with pytest.raises(ValidationError):
        LayoutUpdate(
            logo={"x": 1.1, "y": 0.05, "width": 0.2, "height": 0.1, "visible": True},
            flag={"x": 0.8, "y": 0.05, "width": 0.13, "height": 0.09, "visible": True},
        )
```

- [ ] **Step 4: Implement item layout route and backend export input contract**

Create `apps/api/app/routes/items.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import GenerationItem, OverlayLayout, Project
from app.security import require_admin
from app.storage import PrivateStorage

router = APIRouter(prefix="/api/v1/items", tags=["items"])


class LayerPayload(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    visible: bool


class LayoutUpdate(BaseModel):
    logo: LayerPayload
    flag: LayerPayload


class PreviewResponse(BaseModel):
    base_url: str
    logo_url: str
    flag_url: str


@router.put("/{item_id}/layout")
def update_layout(
    item_id: str,
    payload: LayoutUpdate,
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    layout = db.get(OverlayLayout, UUID(item_id))
    if layout is None:
        raise HTTPException(status_code=404, detail="Generation item not found")
    layout.logo_x, layout.logo_y = payload.logo.x, payload.logo.y
    layout.logo_width, layout.logo_height, layout.logo_visible = payload.logo.width, payload.logo.height, payload.logo.visible
    layout.flag_x, layout.flag_y = payload.flag.x, payload.flag.y
    layout.flag_width, layout.flag_height, layout.flag_visible = payload.flag.width, payload.flag.height, payload.flag.visible
    layout.revision += 1
    db.commit()
    return {"revision": layout.revision}


@router.get("/{item_id}/previews", response_model=PreviewResponse)
def previews(
    item_id: str,
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(PrivateStorage),
) -> PreviewResponse:
    item = db.get(GenerationItem, UUID(item_id))
    if item is None or item.base_composite_asset_key is None:
        raise HTTPException(status_code=404, detail="Preview not available")
    project = db.get(Project, item.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return PreviewResponse(
        base_url=storage.signed_url("editimage", item.base_composite_asset_key, get_settings().signed_url_ttl_seconds),
        logo_url=storage.signed_url("editimage", project.logo_asset_key, get_settings().signed_url_ttl_seconds),
        flag_url=storage.signed_url("editimage", project.flag_asset_key, get_settings().signed_url_ttl_seconds),
    )
```

Add this route assertion to `apps/api/tests/test_layout_routes.py`:

```python
from unittest.mock import Mock
from uuid import uuid4

from app.routes.items import update_layout


def test_update_layout_increments_revision() -> None:
    current = Mock(revision=1)
    db = Mock()
    db.get.return_value = current
    payload = LayoutUpdate(
        logo={"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.1, "visible": True},
        flag={"x": 0.7, "y": 0.1, "width": 0.15, "height": 0.1, "visible": True},
    )

    response = update_layout(str(uuid4()), payload, {"sub": "admin"}, db)

    assert response == {"revision": 2}
    db.commit.assert_called_once()
```

Run:

```bash
cd apps/api
uv run pytest tests/test_render.py tests/test_layout_routes.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit overlay layout and renderer behavior**

```bash
git add apps/api
git commit -m "feat: persist layouts and render branded image overlays"
```

## Task 7: Export PNG Files, Retry Failed Items, And Package Batch ZIPs

**Files:**
- Create: `apps/api/app/services/exports.py`
- Create: `apps/api/app/routes/exports.py`
- Modify: `apps/api/app/routes/items.py`
- Modify: `apps/api/app/routes/projects.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_exports.py`
- Test: `apps/api/tests/test_retry.py`

- [ ] **Step 1: Write export and ZIP unit tests**

Create `apps/api/tests/test_exports.py`:

```python
from io import BytesIO
from zipfile import ZipFile

from app.services.exports import build_zip


def test_batch_zip_contains_named_final_png_files() -> None:
    archive = build_zip([("serum-final.png", b"serum"), ("cleanser-final.png", b"cleanser")])
    with ZipFile(BytesIO(archive)) as result:
        assert result.namelist() == ["serum-final.png", "cleanser-final.png"]
        assert result.read("serum-final.png") == b"serum"
```

Create `apps/api/tests/test_retry.py`:

```python
import pytest

from app.services.projects import retryable_status


def test_only_failed_generation_items_are_retryable() -> None:
    assert retryable_status("failed") is True
    assert retryable_status("generated") is False
    with pytest.raises(ValueError, match="Only failed items"):
        retryable_status("processing")
```

Run:

```bash
cd apps/api
uv run pytest tests/test_exports.py tests/test_retry.py -v
```

Expected: FAIL until export and retry helpers exist.

- [ ] **Step 2: Implement ZIP creation and retry guard**

Create `apps/api/app/services/exports.py`:

```python
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile


def build_zip(files: list[tuple[str, bytes]]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for filename, payload in files:
            archive.writestr(filename, payload)
    return output.getvalue()
```

Add to `apps/api/app/services/projects.py`:

```python
def retryable_status(status: str) -> bool:
    if status == "failed":
        return True
    if status in {"queued", "processing"}:
        raise ValueError("Only failed items may be retried")
    return False
```

- [ ] **Step 3: Implement authenticated export routes**

Create `apps/api/app/routes/exports.py`:

```python
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ExportAsset, GenerationItem, OverlayLayout, Project
from app.security import require_admin
from app.services.exports import build_zip
from app.services.render import Layer, render_final_png
from app.storage import PrivateStorage

router = APIRouter(prefix="/api/v1", tags=["exports"])


@router.post("/items/{item_id}/export", status_code=201)
def export_item(
    item_id: str,
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(PrivateStorage),
) -> dict[str, str]:
    item = db.get(GenerationItem, UUID(item_id))
    if item is None or item.base_composite_asset_key is None:
        raise HTTPException(status_code=409, detail="Generated image is not available")
    project = db.get(Project, item.project_id)
    layout = db.get(OverlayLayout, item.id)
    if project is None or layout is None:
        raise HTTPException(status_code=404, detail="Export inputs not found")
    final = render_final_png(
        storage.download("editimage", item.base_composite_asset_key),
        storage.download("editimage", project.logo_asset_key),
        storage.download("editimage", project.flag_asset_key),
        Layer(float(layout.logo_x), float(layout.logo_y), float(layout.logo_width), float(layout.logo_height), layout.logo_visible),
        Layer(float(layout.flag_x), float(layout.flag_y), float(layout.flag_width), float(layout.flag_height), layout.flag_visible),
    )
    export_id = uuid4()
    key = f"exports/projects/{project.id}/items/{item.id}/final-r{layout.revision}.png"
    storage.upload("editimage", key, final, "image/png")
    db.add(ExportAsset(id=export_id, project_id=project.id, generation_item_id=item.id, asset_type="final_png", storage_key=key, layout_revision=layout.revision))
    item.status = "exported"
    db.commit()
    return {"export_id": str(export_id), "status": "exported"}


@router.post("/projects/{project_id}/exports/zip", status_code=201)
def export_batch_zip(
    project_id: str,
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(PrivateStorage),
) -> dict[str, str]:
    project_uuid = UUID(project_id)
    items = list(db.scalars(select(GenerationItem).where(GenerationItem.project_id == project_uuid)))
    files: list[tuple[str, bytes]] = []
    for item in items:
        final = db.scalar(
            select(ExportAsset)
            .where(ExportAsset.generation_item_id == item.id, ExportAsset.asset_type == "final_png")
            .order_by(ExportAsset.layout_revision.desc())
            .limit(1)
        )
        if final is not None:
            files.append((f"{item.id}-final.png", storage.download("editimage", final.storage_key)))
    if not files:
        raise HTTPException(status_code=409, detail="No final images are available")
    export_id = uuid4()
    key = f"exports/projects/{project_id}/batch-{export_id}.zip"
    storage.upload("editimage", key, build_zip(files), "application/zip")
    db.add(ExportAsset(id=export_id, project_id=project_uuid, generation_item_id=None, asset_type="batch_zip", storage_key=key, layout_revision=None))
    db.commit()
    return {"export_id": str(export_id), "status": "exported"}


@router.get("/downloads/{export_id}")
def signed_download(
    export_id: str,
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    storage: PrivateStorage = Depends(PrivateStorage),
) -> dict[str, str]:
    asset = db.get(ExportAsset, UUID(export_id))
    if asset is None:
        raise HTTPException(status_code=404, detail="Export not found")
    url = storage.signed_url("editimage", asset.storage_key, get_settings().signed_url_ttl_seconds)
    return {"download_url": url}
```

Add to `apps/api/tests/test_exports.py`:

```python
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.routes.exports import signed_download


def test_signed_download_uses_private_exports_bucket(monkeypatch) -> None:
    export_id = uuid4()
    db = Mock()
    db.get.return_value = SimpleNamespace(storage_key="projects/p1/items/i1/final-r1.png")
    storage = Mock()
    storage.signed_url.return_value = "https://signed.example/final.png"
    monkeypatch.setattr("app.routes.exports.get_settings", lambda: SimpleNamespace(signed_url_ttl_seconds=900))

    result = signed_download(str(export_id), {"sub": "admin"}, db, storage)

    assert result == {"download_url": "https://signed.example/final.png"}
    storage.signed_url.assert_called_once_with("editimage", "exports/projects/p1/items/i1/final-r1.png", 900)
```

The PNG export route behavior is asserted by `apps/api/tests/integration/test_generation_flow.py` in Task 10; the ZIP service test above verifies archive contents before the route stores that archive in the same private `exports` bucket.

- [ ] **Step 4: Implement item retry and project status aggregation**

Add to `apps/api/app/routes/items.py`:

```python
from rq import Queue

from app.jobs import generate_item, generation_queue
from app.models import GenerationItem
from app.services.projects import retryable_status


@router.post("/{item_id}/retry", status_code=202)
def retry_item(
    item_id: str,
    admin: dict[str, str] = Depends(require_admin),
    db: Session = Depends(get_db),
    queue: Queue = Depends(generation_queue),
) -> dict[str, str]:
    item = db.get(GenerationItem, UUID(item_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Generation item not found")
    if not retryable_status(item.status):
        raise HTTPException(status_code=409, detail="Completed items are not retryable")
    item.status = "queued"
    item.provider_error_code = None
    item.provider_error_message = None
    db.commit()
    queue.enqueue(generate_item, item_id, job_id=f"generation:{item_id}:retry:{item.attempt_count + 1}")
    return {"item_id": item_id, "status": "queued"}
```

Add tests that establish these rollup rules in `apps/api/tests/test_retry.py`:

```python
from app.services.projects import aggregate_project_status


def test_mixed_generated_and_failed_items_are_partially_failed() -> None:
    assert aggregate_project_status(["generated", "failed"]) == "partially_failed"


def test_all_generated_items_are_completed() -> None:
    assert aggregate_project_status(["generated", "exported"]) == "completed"
```

These status tests exercise `aggregate_project_status()` introduced with the worker in Task 5.

Update `apps/api/app/main.py` so all implemented API surfaces are reachable:

```python
from fastapi import FastAPI

from app.routes.auth import router as auth_router
from app.routes.exports import router as exports_router
from app.routes.items import router as items_router
from app.routes.projects import router as projects_router

app = FastAPI(title="Product Creative API")
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(items_router)
app.include_router(exports_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Run:

```bash
cd apps/api
uv run pytest tests/test_exports.py tests/test_retry.py tests/test_render.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit downloadable export behavior**

```bash
git add apps/api
git commit -m "feat: export png and batch zip results"
```

## Task 8: Build Login, Dashboard, And Project Creation Interface

**Files:**
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/countries.ts`
- Create: `apps/web/src/app/login/page.tsx`
- Create: `apps/web/src/app/dashboard/page.tsx`
- Create: `apps/web/src/app/projects/new/page.tsx`
- Create: `apps/web/src/components/ProjectForm.tsx`
- Create: `apps/web/src/components/ProjectCard.tsx`
- Test: `apps/web/src/components/ProjectForm.test.tsx`
- Test: `apps/web/src/app/dashboard/page.test.tsx`

- [ ] **Step 1: Write frontend tests for shared-input batch submission and status cards**

Create `apps/web/src/components/ProjectForm.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProjectForm } from "./ProjectForm";

describe("ProjectForm", () => {
  it("shows multiple product upload for batch mode while keeping shared campaign inputs", () => {
    render(<ProjectForm onSubmit={async () => undefined} />);
    fireEvent.click(screen.getByLabelText("Batch"));

    expect(screen.getByLabelText("Product images")).toHaveAttribute("multiple");
    expect(screen.getByLabelText("Background image")).toBeInTheDocument();
    expect(screen.getByLabelText("Brand logo")).toBeInTheDocument();
    expect(screen.getByLabelText("Country flag")).toBeInTheDocument();
  });
});
```

Create `apps/web/src/app/dashboard/page.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DashboardPage from "./page";

vi.mock("../../lib/api", () => ({
  listProjects: async () => [{ id: "p1", name: "Summer launch", status: "partially_failed", itemCount: 3 }]
}));

describe("DashboardPage", () => {
  it("shows saved project status", async () => {
    render(<DashboardPage />);
    expect(await screen.findByText("Summer launch")).toBeInTheDocument();
    expect(await screen.findByText("Partially failed")).toBeInTheDocument();
  });
});
```

Run:

```bash
pnpm --filter web test
```

Expected: FAIL because the page and components do not exist.

- [ ] **Step 2: Implement typed API calls and country options**

Create `apps/web/src/lib/api.ts`:

```ts
export type ProjectSummary = {
  id: string;
  name: string;
  status: "draft" | "queued" | "processing" | "completed" | "partially_failed" | "failed";
  itemCount: number;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: "include"
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export function listProjects(): Promise<ProjectSummary[]> {
  return api<ProjectSummary[]>("/api/v1/projects");
}

export function createProject(formData: FormData): Promise<{ id: string }> {
  return api<{ id: string }>("/api/v1/projects", { method: "POST", body: formData });
}
```

Create `apps/web/src/lib/countries.ts`:

```ts
import isoCountries from "i18n-iso-countries";
import english from "i18n-iso-countries/langs/en.json";

isoCountries.registerLocale(english);

export const countries = Object.entries(isoCountries.getNames("en", { select: "official" }))
  .map(([code, name]) => ({ code, name }))
  .filter(({ code }) => code.length === 2)
  .sort((left, right) => left.name.localeCompare(right.name));
```

Add `i18n-iso-countries` to `apps/web/package.json` and add a test asserting that `countries` includes `{ code: "LK", name: "Sri Lanka" }`; the synchronized `flag-icons` directory uses the same ISO two-letter code convention consumed by the backend.

- [ ] **Step 3: Implement the creation form**

Create `apps/web/src/components/ProjectForm.tsx`:

```tsx
"use client";

import { useState } from "react";
import { countries } from "../lib/countries";

export function ProjectForm({ onSubmit }: { onSubmit: (form: FormData) => Promise<void> }) {
  const [mode, setMode] = useState<"single" | "batch">("single");

  return (
    <form action={onSubmit}>
      <label><input type="radio" checked={mode === "single"} onChange={() => setMode("single")} />Single</label>
      <label><input type="radio" checked={mode === "batch"} onChange={() => setMode("batch")} />Batch</label>
      <input type="hidden" name="mode" value={mode} />
      <label>Project name<input name="name" required maxLength={120} /></label>
      <label>Product images<input aria-label="Product images" name="products" type="file" accept="image/png,image/jpeg,image/webp" multiple={mode === "batch"} required /></label>
      <label>Background image<input aria-label="Background image" name="background" type="file" accept="image/png,image/jpeg,image/webp" required /></label>
      <label>Brand logo<input aria-label="Brand logo" name="logo" type="file" accept="image/png,image/webp" required /></label>
      <label>Country flag<select aria-label="Country flag" name="country_code">{countries.map((country) => <option key={country.code} value={country.code}>{country.name}</option>)}</select></label>
      <label>Creative instruction<textarea name="optional_instruction" maxLength={300} /></label>
      <button type="submit">Generate creatives</button>
    </form>
  );
}
```

- [ ] **Step 4: Implement login and dashboard pages connected to the FastAPI contract**

Implement `apps/web/src/components/ProjectCard.tsx`:

```tsx
import Link from "next/link";
import type { ProjectSummary } from "../lib/api";

export function ProjectCard({ project }: { project: ProjectSummary }) {
  const status = project.status.replace("_", " ");
  return (
    <article>
      <h2>{project.name}</h2>
      <p>{status[0].toUpperCase() + status.slice(1)}</p>
      <p>{project.itemCount} output(s)</p>
      <Link href={`/projects/${project.id}`}>Open</Link>
    </article>
  );
}
```

Implement `apps/web/src/app/dashboard/page.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProjectCard } from "../../components/ProjectCard";
import { listProjects, type ProjectSummary } from "../../lib/api";

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  useEffect(() => { void listProjects().then(setProjects); }, []);
  return (
    <main>
      <header><h1>Projects</h1><Link href="/projects/new">New project</Link></header>
      {projects.map((project) => <ProjectCard key={project.id} project={project} />)}
    </main>
  );
}
```

Add to `apps/web/src/lib/api.ts`:

```ts
export function login(email: string, password: string): Promise<{ email: string }> {
  return api<{ email: string }>("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
}
```

Create `apps/web/src/app/login/page.tsx`:

```tsx
"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { login } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = new FormData(event.currentTarget);
    try {
      await login(String(values.get("email")), String(values.get("password")));
      router.push("/dashboard");
    } catch {
      setError("Invalid email or password");
    }
  }

  return (
    <main>
      <h1>Admin sign in</h1>
      <form onSubmit={submit}>
        <label>Email<input name="email" type="email" required /></label>
        <label>Password<input name="password" type="password" required /></label>
        {error && <p role="alert">{error}</p>}
        <button type="submit">Sign in</button>
      </form>
    </main>
  );
}
```

Create `apps/web/src/app/projects/new/page.tsx`:

```tsx
"use client";

import { useRouter } from "next/navigation";
import { ProjectForm } from "../../../components/ProjectForm";
import { createProject } from "../../../lib/api";

export default function NewProjectPage() {
  const router = useRouter();
  return (
    <main>
      <h1>New creative project</h1>
      <ProjectForm onSubmit={async (formData) => {
        const result = await createProject(formData);
        router.push(`/projects/${result.id}`);
      }} />
    </main>
  );
}
```

Run:

```bash
pnpm --filter web test
```

Expected: PASS.

- [ ] **Step 5: Commit admin-facing project UI**

```bash
git add apps/web package.json pnpm-lock.yaml
git commit -m "feat: add login dashboard and creative upload form"
```

## Task 9: Build Progress, Overlay Editor, Export, And Download UI

**Files:**
- Create: `apps/web/src/app/projects/[projectId]/page.tsx`
- Create: `apps/web/src/app/projects/[projectId]/items/[itemId]/page.tsx`
- Create: `apps/web/src/components/GenerationItemList.tsx`
- Create: `apps/web/src/components/editor/OverlayEditor.tsx`
- Create: `apps/web/src/components/editor/ExportControls.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Test: `apps/web/src/components/GenerationItemList.test.tsx`
- Test: `apps/web/src/components/editor/OverlayEditor.test.tsx`

- [ ] **Step 1: Define project/item frontend types and write progress/editor tests**

Add to `apps/web/src/lib/api.ts`:

```ts
export type Layer = { x: number; y: number; width: number; height: number; visible: boolean };
export type Layout = { revision: number; logo: Layer; flag: Layer };
export type GenerationItem = { id: string; status: "queued" | "processing" | "generated" | "exported" | "failed"; previewUrl?: string; layout?: Layout };
export type ProjectDetail = ProjectSummary & { items: GenerationItem[] };
```

Create `apps/web/src/components/GenerationItemList.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GenerationItemList } from "./GenerationItemList";

it("shows retry only for failed items", () => {
  render(<GenerationItemList projectId="p1" items={[{ id: "a", status: "failed" }, { id: "b", status: "generated" }]} />);
  expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(1);
});
```

Create `apps/web/src/components/editor/OverlayEditor.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { OverlayEditor } from "./OverlayEditor";

it("offers editable logo and flag layers and reset", () => {
  render(<OverlayEditor baseUrl="/base.png" logoUrl="/logo.png" flagUrl="/flag.png" onSave={async () => undefined} />);
  expect(screen.getByText("Brand logo")).toBeInTheDocument();
  expect(screen.getByText("Country flag")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reset positions" })).toBeInTheDocument();
});
```

Run:

```bash
pnpm --filter web test
```

Expected: FAIL because the progress and editor components do not exist.

- [ ] **Step 2: Implement item status presentation and retry operation**

Create `apps/web/src/components/GenerationItemList.tsx`:

```tsx
"use client";

import Link from "next/link";
import type { GenerationItem } from "../lib/api";

export function GenerationItemList({ projectId, items, onRetry }: { projectId: string; items: GenerationItem[]; onRetry?: (itemId: string) => Promise<void> }) {
  return (
    <section>
      {items.map((item) => (
        <article key={item.id}>
          <p>{item.status}</p>
          {item.status === "failed" && <button type="button" onClick={() => void onRetry?.(item.id)}>Retry</button>}
          {["generated", "exported"].includes(item.status) && <Link href={`/projects/${projectId}/items/${item.id}`}>Edit result</Link>}
        </article>
      ))}
    </section>
  );
}
```

Add to `apps/web/src/lib/api.ts`:

```ts
export function getProject(projectId: string): Promise<ProjectDetail> {
  return api<ProjectDetail>(`/api/v1/projects/${projectId}`);
}

export function retryItem(itemId: string): Promise<{ status: string }> {
  return api(`/api/v1/items/${itemId}/retry`, { method: "POST" });
}

export function exportBatch(projectId: string): Promise<{ export_id: string }> {
  return api(`/api/v1/projects/${projectId}/exports/zip`, { method: "POST" });
}
```

- [ ] **Step 3: Implement normalized `react-konva` overlay editor**

Create `apps/web/src/components/editor/OverlayEditor.tsx`:

```tsx
"use client";

import { useEffect, useRef, useState } from "react";
import Konva from "konva";
import { Image as CanvasImage, Layer as CanvasLayer, Stage, Transformer } from "react-konva";
import useImage from "use-image";
import type { Layout } from "../../lib/api";

const CANVAS_WIDTH = 800;
const CANVAS_HEIGHT = 800;
const defaults: Layout = {
  revision: 1,
  logo: { x: 0.05, y: 0.05, width: 0.22, height: 0.12, visible: true },
  flag: { x: 0.82, y: 0.05, width: 0.13, height: 0.09, visible: true }
};

export function OverlayEditor({
  baseUrl,
  logoUrl,
  flagUrl,
  initialLayout = defaults,
  onSave
}: {
  baseUrl: string;
  logoUrl: string;
  flagUrl: string;
  initialLayout?: Layout;
  onSave: (layout: Layout) => Promise<void>;
}) {
  const [layout, setLayout] = useState(initialLayout);
  const [selection, setSelection] = useState<"logo" | "flag">("logo");
  const [base] = useImage(baseUrl, "anonymous");
  const [logo] = useImage(logoUrl, "anonymous");
  const [flag] = useImage(flagUrl, "anonymous");
  const logoRef = useRef<Konva.Image>(null);
  const flagRef = useRef<Konva.Image>(null);
  const transformerRef = useRef<Konva.Transformer>(null);

  useEffect(() => {
    const node = selection === "logo" ? logoRef.current : flagRef.current;
    if (node && transformerRef.current) {
      transformerRef.current.nodes([node]);
      transformerRef.current.getLayer()?.batchDraw();
    }
  }, [selection]);

  function layerNode(name: "logo" | "flag", image: HTMLImageElement | undefined) {
    const value = layout[name];
    return (
      <CanvasImage
        ref={name === "logo" ? logoRef : flagRef}
        image={image}
        x={value.x * CANVAS_WIDTH}
        y={value.y * CANVAS_HEIGHT}
        width={value.width * CANVAS_WIDTH}
        height={value.height * CANVAS_HEIGHT}
        visible={value.visible}
        draggable
        onClick={() => setSelection(name)}
        onDragEnd={(event) => {
          const node = event.target;
          setLayout((current) => ({ ...current, [name]: { ...current[name], x: node.x() / CANVAS_WIDTH, y: node.y() / CANVAS_HEIGHT } }));
        }}
        onTransformEnd={(event) => {
          const node = event.target;
          const width = node.width() * node.scaleX();
          const height = node.height() * node.scaleY();
          node.scaleX(1);
          node.scaleY(1);
          setLayout((current) => ({ ...current, [name]: { ...current[name], x: node.x() / CANVAS_WIDTH, y: node.y() / CANVAS_HEIGHT, width: width / CANVAS_WIDTH, height: height / CANVAS_HEIGHT } }));
        }}
      />
    );
  }

  return (
    <section>
      <p>Brand logo</p>
      <p>Country flag</p>
      <Stage aria-label="Canvas editor" width={CANVAS_WIDTH} height={CANVAS_HEIGHT}>
        <CanvasLayer>
          <CanvasImage image={base} width={CANVAS_WIDTH} height={CANVAS_HEIGHT} />
          {layerNode("logo", logo)}
          {layerNode("flag", flag)}
          <Transformer ref={transformerRef} keepRatio />
        </CanvasLayer>
      </Stage>
      <button type="button" onClick={() => setLayout(defaults)}>Reset positions</button>
      <button type="button" onClick={() => void onSave(layout)}>Save layout</button>
    </section>
  );
}
```

Mock `react-konva` in `OverlayEditor.test.tsx` with plain React elements so the component test runs in JSDOM; `use-image` is already declared in the frontend dependencies from Task 1.

- [ ] **Step 4: Implement project result and item editor pages**

Create `apps/web/src/app/projects/[projectId]/page.tsx`:

```tsx
"use client";

import { use } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GenerationItemList } from "../../../components/GenerationItemList";
import { exportBatch, getDownload, getProject, retryItem } from "../../../lib/api";

export default function ProjectPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
    refetchInterval: (result) => result.state.data?.items.some((item) => ["queued", "processing"].includes(item.status)) ? 2000 : false
  });
  const retry = useMutation({
    mutationFn: retryItem,
    onSuccess: () => client.invalidateQueries({ queryKey: ["project", projectId] })
  });
  if (!query.data) return <p>Loading project...</p>;
  return (
    <main>
      <h1>{query.data.name}</h1>
      <p>{query.data.status}</p>
      <GenerationItemList projectId={projectId} items={query.data.items} onRetry={(id) => retry.mutateAsync(id).then(() => undefined)} />
      {query.data.items.some((item) => item.status === "exported") && (
        <button type="button" onClick={async () => window.location.assign((await getDownload((await exportBatch(projectId)).export_id)).download_url)}>
          Download all final PNGs
        </button>
      )}
    </main>
  );
}
```

Create `apps/web/src/components/editor/ExportControls.tsx`:

```tsx
"use client";

export function ExportControls({ onExport, onDownload }: { onExport: () => Promise<void>; onDownload: () => Promise<void> }) {
  return (
    <div>
      <button type="button" onClick={() => void onExport()}>Render final PNG</button>
      <button type="button" onClick={() => void onDownload()}>Download PNG</button>
    </div>
  );
}
```

Add API calls to `apps/web/src/lib/api.ts`:

```ts
export function saveLayout(itemId: string, layout: Layout): Promise<{ revision: number }> {
  return api(`/api/v1/items/${itemId}/layout`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(layout) });
}

export function exportItem(itemId: string): Promise<{ export_id: string }> {
  return api(`/api/v1/items/${itemId}/export`, { method: "POST" });
}

export function getDownload(exportId: string): Promise<{ download_url: string }> {
  return api(`/api/v1/downloads/${exportId}`);
}

export function getPreviews(itemId: string): Promise<{ base_url: string; logo_url: string; flag_url: string }> {
  return api(`/api/v1/items/${itemId}/previews`);
}
```

Create `apps/web/src/app/projects/[projectId]/items/[itemId]/page.tsx`:

```tsx
"use client";

import { use, useEffect, useState } from "react";
import { ExportControls } from "../../../../../components/editor/ExportControls";
import { OverlayEditor } from "../../../../../components/editor/OverlayEditor";
import { exportItem, getDownload, getPreviews, saveLayout } from "../../../../../lib/api";

export default function ItemEditorPage({ params }: { params: Promise<{ itemId: string }> }) {
  const { itemId } = use(params);
  const [exportId, setExportId] = useState<string>();
  const [previews, setPreviews] = useState<{ base_url: string; logo_url: string; flag_url: string }>();
  useEffect(() => { void getPreviews(itemId).then(setPreviews); }, [itemId]);
  if (!previews) return <p>Loading preview...</p>;
  return (
    <main>
      <h1>Edit creative</h1>
      <OverlayEditor
        baseUrl={previews.base_url}
        logoUrl={previews.logo_url}
        flagUrl={previews.flag_url}
        onSave={(layout) => saveLayout(itemId, layout).then(() => undefined)}
      />
      <ExportControls
        onExport={async () => setExportId((await exportItem(itemId)).export_id)}
        onDownload={async () => {
          if (exportId) window.location.assign((await getDownload(exportId)).download_url);
        }}
      />
    </main>
  );
}
```

Run:

```bash
pnpm --filter web test
```

Expected: PASS.

- [ ] **Step 5: Commit result editing UI**

```bash
git add apps/web
git commit -m "feat: edit overlays and download generated results"
```

## Task 10: Complete Integration, Browser Verification, And Deployment Controls

**Files:**
- Create: `apps/api/tests/integration/test_generation_flow.py`
- Create: `tests/e2e/mock-api.ts`
- Create: `tests/e2e/single-flow.spec.ts`
- Create: `tests/e2e/batch-flow.spec.ts`
- Create: `playwright.config.ts`
- Create: `docker-compose.yml`
- Create: `README.md`
- Create: `.env.example`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Write backend integration tests for stored Qwen output and re-export**

Create `apps/api/tests/integration/test_generation_flow.py`:

```python
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from PIL import Image

from app.routes.exports import export_item
from app.services.render import Layer, render_final_png


def png() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (32, 32), (255, 255, 255, 255)).save(output, "PNG")
    return output.getvalue()


def test_export_reads_stored_base_and_does_not_need_provider() -> None:
    item_id, project_id = uuid4(), uuid4()
    item = SimpleNamespace(id=item_id, project_id=project_id, base_composite_asset_key="base.png", status="generated")
    project = SimpleNamespace(id=project_id, logo_asset_key="logo.png", flag_asset_key="flag.png")
    layout = SimpleNamespace(revision=1, logo_x=0.05, logo_y=0.05, logo_width=0.2, logo_height=0.1, logo_visible=True, flag_x=0.8, flag_y=0.05, flag_width=0.1, flag_height=0.1, flag_visible=True)
    db = Mock()
    db.get.side_effect = [item, project, layout]
    storage = Mock()
    storage.download.return_value = png()

    response = export_item(str(item_id), {"sub": "admin"}, db, storage)

    assert response["status"] == "exported"
    assert storage.download.call_count == 3
    assert storage.upload.call_args.args[0] == "exports"
    assert storage.upload.call_args.args[1].endswith("/final-r1.png")
    db.commit.assert_called_once()


def test_renderer_can_be_called_repeatedly_from_same_saved_base() -> None:
    layer = Layer(0.05, 0.05, 0.2, 0.1, True)
    first = render_final_png(png(), png(), png(), layer, layer)
    second = render_final_png(png(), png(), png(), layer, layer)

    assert first == second
```

The Qwen adapter tests in Task 5 cover provider invocation and immediate base-output storage, while these export tests verify deterministic reuse of saved data without a provider call.

- [ ] **Step 2: Add browser-level single and batch acceptance flows**

Install the browser-test runner:

```bash
pnpm add -D @playwright/test
pnpm exec playwright install chromium
```

Create `tests/e2e/mock-api.ts`:

```ts
import type { Page } from "@playwright/test";

export async function installMockApi(page: Page, batch = false) {
  let retried = false;
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/auth/login")) return route.fulfill({ json: { email: "owner@example.com" } });
    if (path === "/api/v1/projects" && request.method() === "GET") return route.fulfill({ json: [] });
    if (path === "/api/v1/projects" && request.method() === "POST") return route.fulfill({ json: { id: "p1" } });
    if (path === "/api/v1/projects/p1") {
      const items = batch
        ? [{ id: "one", status: "exported" }, { id: "two", status: retried ? "exported" : "failed" }]
        : [{ id: "one", status: "generated" }];
      return route.fulfill({ json: { id: "p1", name: "Campaign", status: batch && !retried ? "partially_failed" : "completed", itemCount: items.length, items } });
    }
    if (path.endsWith("/retry")) {
      retried = true;
      return route.fulfill({ json: { status: "queued" } });
    }
    if (path.endsWith("/previews")) return route.fulfill({ json: { base_url: "/base.png", logo_url: "/logo.png", flag_url: "/flag.png" } });
    if (path.endsWith("/export")) return route.fulfill({ json: { export_id: "e1" } });
    if (path.endsWith("/exports/zip")) return route.fulfill({ json: { export_id: "zip1" } });
    if (path.includes("/downloads/")) return route.fulfill({ json: { download_url: "/download.png" } });
    return route.fallback();
  });
}
```

Create `tests/e2e/single-flow.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import { installMockApi } from "./mock-api";

const png = { name: "image.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64") };

test("admin creates, edits, and downloads a single creative", async ({ page }) => {
  await installMockApi(page);
  await page.goto("/login");
  await page.getByLabel("Email").fill("owner@example.com");
  await page.getByLabel("Password").fill("test-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("link", { name: "New project" }).click();
  await page.getByLabel("Project name").fill("Serum campaign");
  await page.getByLabel("Product images").setInputFiles(png);
  await page.getByLabel("Background image").setInputFiles(png);
  await page.getByLabel("Brand logo").setInputFiles(png);
  await page.getByLabel("Country flag").selectOption("LK");
  await page.getByRole("button", { name: "Generate creatives" }).click();
  await expect(page.getByText("generated")).toBeVisible();
  await page.getByRole("link", { name: "Edit result" }).click();
  await page.getByRole("button", { name: "Render final PNG" }).click();
  await expect(page.getByRole("button", { name: "Download PNG" })).toBeEnabled();
});
```

Create `tests/e2e/batch-flow.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import { installMockApi } from "./mock-api";

const png = { name: "image.png", mimeType: "image/png", buffer: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64") };

test("batch keeps completed items while retrying a failed product", async ({ page }) => {
  await installMockApi(page, true);
  await page.goto("/projects/new");
  await page.getByLabel("Batch").check();
  await page.getByLabel("Project name").fill("Collection launch");
  await page.getByLabel("Product images").setInputFiles([{ ...png, name: "one.png" }, { ...png, name: "two.png" }]);
  await page.getByLabel("Background image").setInputFiles(png);
  await page.getByLabel("Brand logo").setInputFiles(png);
  await page.getByRole("button", { name: "Generate creatives" }).click();
  await expect(page.getByText("partially_failed")).toBeVisible();
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("completed")).toBeVisible();
  await expect(page.getByRole("button", { name: "Download all final PNGs" })).toBeVisible();
});
```

Create `playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  use: { baseURL: "http://127.0.0.1:3000" },
  webServer: { command: "pnpm dev:web", url: "http://127.0.0.1:3000", reuseExistingServer: true }
});
```

- [ ] **Step 3: Document local services and required secure configuration**

Create `.env.example`:

```dotenv
API_ORIGIN=http://localhost:8000
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=local-anon-key
SUPABASE_SECRET_KEY=server-only-supabase-secret-key
SESSION_SECRET=replace-with-a-long-random-session-secret
REDIS_URL=redis://localhost:6379/0
DASHSCOPE_API_KEY=server-only-dashscope-api-key
DASHSCOPE_BASE_URL=https://dashscope-intl.aliyuncs.com/api/v1
DASHSCOPE_MODEL=qwen-image-2.0-pro
SIGNED_URL_TTL_SECONDS=900
```

Create `docker-compose.yml`:

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

Document in `README.md`:

```markdown
# Product Creative Generator

## Local Run

1. Run `supabase start` and `supabase db reset`.
2. Run `docker compose up -d redis`.
3. Configure `apps/api/.env` from `.env.example` with local Supabase values, and set `API_ORIGIN=http://localhost:8000` in `apps/web/.env.local`.
4. Run `cd apps/api && uv sync && uv run python scripts/create_admin.py`.
5. Run `cd apps/api && uv run uvicorn app.main:app --reload`.
6. Run `cd apps/api && uv run python -m app.worker`.
7. Run `pnpm install && pnpm sync:flags && pnpm dev:web`.

## Security Rules

- Keep `SUPABASE_SECRET_KEY`, `DASHSCOPE_API_KEY`, database credentials, and `SESSION_SECRET` only in server environments.
- Keep the `editimage` Storage bucket private.
- Do not add browser Data API policies for project records in the admin-only release.
```

- [ ] **Step 4: Run all automated and manual verification**

Run:

```bash
supabase db reset
cd apps/api
uv run pytest -v
cd ../..
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
pnpm exec playwright test
```

Expected: All backend, frontend, lint, build, and browser tests PASS; browser tests use fake provider output and do not incur a DashScope request.

- [ ] **Step 5: Commit verified end-to-end delivery**

```bash
git add .env.example docker-compose.yml README.md playwright.config.ts tests apps
git commit -m "test: verify product creative workflows end to end"
```

## Plan Verification Checklist

- The plan covers admin-only access, saved projects, single and shared-input batch generation, country dropdown assets, bounded optional instruction, editable overlays, private Supabase persistence, PNG exports, ZIP downloads, and item-level retry.
- Qwen access exists in one backend adapter, with base outputs copied immediately from temporary provider links into private Storage.
- Frontend code never receives Supabase service credentials or DashScope credentials.
- Re-export is deterministic and does not cause additional paid Qwen calls.
- Database and Storage security are verified through explicit anonymous-denial integration tests.
- Provider charging is avoided in automated tests by fake adapter injection; production enablement requires a deliberate administrator-run real generation after deployment credentials are configured.
