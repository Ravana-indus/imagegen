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
  optional_instruction text check (optional_instruction is null or char_length(optional_instruction) <= 1000),
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

revoke all on public.admin_users, public.projects, public.generation_items,
  public.overlay_layouts, public.export_assets from anon, authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'editimage',
  'editimage',
  false,
  104857600,
  array['image/png', 'image/jpeg', 'image/webp', 'image/svg+xml', 'application/zip']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
