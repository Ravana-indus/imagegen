# Product Creative Generator Design

**Date:** 2026-05-23  
**Status:** Approved  
**Product scope:** Hosted, admin-only web application for generating branded product advertising images with single-item and campaign batch workflows, using Supabase Database and Storage.

## Goal

Build a hosted web application in which an admin uploads product imagery, a campaign background, and a brand logo; selects a country flag; optionally supplies a short creative instruction; generates a realistic base composite with Alibaba Cloud Model Studio Qwen Image Edit; positions logo and flag overlays; previews the final result; and downloads saved final images.

## Confirmed Requirements

- The product is a hosted web app, not a local-only utility.
- Alibaba Cloud Model Studio / DashScope is the external image editing provider.
- The application supports both a single-product flow and a simple batch flow.
- A batch consists of multiple product images sharing one background, one logo, one country flag, and one optional creative instruction.
- Country flags are selected from an application-provided dropdown, not uploaded by the user.
- The prompt includes a controlled system-owned product-compositing instruction plus an optional user instruction.
- Logo and flag use default positions but can be dragged and resized per output before export.
- Generated projects and outputs are saved and accessible from a gallery/dashboard.
- Initial access is restricted to one administrator account.
- Project records and asset storage are implemented on Supabase Database and Supabase Storage.

## Scope Boundaries

### Included In Version 1

- Admin sign-in.
- Project dashboard and saved output history.
- Single generation and batch generation.
- Uploads for product images, campaign background, and transparent brand logo.
- Country selection with bundled or application-hosted flag assets.
- Qwen-assisted product/background composition and lighting adjustment.
- Per-output logo/flag placement editor.
- Server-rendered flattened PNG export.
- Individual downloads and ZIP download for completed batch exports.
- Individual retry for failed generation items.

### Excluded From Version 1

- Public registration, billing, quotas, and customer workspaces.
- Spreadsheet-driven batch import.
- User-uploaded custom flag overrides.
- Full free-form prompt authoring.
- Logo or flag generation by the AI model.
- Collaboration, approval workflows, or shared editing.
- Automated product-background removal as a distinct local preprocessing feature; the Qwen edit request owns scene composition in the initial workflow.

## External Provider Contract

The first provider adapter targets Alibaba Cloud Model Studio Qwen Image Edit using `qwen-image-2.0-pro` as the default configured model. The current official API documentation describes multi-image editing with one to three input images; the application sends the product as Image 1 and the campaign background as Image 2, followed by a text instruction.

The provider prompt is owned by the application and instructs the model to:

- Keep the product identity, labeling, shape, and key visual details faithful to Image 1.
- Place the product naturally into Image 2.
- Harmonize lighting, reflections, contact shadows, and perspective for advertising quality.
- Avoid adding any logos, flags, badges, promotional text, or unrequested objects.
- Respect the optional user direction only when it does not conflict with product fidelity or the no-brand-overlay rule.

The user instruction is appended as a bounded additional instruction. It is intended for requests such as warmer lighting, center placement, or a premium studio mood, rather than replacing the base prompt.

Qwen-generated output links are temporary. The worker downloads every successful base composite into application-controlled storage immediately after a successful provider response and retains the provider request ID for diagnosis.

## Architecture

### Web Application

A Next.js application provides:

- Admin login and authenticated routes.
- Dashboard of projects, batches, status, and result thumbnails.
- Creation form for uploads, country selection, and optional instruction.
- Processing status views with per-item retry.
- Browser editor for previewing and repositioning logo and flag layers.
- Export and download controls.

The editor uses a canvas-based UI, such as `react-konva`, for drag and resize interactions. The browser never flattens the authoritative export; it sends normalized overlay layout values to the backend.

### API And Worker

A Python FastAPI service provides:

- Validated upload and project creation endpoints.
- Authenticated project, generation item, editor layout, retry, export, and download endpoints.
- A provider adapter that encapsulates DashScope credentials, request construction, response mapping, model configuration, and provider errors.
- Pillow-based final rendering for deterministic logo and flag placement.
- Batch ZIP assembly for already-rendered completed outputs.

Generation is asynchronous. A background worker consumes generation jobs from a durable queue, invokes DashScope, retrieves the base output, and updates item status. Worker concurrency is configured conservatively to remain within provider rate limits and avoid accidental excess spend.

### Supabase Database And Storage

Supabase is the concrete persistence platform for version 1:

- Supabase Postgres stores administrator records, projects, generation items, provider traces, overlay layouts, exports, and statuses.
- Supabase Storage uses the private `editimage` bucket with segregated object prefixes for product uploads, shared backgrounds, brand logos, stored flag snapshots, Qwen base composites, final PNGs, thumbnails, and batch ZIP archives.
- Bucket-level restrictions enforce accepted MIME types and upload-size limits where appropriate, with API validation providing additional image dimension and content validation before generation begins.
- The FastAPI backend and worker use a server-only Supabase secret key for trusted database and storage operations. The provided publishable key is safe for browser configuration but does not replace this backend credential. The secret key is never exposed to the Next.js browser bundle.
- The browser receives only application API responses and short-lived signed download or preview URLs for assets it is authorized to view; no project asset is permanently public.

All application tables in the Supabase `public` schema have Row Level Security enabled. Since version 1 reads and writes project data through the authenticated FastAPI application rather than directly from the browser, policies do not grant general `anon` access to creative records or stored image assets.

### Authentication

Version 1 has one configured administrator identity. Credentials are verified server-side against a securely stored password hash in Supabase Postgres or an equivalent single-admin credential provider; sessions use secure, HTTP-only cookies. Supabase Auth is not required for version 1 because the approved scope is a server-mediated single-admin application; it can be introduced later if multi-user access is required. There is no registration, invite, or organization model in this release.

## User Workflow

### Dashboard

The authenticated landing screen lists projects ordered by newest first. Each row or card includes project name, single/batch mode, status, item success/failure counts, thumbnail where available, creation time, and actions to open results or download completed exports.

### New Single Project

1. The admin chooses single mode.
2. The admin uploads one product image, one background image, and one brand logo.
3. The admin selects one country from the flag dropdown and optionally enters a short creative instruction.
4. The application validates files and creates one generation item.
5. The item is queued and processed asynchronously.
6. When complete, the admin edits overlays, exports a final PNG, and downloads it.

### New Batch Project

1. The admin chooses batch mode.
2. The admin uploads multiple product images plus one shared background and one shared brand logo.
3. The admin selects one shared country and optional creative instruction.
4. Validation runs before any generation job is queued.
5. One independent generation item is created for each product image.
6. Items run with limited concurrency and update status independently.
7. Completed outputs can be edited and exported independently.
8. Once exports exist, the admin can download individual PNG files or a ZIP containing completed final PNGs.

### Preview And Export

Each successful generation item displays its stored AI base composite with two editable overlay layers:

- Brand logo: default top-left position.
- Country flag: default top-right position.

Defaults use normalized coordinates and normalized width/height so placement adapts across output dimensions. The admin can drag, resize, hide/show, or reset each overlay. Layout changes persist per item.

Export sends the current overlay layout to FastAPI. The backend uses Pillow to render the stored logo and selected flag over the saved base composite at output resolution, preserving transparency and avoiding browser screenshot inconsistencies. Re-export after an overlay edit does not incur a new Qwen request.

## Data Model

### `admin_users`

- `id`: UUID primary key.
- `email`: unique administrator email.
- `password_hash` or `external_subject`: server-side authentication linkage.
- `created_at`, `updated_at`.

### `projects`

- `id`: UUID primary key.
- `name`: administrator-visible label.
- `mode`: `single` or `batch`.
- `status`: `draft`, `queued`, `processing`, `completed`, `partially_failed`, or `failed`.
- `background_asset_key`: private Supabase Storage object reference.
- `logo_asset_key`: private Supabase Storage object reference.
- `country_code`: ISO country identifier used to resolve the flag.
- `flag_asset_key`: private Supabase Storage reference for the stored flag snapshot used for repeatable exports.
- `optional_instruction`: nullable bounded text.
- `prompt_version`: identifies the fixed base prompt used.
- `created_by`, `created_at`, `updated_at`.

### `generation_items`

- `id`: UUID primary key.
- `project_id`: parent project.
- `source_product_asset_key`: private Supabase Storage reference for the uploaded product.
- `status`: `queued`, `processing`, `generated`, `exported`, or `failed`.
- `provider_model`, `provider_request_id`: provider trace fields.
- `provider_error_code`, `provider_error_message`: nullable failure details.
- `attempt_count`: retry tracking.
- `base_composite_asset_key`: nullable private Supabase Storage reference for the stored Qwen output.
- `thumbnail_asset_key`: nullable private Supabase Storage preview reference.
- `created_at`, `updated_at`.

### `overlay_layouts`

- `generation_item_id`: one-to-one item reference.
- `logo_x`, `logo_y`, `logo_width`, `logo_height`: normalized values in the range `0.0` to `1.0`.
- `logo_visible`: boolean.
- `flag_x`, `flag_y`, `flag_width`, `flag_height`: normalized values in the range `0.0` to `1.0`.
- `flag_visible`: boolean.
- `updated_at`.

### `export_assets`

- `id`: UUID primary key.
- `generation_item_id`: nullable for batch ZIP assets.
- `project_id`: owning project.
- `asset_type`: `final_png` or `batch_zip`.
- `storage_key`: private Supabase Storage object reference.
- `layout_revision`: identifies the overlay layout used for final PNG output.
- `created_at`.

## State And Failure Handling

- Upload validation completes before project processing is accepted. Uploaded product, background, and logo images are limited to 10 MB each and, for the version-one quality gate, 384 to 3072 pixels per side; validation also checks file type, image decodability, batch item count, and required assets.
- A failed item records a sanitized provider or processing failure and remains retryable.
- Retrying an item creates a new provider attempt only for that item and leaves successful sibling items unchanged.
- A project reaches `completed` when all items have generated successfully; it reaches `partially_failed` when successful and failed items coexist; it reaches `failed` when all items fail.
- Export failures do not discard the saved AI base composite; the admin can retry rendering.
- Provider credentials are only stored in server environment configuration.
- Temporary DashScope result links are never treated as durable application assets.
- Stored originals and final exports remain in the private Supabase Storage `editimage` bucket and are served only through authenticated application operations or short-lived signed URLs.
- RLS is enabled for application tables in the exposed schema; browser clients do not receive blanket read/write policies for project or item records.
- Supabase Storage policies deny general anonymous reads and writes. Any trusted service-role access is confined to FastAPI and worker server configuration.

## API Surface

The web app consumes an authenticated application API with these logical operations:

- Authenticate administrator and end session.
- Create a single or batch project with shared and per-item uploads.
- List projects and load project/item details.
- Poll or subscribe to project and item status updates.
- Retry a failed generation item.
- Read and update a generation item's overlay layout.
- Render or re-render a final PNG.
- Request authenticated download for a final PNG.
- Build and request download for a project's completed batch ZIP.

The Qwen provider API is called only by the backend worker through the provider adapter.

## Deployment And Configuration

The deployed system consists of:

- A Next.js web deployment.
- A FastAPI API deployment.
- A separately running background worker using the same backend package.
- A durable queue or job broker accessible to the API and worker.
- A Supabase project supplying Postgres Database and the private Storage bucket `editimage`.

Required secure configuration includes admin authentication credentials, session signing keys, Supabase project URL, browser-safe Supabase publishable key, server-only Supabase secret key, private bucket name (`editimage`) and restrictions, queue/broker configuration, DashScope API key, DashScope endpoint region, configured Qwen model ID, upload constraints, signed URL expiry, and worker concurrency.

## Testing Strategy

### Frontend

- Form tests validate mode-dependent product upload rules, shared inputs, country selection, and optional instruction limits.
- Editor tests validate loading default layers, drag/resize persistence payloads, reset behavior, export requests, and per-item batch navigation.
- Dashboard tests validate state rendering for processing, completed, partially failed, and failed projects.

### Backend

- API tests cover authentication, upload validation, Supabase-backed project creation, item listing, layout persistence, retries, export authorization, and ZIP export eligibility.
- Supabase integration tests verify private bucket behavior, signed preview/download URL issuance, table RLS configuration, and denial of anonymous project/storage access.
- Provider adapter tests mock DashScope responses for success, temporary output download, invalid credentials, rejected input, rate limiting, and generation failure.
- Renderer tests compare deterministic output dimensions and known logo/flag pixel placement for saved normalized layouts.
- Worker tests verify single and batch item state transitions, bounded independent retries, provider trace storage, and failure isolation.

### End-To-End

- Single flow: sign in, create generation, simulate successful provider output, position overlays, export, and download PNG.
- Batch flow: create several items, simulate mixed success and failure, retry one failure, edit completed outputs, and download a ZIP of rendered PNGs.
- Access control: unauthenticated users cannot read assets, results, or download URLs.

## Acceptance Criteria

- An authenticated administrator can create a single project or a shared-input batch project.
- Each product image is sent with the shared background to Qwen through the backend adapter, and its returned base image is immediately copied to private Supabase Storage.
- A generated result can be previewed with exact logo and application-provided country flag overlays.
- Logo and flag placements can be adjusted per generated output and saved.
- The backend produces a downloadable final PNG reflecting the saved overlay layout without calling Qwen again.
- Batch generation exposes per-item states, permits item-specific retry, and can export completed final images as a ZIP.
- Saved projects and results remain accessible from the authenticated dashboard.
- API keys and stored image assets are not exposed publicly.
- Supabase Database tables and Storage assets used for projects are protected from anonymous access, with secret/service credentials restricted to backend and worker processes.

## Provider Documentation References

- Alibaba Cloud Model Studio, "Qwen-Image-Edit API reference," last updated March 13, 2026: supports `qwen-image-2.0-pro` and one to three input images with text instruction.
- Alibaba Cloud Model Studio, "Qwen-Image-Edit," last updated March 15, 2026: provides DashScope SDK/API multi-image examples.
- Alibaba Cloud Model Studio, "Qwen-Image-Edit API reference," last updated October 31, 2025: generated output URLs and task data are retained for 24 hours and outputs should be saved promptly.

## Supabase Documentation References

- Supabase, "Storage Buckets": private buckets are access-controlled through RLS, support bucket upload restrictions, and can serve time-limited signed URLs.
- Supabase, "Storage Access Control": Storage policies are defined on `storage.objects`, while trusted server service credentials bypass RLS and must not be exposed to clients.
- Supabase Changelog, "Breaking Change: Tables not exposed to Data and GraphQL API automatically," May 1, 2026: schema/API grants must be considered explicitly alongside RLS during implementation.
