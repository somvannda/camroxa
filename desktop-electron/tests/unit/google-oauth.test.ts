import { describe, expect, it } from "vitest";
import { GoogleLoopbackServer } from "../../electron/services/google-oauth";

describe("Google loopback server", () => {
  it("accepts exactly one callback and resolves code/state", async () => {
    const server = new GoogleLoopbackServer(0);
    try {
      await server.start();
      expect(server.redirectUri).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/google\/callback$/);

      const pending = server.wait(5_000);
      const response = await fetch(`${server.redirectUri}?code=auth-code&state=signed-state`);
      expect(response.status).toBe(200);
      await expect(pending).resolves.toEqual({ code: "auth-code", state: "signed-state" });
    } finally {
      server.close();
    }
  });

  it("fails loudly when the fixed loopback port is already busy", async () => {
    const first = new GoogleLoopbackServer(0);
    await first.start();
    const second = new GoogleLoopbackServer(first.port);
    try {
      await expect(second.start()).rejects.toMatchObject({ code: "OAUTH_PORT_BUSY" });
    } finally {
      first.close();
      second.close();
    }
  });

  it("reports a cancellation callback", async () => {
    const server = new GoogleLoopbackServer(0);
    try {
      await server.start();
      const pending = expect(server.wait(5_000)).rejects.toMatchObject({
        code: "OAUTH_CANCELLED",
      });
      await fetch(`${server.redirectUri}?error=access_denied`);
      await pending;
    } finally {
      server.close();
    }
  });

  it("rejects when the callback carries no authorization code", async () => {
    const server = new GoogleLoopbackServer(0);
    try {
      await server.start();
      const pending = expect(server.wait(5_000)).rejects.toMatchObject({ code: "OAUTH_ERROR" });
      await fetch(`${server.redirectUri}?state=only-state`);
      await pending;
    } finally {
      server.close();
    }
  });

  it("times out when the browser never returns", async () => {
    const server = new GoogleLoopbackServer(0);
    try {
      await server.start();
      await expect(server.wait(50)).rejects.toMatchObject({ code: "OAUTH_TIMEOUT" });
    } finally {
      server.close();
    }
  });

  it("can be cancelled from the sign-in screen", async () => {
    const server = new GoogleLoopbackServer(0);
    try {
      await server.start();
      const pending = expect(server.wait(5_000)).rejects.toMatchObject({
        code: "OAUTH_CANCELLED",
      });
      server.cancel();
      await pending;
    } finally {
      server.close();
    }
  });
});
