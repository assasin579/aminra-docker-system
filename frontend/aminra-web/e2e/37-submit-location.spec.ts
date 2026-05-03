/**
 * Static regression guard — vị trí "Gửi hồ sơ mới"
 *
 * Migration: button/modal "Gửi hồ sơ" đã được move từ documents/page.tsx
 * sang submissions/page.tsx (lỗi nghiệp vụ — action này thuộc vòng đời
 * submission, không phải vòng đời tài liệu).
 *
 * Test này đọc source file trực tiếp để đảm bảo:
 * 1. documents/page.tsx KHÔNG còn chứa submit state / handler / modal
 * 2. submissions/page.tsx CÓ đầy đủ: state, openSubmitModal, handleSubmit,
 *    button "Gửi hồ sơ mới", và isBusiness guard
 *
 * Không cần server. Chạy trên mọi CI không có backend.
 */
import { test, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";

const DOCS_PAGE = "app/documents/page.tsx";
const SUBS_PAGE = "app/submissions/page.tsx";

test.describe("37 — submit-location static guard", () => {
  test("documents/page.tsx không còn submit state hay modal", async () => {
    const src = await readFile(DOCS_PAGE, "utf8");

    // State variables đã bị xoá
    expect(src, "showSubmit state đã bị xoá khỏi documents page").not.toMatch(
      /const \[showSubmit/,
    );
    expect(src, "providers state đã bị xoá khỏi documents page").not.toMatch(
      /const \[providers.*setProviders/,
    );
    expect(src, "selectedProvider state đã bị xoá khỏi documents page").not.toMatch(
      /const \[selectedProvider/,
    );
    expect(src, "submitting state đã bị xoá khỏi documents page").not.toMatch(
      /const \[submitting.*setSubmitting/,
    );

    // Handlers đã bị xoá
    expect(src, "openSubmitModal đã bị xoá khỏi documents page").not.toMatch(
      /openSubmitModal/,
    );
    expect(src, "handleSubmit đã bị xoá khỏi documents page").not.toMatch(
      /const handleSubmit/,
    );

    // Button / modal text đã bị xoá
    expect(src, "button Gửi hồ sơ đã bị xoá khỏi documents page").not.toMatch(
      /Gửi hồ sơ/,
    );
    expect(src, "submit modal không còn trong documents page").not.toMatch(
      /Gửi hồ sơ đến tổ chức chứng nhận/,
    );
    expect(src, "/submissions/submit không được gọi từ documents page").not.toMatch(
      /\/submissions\/submit/,
    );
  });

  test("submissions/page.tsx có đầy đủ submit state, handlers, và isBusiness guard", async () => {
    const src = await readFile(SUBS_PAGE, "utf8");

    // State present
    expect(src, "showSubmit state có trong submissions page").toMatch(
      /const \[showSubmit/,
    );
    expect(src, "submitDocs state có trong submissions page").toMatch(
      /const \[submitDocs/,
    );
    expect(src, "selectedProvider state có trong submissions page").toMatch(
      /const \[selectedProvider/,
    );
    expect(src, "submitting state có trong submissions page").toMatch(
      /const \[submitting.*setSubmitting/,
    );

    // Handlers present
    expect(src, "openSubmitModal có trong submissions page").toMatch(
      /const openSubmitModal/,
    );
    expect(src, "handleSubmit có trong submissions page").toMatch(
      /const handleSubmit/,
    );

    // Parallel fetch — cả hai endpoint phải được gọi
    expect(src, "openSubmitModal fetch providers").toMatch(
      /\/submissions\/providers/,
    );
    expect(src, "openSubmitModal fetch documents").toMatch(
      /\/documents\?page=1/,
    );
    expect(src, "openSubmitModal dùng Promise.all").toMatch(/Promise\.all/);

    // Sau submit thành công → fetchSubs được gọi (không chỉ alert)
    expect(src, "handleSubmit gọi fetchSubs sau khi submit thành công").toMatch(
      /fetchSubs\(\)[\s\S]{0,200}setShowSubmit\(false\)|setShowSubmit\(false\)[\s\S]{0,200}fetchSubs\(\)/,
    );

    // Button có isBusiness guard
    expect(src, "button Gửi hồ sơ mới chỉ render khi isBusiness").toMatch(
      /isBusiness[\s\S]{0,200}Gửi hồ sơ mới|Gửi hồ sơ mới[\s\S]{0,200}isBusiness/,
    );

    // Modal text có trong submissions page
    expect(src, "submit modal có trong submissions page").toMatch(
      /Gửi hồ sơ đến tổ chức chứng nhận/,
    );

    // Empty state guard khi không có doc
    expect(src, "empty state guard khi submitDocs rỗng").toMatch(
      /submitDocs\.length === 0/,
    );
    expect(src, "link redirect về documents khi không có doc").toMatch(
      /href="\/documents"/,
    );
  });

  test("submissions/page.tsx gọi fetchSubs sau submit — không dùng alert làm UX chính", async () => {
    const src = await readFile(SUBS_PAGE, "utf8");

    // fetchSubs phải xuất hiện trong handleSubmit block
    // (dùng regex loose vì minification không áp dụng ở source)
    const handleSubmitBlock = src.slice(src.indexOf("const handleSubmit"));
    expect(
      handleSubmitBlock,
      "fetchSubs() phải được gọi trong handleSubmit",
    ).toMatch(/fetchSubs\(\)/);
  });
});
