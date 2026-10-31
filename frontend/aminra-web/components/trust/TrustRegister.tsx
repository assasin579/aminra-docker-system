"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode, type FormEvent } from "react";
import { ApiClientError, apiJson } from "@/lib/apiClient";

export const fieldClass = "mb-3 mt-1 w-full rounded border p-2";

export function Field({ name, label, required = false, children, ...props }: {
  name: string; label: string; required?: boolean; children?: ReactNode;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return <label className="block text-sm font-medium">{label}
    {children || <input name={name} className={fieldClass} required={required} {...props} />}
  </label>;
}

export function formValues(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  return Object.fromEntries(Array.from(new FormData(event.currentTarget), ([key, value]) => [key, String(value).trim()]));
}

/** Keep writes serialized. A failed refresh must never imply the saved write failed. */
export function useTrustRegister<T extends { id: string }>(path: string, collection: string, token: string) {
  const [rows, setRows] = useState<T[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uncertain, setUncertain] = useState(false);
  const busy = useRef(false);
  const blocked = useRef(false);
  const revision = useRef(0);
  const reload = useCallback(async () => {
    const data = await apiJson<Record<string, T[]>>(path, { token, cache: "no-store" });
    if (!Array.isArray(data[collection])) throw new Error("Invalid register response. Reload to try again.");
    setRows(data[collection]);
  }, [path, collection, token]);
  useEffect(() => {
    let active = true;
    const readRevision = revision.current;
    apiJson<Record<string, T[]>>(path, { token, cache: "no-store" }).then(data => {
      if (!Array.isArray(data[collection])) throw new Error("Invalid register response.");
      if (active && readRevision === revision.current) setRows(data[collection]);
    }).catch(e => { if (active) setError(e instanceof Error ? e.message : "Unable to load register."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [path, collection, token]);
  async function mutate(endpoint: string, json: unknown) {
    if (busy.current || blocked.current) return;
    busy.current = true;
    revision.current += 1;
    setPending(true); setError(""); setNotice("");
    try {
      const saved = await apiJson<T>(endpoint, { token, method: "POST", json });
      if (!saved || typeof saved.id !== "string" || !saved.id.trim()) {
        throw new Error("The server did not confirm a saved record. Reload before repeating this action.");
      }
      revision.current += 1;
      setRows(old => [saved, ...old.filter(row => row.id !== saved.id)]);
      setNotice(`Saved ${saved.id}.`);
      try { await reload(); } catch {
        blocked.current = true;
        setUncertain(true);
        setError("Saved successfully, but the register could not refresh. Reload before repeating this action.");
      }
      return saved;
    } catch (e) {
      if (!(e instanceof ApiClientError) || e.status === 0 || e.status >= 500) {
        blocked.current = true;
        setUncertain(true);
      }
      setError(`${e instanceof Error ? e.message : "Request failed."} If the response was lost, reload the register before submitting again.`);
    } finally { busy.current = false; setPending(false); }
  }
  return { rows, error, notice, pending, loading, uncertain, mutate };
}

export function Feedback({ error, notice, loading }: { error: string; notice: string; loading: boolean }) {
  return <>{loading && <p role="status">Loading register…</p>}
    {error && <div role="alert" className="my-3 text-red-700"><p>{error}</p><button type="button" className="underline" onClick={() => window.location.reload()}>Reload register</button></div>}
    {notice && <p role="status" className="my-3 text-green-800">{notice}</p>}</>;
}
