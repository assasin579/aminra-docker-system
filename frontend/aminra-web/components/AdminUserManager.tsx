"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { parseApiError, validatePassword } from "@/lib/apiError";
import { purgeAuthSessionState } from "@/lib/auth-session-cleanup";
import { signoutRedirect } from "@/lib/auth-oidc";
import Modal from "@/components/Modal";

const API = "/api";

interface User {
  id: string;
  email: string;
  role: "business" | "provider";
  company_name: string;
  company_code: string | null;
  status: "active" | "pending" | "suspended";
  is_owner: boolean;
  tenant_id: string | null;
  created_at: string;
}

const STATUS_CFG = {
  active: { label: "Hoạt động", bg: "rgba(10,31,68,0.1)", color: "#0A1F44" },
  pending: { label: "Chờ duyệt", bg: "rgba(245,158,11,0.1)", color: "#F59E0B" },
  suspended: { label: "Đình chỉ", bg: "rgba(239,68,68,0.1)", color: "#f87171" },
};
const ROLE_CFG = {
  business: { label: "Doanh nghiệp", color: "#0A1F44" },
  provider: { label: "Tổ chức", color: "#0EA5E9" },
};

function timeAgo(iso: string) {
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000);
  if (d === 0) return "Hôm nay";
  if (d === 1) return "Hôm qua";
  if (d < 30) return `${d} ngày trước`;
  return new Date(iso).toLocaleDateString("vi-VN");
}

interface FormState {
  email: string;
  password: string;
  company_name: string;
  company_code: string;
  role: string;
  status: string;
}
const EMPTY_FORM: FormState = {
  email: "",
  password: "",
  company_name: "",
  company_code: "",
  role: "business",
  status: "active",
};

export default function AdminUserManager({ token }: { token: string }) {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [fetching, setFetching] = useState(false);

  const [filterRole, setFilterRole] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [search, setSearch] = useState("");

  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [editTarget, setEditTarget] = useState<User | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState("");

  const [deleteId, setDeleteId] = useState<string | null>(null);

  const authHdr = { Authorization: `Bearer ${token}` };

  // Close modal on ESC + focus first input when opening.
  const firstInputRef = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (!modal) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setModal(null);
    };
    window.addEventListener("keydown", onKey);
    // Defer focus so DOM is mounted.
    setTimeout(() => firstInputRef.current?.focus(), 50);
    return () => window.removeEventListener("keydown", onKey);
  }, [modal]);

  const fetchUsers = useCallback(async () => {
    setFetching(true);
    try {
      const params = new URLSearchParams();
      if (filterRole) params.set("role", filterRole);
      if (filterStatus) params.set("status", filterStatus);
      if (search) params.set("q", search);
      const res = await fetch(`${API}/admin/users?${params}`, {
        headers: authHdr,
      });
      if (res.ok) {
        const d = await res.json();
        setUsers(d.users);
        setTotal(d.total);
      }
    } finally {
      setFetching(false);
    }
  }, [filterRole, filterStatus, search, token]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setFormError("");
    setEditTarget(null);
    setModal("create");
  };

  const openEdit = (u: User) => {
    setForm({
      email: u.email,
      password: "",
      company_name: u.company_name,
      company_code: u.company_code ?? "",
      role: u.role,
      status: u.status,
    });
    setFormError("");
    setEditTarget(u);
    setModal("edit");
  };

  const handleSave = async () => {
    setFormError("");

    // Client-side validation first (fail fast, no wasted request).
    if (modal === "create") {
      if (!form.email || !form.password || !form.company_name) {
        setFormError("Vui lòng điền đầy đủ thông tin bắt buộc");
        return;
      }
      const pwErr = validatePassword(form.password);
      if (pwErr) {
        setFormError(pwErr);
        return;
      }
    } else if (modal === "edit" && form.password) {
      // Edit: password optional; validate only when admin sets a new one.
      const pwErr = validatePassword(form.password);
      if (pwErr) {
        setFormError(pwErr);
        return;
      }
    }

    // Warn admin if role change risks orphaning historical data.
    if (modal === "edit" && editTarget && form.role !== editTarget.role) {
      if (
        !confirm(
          `Đổi vai trò ${editTarget.role} → ${form.role} có thể gây không nhất quán với hồ sơ + chứng nhận đã tồn tại. Tiếp tục?`,
        )
      )
        return;
    }

    setSaving(true);
    try {
      if (modal === "create") {
        const res = await fetch(`${API}/admin/users`, {
          method: "POST",
          headers: { ...authHdr, "Content-Type": "application/json" },
          body: JSON.stringify({
            email: form.email.trim().toLowerCase(),
            password: form.password,
            company_name: form.company_name.trim(),
            company_code: form.company_code.trim() || undefined,
            role: form.role,
            status: form.status,
          }),
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(
            parseApiError(body, `Tạo thất bại (HTTP ${res.status})`),
          );
        }
      } else if (modal === "edit" && editTarget) {
        const profileBody: Record<string, unknown> = {};
        if (form.company_name !== editTarget.company_name)
          profileBody.company_name = form.company_name.trim();
        if (form.company_code !== (editTarget.company_code ?? ""))
          profileBody.company_code = form.company_code.trim() || null;
        if (form.status !== editTarget.status) profileBody.status = form.status;
        if (form.role !== editTarget.role) profileBody.role = form.role;
        const passwordChanged = Boolean(form.password);
        if (Object.keys(profileBody).length === 0 && !passwordChanged) {
          setFormError("Không có thay đổi nào để lưu");
          setSaving(false);
          return;
        }

        if (Object.keys(profileBody).length > 0) {
          const res = await fetch(`${API}/admin/users/${editTarget.id}`, {
            method: "PUT",
            headers: { ...authHdr, "Content-Type": "application/json" },
            body: JSON.stringify(profileBody),
          });
          if (!res.ok) {
            const respBody = await res.json().catch(() => ({}));
            throw new Error(
              parseApiError(respBody, `Cập nhật thất bại (HTTP ${res.status})`),
            );
          }
        }

        if (passwordChanged) {
          const pwRes = await fetch(
            `${API}/admin/users/${editTarget.id}/reset-password`,
            {
              method: "POST",
              headers: { ...authHdr, "Content-Type": "application/json" },
              body: JSON.stringify({ new_password: form.password }),
            },
          );
          let resetBody: { sessions_revoked?: boolean; self_reset?: boolean } | null =
            null;
          if (!pwRes.ok) {
            const respBody = await pwRes.json().catch(() => ({}));
            throw new Error(
              parseApiError(respBody, `Đổi mật khẩu thất bại (HTTP ${pwRes.status})`),
            );
          }
          resetBody = await pwRes.json().catch(() => null);
          if (resetBody?.self_reset) {
            setFormError(
              "Mật khẩu đã đổi. Vui lòng đăng nhập lại bằng mật khẩu mới.",
            );
            await purgeAuthSessionState();
            await signoutRedirect();
            return;
          }
        }
      }
      setModal(null);
      fetchUsers();
    } catch (e) {
      setFormError(e instanceof Error ? e.message : "Lỗi không xác định");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Xác nhận xoá user này? Toàn bộ dữ liệu liên quan sẽ bị xoá."))
      return;
    setDeleteId(id);
    try {
      await fetch(`${API}/admin/users/${id}`, {
        method: "DELETE",
        headers: authHdr,
      });
      fetchUsers();
    } finally {
      setDeleteId(null);
    }
  };

  const set =
    (k: keyof FormState) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  const inputCls = "w-full px-3 py-2.5 rounded-xl text-sm outline-none";
  const inputStyle = {
    background: "#FFFFFF",
    border: "1px solid #E2E8F0",
    color: "#0A1F44",
  };

  return (
    <div>
      {/* Toolbar */}
      <div
        className="grid items-center mb-5 gap-3"
        style={{ gridTemplateColumns: "1fr auto" }}
      >
        <div
          className="grid gap-2"
          style={{
            gridTemplateColumns: "repeat(auto-fill, minmax(12rem, auto))",
          }}
        >
          <input
            type="text"
            placeholder="Tìm email, tên..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg outline-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#374151",
            }}
          />
          <select
            value={filterRole}
            onChange={(e) => setFilterRole(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg outline-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#374151",
            }}
          >
            <option value="">Tất cả loại</option>
            <option value="business">Doanh nghiệp</option>
            <option value="provider">Tổ chức</option>
          </select>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="text-sm px-3 py-2 rounded-lg outline-none"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              color: "#374151",
            }}
          >
            <option value="">Tất cả trạng thái</option>
            <option value="active">Hoạt động</option>
            <option value="pending">Chờ duyệt</option>
            <option value="suspended">Đình chỉ</option>
          </select>
        </div>
        <button
          onClick={openCreate}
          className="grid items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-white"
          style={{ gridTemplateColumns: "auto 1fr", background: "#0A1F44" }}
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M12 4v16m8-8H4"
            />
          </svg>
          Thêm user
        </button>
      </div>

      {/* Table */}
      <div
        className="rounded-xl overflow-hidden"
        style={{ border: "1px solid #E2E8F0", background: "#FFFFFF" }}
      >
        {fetching ? (
          <div className="divide-y" style={{ borderColor: "#E2E8F0" }}>
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="px-4 py-4 flex items-center gap-4">
                <div className="flex-1 space-y-2">
                  <div className="shimmer skeleton-text w-48" />
                  <div className="shimmer skeleton-text w-32" />
                </div>
                <div className="shimmer skeleton-text w-20" />
                <div className="shimmer skeleton-text w-16" />
              </div>
            ))}
          </div>
        ) : users.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <svg
              className="w-12 h-12 mx-auto mb-3"
              fill="none"
              stroke="#CBD5E1"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.5"
                d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
              />
            </svg>
            <p className="font-medium text-sm" style={{ color: "#0A1F44" }}>
              Không có user nào
            </p>
            <p className="text-xs mt-1" style={{ color: "#94A3B8" }}>
              {filterRole || filterStatus || search
                ? "Thử bỏ bớt filter"
                : "Chưa có ai đăng ký"}
            </p>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead style={{ background: "#F5F1E8" }}>
              <tr>
                {["Email / Tên", "Loại", "Trạng thái", "Ngày tạo", ""].map(
                  (h) => (
                    <th
                      key={h}
                      className="text-left px-4 py-3 text-xs font-medium"
                      style={{ color: "#6B7280" }}
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => {
                const st = STATUS_CFG[u.status] ?? STATUS_CFG.active;
                const rl = ROLE_CFG[u.role] ?? ROLE_CFG.business;
                return (
                  <tr
                    key={u.id}
                    style={{
                      background: i % 2 === 0 ? "#FFFFFF" : "#FFFFFF",
                      borderTop: "1px solid #E2E8F0",
                    }}
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium" style={{ color: "#0A1F44" }}>
                        {u.email}
                      </p>
                      <p
                        className="text-xs mt-0.5"
                        style={{ color: "#6B7280" }}
                      >
                        {u.company_name}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="text-xs font-medium"
                        style={{ color: rl.color }}
                      >
                        {rl.label}
                      </span>
                      {!u.is_owner && (
                        <span
                          className="ml-1 text-xs"
                          style={{ color: "#94A3B8" }}
                        >
                          · thành viên
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="px-2 py-0.5 rounded-full text-xs"
                        style={{ background: st.bg, color: st.color }}
                      >
                        {st.label}
                      </span>
                    </td>
                    <td
                      className="px-4 py-3 text-xs"
                      style={{ color: "#6B7280" }}
                    >
                      {timeAgo(u.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="grid grid-flow-col items-center gap-3 justify-end">
                        <button
                          onClick={() => openEdit(u)}
                          className="text-xs transition-colors"
                          style={{ color: "#6B7280" }}
                        >
                          Sửa
                        </button>
                        <button
                          onClick={() => handleDelete(u.id)}
                          disabled={deleteId === u.id}
                          className="text-xs hover:text-red-400 transition-colors"
                          style={{ color: "#6B7280" }}
                        >
                          {deleteId === u.id ? "..." : "Xoá"}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-xs mt-2" style={{ color: "#6B7280" }}>
        {total} user
      </p>

      {/* Modal */}
      {modal && (
        <Modal onClose={() => setModal(null)}>
          <div
            className="w-full max-w-md rounded-2xl p-6 animate-modal-content"
            style={{
              background: "#FFFFFF",
              border: "1px solid #E2E8F0",
              boxShadow: "0 12px 40px rgba(10,31,68,0.18)",
            }}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") handleSave();
            }}
          >
            <div className="flex items-start justify-between gap-3 mb-5">
              <div className="min-w-0">
                <h3
                  className="text-base font-bold"
                  style={{ color: "#0A1F44" }}
                >
                  {modal === "create" ? "Thêm user mới" : "Sửa thông tin user"}
                </h3>
                {modal === "edit" && editTarget && (
                  <p
                    className="text-xs mt-0.5 truncate font-mono"
                    style={{ color: "#64748B" }}
                    title={editTarget.email}
                  >
                    {editTarget.email}
                  </p>
                )}
              </div>
              <button
                onClick={() => setModal(null)}
                aria-label="Đóng"
                className="w-8 h-8 grid place-items-center rounded-lg flex-shrink-0 transition-colors hover:bg-black/5"
                style={{ color: "#6B7280" }}
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  strokeWidth="2"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div className="space-y-3">
              {/* Warning for member accounts */}
              {modal === "edit" &&
                editTarget &&
                !editTarget.is_owner &&
                editTarget.role === "business" && (
                  <div
                    className="px-4 py-3 rounded-lg text-xs leading-relaxed"
                    style={{
                      background: "rgba(245,158,11,0.08)",
                      border: "1px solid rgba(245,158,11,0.2)",
                      color: "#92400E",
                    }}
                  >
                    <strong>Tài khoản thành viên.</strong> Được mời bởi chủ tổ
                    chức. Thông tin công ty kế thừa từ owner — sửa ở đây có thể
                    gây không nhất quán.
                  </div>
                )}

              {/* Email — editable on create, read-only on edit */}
              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6B7280" }}
                >
                  Email {modal === "create" && "*"}
                </label>
                {modal === "create" ? (
                  <input
                    ref={firstInputRef}
                    type="email"
                    required
                    value={form.email}
                    onChange={set("email")}
                    placeholder="user@company.vn"
                    className={inputCls}
                    style={inputStyle}
                    autoFocus
                  />
                ) : (
                  <input
                    type="email"
                    value={editTarget?.email ?? ""}
                    readOnly
                    disabled
                    className={inputCls}
                    style={{
                      ...inputStyle,
                      background: "#F5F1E8",
                      cursor: "not-allowed",
                      color: "#6B7280",
                    }}
                  />
                )}
              </div>

              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6B7280" }}
                >
                  {modal === "create" ? "Mật khẩu *" : "Mật khẩu mới"}
                  {modal === "edit" && (
                    <span className="font-normal" style={{ color: "#94A3B8" }}>
                      {" "}
                      · để trống nếu không đổi
                    </span>
                  )}
                </label>
                <input
                  ref={modal === "edit" ? firstInputRef : undefined}
                  type="password"
                  value={form.password}
                  onChange={set("password")}
                  placeholder="••••••••••"
                  minLength={modal === "create" ? 10 : undefined}
                  className={inputCls}
                  style={inputStyle}
                  autoFocus={modal === "edit"}
                />
                <p className="text-xs mt-1" style={{ color: "#94A3B8" }}>
                  10+ ký tự, có chữ hoa, chữ thường và số
                </p>
              </div>

              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6B7280" }}
                >
                  Tên công ty / Tổ chức *
                </label>
                <input
                  type="text"
                  required
                  value={form.company_name}
                  onChange={set("company_name")}
                  placeholder="Công ty ABC"
                  className={inputCls}
                  style={inputStyle}
                />
              </div>

              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6B7280" }}
                >
                  Mã số thuế / Giấy phép
                </label>
                <input
                  type="text"
                  value={form.company_code}
                  onChange={set("company_code")}
                  placeholder="Tuỳ chọn"
                  className={inputCls}
                  style={inputStyle}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label
                    className="block text-xs font-medium mb-1.5"
                    style={{ color: "#6B7280" }}
                  >
                    Vai trò
                  </label>
                  <select
                    value={form.role}
                    onChange={set("role")}
                    className={inputCls}
                    style={inputStyle}
                  >
                    <option value="business">Doanh nghiệp</option>
                    <option value="provider">Tổ chức cấp chứng nhận</option>
                  </select>
                </div>
                <div>
                  <label
                    className="block text-xs font-medium mb-1.5"
                    style={{ color: "#6B7280" }}
                  >
                    Trạng thái
                  </label>
                  <select
                    value={form.status}
                    onChange={set("status")}
                    className={inputCls}
                    style={inputStyle}
                  >
                    <option value="active">Hoạt động</option>
                    {/* Pending only meaningful for providers (need admin approval) */}
                    {form.role === "provider" && (
                      <option value="pending">Chờ duyệt</option>
                    )}
                    <option value="suspended">Đình chỉ</option>
                  </select>
                </div>
              </div>

              {formError && (
                <div
                  role="alert"
                  className="grid items-start gap-2 px-3 py-2.5 rounded-lg text-xs"
                  style={{
                    gridTemplateColumns: "auto 1fr",
                    background: "rgba(239,68,68,0.08)",
                    color: "#991B1B",
                    border: "1px solid rgba(239,68,68,0.2)",
                  }}
                >
                  <svg
                    className="w-4 h-4 mt-0.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    strokeWidth="2"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <span>{formError}</span>
                </div>
              )}

              <div className="flex gap-2 mt-1">
                <button
                  type="button"
                  onClick={() => setModal(null)}
                  disabled={saving}
                  className="flex-1 py-2.5 rounded-xl font-medium text-sm transition-all"
                  style={{
                    background: "#F5F1E8",
                    color: "#6B7280",
                    border: "1px solid #E2E8F0",
                  }}
                >
                  Huỷ
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex-1 py-2.5 rounded-xl font-semibold text-sm text-white transition-all"
                  style={{
                    background: saving ? "rgba(10,31,68,0.4)" : "#0A1F44",
                    cursor: saving ? "wait" : "pointer",
                  }}
                >
                  {saving
                    ? "Đang lưu..."
                    : modal === "create"
                      ? "Tạo user"
                      : "Lưu thay đổi"}
                </button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
