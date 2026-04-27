/**
 * Vitest tests cho RevisionPanel — UI cho submission revisions cycle.
 *
 * Coverage:
 * - History fetched on mount
 * - Provider sees request-revision form when status is reviewing/returned
 * - Business sees resubmit form when status is revision_required
 * - Form submission calls correct endpoint với correct payload
 * - History rendering (rounds + per-doc feedback + severity colors)
 */
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import RevisionPanel from '@/components/submissions/RevisionPanel';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
});
afterEach(() => {
  vi.unstubAllGlobals();
});

const respond = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

const docs = [
  { id: 'doc-1', filename: 'application.pdf' },
  { id: 'doc-2', filename: 'sop.docx' },
];

const baseProps = {
  submissionId: 'sub-123',
  token: 'jwt-xyz',
  documents: docs,
};


// ── Initial fetch ──────────────────────────────────────────────────────────

describe('RevisionPanel — initial fetch', () => {
  test('fetches history on mount with bearer token', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { history: [] }),
    );

    render(<RevisionPanel {...baseProps} role="business" status="reviewing" />);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/api/submissions/sub-123/revisions',
        expect.objectContaining({
          headers: { Authorization: 'Bearer jwt-xyz' },
        }),
      );
    });
  });

  test('shows empty state when no rounds yet', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { history: [] }),
    );

    render(<RevisionPanel {...baseProps} role="business" status="reviewing" />);
    expect(await screen.findByText(/Chưa có vòng sửa nào/i)).toBeInTheDocument();
  });

  test('shows error message when fetch fails', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(403, { detail: 'forbidden' }),
    );

    render(<RevisionPanel {...baseProps} role="business" status="reviewing" />);
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});


// ── Provider request-revision form ─────────────────────────────────────────

describe('RevisionPanel — provider request-revision', () => {
  test('shows form for provider when status=reviewing', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { history: [] }),
    );

    render(<RevisionPanel {...baseProps} role="provider" status="reviewing" />);

    expect(await screen.findByPlaceholderText(/Mô tả những vấn đề/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Gửi yêu cầu sửa/i })).toBeInTheDocument();
  });

  test('does NOT show form when status=approved', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { history: [] }),
    );

    render(<RevisionPanel {...baseProps} role="provider" status="approved" />);
    await waitFor(() => {
      expect(screen.queryByPlaceholderText(/Mô tả những vấn đề/i)).not.toBeInTheDocument();
    });
  });

  test('submitting form calls request-revision endpoint with feedback', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(respond(200, { history: [] }))                      // initial fetch
      .mockResolvedValueOnce(respond(200, { round: 1, request_id: 'req-1' }))   // post
      .mockResolvedValueOnce(respond(200, { history: [] }));                     // refetch

    render(<RevisionPanel {...baseProps} role="provider" status="reviewing" />);

    const textarea = await screen.findByPlaceholderText(/Mô tả những vấn đề/i);
    fireEvent.change(textarea, { target: { value: 'Cần bổ sung JAKIM cert' } });
    fireEvent.click(screen.getByRole('button', { name: /Gửi yêu cầu sửa/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/api/submissions/received/sub-123/request-revision',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            feedback: 'Cần bổ sung JAKIM cert',
            document_feedback: [],
          }),
        }),
      );
    });
  });

  test('per-document issues included in payload', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(respond(200, { history: [] }))
      .mockResolvedValueOnce(respond(200, { round: 1, request_id: 'req-1' }))
      .mockResolvedValueOnce(respond(200, { history: [] }));

    render(<RevisionPanel {...baseProps} role="provider" status="reviewing" />);

    fireEvent.change(
      await screen.findByPlaceholderText(/Mô tả những vấn đề/i),
      { target: { value: 'Issues found' } },
    );
    fireEvent.click(screen.getByText(/\+ Thêm vấn đề cụ thể/i));

    const issueInput = screen.getByPlaceholderText(/Vấn đề cụ thể/i);
    fireEvent.change(issueInput, { target: { value: 'Missing seal' } });

    fireEvent.click(screen.getByRole('button', { name: /Gửi yêu cầu sửa/i }));

    await waitFor(() => {
      const lastCall = fetchMock.mock.calls.find(
        c => typeof c[0] === 'string' && c[0].includes('request-revision'),
      );
      expect(lastCall).toBeDefined();
      const body = JSON.parse(lastCall![1].body);
      expect(body.document_feedback).toEqual([
        expect.objectContaining({
          document_id: 'doc-1',
          issue: 'Missing seal',
          severity: 'minor',
        }),
      ]);
    });
  });

  test('rejects empty feedback before calling API', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock.mockResolvedValueOnce(respond(200, { history: [] }));

    render(<RevisionPanel {...baseProps} role="provider" status="reviewing" />);

    await screen.findByPlaceholderText(/Mô tả những vấn đề/i);

    // Button is disabled when feedback empty
    const button = screen.getByRole('button', { name: /Gửi yêu cầu sửa/i });
    expect(button).toBeDisabled();

    // Force-click anyway via form submit
    expect(fetchMock).toHaveBeenCalledTimes(1);  // only the initial GET
  });
});


// ── Business resubmit form ─────────────────────────────────────────────────

describe('RevisionPanel — business resubmit', () => {
  test('shows resubmit form when status=revision_required', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { history: [] }),
    );

    render(<RevisionPanel {...baseProps} role="business" status="revision_required" />);

    expect(await screen.findByText(/Hồ sơ đang ở trạng thái/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Đã sửa — gửi lại/i })).toBeInTheDocument();
  });

  test('does NOT show resubmit form when status=reviewing', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, { history: [] }),
    );

    render(<RevisionPanel {...baseProps} role="business" status="reviewing" />);
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Đã sửa — gửi lại/i })).not.toBeInTheDocument();
    });
  });

  test('submitting calls resubmit endpoint', async () => {
    const fetchMock = fetch as unknown as ReturnType<typeof vi.fn>;
    fetchMock
      .mockResolvedValueOnce(respond(200, { history: [] }))
      .mockResolvedValueOnce(respond(200, { round_resolved: 1, resubmitted_at: 'now' }))
      .mockResolvedValueOnce(respond(200, { history: [] }));

    render(<RevisionPanel {...baseProps} role="business" status="revision_required" />);

    fireEvent.change(
      await screen.findByPlaceholderText(/Mô tả những gì đã sửa/i),
      { target: { value: 'Đã upload bản mới có seal' } },
    );
    fireEvent.click(screen.getByRole('button', { name: /Đã sửa — gửi lại/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        '/api/api/submissions/sub-123/resubmit',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ business_notes: 'Đã upload bản mới có seal' }),
        }),
      );
    });
  });
});


// ── History rendering ──────────────────────────────────────────────────────

describe('RevisionPanel — history rendering', () => {
  test('renders multiple rounds newest-first with proper severity badges', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        history: [
          {
            id: 'r2',
            round: 2,
            requester_id: 'cb',
            requester_name: 'Halal CB',
            feedback: 'Vẫn còn vấn đề ở seal',
            document_feedback: [{
              document_id: 'doc-1',
              issue: 'Seal mờ',
              severity: 'major',
              suggestion: 'Scan lại',
            }],
            requested_at: '2026-04-25T10:00:00Z',
            resolved_at: null,
          },
          {
            id: 'r1',
            round: 1,
            requester_id: 'cb',
            requester_name: 'Halal CB',
            feedback: 'Lần đầu',
            document_feedback: [],
            requested_at: '2026-04-24T10:00:00Z',
            resolved_at: '2026-04-24T15:00:00Z',
          },
        ],
      }),
    );

    render(<RevisionPanel {...baseProps} role="business" status="revision_required" />);

    expect(await screen.findByText(/Vẫn còn vấn đề ở seal/)).toBeInTheDocument();
    expect(screen.getByText(/Lần đầu/)).toBeInTheDocument();

    // Round 2 unresolved → no resolved badge
    // Round 1 resolved → has "Đã giải quyết" text
    expect(screen.getByText(/Đã giải quyết/)).toBeInTheDocument();

    // Severity badge
    expect(screen.getByText('major')).toBeInTheDocument();
    expect(screen.getByText(/Seal mờ/)).toBeInTheDocument();
    expect(screen.getByText(/Scan lại/)).toBeInTheDocument();
  });

  test('shows round count badge when history not empty', async () => {
    (fetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
      respond(200, {
        history: [
          {
            id: 'r1', round: 1, requester_id: 'x', requester_name: 'X',
            feedback: 'a', document_feedback: [],
            requested_at: '2026-04-25T00:00:00Z', resolved_at: null,
          },
        ],
      }),
    );
    render(<RevisionPanel {...baseProps} role="business" status="reviewing" />);
    expect(await screen.findByText(/1 vòng/)).toBeInTheDocument();
  });
});
