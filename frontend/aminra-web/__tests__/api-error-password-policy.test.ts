import { describe, expect, test } from "vitest";

import { validatePassword } from "@/lib/apiError";

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
