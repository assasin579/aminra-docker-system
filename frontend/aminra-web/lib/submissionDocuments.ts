export type SubmissionDocument = {
  id: string;
  original_filename: string;
  doc_type?: string | null;
  doc_type_label?: string | null;
  is_current_selection?: boolean;
};

/** Read one representative per type; pending groups use the legacy upload view. */
export async function loadDocumentRepresentatives(token: string | null, view: "official_by_type" | "latest_by_type" = "official_by_type"): Promise<SubmissionDocument[]> {
  const documents: SubmissionDocument[] = [];
  const ids = new Set<string>();
  const types = new Set<string>();
  for (let page = 1; ; page++) {
    const response = await fetch(`/api/api/documents?view=${view}&page=${page}&page_size=100`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Không tải được tổ chức chứng nhận hoặc tài liệu. Vui lòng thử lại.");
    const data = await response.json();
    if (!Array.isArray(data.documents)) throw new Error("Dữ liệu tài liệu đại diện không hợp lệ. Vui lòng thử lại.");
    for (const document of data.documents as SubmissionDocument[]) {
      // Reject an inconsistent paginated read instead of offering duplicate types.
      if (!document.id || ids.has(document.id) || (document.doc_type && types.has(document.doc_type))) {
        throw new Error("Danh sách tài liệu đại diện đã thay đổi. Vui lòng tải lại.");
      }
      ids.add(document.id);
      if (document.doc_type) types.add(document.doc_type);
      documents.push(document);
    }
    if (typeof data.total === "number" && documents.length >= data.total) break;
    if (data.documents.length < 100) {
      if (typeof data.total === "number" && documents.length < data.total) {
        throw new Error("Danh sách tài liệu đại diện chưa đầy đủ. Vui lòng tải lại.");
      }
      break;
    }
  }
  return documents;
}

export async function loadSubmissionDocuments(token: string | null): Promise<SubmissionDocument[]> {
  return loadDocumentRepresentatives(token, "official_by_type");
}

/** A pinned dossier can use current representatives only if explicitly attached. */
export function currentDossierDocuments(
  current: SubmissionDocument[], attached: Array<{ id: string; doc_type?: string | null }>,
): SubmissionDocument[] {
  const attachedIds = new Set(attached.map(document => document.id));
  const available = current.filter(document => attachedIds.has(document.id));
  const represented = new Set(available.map(document => document.doc_type || document.id));
  if (attached.some(document => !represented.has(document.doc_type || document.id))) {
    throw new Error("Hồ sơ chưa gắn tài liệu đại diện hiện hành cho một số loại tài liệu. Hãy quay lại hồ sơ và cập nhật tài liệu trước khi gửi.");
  }
  return available;
}
