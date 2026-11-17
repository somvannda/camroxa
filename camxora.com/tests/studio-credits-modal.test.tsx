import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  AUTO_RELOAD_STORAGE_KEY,
  AUTO_RELOAD_SUPPORTED,
  CreateCreditsModal,
  creditsUsedPercent,
  formatPackPrice,
  packAt,
  readAutoReloadPreference,
  writeAutoReloadPreference,
} from "@/components/CreateCreditsModal";
import type { CreditPack } from "@/lib/pricing-api";
import { fetchCreditPacks, purchaseTopup } from "@/lib/pricing-api";

vi.mock("@/lib/pricing-api", () => ({
  fetchCreditPacks: vi.fn(),
  purchaseTopup: vi.fn(),
}));

const fetchPacks = vi.mocked(fetchCreditPacks);
const buyPack = vi.mocked(purchaseTopup);

// The ladder `127_web_music_plans_v2.py` seeds: $5 / $10 / $30.
const PACKS: CreditPack[] = [
  {
    id: "pack-small",
    slug: "small",
    name: "Small Pack",
    description: "",
    total_credits: 700,
    price_cents: 500,
    display_order: 1,
    songs_equivalent: 140,
  },
  {
    id: "pack-medium",
    slug: "medium",
    name: "Medium Pack",
    description: "",
    total_credits: 1840,
    price_cents: 1000,
    display_order: 2,
    songs_equivalent: 368,
  },
  {
    id: "pack-large",
    slug: "large",
    name: "Large Pack",
    description: "",
    total_credits: 7920,
    price_cents: 3000,
    display_order: 3,
    songs_equivalent: 1584,
  },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.sessionStorage.clear();
});

function renderModal(overrides: Partial<Parameters<typeof CreateCreditsModal>[0]> = {}) {
  const onClose = vi.fn();
  render(
    <CreateCreditsModal
      open
      creditsRemaining={0}
      monthlyAllowance={1000}
      onClose={onClose}
      {...overrides}
    />
  );
  return { onClose };
}

describe("credits modal helpers", () => {
  it("formats pack prices the way the capture shows the amount", () => {
    expect(formatPackPrice(500)).toBe("$5");
    expect(formatPackPrice(600)).toBe("$6");
    expect(formatPackPrice(1050)).toBe("$10.50");
    expect(formatPackPrice(0)).toBe("$0");
  });

  it("measures the monthly grant, and reads 100% when the balance is empty", () => {
    expect(creditsUsedPercent(0, 1000)).toBe(100);
    expect(creditsUsedPercent(250, 1000)).toBe(75);
    expect(creditsUsedPercent(2000, 1000)).toBe(0);
    expect(creditsUsedPercent(null, null)).toBe(100);
    expect(creditsUsedPercent(5, 0)).toBe(100);
  });

  it("clamps the stepper to the packs the API returned", () => {
    expect(packAt(PACKS, 0)?.slug).toBe("small");
    expect(packAt(PACKS, 2)?.slug).toBe("large");
    expect(packAt(PACKS, 9)?.slug).toBe("large");
    expect(packAt(PACKS, -4)?.slug).toBe("small");
    expect(packAt([], 0)).toBeNull();
  });

  it("round-trips the session auto-reload preference", () => {
    const store = new Map<string, string>();
    const storage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
    };
    expect(readAutoReloadPreference(storage)).toBe(false);
    writeAutoReloadPreference(storage, true);
    expect(store.get(AUTO_RELOAD_STORAGE_KEY)).toBe("1");
    expect(readAutoReloadPreference(storage)).toBe(true);
    writeAutoReloadPreference(storage, false);
    expect(readAutoReloadPreference(storage)).toBe(false);
    expect(readAutoReloadPreference(null)).toBe(false);
  });
});

describe("out-of-credits modal", () => {
  it("renders the captured anatomy from the pricing API", async () => {
    fetchPacks.mockResolvedValue(PACKS);
    renderModal();

    expect(
      screen.getByRole("dialog", { name: "You're out of credits" }).getAttribute("aria-modal")
    ).toBe("true");
    expect(screen.getByText("Monthly credits used")).toBeTruthy();
    expect(screen.getByText("100%")).toBeTruthy();
    expect(
      screen
        .getByRole("progressbar", { name: "Monthly credits used" })
        .getAttribute("aria-valuenow")
    ).toBe("100");
    expect(screen.getByText(/Get back to creating/)).toBeTruthy();

    await screen.findByText("$5");
    expect(screen.getByText("Auto-reload amount")).toBeTruthy();
    expect(screen.getByTestId("credits-modal-amount").textContent).toBe("$5");
    expect(screen.getByText("700 credits · about 140 songs")).toBeTruthy();
    expect(screen.getByText("Better value than one-time credit packs")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Buy credits" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Not now" })).toBeTruthy();
  });

  it("steps through the ladder and stops at both ends", async () => {
    fetchPacks.mockResolvedValue(PACKS);
    renderModal();
    const amount = await screen.findByTestId("credits-modal-amount");
    const down = screen.getByRole("button", { name: "Decrease amount" });
    const up = screen.getByRole("button", { name: "Increase amount" });

    expect(amount.textContent).toBe("$5");
    expect((down as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(up);
    expect(amount.textContent).toBe("$10");
    fireEvent.click(up);
    expect(amount.textContent).toBe("$30");
    expect((up as HTMLButtonElement).disabled).toBe(true);

    fireEvent.click(down);
    expect(amount.textContent).toBe("$10");
  });

  it("renders auto-reload as a disabled, explained switch when it is not configured", async () => {
    fetchPacks.mockResolvedValue(PACKS);
    renderModal();
    await screen.findByText("$5");

    const toggle = screen.getByRole("switch", { name: "Turn on auto-reload" });
    expect(AUTO_RELOAD_SUPPORTED).toBe(false);
    expect((toggle as HTMLButtonElement).disabled).toBe(true);
    expect(toggle.getAttribute("title")).toBe(
      "Auto-reload isn't configured for this account yet"
    );
    expect(screen.getByText(/Auto-reload isn't configured yet/)).toBeTruthy();
  });

  it("moves focus to the title and closes on Escape", async () => {
    fetchPacks.mockResolvedValue(PACKS);
    const { onClose } = renderModal();

    const heading = screen.getByRole("heading", { name: "You're out of credits" });
    await waitFor(() => expect(document.activeElement).toBe(heading));

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on Not now and on the close button", async () => {
    fetchPacks.mockResolvedValue(PACKS);
    const { onClose } = renderModal();
    await screen.findByText("$5");

    fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("starts the existing checkout for the selected pack", async () => {
    fetchPacks.mockResolvedValue(PACKS);
    buyPack.mockResolvedValue({
      checkoutUrl: "https://pay.chmaba.com/checkout/abc",
      paymentId: "pay_123",
    });
    renderModal();
    await screen.findByText("$5");

    fireEvent.click(screen.getByRole("button", { name: "Increase amount" }));
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Buy credits" }));

    await waitFor(() => expect(buyPack).toHaveBeenCalledWith("medium"));
    expect(window.sessionStorage.getItem("camxora:checkout-payment")).toBe("pay_123");
  });

  it("surfaces a pricing failure instead of inventing an amount", async () => {
    fetchPacks.mockRejectedValue(new Error("Could not load credit packs (503)"));
    renderModal();

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Could not load credit packs (503)"
    );
    expect(screen.queryByTestId("credits-modal-amount")).toBeNull();
    expect(
      (screen.getByRole("button", { name: "Buy credits" }) as HTMLButtonElement).disabled
    ).toBe(true);
  });
});
