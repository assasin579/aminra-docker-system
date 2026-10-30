/**
 * Helper for the new HTML/CSS PDF renderer
 * (POST /api/api/templates/{doc_type}/render-pdf, backend Playwright route).
 *
 * Falls back to throwing — caller decides whether to retry or degrade
 * to the legacy DOCX route.
 */

import { saveAs } from "file-saver";

export interface RenderPdfOptions {
  docType: string;
  data: Record<string, unknown>;
  title?: string;
  isDraft?: boolean;
  lang?: "vi" | "en";
  token: string;
  filename?: string;
}

export interface RenderPdfResult {
  blob: Blob;
  durationMs: number;
  templateVersion: string;
  etag: string | null;
}

export class RenderPdfError extends Error {
  constructor(
    message: string,
    public status: number,
    public retryable: boolean,
  ) {
    super(message);
    this.name = "RenderPdfError";
  }
}

/**
 * Render the PDF and return the Blob (caller can save or display in iframe).
 * Throws RenderPdfError on non-2xx response. The .retryable flag tells caller
 * whether a fresh attempt makes sense (503 queue full → yes; 400 schema → no).
 */
export async function renderPdfHtml(opts: RenderPdfOptions): Promise<RenderPdfResult> {
  const {
    docType,
    data,
    title,
    isDraft = true,
    lang = "vi",
    token,
  } = opts;

  const res = await fetch(
    `/api/api/templates/${encodeURIComponent(docType)}/render-pdf`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        Accept: "application/pdf",
      },
      body: JSON.stringify({ data, title, is_draft: isDraft, lang }),
    },
  );

  if (!res.ok) {
    let message = `PDF render failed: ${res.status}`;
    try {
      const err = await res.json();
      if (err?.detail) {
        message = typeof err.detail === "string"
          ? err.detail
          : JSON.stringify(err.detail);
      }
    } catch {
      // Body may not be JSON (e.g., upstream HTML error page)
    }
    const retryable = res.status === 503 || res.status === 408;
    throw new RenderPdfError(message, res.status, retryable);
  }

  const blob = await res.blob();
  return {
    blob,
    durationMs: Number(res.headers.get("X-Render-Duration-Ms") || 0),
    templateVersion: res.headers.get("X-Template-Version") || "unknown",
    etag: res.headers.get("ETag"),
  };
}

/**
 * Render and trigger a browser download. Convenience wrapper around renderPdfHtml.
 */
export async function downloadPdfHtml(opts: RenderPdfOptions): Promise<RenderPdfResult> {
  const result = await renderPdfHtml(opts);
  const safeFilename = (opts.filename || `${opts.docType}.pdf`)
    .replace(/[\\/:*?"<>|]/g, "_");
  saveAs(result.blob, safeFilename);
  return result;
}
