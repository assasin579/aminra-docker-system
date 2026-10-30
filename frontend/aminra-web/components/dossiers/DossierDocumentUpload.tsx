"use client";
import { useState, type FormEvent } from "react";

export default function DossierDocumentUpload({ dossierId, token, slots, onUploaded }: {
  dossierId: string; token: string; slots: Array<{ doc_type: string; required: boolean }>; onUploaded?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = fileInput?.files?.[0];
    if (!file) { setError("Vui lòng chọn tệp tài liệu."); setBusy(false); return; }
    const data = new FormData(form); data.set("dossier_id", dossierId); data.set("file", file);
    try {
      const response = await fetch("/api/api/documents/upload", { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: data });
      if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(typeof body.detail === "string" ? body.detail : "Không tải được tài liệu. Vui lòng thử lại."); }
      if (onUploaded) onUploaded(); else window.location.reload();
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Tải tài liệu thất bại"); }
    finally { setBusy(false); }
  }
  if (!slots.length) return null;
  return <form onSubmit={upload} aria-label="Bổ sung tài liệu hồ sơ" className="mb-6 rounded-xl border border-cream-300 bg-white p-4 space-y-3 text-navy-900">
    <h2 className="font-semibold">Bổ sung tài liệu cho hồ sơ</h2>
    <p className="text-sm text-ink-500">Chọn loại tài liệu theo bộ yêu cầu đã chốt của hồ sơ này.</p>
    <label className="block text-sm">Loại tài liệu<select name="doc_type" className="mt-1 block w-full rounded-lg border border-cream-300 p-2" required>{slots.map(slot => <option key={slot.doc_type} value={slot.doc_type}>{slot.doc_type}{slot.required ? " · bắt buộc" : " · tùy chọn"}</option>)}</select></label>
    <label className="block text-sm">Tệp tài liệu<input name="file" type="file" required className="mt-1 block max-w-full" /></label>
    {error && <p role="alert">{error}</p>}
    <button type="submit" disabled={busy} className="rounded-lg bg-navy-900 px-4 py-2 text-sm text-white disabled:opacity-50">{busy ? "Đang tải tài liệu…" : "Tải lên hồ sơ"}</button>
  </form>;
}
