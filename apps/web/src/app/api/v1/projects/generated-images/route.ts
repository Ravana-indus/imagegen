import generatedImages from "@/data/generated-images.json";
import { fetchApiWithFallback } from "@/lib/api-fallback";

export const dynamic = "force-dynamic";

export function GET() {
  return fetchApiWithFallback("/projects/generated-images", generatedImages);
}
