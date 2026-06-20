export async function fetchApiWithFallback<T>(
  path: string,
  fallback: T,
): Promise<Response> {
  const origin = process.env.API_ORIGIN?.replace(/\/$/, "");
  if (origin) {
    try {
      const response = await fetch(`${origin}/api/v1${path}`, {
        cache: "no-store",
      });
      if (response.ok) {
        const data = (await response.json()) as unknown;
        const hasData = !Array.isArray(data) || data.length > 0;
        if (hasData) {
          return Response.json(data);
        }
      }
    } catch {
      // The bundled data keeps read-only galleries available during API outages.
    }
  }
  return Response.json(fallback);
}
