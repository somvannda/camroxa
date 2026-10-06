import { test } from "node:test";
import assert from "node:assert/strict";
import {
  PROTECTED_PREFIXES,
  PUBLIC_PROTECTED_ROUTES,
  isProtectedPath,
  isPublicProtectedRoute,
} from "../src/routeAuth.js";

test("protected prefixes cover every authenticated surface", () => {
  for (const p of [
    "/me/generate",
    "/me/download",
    "/v1/credits",
    "/api/v1/generate",
    "/api/file-stream-upload",
    "/admin/users",
    "/payments/chmaba/create",
  ]) {
    assert.equal(isProtectedPath(p), true, `${p} should be protected`);
  }
});

test("public routes are not treated as protected", () => {
  for (const p of [
    "/health",
    "/auth/login",
    "/auth/google/callback",
    "/settings",
    "/pricing",
    "/models",
    "/openapi.json",
    "/llms.txt",
    "/updates",
  ]) {
    assert.equal(isProtectedPath(p), false, `${p} should be public`);
  }
});

test("the only public protected-prefix route is the HMAC webhook", () => {
  assert.deepEqual([...PUBLIC_PROTECTED_ROUTES], ["POST /payments/chmaba/webhook"]);
  assert.equal(isPublicProtectedRoute("POST", "/payments/chmaba/webhook"), true);
  assert.equal(isPublicProtectedRoute("GET", "/payments/chmaba/webhook"), false);
  assert.equal(isPublicProtectedRoute("POST", "/payments/chmaba/create"), false);
});

test("the protected-prefix list is non-empty and stable", () => {
  assert.deepEqual([...PROTECTED_PREFIXES], ["/me/", "/v1/", "/api/", "/admin/", "/payments/"]);
});
