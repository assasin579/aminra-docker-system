/**
 * Open authed resources in a new tab WITHOUT putting the JWT in the URL.
 *
 * Bug C5 from the 2026-04-26 audit: tokens in `?token=` querystring leak
 * to nginx access logs, browser history, and Referer headers when the
 * preview page links anywhere. Fix: fetch via `Authorization` header,
 * convert to blob URL, open the blob.
 */

interface OpenOptions {
  /** Optional filename (used when downloading). Browser may ignore for blobs. */
  filename?: string;
  /** Open as `download` instead of new tab. Defaults false (preview). */
  download?: boolean;
}

export async function openAuthed(url: string, token: string, opts: OpenOptions = {}): Promise<void> {
  let res: Response;
  try {
    res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  } catch (e) {
    alert('Không tải được tài liệu. Vui lòng thử lại.');
    return;
  }
  if (!res.ok) {
    if (res.status === 404) alert('Không tìm thấy tài liệu hoặc không có quyền xem.');
    else if (res.status === 401) alert('Phiên đăng nhập hết hạn. Vui lòng đăng nhập lại.');
    else alert(`Lỗi tải tài liệu (HTTP ${res.status})`);
    return;
  }
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);

  if (opts.download && opts.filename) {
    const a = document.createElement('a');
    a.href = blobUrl;
    a.download = opts.filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } else {
    // Open in new tab — let browser preview if it can (PDF, images).
    window.open(blobUrl, '_blank', 'noopener,noreferrer');
  }

  // Revoke after 60s — long enough for new tab to load, short enough to free memory.
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
}
