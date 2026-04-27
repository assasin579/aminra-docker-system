/**
 * Parse FastAPI error responses into a single human-readable string.
 *
 * FastAPI returns 422 validation errors with `detail` as an ARRAY of
 * { loc, msg, type } objects, not a string. The naive
 *   throw new Error(err.detail || 'fallback')
 * crashes to "[object Object]" — this helper normalizes both cases.
 */
type FastApiValidationItem = { loc?: (string | number)[]; msg?: string; type?: string };

export function parseApiError(body: unknown, fallback = 'Đã có lỗi xảy ra'): string {
  if (!body || typeof body !== 'object') return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as FastApiValidationItem;
    const field = Array.isArray(first.loc) ? first.loc.filter(p => p !== 'body').join('.') : '';
    const msg = first.msg ?? fallback;
    return field ? `${field}: ${msg}` : msg;
  }
  return fallback;
}

/**
 * Match the backend `BusinessRegisterRequest.password_strength` validator.
 * Keep this in sync with backend/auth/models.py whenever rules change.
 */
export function validatePassword(pw: string): string | null {
  if (pw.length < 10)        return 'Mật khẩu tối thiểu 10 ký tự';
  if (!/[A-Z]/.test(pw))     return 'Mật khẩu phải có ít nhất 1 chữ hoa (A-Z)';
  if (!/[a-z]/.test(pw))     return 'Mật khẩu phải có ít nhất 1 chữ thường (a-z)';
  if (!/[0-9]/.test(pw))     return 'Mật khẩu phải có ít nhất 1 chữ số (0-9)';
  return null;
}
