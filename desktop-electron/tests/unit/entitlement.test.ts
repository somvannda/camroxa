import { describe, expect, it } from "vitest";
import {
  DESKTOP_PLAN_REQUIRED_CODE,
  isPaidCatalogPlanName,
  resolveBootstrapDestination,
  userCanUseDesktopStudio,
} from "../../electron/services/entitlement";

describe("desktop entitlement", () => {
  it("always allows admins", () => {
    expect(
      userCanUseDesktopStudio({
        role: "admin",
        desktop_access: false,
        onboarding_paid: false,
        plan_name: "Free",
      }),
    ).toBe(true);
  });

  it("trusts desktop_access when the API provides it", () => {
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: true, plan_name: "Free" }),
    ).toBe(true);
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: false, onboarding_paid: true }),
    ).toBe(false);
  });

  it("falls back to onboarding_paid and paid plan names when desktop_access is null", () => {
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: null, onboarding_paid: true }),
    ).toBe(true);
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: null, plan_name: "Creator" }),
    ).toBe(true);
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: null, plan_name: "starter" }),
    ).toBe(true);
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: null, plan_name: "Studio-Pro" }),
    ).toBe(true);
  });

  it("rejects free plans and missing flags", () => {
    expect(userCanUseDesktopStudio({ role: "user" })).toBe(false);
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: null, plan_name: "Free" }),
    ).toBe(false);
    expect(
      userCanUseDesktopStudio({ role: "user", desktop_access: null, plan_name: "Free Creator" }),
    ).toBe(false);
  });

  it("matches paid catalog plan names like the Python client", () => {
    expect(isPaidCatalogPlanName("Starter")).toBe(true);
    expect(isPaidCatalogPlanName("creator-plan")).toBe(true);
    expect(isPaidCatalogPlanName("STUDIO")).toBe(true);
    expect(isPaidCatalogPlanName("Free")).toBe(false);
    expect(isPaidCatalogPlanName("")).toBe(false);
    expect(isPaidCatalogPlanName(undefined)).toBe(false);
  });

  it("exposes the paid-gate error code", () => {
    expect(DESKTOP_PLAN_REQUIRED_CODE).toBe("DESKTOP_PLAN_REQUIRED");
  });
});

describe("bootstrap routing", () => {
  const paid = { role: "user", desktop_access: true };

  it("sends unentitled accounts to the in-app top-up gate", () => {
    expect(
      resolveBootstrapDestination({
        role: "user",
        desktop_access: false,
        email_confirmed: true,
        channel_profile_count: 3,
      }),
    ).toEqual({ destination: "topup" });
  });

  it("checks email confirmation before the credits gate", () => {
    expect(
      resolveBootstrapDestination({
        role: "user",
        desktop_access: false,
        email_confirmed: false,
        channel_profile_count: 0,
      }),
    ).toEqual({ destination: "confirm_email" });
  });

  it("checks email confirmation before channel profiles", () => {
    expect(
      resolveBootstrapDestination({
        ...paid,
        email_confirmed: false,
        channel_profile_count: 0,
      }),
    ).toEqual({ destination: "confirm_email" });
  });

  it("opens the shell when the account has no channel profiles", () => {
    expect(
      resolveBootstrapDestination({
        ...paid,
        email_confirmed: true,
        channel_profile_count: 0,
      }),
    ).toEqual({ destination: "app" });
  });

  it("opens the shell for entitled, confirmed accounts with profiles", () => {
    expect(
      resolveBootstrapDestination({
        ...paid,
        email_confirmed: true,
        channel_profile_count: 2,
      }),
    ).toEqual({ destination: "app" });
  });
});
