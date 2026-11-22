import { describe, expect, it } from "vitest";
import { classifyApiEnvironment } from "../../electron/shared/api-environment";

describe("classifyApiEnvironment", () => {
  it("recognises the packaged production base URL", () => {
    expect(classifyApiEnvironment("https://api.camxora.com/api/v1")).toBe("production");
  });

  it("recognises sandbox, local and custom hosts", () => {
    expect(classifyApiEnvironment("https://api.sandbox.camxora.com/api/v1")).toBe("sandbox");
    expect(classifyApiEnvironment("http://127.0.0.1:8000/api/v1")).toBe("local");
    expect(classifyApiEnvironment("http://localhost:4003/api/v3")).toBe("local");
    expect(classifyApiEnvironment("https://music.example.test/api/v1")).toBe("development");
    expect(classifyApiEnvironment("not a url")).toBe("development");
  });
});
