/** Retry a read once when an upstream pooled socket closes before headers. */
export async function fetchBackendRead(
  url: string,
  init: RequestInit,
): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (error) {
    const method = (init.method ?? "GET").toUpperCase();
    const code = (error as { cause?: { code?: string } } | null)?.cause?.code;
    if ((method === "GET" || method === "HEAD") && code === "UND_ERR_SOCKET" && !init.signal?.aborted) {
      return fetch(url, init);
    }
    throw error;
  }
}
