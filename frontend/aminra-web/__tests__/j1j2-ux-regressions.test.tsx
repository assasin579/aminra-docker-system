import React from 'react';
import { beforeEach, afterEach, test, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import RevisionPanel from '@/components/submissions/RevisionPanel';
import SubmissionsPage from '@/app/submissions/page';
const auth = vi.hoisted(() => ({ user: { id: 'actor', tenant_id: 'tenant', role: 'business' as string, is_owner: true }, token: 'test-token', isAuthenticated: true, loading: false }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ replace: vi.fn() }), useSearchParams: () => new URLSearchParams('dossier_id=dossier-A') }));
vi.mock('@/components/UserAuthContext', () => ({ useUserAuth: () => auth }));
const response = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => { auth.user.id = 'actor'; auth.token = 'test-token'; auth.user.role = 'business'; vi.stubGlobal('fetch', vi.fn()); });
afterEach(() => vi.unstubAllGlobals());
const current = [{ id: 'new-policy', filename: 'policy-v2.pdf', doc_type: 'policy' }];
const round = { id: 'round1', round: 1, requester_id: 'cb', requester_name: 'CB', feedback: 'Fix the old policy', document_feedback: [{ document_id: 'old-policy-uuid', issue: 'Missing signature', severity: 'major' }], requested_at: '2026-10-30T00:00:00Z', resolved_at: null, submitted_document_ids: ['old-policy-uuid'], submitted_documents: [{ id: 'old-policy-uuid', filename: 'policy-v1.pdf', doc_type: 'policy' }] };
test('historical feedback uses its own round snapshot after replacement', async () => {
    vi.mocked(fetch).mockResolvedValue(response(200, { history: [round] }));
    render(<RevisionPanel submissionId="s1" status="revision_required" role="business" token="t" documents={current}/>);
    await screen.findByText('Missing signature', { exact: false });
    const feedback = screen.getByText('Missing signature', { exact: false }).closest('li')!;
    expect(feedback).toHaveTextContent('policy-v1.pdf');
    expect(feedback).not.toHaveTextContent('old-poli…');
});
test('successful history refetch clears previous error', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(response(503, {})).mockResolvedValueOnce(response(200, { history: [round] }));
    const p = { submissionId: 's1', role: 'business' as const, token: 't', documents: current };
    const view = render(<RevisionPanel {...p} status="reviewing"/>);
    await screen.findByRole('alert');
    view.rerender(<RevisionPanel {...p} status="revision_required"/>);
    await screen.findByText('Fix the old policy');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
const sub = { id: 's1', company_name: 'Business A', status: 'revision_required', notes: null, auditor_notes: null, doc_count: 1, document_ids: ['doc1'], auditor_id: null, auditor_name: null, submitted_at: '2026-10-30T00:00:00Z', updated_at: '2026-10-30T00:00:00Z', deadline: null, provider_name: 'CB A' };
test('revision_required shows actionable correction status', async () => {
    vi.mocked(fetch).mockResolvedValue(response(200, { submissions: [sub] }));
    render(<SubmissionsPage />);
    expect(await screen.findByText('Cần sửa và gửi lại')).toBeInTheDocument();
    expect(screen.queryByText('Chờ được audit')).not.toBeInTheDocument();
});
test('list failure shows retry instead of empty-state claim', async () => {
    vi.mocked(fetch).mockResolvedValue(response(503, { detail: 'Service unavailable' }));
    render(<SubmissionsPage />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được danh sách hồ sơ');
    expect(screen.queryByText('Chưa có hồ sơ nào')).not.toBeInTheDocument();
    vi.mocked(fetch).mockResolvedValue(response(200, { submissions: [sub] }));
    fireEvent.click(screen.getByRole('button', { name: 'Thử tải lại danh sách' }));
    expect(await screen.findByText('Cần sửa và gửi lại')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
test('submit setup failure is actionable and cannot be submitted', async () => {
    vi.mocked(fetch).mockImplementation(async (url) => String(url).includes('my-submissions') ? response(200, { submissions: [] }) : response(503, { detail: 'Unavailable' }));
    render(<SubmissionsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Gửi hồ sơ mới/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được tổ chức chứng nhận');
    expect(screen.queryByText('Chưa có tổ chức nào trong hệ thống')).not.toBeInTheDocument();
    expect(screen.queryByText('Bạn chưa có tài liệu nào')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Gửi 0 tài liệu' })).toBeDisabled();
});
const dossier = { id: 'dossier-A', title: 'Factory A dossier', standard_code: 'HAS', requirements_version_id: 'pinned-v1', requirements_binding_status: 'bound', documents: [{ id: 'doc1', original_filename: 'policy.pdf', doc_type: 'policy' }] };
function mockSetup() {
    vi.mocked(fetch).mockImplementation(async (url) => {
        const path = String(url);
        if (path.endsWith('my-submissions') || path.endsWith('/received'))
            return response(200, { submissions: [sub] });
        if (path.endsWith('/providers'))
            return response(200, { providers: [{ id: 'cb', company_name: 'CB A', email: 'cb@example.test' }] });
        if (path.endsWith('/dossier-A'))
            return response(200, dossier);
        return response(200, { auditors: [] });
    });
}
test('submit form displays pinned dossier and preserves receipt key after response loss', async () => {
    mockSetup();
    render(<SubmissionsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Gửi hồ sơ mới/ }));
    expect(await screen.findByRole('region', { name: 'Hồ sơ đang gửi' })).toHaveTextContent('Factory A dossier');
    expect(screen.getByRole('region', { name: 'Hồ sơ đang gửi' })).toHaveTextContent('pinned-v1');
    fireEvent.click(screen.getByRole('button', { name: /CB A cb@example.test/ }));
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Connection lost'));
    fireEvent.click(screen.getByRole('button', { name: 'Gửi 1 tài liệu' }));
    await screen.findByText(/Giữ nguyên nội dung và thử lại/);
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Connection lost again'));
    fireEvent.click(screen.getByRole('button', { name: 'Gửi 1 tài liệu' }));
    await screen.findByText(/Giữ nguyên nội dung và thử lại/);
    const calls = vi.mocked(fetch).mock.calls.filter(([url]) => String(url).endsWith('/submissions/submit'));
    expect(calls).toHaveLength(2);
    expect(new Headers(calls[0][1]?.headers).get('Idempotency-Key')).toBe(new Headers(calls[1][1]?.headers).get('Idempotency-Key'));
    expect(JSON.parse(String(calls[0][1]?.body))).toMatchObject({ dossier_id: 'dossier-A', provider_id: 'cb', document_ids: ['doc1'] });
}, 15000);
test('CB no longer offers legacy returned as a competing correction action', async () => {
    auth.user.role = 'provider';
    mockSetup();
    render(<SubmissionsPage />);
    // Company folder then submission row.
    fireEvent.click(await screen.findByRole('button', { name: /Business A.*1 hồ sơ/ }));
    await waitFor(() => expect(screen.getByText('Cần sửa và gửi lại')).toBeInTheDocument());
    fireEvent.click(screen.getByText('Cần sửa và gửi lại').closest('button')!);
    expect(screen.queryByRole('button', { name: 'Cần bổ sung' })).not.toBeInTheDocument();
});
test('two rounds retain the correct historical file name independently', async () => {
    vi.mocked(fetch).mockResolvedValue(response(200, { history: [{ ...round, id: 'r2', round: 2, document_feedback: [{ document_id: 'new-policy', issue: 'Second issue', severity: 'minor' }], submitted_documents: current, submitted_document_ids: ['new-policy'] }, round] }));
    render(<RevisionPanel submissionId="s1" status="revision_required" role="business" token="t" documents={[{ id: 'v3', filename: 'policy-v3.pdf', doc_type: 'policy' }]}/>);
    expect((await screen.findByText('Missing signature', { exact: false })).closest('li')).toHaveTextContent('policy-v1.pdf');
    expect(screen.getByText('Second issue', { exact: false }).closest('li')).toHaveTextContent('policy-v2.pdf');
});
test('setup retry recovers valid pinned data without treating failure as empty', async () => {
    vi.mocked(fetch).mockImplementation(async (url) => String(url).includes('my-submissions') ? response(200, { submissions: [] }) : response(503, {}));
    render(<SubmissionsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Gửi hồ sơ mới/ }));
    await screen.findByRole('alert');
    mockSetup();
    fireEvent.click(screen.getByRole('button', { name: 'Thử tải lại dữ liệu gửi hồ sơ' }));
    expect(await screen.findByRole('region', { name: 'Hồ sơ đang gửi' })).toHaveTextContent('Factory A dossier');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
test('failed document loading blocks correction controls until a successful retry', async () => {
    mockSetup();
    const normal = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (url, init) => String(url).endsWith('/s1/documents') ? response(503, {}) : normal(url, init));
    render(<SubmissionsPage />);
    fireEvent.click((await screen.findByText('Cần sửa và gửi lại')).closest('button')!);
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được tài liệu của hồ sơ');
    expect(screen.queryByRole('button', { name: 'Đã sửa — gửi lại cho CB' })).not.toBeInTheDocument();
    vi.mocked(fetch).mockImplementation(async (url, init) => {
        if (String(url).endsWith('/s1/documents'))
            return response(200, { documents: [{ id: 'new-policy', original_filename: 'policy-v2.pdf' }] });
        if (String(url).endsWith('/s1/revisions'))
            return response(200, { history: [round] });
        return normal(url, init);
    });
    fireEvent.click(screen.getByRole('button', { name: 'Thử tải lại tài liệu hồ sơ' }));
    expect(await screen.findByRole('button', { name: 'Đã sửa — gửi lại cho CB' })).toBeEnabled();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('silent token refresh preserves a draft but account change clears it', async () => {
    mockSetup();
    const view = render(<SubmissionsPage />);
    fireEvent.click(await screen.findByRole('button', { name: /Gửi hồ sơ mới/ }));
    await screen.findByRole('region', { name: 'Hồ sơ đang gửi' });
    fireEvent.change(screen.getByLabelText('Ghi chú (tuỳ chọn)'), { target: { value: 'Private draft for actor A' } });
    auth.token = 'refreshed-token';
    view.rerender(<SubmissionsPage />);
    expect(screen.getByLabelText('Ghi chú (tuỳ chọn)')).toHaveValue('Private draft for actor A');
    auth.user.id = 'actor-B';
    view.rerender(<SubmissionsPage />);
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Gửi hồ sơ mới/ }));
    await screen.findByRole('region', { name: 'Hồ sơ đang gửi' });
    expect(screen.getByLabelText('Ghi chú (tuỳ chọn)')).toHaveValue('');
});

test('CB feedback draft survives a silent token refresh', async () => {
    vi.mocked(fetch).mockImplementation(async () => response(200, { history: [] }));
    const view = render(<RevisionPanel submissionId="s1" status="reviewing" role="provider" token="old-token" documents={current} />);
    fireEvent.change(await screen.findByLabelText('Nội dung yêu cầu sửa'), { target: { value: 'Draft correction feedback' } });
    view.rerender(<RevisionPanel submissionId="s1" status="reviewing" role="provider" token="new-token" documents={current} />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Gửi yêu cầu sửa cho doanh nghiệp' })).toBeEnabled());
    expect(screen.getByLabelText('Nội dung yêu cầu sửa')).toHaveValue('Draft correction feedback');
});
