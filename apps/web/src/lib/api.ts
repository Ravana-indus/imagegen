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

export type SupabaseUploadAsset = {
  asset_type: string;
  source_key: string;
  supabase_key: string;
};

export type StagedSourceUpload = {
  asset_type: string;
  filename: string;
  storage_key: string;
  signed_url: string;
};

export type StagedSourceUploadResponse = {
  uploads: StagedSourceUpload[];
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

export function uploadWithProgress(
  path: string,
  formData: FormData,
  onProgress: (percent: number) => void,
): Promise<Response> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/v1${path}`);
    xhr.withCredentials = true;
    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(
          new Response(xhr.responseText, {
            status: xhr.status,
            headers: { "Content-Type": "application/json" },
          }),
        );
      } else {
        let detail = "Request failed";
        try {
          const body = JSON.parse(xhr.responseText);
          detail = body.detail ?? detail;
        } catch {
          /* use default */
        }
        reject(new Error(detail));
      }
    });
    xhr.addEventListener("error", () => reject(new Error("Network error")));
    xhr.addEventListener("abort", () => reject(new Error("Upload cancelled")));
    xhr.send(formData);
  });
}

export function friendlyError(message: string): { message: string; suggestion: string } {
  const safeMsg = message || "Request failed";
  const dims = safeMsg.match(
    /(\S+) dimensions (\d+)×(\d+) are outside the allowed range of (\d+)–(\d+) pixels/,
  );
  if (dims) {
    const [, label, width, height, minDim, maxDim] = dims;
    const w = Number(width);
    const h = Number(height);
    const min = Number(minDim);
    if (w < min || h < min) {
      return {
        message: `${label} is too small (${w}×${h})`,
        suggestion: `Resize to at least ${min}×${min} pixels before uploading.`,
      };
    }
    return {
      message: `${label} is too large (${w}×${h})`,
      suggestion: `Resize to at most ${maxDim}×${maxDim} pixels before uploading.`,
    };
  }
  if (safeMsg.includes("Unsupported image")) {
    return {
      message: "Unsupported image upload",
      suggestion: "Use PNG, JPEG, or WebP files under 10 MB each.",
    };
  }
  if (safeMsg.includes("Invalid image")) {
    return {
      message: "Cannot read image file",
      suggestion: "The file may be corrupted or not a valid image. Try re-saving it.",
    };
  }
  if (safeMsg.includes("Single projects require")) {
    return { message: safeMsg, suggestion: "Switch to single mode and upload exactly one product image." };
  }
  if (safeMsg.includes("Batch projects require")) {
    return { message: safeMsg, suggestion: "Upload between 1 and 25 product images." };
  }
  if (safeMsg.includes("Unsupported project mode")) {
    return { message: safeMsg, suggestion: "Choose Single or Batch mode." };
  }
  if (safeMsg.includes("Database connection")) {
    return {
      message: "Server cannot reach the database",
      suggestion: "Check that DATABASE_URL is configured correctly and the database is running.",
    };
  }
  return {
    message: safeMsg,
    suggestion: "Check that all required files are selected and have valid dimensions (384–3072 px).",
  };
}
