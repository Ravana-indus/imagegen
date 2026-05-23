"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import countries from "i18n-iso-countries";
import english from "i18n-iso-countries/langs/en.json";
import { apiRequest, Project } from "@/lib/api";

countries.registerLocale(english);
const countryOptions = Object.entries(countries.getNames("en", { select: "official" }))
  .map(([code, name]) => ({ code, name }))
  .sort((left, right) => left.name.localeCompare(right.name));

export function CreateProjectForm() {
  const router = useRouter();
  const [mode, setMode] = useState("single");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setPending(true);
    try {
      const project = await apiRequest<Project>("/projects", {
        method: "POST",
        body: new FormData(event.currentTarget),
      });
      router.push(`/projects/${project.id}`);
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Upload failed",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="creation-form" onSubmit={submit}>
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
        <label>
          Background image
          <input name="background" type="file" accept="image/png,image/jpeg,image/webp" required />
        </label>
        <label>
          Brand logo
          <input name="logo" type="file" accept="image/png,image/jpeg,image/webp" required />
        </label>
        <label>
          Country flag
          <select name="country_code" defaultValue="LK" required>
            {countryOptions.map(({ code, name }) => (
              <option value={code} key={code}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Product image{mode === "batch" ? "s" : ""}
          <input
            name="products"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple={mode === "batch"}
            required
          />
          <span className="hint">
            {mode === "batch" ? "Upload up to 25 products." : "Upload one product."}
          </span>
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
      {error && <p className="form-error">{error}</p>}
      <button className="primary-button" type="submit" disabled={pending}>
        {pending ? "Submitting..." : "Generate creative"}
      </button>
    </form>
  );
}
