import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import DataExportPage from '@/app/settings/data-export/page';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
  localStorage.clear();
  sessionStorage.clear();

  // jsdom doesn't implement these
  global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
  global.URL.revokeObjectURL = vi.fn();
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });

describe('DataExportPage', () => {
  test('renders explainer + button + Vietnamese law citation', () => {
    render(<DataExportPage />);
    expect(screen.getByRole('heading', { name: /Xuất dữ liệu cá nhân/i })).toBeInTheDocument();
    expect(screen.getByText(/13\/2023\/NĐ-CP/)).toBeInTheDocument();
    expect(screen.getByText(/GDPR Article 20/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Tải bản xuất/i })).toBeInTheDocument();
  });

  test('shows error when no auth token in storage', async () => {
    const user = userEvent.setup();
    render(<DataExportPage />);
    await user.click(screen.getByRole('button', { name: /Tải bản xuất/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/cần đăng nhập/i);
  });

  test('clicking export downloads file with Authorization header', async () => {
    localStorage.setItem('aminra_user_token', 'jwt-token-xyz');
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(
        200,
        '{"user_id":"abc","data_subject":{}}',
        { 'content-disposition': 'attachment; filename="aminra-export-abc-20260425.json"' }
      )
    );

    // Capture <a> click for download
    const clickSpy = vi.fn();
    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = origCreate(tag) as HTMLElement;
      if (tag === 'a') (el as HTMLAnchorElement).click = clickSpy;
      return el;
    });

    const user = userEvent.setup();
    render(<DataExportPage />);
    await user.click(screen.getByRole('button', { name: /Tải bản xuất/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/api/users/me/export-data',
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: 'Bearer jwt-token-xyz' }),
        })
      );
    });

    expect(clickSpy).toHaveBeenCalledTimes(1);

    expect(await screen.findByRole('status')).toHaveTextContent('aminra-export-abc-20260425.json');
  });

  test('shows backend error message on failure', async () => {
    localStorage.setItem('aminra_user_token', 'jwt');
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(429, { detail: 'Rate limit exceeded. Try again in 3600s.' })
    );

    const user = userEvent.setup();
    render(<DataExportPage />);
    await user.click(screen.getByRole('button', { name: /Tải bản xuất/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/rate limit/i);
  });

  test('mentions audit log + retention disclosure', () => {
    render(<DataExportPage />);
    expect(screen.getAllByText(/audit log/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/5 năm/i)).toBeInTheDocument();
  });
});
