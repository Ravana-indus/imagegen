export type Layout = {
  revision: number;
  logo_x: number;
  logo_y: number;
  logo_width: number;
  logo_height: number;
  logo_visible: boolean;
  flag_x: number;
  flag_y: number;
  flag_width: number;
  flag_height: number;
  flag_visible: boolean;
};

export type GenerationItem = {
  id: string;
  status: string;
  attempt_count: number;
  preview_url: string | null;
  error_message: string | null;
  layout: Layout;
};

export type ProjectSummary = {
  id: string;
  name: string;
  mode: string;
  status: string;
  country_code: string;
  created_at: string;
};

export type Project = ProjectSummary & {
  background_url: string;
  logo_url: string;
  flag_url: string;
  items: GenerationItem[];
};

export type ExportAsset = {
  id: string;
  asset_type: string;
  download_url: string;
};

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "same-origin",
    ...init,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(error.detail ?? "Request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
