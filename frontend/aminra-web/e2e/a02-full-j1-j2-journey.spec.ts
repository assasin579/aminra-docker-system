import { createHash, randomUUID } from 'node:crypto';
import { test, expect, type Page } from '@playwright/test';

test.use({ serviceWorkers: 'block' });

const business = {
  id: 'b7094001-c02d-4f98-8e4c-06d55c69c2c0',
  tenant: 'a10d44c1-5f97-4e9f-b1d4-0abf90598417',
  email: 'a02-b7094001-c02d-4f98-8e4c-06d55c69c2c0@example.invalid',
  role: 'business',
};
const provider = {
  id: 'c325bc0e-8e37-4f94-97a6-805111ac2d8f',
  tenant: '54182089-3a6d-458a-994d-93ac4e0c504f',
  email: 'cb-synthetic@example.invalid',
  role: 'provider',
};
const platformAdmin = {
  id: 'c325bc0e-8e37-4f94-97a6-805111ac2d8e',
  tenant: '54182089-3a6d-458a-994d-93ac4e0c504f',
  email: 'a02-platform-admin@example.invalid',
  role: 'admin',
};

async function setActor(page: Page, actor: typeof business | typeof provider | typeof platformAdmin) {
  await page.addInitScript(({ id, tenant, email, role }) => {
    const payload = btoa(JSON.stringify({ sub: id, email, exp: Math.floor(Date.now() / 1000) + 7200 }))
      .replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
    localStorage.setItem('aminra_user_token', `e30.${payload}.synthetic-signature`);
    localStorage.setItem('aminra_user_profile', JSON.stringify({
      id, tenant_id: tenant, email, role, status: 'active', is_owner: true,
      company_name: role === 'business' ? 'SYNTH A02 Business' : 'Synthetic CB',
    }));
    document.cookie = 'aminra_session=1; path=/; max-age=31536000; SameSite=Lax';
  }, { id: actor.id, tenant: actor.tenant, email: actor.email, role: actor.role });
}

const sha256 = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');

test('J1/J2: one fresh Business–CB pair completes rendered evidence and revision journey', async ({ page, browser }) => {
  const run = randomUUID();
  const dossierTitle = `A02 synthetic journey ${run}`;
  const marker = `A02-J1J2-${run}`;
  const originalBytes = Buffer.from(`%PDF-1.4\n% synthetic original ${run}\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n`);
  const revisedBytes = Buffer.from(`%PDF-1.4\n% synthetic revised ${run}\n1 0 obj << /Type /Catalog >> endobj\n%%EOF\n`);
  const originalHash = sha256(originalBytes);
  const revisedHash = sha256(revisedBytes);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await setActor(page, business);
  await page.goto('/');

  // Read only the canonical scheme identity as Business; setup requirements through
  // the existing platform-admin CRUD + publish routes, never by writing version pointers.
  const standardTypeId = await page.evaluate(async () => {
    const token = localStorage.getItem('aminra_user_token')!;
    const response = await fetch('/api/standard-types', { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error(`canonical standard listing ${response.status}: ${await response.text()}`);
    const standards = await response.json();
    const selected = standards.find((item: { enabled: boolean }) => item.enabled);
    if (!selected?.id) throw new Error('no canonical enabled standard available for synthetic fixture');
    return selected.id as string;
  });

  const adminContext = await browser.newContext({ baseURL: new URL(page.url()).origin, serviceWorkers: 'block' });
  const adminPage = await adminContext.newPage();
  await setActor(adminPage, platformAdmin);
  await adminPage.goto('/');
  const published = await adminPage.evaluate(async ({ standardTypeId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    const slotsResponse = await fetch(`/api/auth/admin/standard-types/${standardTypeId}/doc-types`, {
      method: 'PUT', headers,
      body: JSON.stringify({ doc_types: [{ doc_type: 'policy', required: true, display_order: 1 }] }),
    });
    if (!slotsResponse.ok) throw new Error(`canonical slots ${slotsResponse.status}: ${await slotsResponse.text()}`);
    const publishResponse = await fetch(`/api/auth/admin/standard-types/${standardTypeId}/publish-requirements`, {
      method: 'POST', headers, body: '{}',
    });
    if (!publishResponse.ok) throw new Error(`canonical publish ${publishResponse.status}: ${await publishResponse.text()}`);
    return publishResponse.json();
  }, { standardTypeId });
  expect(published.requirements_version_id).toBeTruthy();
  await adminContext.close();

  const fixture = await page.evaluate(async ({ standardTypeId, title }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
    const createResponse = await fetch('/api/dossiers', {
      method: 'POST', headers,
      body: JSON.stringify({ title, standard_type_id: standardTypeId, notes: 'synthetic acceptance fixture' }),
    });
    if (!createResponse.ok) throw new Error(`fresh dossier create ${createResponse.status}: ${await createResponse.text()}`);
    return createResponse.json();
  }, { standardTypeId, title: dossierTitle });
  const dossierId = fixture.id as string;
  expect(dossierId).toBeTruthy();

  const boundReadiness = await page.evaluate(async ({ dossierId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const response = await fetch(`/api/dossiers/${dossierId}/readiness`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error(`bound readiness ${response.status}: ${await response.text()}`);
    return response.json();
  }, { dossierId });
  expect(boundReadiness.requirements_binding_status).toBe('bound');
  expect(boundReadiness.requirements_version_id).toBe(published.requirements_version_id);

  await page.goto(`/dossiers/${dossierId}`);
  await expect(page.getByRole('heading', { name: dossierTitle })).toBeVisible();
  const policySlot = page.getByTestId('doc-type-row-policy');
  await policySlot.getByLabel('Tệp mới cho policy').setInputFiles({
    name: `original-${run}.pdf`, mimeType: 'application/pdf', buffer: originalBytes,
  });
  const attachWait = page.waitForResponse(response =>
    response.request().method() === 'POST' && new URL(response.url()).pathname === `/api/dossiers/${dossierId}/documents`,
  );
  await policySlot.getByRole('button', { name: 'Đính kèm slot' }).click();
  const attachResponse = await attachWait;
  expect(attachResponse.status()).toBe(200);
  const attached = await attachResponse.json();
  const originalDocumentId = attached.document_id as string;
  expect(originalDocumentId).toBeTruthy();
  expect(attached.doc_type).toBe('policy');
  expect(attached.attachment_state).toBe('attached');
  expect(attached.created_attachment).toBe(true);

  // Read back the persisted association through the same rendered journey's API
  // boundary: exact Dossier, pinned requirements version, slot, and document version.
  const dossierReadback = await page.evaluate(async ({ dossierId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const response = await fetch(`/api/dossiers/${dossierId}`, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
    if (!response.ok) throw new Error(`Dossier attachment readback ${response.status}: ${await response.text()}`);
    return response.json();
  }, { dossierId });
  expect(dossierReadback.id).toBe(dossierId);
  expect(dossierReadback.requirements_binding_status).toBe('bound');
  expect(dossierReadback.requirements_version_id).toBe(published.requirements_version_id);
  expect(dossierReadback.documents).toEqual(expect.arrayContaining([
    expect.objectContaining({ id: originalDocumentId, doc_type: 'policy', version_number: 1 }),
  ]));

  await page.goto(`/submissions?dossier_id=${dossierId}`);
  await page.getByRole('button', { name: 'Gửi hồ sơ mới' }).click();
  const submitDialog = page.getByRole('dialog');
  await expect(submitDialog.getByRole('heading', { name: 'Gửi hồ sơ đến tổ chức chứng nhận' })).toBeVisible();
  await submitDialog.getByRole('button').filter({ hasText: provider.email }).click();
  await submitDialog.locator('textarea').fill(marker);
  const submitWait = page.waitForResponse(response =>
    response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/api/submissions/submit',
  );
  await submitDialog.getByRole('button', { name: /^Gửi \d+ tài liệu$/ }).click();
  const submitResponse = await submitWait;
  expect(submitResponse.status(), await submitResponse.text()).toBe(200);
  const submitBody = await submitResponse.json();
  const submissionId = (submitBody.submission_id || submitBody.id) as string;
  expect(submissionId).toBeTruthy();

  const cbContext = await browser.newContext({ baseURL: new URL(page.url()).origin, serviceWorkers: 'block' });
  const cbPage = await cbContext.newPage();
  cbPage.on('pageerror', error => errors.push(error.message));
  await setActor(cbPage, provider);
  await cbPage.goto('/submissions');
  const cbReceived = await cbPage.evaluate(async ({ submissionId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const response = await fetch('/api/api/submissions/received', { headers: { Authorization: `Bearer ${token}`, 'Cache-Control': 'no-store' } });
    if (!response.ok) throw new Error(`received ${response.status}: ${await response.text()}`);
    const data = await response.json();
    return (data.submissions || []).find((item: { id: string }) => item.id === submissionId) || null;
  }, { submissionId });
  expect(cbReceived).toBeTruthy();
  const businessGroupName = cbReceived.company_name as string;
  await cbPage.getByRole('button').filter({ hasText: businessGroupName }).first().click();
  const submissionCard = cbPage.getByRole('button').filter({ hasText: marker }).first();
  await expect(submissionCard).toBeVisible();
  await submissionCard.click();
  await expect(cbPage.getByText(`original-${run}.pdf`)).toBeVisible();

  const firstPreviewWait = cbPage.waitForResponse(response =>
    response.request().method() === 'GET' && new URL(response.url()).pathname.endsWith('/preview'),
  );
  const firstPreviewPopup = cbPage.waitForEvent('popup');
  await cbPage.getByRole('button', { name: 'Xem', exact: true }).click();
  const firstPreview = await firstPreviewWait;
  const openedOriginalPreview = await firstPreviewPopup;
  expect(firstPreview.status()).toBe(200);
  expect(openedOriginalPreview).toBeTruthy();
  const firstPreviewEvidence = await cbPage.evaluate(async ({ documentId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const response = await fetch(`/api/api/documents/${documentId}/preview`, {
      headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
    });
    return { status: response.status, bytes: Array.from(new Uint8Array(await response.arrayBuffer())) };
  }, { documentId: originalDocumentId });
  expect(firstPreviewEvidence.status).toBe(200);
  expect(sha256(Buffer.from(firstPreviewEvidence.bytes))).toBe(originalHash);
  const directFileEvidence = await cbPage.evaluate(async ({ documentId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const response = await fetch(`/api/api/documents/${documentId}/file`, {
      headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
    });
    return { status: response.status, bytes: Array.from(new Uint8Array(await response.arrayBuffer())) };
  }, { documentId: originalDocumentId });
  expect(directFileEvidence.status).toBe(200);
  expect(sha256(Buffer.from(directFileEvidence.bytes))).toBe(originalHash);

  await cbPage.getByRole('button', { name: 'Đang đánh giá', exact: true }).click();
  const requestForm = cbPage.locator('[data-form="request-revision"]');
  await expect(requestForm).toBeVisible();
  await requestForm.locator('textarea').fill(`${marker}: replace policy evidence`);
  const requestWait = cbPage.waitForResponse(response =>
    response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/request-revision'),
  );
  await requestForm.getByRole('button', { name: 'Gửi yêu cầu sửa cho doanh nghiệp' }).click();
  const requestResponse = await requestWait;
  expect(requestResponse.status()).toBe(200);

  // Business replaces the document through its rendered submission view, then resubmits.
  await page.goto('/submissions');
  const businessCardHeader = page.getByRole('button').filter({ hasText: marker }).first();
  await expect(businessCardHeader).toBeVisible();
  await businessCardHeader.click();
  await expect(page.locator('[data-revision-panel]')).toBeVisible();
  await expect(page.locator('[data-revision-panel]')).toContainText(`${marker}: replace policy evidence`);
  await expect(page.locator('[data-revision-panel]')).toContainText('Vòng 1');
  const businessCard = businessCardHeader.locator('xpath=..');
  const replacementInput = businessCard.locator('input[type="file"]').first();
  await businessCard.locator('button[title="Upload phiên bản mới"]').click();
  const uploadWait = page.waitForResponse(response =>
    response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/api/documents/upload',
  );
  const replaceWait = page.waitForResponse(response =>
    response.request().method() === 'PUT' && new URL(response.url()).pathname.endsWith('/replace-document'),
  );
  await replacementInput.setInputFiles({
    name: `revised-${run}.pdf`, mimeType: 'application/pdf', buffer: revisedBytes,
  });
  const uploadResponse = await uploadWait;
  expect(uploadResponse.status()).toBe(200);
  const replacement = await uploadResponse.json();
  const newDocumentId = replacement.id as string;
  expect(newDocumentId).toBeTruthy();
  const replaceResponse = await replaceWait;
  expect(replaceResponse.status()).toBe(200);
  await expect(page.getByText(`revised-${run}.pdf`, { exact: true })).toBeVisible();

  const resubmitForm = page.locator('[data-form="resubmit"]');
  await expect(resubmitForm).toBeVisible();
  await resubmitForm.locator('textarea').fill(`${marker}: corrected evidence submitted`);
  const resubmitWait = page.waitForResponse(response =>
    response.request().method() === 'POST' && new URL(response.url()).pathname.endsWith('/resubmit'),
  );
  await resubmitForm.getByRole('button', { name: 'Đã sửa — gửi lại cho CB' }).click();
  const resubmitResponse = await resubmitWait;
  expect(resubmitResponse.status(), await resubmitResponse.text()).toBe(200);
  expect(resubmitResponse.request().headers()['idempotency-key']).toBeTruthy();

  // Same CB actor sees current round and the immutable evidence set from the prior submitted round.
  await cbPage.reload();
  await cbPage.getByRole('button').filter({ hasText: businessGroupName }).first().click();
  const refreshedCard = cbPage.getByRole('button').filter({ hasText: marker }).first();
  await expect(refreshedCard).toBeVisible();
  await refreshedCard.click();
  await expect(cbPage.getByText(`revised-${run}.pdf`, { exact: true })).toBeVisible();
  const roundDiff = cbPage.getByRole('region', { name: /So sánh bằng chứng vòng 1/ });
  await expect(roundDiff).toContainText(`original-${run}.pdf → revised-${run}.pdf`);
  const currentPreviewWait = cbPage.waitForResponse(response =>
    response.request().method() === 'GET' && new URL(response.url()).pathname.endsWith('/preview'),
  );
  const openedCurrentPreview = cbPage.waitForEvent('popup');
  await cbPage.getByRole('button', { name: 'Xem', exact: true }).click();
  const currentPreview = await currentPreviewWait;
  const currentPopup = await openedCurrentPreview;
  expect(currentPreview.status()).toBe(200);
  expect(currentPopup).toBeTruthy();
  const currentPreviewEvidence = await cbPage.evaluate(async ({ documentId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const response = await fetch(`/api/api/documents/${documentId}/preview`, {
      headers: { Authorization: `Bearer ${token}` }, cache: 'no-store',
    });
    return { status: response.status, bytes: Array.from(new Uint8Array(await response.arrayBuffer())) };
  }, { documentId: newDocumentId });
  expect(currentPreviewEvidence.status).toBe(200);
  expect(sha256(Buffer.from(currentPreviewEvidence.bytes))).toBe(revisedHash);

  const roundEvidence = await cbPage.evaluate(async ({ submissionId, originalDocumentId }) => {
    const token = localStorage.getItem('aminra_user_token')!;
    const headers = { Authorization: `Bearer ${token}` };
    const [historyResponse, currentResponse, oldFileResponse] = await Promise.all([
      fetch(`/api/api/submissions/${submissionId}/revisions`, { headers, cache: 'no-store' }),
      fetch(`/api/api/submissions/received/${submissionId}/documents`, { headers, cache: 'no-store' }),
      fetch(`/api/api/documents/${originalDocumentId}/file`, { headers, cache: 'no-store' }),
    ]);
    if (!historyResponse.ok || !currentResponse.ok) throw new Error(`history/current ${historyResponse.status}/${currentResponse.status}`);
    return {
      history: await historyResponse.json(),
      current: await currentResponse.json(),
      oldFileStatus: oldFileResponse.status,
      oldFileBytes: Array.from(new Uint8Array(await oldFileResponse.arrayBuffer())),
    };
  }, { submissionId, originalDocumentId });
  const priorSnapshot = roundEvidence.history.history.find((item: { submitted_round: number }) => item.submitted_round === 1);
  expect(priorSnapshot).toBeTruthy();
  expect(priorSnapshot.submitted_document_ids).toContain(originalDocumentId);
  expect(roundEvidence.oldFileStatus).toBe(200);
  const oldFileBytes = Buffer.from(roundEvidence.oldFileBytes);
  expect(sha256(oldFileBytes)).toBe(originalHash);
  expect(sha256(oldFileBytes)).not.toBe(revisedHash);
  const currentDocs = roundEvidence.current.documents || [];
  expect(currentDocs.some((doc: { id: string }) => doc.id === newDocumentId)).toBe(true);
  expect(currentDocs.some((doc: { id: string }) => doc.id === originalDocumentId)).toBe(false);

  console.log(JSON.stringify({ run, dossierId, submissionId, originalDocumentId, newDocumentId, submittedRound: priorSnapshot.submitted_round, revisionRequestRound: priorSnapshot.round, originalHash, revisedHash, retainedOldHash: sha256(oldFileBytes) }));
  expect(errors).toEqual([]);
  await cbContext.close();
});
