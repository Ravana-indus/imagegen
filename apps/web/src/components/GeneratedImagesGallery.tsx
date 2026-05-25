"use client";

/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiRequest, GeneratedImage } from "@/lib/api";

export function GeneratedImagesGallery() {
  const { data, isPending, error } = useQuery({
    queryKey: ["generated-images"],
    queryFn: () => apiRequest<GeneratedImage[]>("/projects/generated-images"),
    refetchInterval: 5000,
  });

  return (
    <section className="generated-images">
      <div className="section-title">
        <div>
          <p className="eyebrow">Generated library</p>
          <h1>All generated images</h1>
        </div>
        <Link className="primary-link" href="/projects/new">
          New creative
        </Link>
      </div>
      {isPending && <p className="notice">Loading generated images...</p>}
      {error && <p className="form-error">{error.message}</p>}
      {data?.length === 0 && (
        <p className="notice">No generated images yet. Finished images will appear here.</p>
      )}
      <div className="generated-grid">
        {data?.map((image) => (
          <article className="generated-card" key={image.id}>
            <Link href={`/projects/${image.project_id}`}>
              {image.preview_url ? (
                <img src={image.preview_url} alt={image.name} />
              ) : (
                <div className="generated-card-missing">Preview unavailable</div>
              )}
            </Link>
            <div className="generated-card-body">
              <div className="status-row">
                <span className={`status status-${image.status}`}>{image.status}</span>
                <span>Product {image.item_index}</span>
              </div>
              <h2>{image.name}</h2>
              <p>{image.project_name}</p>
              <dl>
                <div>
                  <dt>Attempts</dt>
                  <dd>{image.attempt_count}</dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{new Date(image.created_at).toLocaleString()}</dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd title={image.source_product_asset_key}>
                    {image.source_product_asset_key}
                  </dd>
                </div>
              </dl>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
