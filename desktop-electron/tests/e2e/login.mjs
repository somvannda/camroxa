import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { _electron as electron } from "playwright";

const root = process.cwd();
const artifacts = path.join(root, "artifacts");
fs.mkdirSync(artifacts, { recursive: true });

const API_BASE = process.env.CAMXORA_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

async function launch(name, env = {}) {
  const userData = path.join(artifacts, name);
  fs.rmSync(userData, { recursive: true, force: true });
  const app = await electron.launch({
    args: ["dist-electron/main.cjs"],
    cwd: root,
    env: {
      ...process.env,
      CAMXORA_DEV_AUTH: "0",
      CAMXORA_USER_DATA_DIR: userData,
      CAMXORA_API_BASE_URL: API_BASE,
      ...env,
    },
  });
  const window = await app.firstWindow();
  await window.waitForLoadState("domcontentloaded");
  await window.waitForTimeout(900);
  return { app, window };
}

// 1. The login page renders without the dev bypass.
{
  const { app, window } = await launch("e2e-login");
  try {
    const text = await window.locator("body").innerText();
    await window.screenshot({ path: path.join(artifacts, "login.png"), fullPage: true });

    console.log(
      JSON.stringify({
        title: await window.title(),
        hasLogin: text.includes("Sign in to listen"),
        hasEmail: text.includes("Email"),
        hasGoogle: text.includes("Continue with Google"),
        hasRemember: text.includes("Remember me"),
      }),
    );
    if (!text.includes("Sign in to listen")) {
      throw new Error("Login page did not render");
    }
    if (!text.includes("Continue with Google")) {
      throw new Error("Google sign-in is missing the login page");
    }
  } finally {
    await app.close();
  }
}

// 2. Google sign-in reports a clear error when the server is unreachable,
//    without waiting for the full loopback timeout.
{
  const { app, window } = await launch("e2e-login-google", {
    CAMXORA_API_BASE_URL: "http://127.0.0.1:59998/api/v1",
  });
  try {
    await window.getByRole("button", { name: "Continue with Google" }).click();
    const alert = window.getByText("Cannot reach Camxora. Check your connection.");
    await alert.waitFor({ timeout: 15_000 });
    const text = await window.locator("body").innerText();
    await window.screenshot({ path: path.join(artifacts, "login-google-unreachable.png"), fullPage: true });

    console.log(
      JSON.stringify({
        googleErrorShown: text.includes("Cannot reach Camxora. Check your connection."),
        waitingCleared: !text.includes("Waiting for browser"),
      }),
    );
    if (text.includes("Waiting for browser")) {
      throw new Error("Google sign-in stayed in the waiting state after the failure");
    }
  } finally {
    await app.close();
  }
}

// 3. Paid, email-confirmation and onboarding gates route through bootstrap.
{
  let scenario = "free";
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const json = (status, body) => {
      const raw = JSON.stringify(body);
      response.writeHead(status, {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(raw),
      });
      response.end(raw);
    };

    if (url.pathname.endsWith("/auth/login") && request.method === "POST") {
      request.resume();
      return json(200, {
        access_token: `access-${scenario}`,
        refresh_token: `refresh-${scenario}`,
        token_type: "bearer",
        expires_in: 3600,
      });
    }

    if (url.pathname.endsWith("/users/me") && request.method === "GET") {
      if (!(request.headers.authorization ?? "").startsWith("Bearer ")) {
        return json(401, { error: { code: "AUTHENTICATION_ERROR", message: "Invalid credentials." } });
      }
      return json(200, {
        id: "e2e-user",
        email: "e2e@example.com",
        email_confirmed: scenario !== "unconfirmed",
        display_name: "E2E User",
        role: "user",
        desktop_access: scenario !== "free",
        onboarding_paid: true,
        credit_balance: scenario === "free" ? 0 : 500,
        channel_profile_count: scenario === "ready" ? 2 : 0,
      });
    }

    if (url.pathname.endsWith("/stats/dashboard") && request.method === "GET") {
      return json(200, {
        credits_spent: 0,
        credits_remaining: scenario === "free" ? 0 : 500,
        credits_total: 500,
        songs_generated: 0,
        images_generated: 0,
        videos_generated: 0,
        youtube_uploads: 0,
        studio_exports: 0,
        manual_exports: 0,
        usage_by_day: [],
        recent_activity: [],
      });
    }

    if (url.pathname.endsWith("/profiles") && request.method === "GET") return json(200, []);
    if (url.pathname.endsWith("/topups/packs") && request.method === "GET") {
      return json(200, {
        packs: [
          {
            id: "pack-1",
            slug: "small",
            name: "Small Pack",
            description: "",
            total_credits: 1000,
            price_cents: 500,
            display_order: 1,
            songs_equivalent: 100,
          },
        ],
      });
    }
    if (url.pathname.endsWith("/topups/history") && request.method === "GET") {
      return json(200, { purchases: [], total: 0, limit: 12, offset: 0 });
    }
    if (url.pathname.endsWith("/licenses/validate") && request.method === "GET") {
      return json(404, { error: { code: "NOT_FOUND", message: "No licence" } });
    }

    return json(404, { error: { code: "NOT_FOUND", message: "Not found" } });
  });

  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;

  const { app, window } = await launch("e2e-login-gates", {
    CAMXORA_API_BASE_URL: `http://127.0.0.1:${port}/api/v1`,
    CAMXORA_PORTAL_BASE_URL: "https://app.camxora.com",
  });
  try {
    async function signIn(email) {
      await window.getByLabel("Email", { exact: true }).fill(email);
      await window.getByLabel("Password", { exact: true }).fill("secret-password");
      await window.getByRole("button", { name: /^Sign in$/ }).click();
    }

    // Free account: signs in and lands on the in-app top-up gate with packs.
    await signIn("free@example.com");
    await window.getByTestId("plan-page").waitFor({ timeout: 10_000 });
    if (!(await window.getByText("Top up to unlock Desktop Studio").count())) {
      throw new Error("Credits gate copy missing");
    }
    if (!(await window.getByTestId("plan-pack-small").count())) {
      throw new Error("Free users must see credit packs in the app");
    }
    await window.screenshot({ path: path.join(artifacts, "topup-gate.png"), fullPage: true });

    await window.getByRole("button", { name: "Sign out" }).click();
    scenario = "unconfirmed";
    await signIn("e2e@example.com");
    await window.getByRole("heading", { name: "Confirm your email" }).waitFor({ timeout: 8_000 });

    // No channel profile is not a gate: confirming the email lands in the app.
    scenario = "onboarding";
    await window.getByRole("button", { name: /I confirmed my email/ }).click();
    await window.getByRole("heading", { name: "Dashboard" }).waitFor({ timeout: 8_000 });
    if (await window.getByRole("heading", { name: "Complete your setup" }).count()) {
      throw new Error("Onboarding gate must be removed");
    }

    await window.screenshot({ path: path.join(artifacts, "auth-gates.png"), fullPage: true });
    console.log(
      JSON.stringify({
        topUpInApp: true,
        confirmEmailGate: true,
        noProfileLandsInApp: true,
      }),
    );
  } finally {
    await app.close();
    server.close();
  }
}
