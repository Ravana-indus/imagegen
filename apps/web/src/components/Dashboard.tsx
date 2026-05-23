"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiRequest, ProjectSummary } from "@/lib/api";

export function Dashboard() {
  const { data, isPending, error } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiRequest<ProjectSummary[]>("/projects"),
    refetchInterval: 5000,
  });

  return (
    <section className="dashboard">
      <div className="section-title">
        <div>
          <p className="eyebrow">Saved work</p>
          <h1>Creative projects</h1>
        </div>
        <Link className="primary-link" href="/projects/new">
          New creative
        </Link>
      </div>
      {isPending && <p className="notice">Loading projects...</p>}
      {error && <p className="form-error">{error.message}</p>}
      {data?.length === 0 && (
        <p className="notice">No projects yet. Create a product image campaign.</p>
      )}
      <div className="project-grid">
        {data?.map((project) => (
          <Link className="project-card" href={`/projects/${project.id}`} key={project.id}>
            <div className="status-row">
              <span className={`status status-${project.status}`}>
                {project.status.replaceAll("_", " ")}
              </span>
              <span>{project.mode}</span>
            </div>
            <h2>{project.name}</h2>
            <p>{project.country_code} campaign</p>
            <time>{new Date(project.created_at).toLocaleDateString()}</time>
          </Link>
        ))}
      </div>
    </section>
  );
}
