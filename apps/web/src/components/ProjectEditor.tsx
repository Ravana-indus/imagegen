"use client";

/* eslint-disable @next/next/no-img-element */
import { ChangeEvent, CSSProperties, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  apiRequest,
  ExportAsset,
  GenerationItem,
  Layout,
  Project,
} from "@/lib/api";

function layerStyle(x: number, y: number, width: number, height: number): CSSProperties {
  return {
    left: `${x * 100}%`,
    top: `${y * 100}%`,
    width: `${width * 100}%`,
    height: `${height * 100}%`,
  };
}

export function PreviewCanvas({
  baseUrl,
  logoUrl,
  flagUrl,
  layout,
}: {
  baseUrl: string;
  logoUrl: string;
  flagUrl: string;
  layout: Layout;
}) {
  return (
    <div className="preview-canvas">
      <img className="base-image" alt="Generated base composition" src={baseUrl} />
      {layout.logo_visible && (
        <img
          className="overlay-image"
          alt="Brand logo overlay"
          src={logoUrl}
          style={layerStyle(
            layout.logo_x,
            layout.logo_y,
            layout.logo_width,
            layout.logo_height,
          )}
        />
      )}
      {layout.flag_visible && (
        <img
          className="overlay-image"
          alt="Country flag overlay"
          src={flagUrl}
          style={layerStyle(
            layout.flag_x,
            layout.flag_y,
            layout.flag_width,
            layout.flag_height,
          )}
        />
      )}
    </div>
  );
}

function Slider({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="slider">
      <span>{label}</span>
      <input
        type="range"
        min={0}
        max={1}
        step={0.01}
        value={value}
        onChange={(event: ChangeEvent<HTMLInputElement>) =>
          onChange(Number(event.currentTarget.value))
        }
      />
      <output>{Math.round(value * 100)}%</output>
    </label>
  );
}

export function ProjectEditor({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useState("");
  const [drafts, setDrafts] = useState<Record<string, Layout>>({});
  const [download, setDownload] = useState<ExportAsset | null>(null);
  const [message, setMessage] = useState("");
  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => apiRequest<Project>(`/projects/${projectId}`),
    refetchInterval: ({ state }) => {
      const items = state.data?.items ?? [];
      return items.some((item) => ["queued", "processing"].includes(item.status))
        ? 2500
        : false;
    },
  });
  const project = projectQuery.data;
  const allItemsReady = Boolean(
    project?.items.length && project.items.every((item) => item.preview_url),
  );
  const activeItem = useMemo(
    () => project?.items.find((item) => item.id === activeId) ?? project?.items[0],
    [activeId, project],
  );
  const draft = activeItem
    ? (drafts[activeItem.id] ?? activeItem.layout)
    : null;

  function updateDraft(changes: Partial<Layout>) {
    if (activeItem && draft) {
      setDrafts((current) => ({
        ...current,
        [activeItem.id]: { ...draft, ...changes },
      }));
    }
  }

  const saveLayout = useMutation({
    mutationFn: (layout: Layout) =>
      apiRequest<Layout>(`/items/${activeItem?.id}/layout`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(layout),
      }),
    onSuccess: async (layout) => {
      if (activeItem) {
        setDrafts((current) => ({ ...current, [activeItem.id]: layout }));
      }
      setMessage("Overlay layout saved.");
      await queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });

  async function exportItem(item: GenerationItem) {
    const output = await apiRequest<ExportAsset>(`/items/${item.id}/export`, {
      method: "POST",
    });
    setDownload(output);
    setMessage("Final PNG is ready.");
  }

  async function retryItem(item: GenerationItem) {
    await apiRequest(`/items/${item.id}/retry`, { method: "POST" });
    setMessage("Generation queued again.");
    await queryClient.invalidateQueries({ queryKey: ["project", projectId] });
  }

  async function prepareAllDownloads(startDownload = false) {
    const output = await apiRequest<ExportAsset>(
      `/projects/${projectId}/exports/zip`,
      { method: "POST" },
    );
    setDownload(output);
    setMessage("All downloads are ready.");
    if (startDownload) {
      window.location.href = output.download_url;
    }
  }

  if (projectQuery.isPending) return <p className="notice">Loading project...</p>;
  if (projectQuery.error) return <p className="form-error">{projectQuery.error.message}</p>;
  if (!project || !activeItem || !draft) return <p className="notice">No generated items.</p>;

  return (
    <section className="editor">
      <div className="section-title compact">
        <div>
          <p className="eyebrow">{project.mode} project</p>
          <h1>{project.name}</h1>
        </div>
        <button
          className="secondary-button"
          type="button"
          disabled={!allItemsReady}
          onClick={() => prepareAllDownloads(true)}
        >
          Download all ZIP
        </button>
      </div>
      <div className="editor-layout">
        <aside className="item-list" aria-label="Products">
          {project.items.map((item, index) => (
            <button
              type="button"
              key={item.id}
              className={item.id === activeItem.id ? "item active" : "item"}
              onClick={() => setActiveId(item.id)}
            >
              <strong>Product {index + 1}</strong>
              <span className={`status status-${item.status}`}>{item.status}</span>
            </button>
          ))}
        </aside>
        <div className="canvas-column">
          {activeItem.preview_url ? (
            <PreviewCanvas
              baseUrl={activeItem.preview_url}
              logoUrl={project.logo_url}
              flagUrl={project.flag_url}
              layout={draft}
            />
          ) : (
            <div className="pending-canvas">
              {activeItem.status === "failed"
                ? activeItem.error_message ?? "Generation failed."
                : "Qwen is composing this product image..."}
            </div>
          )}
          {download && (
            <a className="download-link" href={download.download_url} download>
              Download {download.asset_type === "batch_zip" ? "ZIP" : "final PNG"}
            </a>
          )}
        </div>
        <aside className="controls">
          <h2>Overlay placement</h2>
          <Slider
            label="Logo horizontal"
            value={draft.logo_x}
            onChange={(logo_x) => updateDraft({ logo_x })}
          />
          <Slider
            label="Logo vertical"
            value={draft.logo_y}
            onChange={(logo_y) => updateDraft({ logo_y })}
          />
          <Slider
            label="Logo size"
            value={draft.logo_width}
            onChange={(logo_width) =>
              updateDraft({
                logo_width,
                logo_height: logo_width * (draft.logo_height / draft.logo_width),
              })
            }
          />
          <Slider
            label="Flag horizontal"
            value={draft.flag_x}
            onChange={(flag_x) => updateDraft({ flag_x })}
          />
          <Slider
            label="Flag vertical"
            value={draft.flag_y}
            onChange={(flag_y) => updateDraft({ flag_y })}
          />
          <Slider
            label="Flag size"
            value={draft.flag_width}
            onChange={(flag_width) =>
              updateDraft({
                flag_width,
                flag_height: flag_width * (draft.flag_height / draft.flag_width),
              })
            }
          />
          <label className="check-row">
            <input
              type="checkbox"
              checked={draft.flag_visible}
              onChange={(event) =>
                updateDraft({ flag_visible: event.currentTarget.checked })
              }
            />
            Show flag
          </label>
          <button
            className="secondary-button"
            type="button"
            onClick={() => saveLayout.mutate(draft)}
          >
            Save placement
          </button>
          {activeItem.status === "failed" ? (
            <button className="primary-button" type="button" onClick={() => retryItem(activeItem)}>
              Retry generation
            </button>
          ) : (
            <button
              className="primary-button"
              type="button"
              disabled={!activeItem.preview_url}
              onClick={() => exportItem(activeItem)}
            >
              Prepare download
            </button>
          )}
          <button
            className="secondary-button"
            type="button"
            disabled={!allItemsReady}
            onClick={() => prepareAllDownloads()}
          >
            Prepare all downloads
          </button>
          {message && <p className="notice small">{message}</p>}
        </aside>
      </div>
    </section>
  );
}
