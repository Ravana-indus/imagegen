import projectAssets from "@/data/project-assets.json";
import { fetchApiWithFallback } from "@/lib/api-fallback";

export const dynamic = "force-dynamic";

export function GET() {
  return fetchApiWithFallback("/projects/assets", projectAssets);
}
