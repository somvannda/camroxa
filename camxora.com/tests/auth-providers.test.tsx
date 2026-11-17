import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/**
 * S02 sign-in providers. The backend is mocked: the contract under test is the
 * captured provider order, that the five unwired providers are inert and say
 * why, and that Google asks the API for the consent URL instead of pretending
 * to be a local control.
 */

const google = vi.hoisted(() => ({
  requestGoogleAuthUrl: vi.fn(),
  completeGoogleSignIn: vi.fn(),
}));

vi.mock("@/lib/google-auth", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/google-auth")>();
  return { ...actual, ...google };
});

import { AuthProviders } from "@/components/AuthProviders";
import {
  GOOGLE_NEXT_KEY,
  GOOGLE_REFERRAL_KEY,
  GOOGLE_STATE_KEY,
  GoogleUnavailableError,
} from "@/lib/google-auth";

const assign = vi.fn();

function setLocation(search = "") {
  Object.defineProperty(window, "location", {
    configurable: true,
    writable: true,
    value: {
      origin: "http://localhost:3103",
      search,
      assign,
      replace: vi.fn(),
      href: "http://localhost:3103/login",
    },
  });
}

function googleButton() {
  return screen.getByRole("button", { name: /Continue with Google/ }) as HTMLButtonElement;
}

beforeEach(() => {
  google.requestGoogleAuthUrl.mockReset();
  google.completeGoogleSignIn.mockReset();
  assign.mockReset();
  window.localStorage.clear();
  setLocation();
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("AuthProviders (S02)", () => {
  it("renders the captured providers in order and marks the five unwired ones inert", async () => {
    google.requestGoogleAuthUrl.mockResolvedValue({
      url: "https://accounts.google.com/consent",
      state: "signed-state",
    });

    render(<AuthProviders />);
    await waitFor(() => expect(googleButton().disabled).toBe(false));

    const group = screen.getByRole("group", { name: "Continue with a provider" });
    const buttons = Array.from(group.querySelectorAll("button"));
    expect(buttons.map((node) => node.textContent?.trim())).toEqual([
      "Continue with Google",
      "Continue with Apple",
      "Continue with Phone",
      "Discord",
      "Facebook",
      "Microsoft",
    ]);

    const expectedTitles: Record<string, string> = {
      apple: "Apple sign-in is not configured in this build",
      phone: "Phone sign-in is not configured in this build",
      discord: "Discord sign-in is not configured in this build",
      facebook: "Facebook sign-in is not configured in this build",
      microsoft: "Microsoft sign-in is not configured in this build",
    };

    for (const [id, title] of Object.entries(expectedTitles)) {
      const node = group.querySelector<HTMLButtonElement>(`[data-provider="${id}"]`);
      expect(node, id).not.toBeNull();
      expect(node!.disabled, id).toBe(true);
      expect(node!.getAttribute("aria-disabled"), id).toBe("true");
      expect(node!.getAttribute("title"), id).toBe(title);
      expect(node!.getAttribute("data-configured"), id).toBe("false");
    }

    // The "or" divider sits between the three large buttons and the compact row.
    expect(group.querySelector(".auth-divider")?.textContent).toBe("or");
  });

  it("asks the API for the consent URL and remembers state, next and referral", async () => {
    const user = userEvent.setup();
    setLocation("?next=/studio&ref=fr1end");
    google.requestGoogleAuthUrl
      .mockResolvedValueOnce({
        url: "https://accounts.google.com/probe",
        state: "probe",
      })
      .mockResolvedValueOnce({
        url: "https://accounts.google.com/consent",
        state: "signed-state",
      });

    render(<AuthProviders />);
    await waitFor(() => expect(googleButton().disabled).toBe(false));

    await user.click(googleButton());

    expect(google.requestGoogleAuthUrl).toHaveBeenLastCalledWith(
      "http://localhost:3103/auth/callback"
    );
    await waitFor(() =>
      expect(assign).toHaveBeenCalledWith("https://accounts.google.com/consent")
    );
    expect(window.localStorage.getItem(GOOGLE_STATE_KEY)).toBe("signed-state");
    expect(window.localStorage.getItem(GOOGLE_NEXT_KEY)).toBe("/studio");
    expect(window.localStorage.getItem(GOOGLE_REFERRAL_KEY)).toBe("FR1END");
  });

  it("disables Google with a visible reason when the API reports it is not configured", async () => {
    google.requestGoogleAuthUrl.mockRejectedValue(
      new GoogleUnavailableError("Google sign-in is not configured.", "not-configured")
    );

    render(<AuthProviders />);

    const notice = await screen.findByRole("status");
    expect(notice.textContent).toContain("not configured in this build");

    const button = googleButton();
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.getAttribute("title")).toBe(
      "Google sign-in is not configured in this build"
    );
  });

  it("distinguishes an origin the API has not allowlisted", async () => {
    google.requestGoogleAuthUrl.mockRejectedValue(
      new GoogleUnavailableError(
        "Google sign-in is not enabled for this application.",
        "origin-not-allowed"
      )
    );

    render(<AuthProviders />);

    expect((await screen.findByRole("status")).textContent).toContain(
      "not enabled for this address"
    );
    expect(googleButton().getAttribute("title")).toBe(
      "Google sign-in is not enabled for this address"
    );
  });
});
