import { describe, expect, test } from "vitest";

import { parseApiError, validatePassword } from "@/lib/apiError";

describe("validatePassword", () => {
  test("requires a special character to match Keycloak password policy", () => {
    expect(validatePassword("DebugPass123")).toBe(
      "Mật khẩu phải có ít nhất 1 ký tự đặc biệt",
    );
  });

  test("accepts the backend/Keycloak policy shape", () => {
    expect(validatePassword("DebugPass123!")).toBeNull();
  });
});

describe("parseApiError", () => {
  test("uses object detail.message for operator-facing partial cleanup errors", () => {
    expect(parseApiError({ detail: { message: "PG/app DB chưa bị xoá" } }, "fallback")).toBe(
      "PG/app DB chưa bị xoá",
    );
  });
});
