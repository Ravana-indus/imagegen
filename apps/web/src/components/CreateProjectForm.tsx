"use client";

/* eslint-disable @next/next/no-img-element */
import { FormEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  apiRequest,
  friendlyError,
  Project,
  StagedSourceUpload,
  StagedSourceUploadResponse,
  uploadWithProgress,
} from "@/lib/api";

type Step = "idle" | "uploading" | "processing" | "done" | "error";

const STEPS: { key: Step; label: string }[] = [
  { key: "uploading", label: "Uploading assets" },
  { key: "processing", label: "Validating images" },
  { key: "done", label: "Project created" },
];

export function CreateProjectForm() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [mode, setMode] = useState("single");
  const [step, setStep] = useState<Step>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [backgroundUpload, setBackgroundUpload] = useState<StagedSourceUpload | null>(null);
  const [productUploads, setProductUploads] = useState<StagedSourceUpload[]>([]);
  const [sourceUploading, setSourceUploading] = useState<"background" | "product" | null>(null);

  const [bgSource, setBgSource] = useState<"upload" | "existing">("upload");
  const [logoSource, setLogoSource] = useState<"upload" | "existing">("upload");
  const [flagSource, setFlagSource] = useState<"upload" | "existing">("upload");

  const [selectedBgKey, setSelectedBgKey] = useState<string | null>(null);
  const [selectedLogoKey, setSelectedLogoKey] = useState<string | null>(null);
  const [selectedFlagKey, setSelectedFlagKey] = useState<string | null>(null);

  const { data: existingAssets } = useQuery({
    queryKey: ["existing-assets"],
    queryFn: () =>
      apiRequest<{
        backgrounds: { key: string; url: string }[];
        logos: { key: string; url: string }[];
        flags: { key: string; url: string }[];
      }>("/projects/assets"),
  });

  async function uploadSource(assetType: "background" | "product") {
    const form = formRef.current;
    if (!form) return;
    setError("");
    setSuggestion("");
    setSourceUploading(assetType);

    try {
      const fields = new FormData(form);
      const projectName = fields.get("name")?.toString().trim();
      if (!projectName) {
        throw new Error("Name the project before uploading to Supabase.");
      }
      const sourceFiles =
        assetType === "background"
          ? [fields.get("background")].filter((value): value is File => value instanceof File && value.size > 0)
          : fields.getAll("products").filter((value): value is File => value instanceof File && value.size > 0);
      if (sourceFiles.length === 0) {
        throw new Error(
          assetType === "background"
            ? "Select a background image first."
            : "Select at least one product image first.",
        );
      }

      const uploadForm = new FormData();
      uploadForm.set("project_name", projectName);
      uploadForm.set("asset_type", assetType);
      sourceFiles.forEach((file) => uploadForm.append("files", file));

      const response = await fetch("/api/v1/projects/source-uploads", {
        method: "POST",
        credentials: "same-origin",
        body: uploadForm,
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(body.detail ?? "Upload failed");
      }
      const result = (await response.json()) as StagedSourceUploadResponse;
      if (assetType === "background") {
        setBackgroundUpload(result.uploads[0] ?? null);
      } else {
        setProductUploads(result.uploads);
      }
    } catch (requestError) {
      const msg = requestError instanceof Error ? requestError.message : "Upload failed";
      const { message, suggestion: sug } = friendlyError(msg);
      setError(message);
      setSuggestion(sug);
    } finally {
      setSourceUploading(null);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSuggestion("");

    if (bgSource === "existing" && !selectedBgKey) {
      setError("Select an existing background image or upload a new one.");
      return;
    }
    if (logoSource === "existing" && !selectedLogoKey) {
      setError("Select an existing brand logo or upload a new one.");
      return;
    }
    if (flagSource === "existing" && !selectedFlagKey) {
      setError("Select an existing country flag or upload a new one.");
      return;
    }

    setStep("uploading");
    setProgress(0);

    const formData = new FormData(event.currentTarget);
    if (bgSource === "upload" && backgroundUpload) {
      formData.set("background_asset_key", backgroundUpload.storage_key);
    } else if (bgSource === "existing" && selectedBgKey) {
      formData.set("background_asset_key", selectedBgKey);
    }

    if (logoSource === "existing" && selectedLogoKey) {
      formData.set("logo_asset_key", selectedLogoKey);
    }

    if (flagSource === "existing" && selectedFlagKey) {
      formData.set("flag_asset_key", selectedFlagKey);
    }

    productUploads.forEach((upload) => {
      formData.append("product_asset_keys", upload.storage_key);
    });
    try {
      const response = await uploadWithProgress("/projects", formData, setProgress);
      setStep("processing");
      const project: Project = await response.json();
      setStep("done");
      router.push(`/projects/${project.id}`);
    } catch (requestError) {
      const msg = requestError instanceof Error ? requestError.message : "Upload failed";
      const { message, suggestion: sug } = friendlyError(msg);
      setError(message);
      setSuggestion(sug);
      setStep("error");
    }
  }

  const activeStepIndex = STEPS.findIndex((s) => s.key === step);

  return (
    <form className="creation-form" ref={formRef} onSubmit={submit}>
      <div className="form-grid">
        <label>
          Project name
          <input name="name" placeholder="Summer launch" maxLength={120} required />
        </label>
        <fieldset className="mode-field">
          <legend>Generation mode</legend>
          <label>
            <input
              type="radio"
              name="mode"
              value="single"
              checked={mode === "single"}
              onChange={() => setMode("single")}
            />
            Single
          </label>
          <label>
            <input
              type="radio"
              name="mode"
              value="batch"
              checked={mode === "batch"}
              onChange={() => setMode("batch")}
            />
            Batch
          </label>
        </fieldset>
        <div className="picker-container">
          <label className="picker-label" htmlFor="background-input">Background image</label>
          <div className="picker-tabs">
            <button
              type="button"
              className={`picker-tab ${bgSource === "upload" ? "active" : ""}`}
              onClick={() => setBgSource("upload")}
            >
              Upload New
            </button>
            <button
              type="button"
              className={`picker-tab ${bgSource === "existing" ? "active" : ""}`}
              onClick={() => setBgSource("existing")}
            >
              Choose Existing
            </button>
          </div>

          {bgSource === "upload" ? (
            <div className="picker-field">
              <input
                id="background-input"
                name="background"
                type="file"
                accept="image/png,image/jpeg,image/webp"
                required={!backgroundUpload}
                onChange={() => setBackgroundUpload(null)}
              />
              <button
                className="secondary-button inline-upload"
                type="button"
                disabled={sourceUploading !== null}
                onClick={() => uploadSource("background")}
              >
                {sourceUploading === "background"
                  ? "Uploading background..."
                  : backgroundUpload
                    ? "Background uploaded"
                    : "Upload background to Supabase"}
              </button>
            </div>
          ) : (
            <div className="picker-field">
              <div className="picker-gallery">
                {existingAssets?.backgrounds && existingAssets.backgrounds.length > 0 ? (
                  existingAssets.backgrounds.map((bg) => (
                    <button
                      key={bg.key}
                      type="button"
                      className={`picker-item ${selectedBgKey === bg.key ? "active" : ""}`}
                      onClick={() => setSelectedBgKey(bg.key)}
                      title={bg.key}
                    >
                      <img src={bg.url} alt="Background option" />
                      {selectedBgKey === bg.key && (
                        <div className="picker-item-selected-badge">✓</div>
                      )}
                    </button>
                  ))
                ) : (
                  <p className="no-assets-hint">No existing backgrounds found.</p>
                )}
              </div>
              {selectedBgKey && (
                <input type="hidden" name="background_asset_key" value={selectedBgKey} />
              )}
            </div>
          )}
        </div>

        <div className="picker-container">
          <label className="picker-label" htmlFor="logo-input">Brand logo</label>
          <div className="picker-tabs">
            <button
              type="button"
              className={`picker-tab ${logoSource === "upload" ? "active" : ""}`}
              onClick={() => setLogoSource("upload")}
            >
              Upload New
            </button>
            <button
              type="button"
              className={`picker-tab ${logoSource === "existing" ? "active" : ""}`}
              onClick={() => setLogoSource("existing")}
            >
              Choose Existing
            </button>
          </div>

          {logoSource === "upload" ? (
            <div className="picker-field">
              <input id="logo-input" name="logo" type="file" accept="image/png,image/jpeg,image/webp" required />
            </div>
          ) : (
            <div className="picker-field">
              <div className="picker-gallery">
                {existingAssets?.logos && existingAssets.logos.length > 0 ? (
                  existingAssets.logos.map((logo) => (
                    <button
                      key={logo.key}
                      type="button"
                      className={`picker-item ${selectedLogoKey === logo.key ? "active" : ""}`}
                      onClick={() => setSelectedLogoKey(logo.key)}
                      title={logo.key}
                    >
                      <img src={logo.url} alt="Brand logo option" />
                      {selectedLogoKey === logo.key && (
                        <div className="picker-item-selected-badge">✓</div>
                      )}
                    </button>
                  ))
                ) : (
                  <p className="no-assets-hint">No existing brand logos found.</p>
                )}
              </div>
              {selectedLogoKey && (
                <input type="hidden" name="logo_asset_key" value={selectedLogoKey} />
              )}
            </div>
          )}
        </div>

        <div className="picker-container">
          <label className="picker-label" htmlFor="flag-input">Flag image</label>
          <div className="picker-tabs">
            <button
              type="button"
              className={`picker-tab ${flagSource === "upload" ? "active" : ""}`}
              onClick={() => setFlagSource("upload")}
            >
              Upload New
            </button>
            <button
              type="button"
              className={`picker-tab ${flagSource === "existing" ? "active" : ""}`}
              onClick={() => setFlagSource("existing")}
            >
              Choose Existing
            </button>
          </div>

          {flagSource === "upload" ? (
            <div className="picker-field">
              <input id="flag-input" name="flag" type="file" accept="image/png,image/jpeg,image/webp" required />
            </div>
          ) : (
            <div className="picker-field">
              <div className="picker-gallery">
                {existingAssets?.flags && existingAssets.flags.length > 0 ? (
                  existingAssets.flags.map((flag) => (
                    <button
                      key={flag.key}
                      type="button"
                      className={`picker-item ${selectedFlagKey === flag.key ? "active" : ""}`}
                      onClick={() => setSelectedFlagKey(flag.key)}
                      title={flag.key}
                    >
                      <img src={flag.url} alt="Flag option" />
                      {selectedFlagKey === flag.key && (
                        <div className="picker-item-selected-badge">✓</div>
                      )}
                    </button>
                  ))
                ) : (
                  <p className="no-assets-hint">No existing flags found.</p>
                )}
              </div>
              {selectedFlagKey && (
                <input type="hidden" name="flag_asset_key" value={selectedFlagKey} />
              )}
            </div>
          )}
        </div>
        <label>
          Product image{mode === "batch" ? "s" : ""}
          <input
            name="products"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple={mode === "batch"}
            required
            onChange={() => setProductUploads([])}
          />
          <span className="hint">
            {mode === "batch" ? "Upload up to 25 products." : "Upload one product."}
          </span>
          <button
            className="secondary-button inline-upload"
            type="button"
            disabled={sourceUploading !== null}
            onClick={() => uploadSource("product")}
          >
            {sourceUploading === "product"
              ? "Uploading products..."
              : productUploads.length > 0
                ? `${productUploads.length} product${productUploads.length === 1 ? "" : "s"} uploaded`
                : "Upload product to Supabase"}
          </button>
        </label>
      </div>
      <label>
        Creative direction
        <textarea
          name="optional_instruction"
          rows={3}
          maxLength={450}
          placeholder="Optional: soft daylight, centered composition"
        />
      </label>

      {step === "uploading" || step === "processing" ? (
        <div className="upload-progress">
          <div className="step-indicators">
            {STEPS.map((s, i) => (
              <span
                key={s.key}
                className={`step ${i < activeStepIndex ? "step-done" : ""} ${i === activeStepIndex ? "step-active" : ""}`}
              >
                {i < activeStepIndex ? "✓" : i === activeStepIndex ? "●" : "○"} {s.label}
              </span>
            ))}
          </div>
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${step === "processing" ? 100 : progress}%` }}
            />
          </div>
          <p className="progress-text">
            {step === "uploading" ? `${progress}% uploaded` : "Processing images on server..."}
          </p>
        </div>
      ) : null}

      {error && (
        <div className="form-error-block">
          <p className="form-error">{error}</p>
          {suggestion && <p className="form-suggestion">{suggestion}</p>}
        </div>
      )}

      <button
        className="primary-button"
        type="submit"
        disabled={step === "uploading" || step === "processing"}
      >
        {step === "uploading"
          ? "Uploading..."
          : step === "processing"
            ? "Processing..."
            : "Generate creative"}
      </button>
    </form>
  );
}
