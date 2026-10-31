import React from 'react';
import { beforeEach, afterEach, test, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import Page from '@/app/create-document/page';
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams('dossier=dossier-A') }));
vi.mock('@/components/UserAuthContext', () => ({ useUserAuth: () => ({ token: 't', isAuthenticated: true, user: { role: 'business', industry_schema_code: 'factory' } }) }));
vi.mock('@/lib/featureFlags', () => ({ useFeatureFlags: () => ({ flags: {} }) }));
const response = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => vi.stubGlobal('fetch', vi.fn(async (url) => {
    const path = String(url);
    if (path.includes('/dossiers/'))
        return response(200, { id: 'dossier-A', title: 'Pinned dossier A', requirements_binding_status: 'bound', requirements_version_id: 'version-A', standard_type_id: 'has', standard_code: 'HAS', standard_name_vi: 'Pinned HAS', doc_types: [{ doc_type: 'halal_policy', required: true, display_order: 1 }] });
    if (path.includes('company-profile'))
        return response(200, { company_name: 'Company', email: 'a@example.test', address: 'Address', phone: '123', representative_name: 'Rep', manager_name: 'Manager' });
    if (path.includes('industry-schemas'))
        return response(200, { code: 'factory', name_vi: 'Factory', available_standards: [{ code: 'OTHER', name_vi: 'Current different standard', is_default: true }] });
    if (path.includes('available'))
        return response(200, { templates: [{ doc_type: 'halal_policy', label: 'Policy', has_vi: true, has_en: true }] });
    return response(200, { placeholders: [] });
})));
afterEach(() => vi.unstubAllGlobals());
test('template journey retains dossier and pinned requirements with a return-to-attachment link', async () => {
    render(<Page />);
    expect(await screen.findByRole('region', { name: 'Ngữ cảnh hồ sơ nguồn' })).toHaveTextContent('Pinned dossier A');
    expect(screen.getByRole('region', { name: 'Ngữ cảnh hồ sơ nguồn' })).toHaveTextContent('version-A');
    expect(screen.getByRole('link', { name: 'Quay lại hồ sơ để đính kèm tài liệu' })).toHaveAttribute('href', '/dossiers/dossier-A#dossier-document-attachments');
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/standard-types/'))).toBe(false);
    expect(screen.queryByText('Current different standard')).not.toBeInTheDocument();
});
test('unavailable dossier blocks generation rather than falling back to global templates', async () => {
    vi.mocked(fetch).mockResolvedValue(response(503, {}));
    render(<Page />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Không tải được hồ sơ nguồn');
    expect(screen.queryByRole('button', { name: /Tạo.*tài liệu/ })).not.toBeInTheDocument();
});
