import assert from "node:assert/strict";
import { test } from "node:test";
import {
  buildClickToken,
  buildOpenToken,
  buildUnsubToken,
  escapeHtml,
  htmlToText,
  instrumentHtml,
  isSafeRedirect,
  parseClickToken,
  parseOpenToken,
  parseUnsubToken,
  renderVars,
  unpack,
} from "../src/mailTracking.js";

const SECRET = "test-tracking-secret";
const SEND_ID = "3f1c9d7e-0000-4000-8000-abcdefabcdef";
const USER_ID = "9a8b7c6d-1111-4222-8333-444455556666";

test("open token round-trips and is bound to its send id", () => {
  const token = buildOpenToken(SECRET, SEND_ID);
  const parsed = parseOpenToken(SECRET, token);
  assert.ok(parsed);
  assert.equal(parsed?.sendId, SEND_ID);
});

test("a token signed with another secret is rejected", () => {
  const token = buildOpenToken("other-secret", SEND_ID);
  assert.equal(unpack(SECRET, token), null);
  assert.equal(parseOpenToken(SECRET, token), null);
});

test("a tampered payload is rejected", () => {
  const token = buildOpenToken(SECRET, SEND_ID);
  const [body, sig] = token.split(".");
  // Re-encode a different payload while keeping the original signature.
  const forged = `${Buffer.from(`o1.${USER_ID}`, "utf8").toString("base64url")}.${sig}`;
  assert.notEqual(forged, token);
  assert.equal(unpack(SECRET, forged), null);
  assert.equal(body.length > 0 && sig.length > 0, true);
});

test("purpose prefixes stop cross-use of tokens", () => {
  const unsub = buildUnsubToken(SECRET, USER_ID);
  // An unsubscribe token must not be usable as an open or click token.
  assert.equal(parseOpenToken(SECRET, unsub), null);
  assert.equal(parseClickToken(SECRET, unsub), null);
  assert.ok(parseUnsubToken(SECRET, unsub));

  const open = buildOpenToken(SECRET, SEND_ID);
  assert.equal(parseUnsubToken(SECRET, open), null);
});

test("click token carries the destination and rejects tampering", () => {
  const url = "https://music.camxora.com/pricing?pack=20";
  const token = buildClickToken(SECRET, SEND_ID, url);
  const parsed = parseClickToken(SECRET, token);
  assert.ok(parsed);
  assert.equal(parsed?.url, url);
  assert.equal(parsed?.sendId, SEND_ID);

  // Swapping the destination inside the payload invalidates the signature, so
  // the redirect endpoint cannot be turned into an open redirect.
  const evil = buildClickToken(SECRET, SEND_ID, "https://evil.example/steal");
  const [, evilSig] = evil.split(".");
  const forged = `${Buffer.from(`c1.${SEND_ID}.${Buffer.from("https://evil.example", "utf8").toString("base64url")}`, "utf8").toString("base64url")}.${evilSig}`;
  assert.equal(parseClickToken(SECRET, forged), null);
});

test("non-http destinations are not redirectable", () => {
  assert.equal(isSafeRedirect("https://music.camxora.com"), true);
  assert.equal(isSafeRedirect("http://localhost:4001/x"), true);
  assert.equal(isSafeRedirect("javascript:alert(1)"), false);
  assert.equal(isSafeRedirect("data:text/html,hi"), false);
  assert.equal(isSafeRedirect("/relative"), false);
  assert.equal(isSafeRedirect("not a url"), false);
});

test("instrumentHtml wraps real links, skips unsafe ones and appends the pixel", () => {
  const html = `<html><body>
    <a href="https://music.camxora.com/pricing">Pricing</a>
    <a href="mailto:hi@camxora.com">Mail us</a>
    <a href="#top">Top</a>
    <a href="{{app_url}}">Placeholder</a>
    <a href="javascript:alert(1)">Bad</a>
  </body></html>`;

  const result = instrumentHtml(html, {
    clickUrl: (target) => `https://track.test/c?u=${encodeURIComponent(target)}`,
    openUrl: "https://track.test/o.gif",
  });

  assert.equal(result.links, 1, "only the https link is wrapped");
  assert.match(result.html, /https:\/\/track\.test\/c\?u=/);
  assert.match(result.html, /mailto:hi@camxora\.com/);
  assert.match(result.html, /href="#top"/);
  assert.match(result.html, /\{\{app_url\}\}/);
  assert.match(result.html, /javascript:alert\(1\)/);
  assert.match(result.html, /https:\/\/track\.test\/o\.gif/);
  // Pixel sits before </body>.
  assert.ok(result.html.indexOf("track.test/o.gif") < result.html.indexOf("</body>"));
});

test("instrumentHtml still appends the pixel when there is no body tag", () => {
  const result = instrumentHtml('<a href="https://music.camxora.com">Go</a>', {
    clickUrl: (t) => `https://track.test/c?u=${encodeURIComponent(t)}`,
    openUrl: "https://track.test/o.gif",
  });
  assert.equal(result.links, 1);
  assert.ok(result.html.endsWith('src="https://track.test/o.gif" width="1" height="1" alt="" style="display:block;width:1px;height:1px;border:0;outline:none;" />'));
});

test("renderVars substitutes known variables and escapes html", () => {
  const out = renderVars("<p>{{name}} — {{credits}} — {{unknown}}</p>", {
    name: "<script>x</script>",
    credits: 2300,
  });
  assert.equal(out, "<p>&lt;script&gt;x&lt;/script&gt; — 2300 — {{unknown}}</p>");
});

test("renderVars can skip escaping for plain-text bodies", () => {
  assert.equal(renderVars("Hi {{name}}", { name: "A & B" }, false), "Hi A & B");
});

test("escapeHtml covers the five dangerous characters", () => {
  assert.equal(escapeHtml(`<>&"'`), "&lt;&gt;&amp;&quot;&#39;");
});

test("htmlToText strips markup and keeps paragraph breaks", () => {
  const text = htmlToText(
    "<html><head><style>p{color:red}</style></head><body><p>Hello</p><p>2,300 credits</p></body></html>",
  );
  assert.equal(text, "Hello\n2,300 credits");
});
