import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AuditLogsPage from '@/app/admin/audit-logs/page';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const mkLog = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id:          '11111111-1111-1111-1111-111111111111',
  user_id:     '22222222-2222-2222-2222-222222222222',
  user_email:  'admin@aminra.com',
  user_role:   'provider',
  tenant_id:   null,
  action:      'login.success',
  entity_type: 'user',
  entity_id:   '22222222-2222-2222-2222-222222222222',
  changes:     null,
  metadata:    { ip: '1.2.3.4' },
  created_at:  '2026-04-25T10:30:00Z',
  ...overrides,
});

describe('AuditLogsPage', () => {
  test('shows login prompt when no token in storage', async () => {
    render(<AuditLogsPage />);
    expect(await screen.findByText(/cần đăng nhập với tài khoản admin/i)).toBeInTheDocument();
    // No fetch call when no token
    expect(fetch).not.toHaveBeenCalled();
  });

  test('fetches logs with token from localStorage on mount', async () => {
    localStorage.setItem('aminra_user_token', 'jwt-token-xyz');
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { logs: [mkLog()], total: 1, page: 1, limit: 25 })
    );

    render(<AuditLogsPage />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/auth/admin/audit-logs?'),
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: 'Bearer jwt-token-xyz' }),
        })
      );
    });

    expect(await screen.findByText('admin@aminra.com')).toBeInTheDocument();
    expect(screen.getByText('login.success')).toBeInTheDocument();
  });

  test('renders before→after diff for change logs', async () => {
    localStorage.setItem('aminra_user_token', 'jwt');
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        logs: [mkLog({
          action: 'submission.status_change.approved',
          changes: { status: ['reviewing', 'approved'] },
        })],
        total: 1, page: 1, limit: 25,
      })
    );

    render(<AuditLogsPage />);

    expect(await screen.findByText('reviewing')).toBeInTheDocument();
    expect(screen.getByText('approved')).toBeInTheDocument();
    expect(screen.getByText(/status:/i)).toBeInTheDocument();
  });

  test('apply filters re-fetches with filter params + resets page to 1', async () => {
    localStorage.setItem('aminra_user_token', 'jwt');
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(respond(200, { logs: [], total: 0, page: 1, limit: 25 })) // initial
      .mockResolvedValueOnce(respond(200, { logs: [], total: 0, page: 1, limit: 25 })); // after filter

    render(<AuditLogsPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('login.success'), { target: { value: 'login.failed' } });
    fireEvent.click(screen.getByRole('button', { name: /Áp dụng filter/i }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const lastUrl = fetchMock.mock.calls[1][0] as string;
    expect(lastUrl).toContain('action=login.failed');
    expect(lastUrl).toContain('page=1');
  });

  test('shows backend error when fetch fails', async () => {
    localStorage.setItem('aminra_user_token', 'jwt');
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(403, { detail: 'Admin access required' })
    );

    render(<AuditLogsPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Admin access required');
  });

  test('shows anonymous indicator for logs without user_email', async () => {
    localStorage.setItem('aminra_user_token', 'jwt');
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        logs: [mkLog({ user_email: null, user_role: null, action: 'login.failed' })],
        total: 1, page: 1, limit: 25,
      })
    );

    render(<AuditLogsPage />);
    expect(await screen.findByText('anonymous')).toBeInTheDocument();
  });
});
