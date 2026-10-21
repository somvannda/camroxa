// Builds docs/mail-templates/gallery.html as a self-contained, tab-based preview.
//
// The email templates are full documents; this extracts each <body> and inlines
// it into a panel. No iframes (the review pane blocks them) and no JavaScript
// (pure CSS :checked tabs), so it renders in any sandbox.

const fs = require("fs");
const path = require("path");

const dir = process.argv[2];
if (!dir) {
  console.error("usage: node build-gallery.cjs <templates-dir>");
  process.exit(1);
}

const META = {
  "01": ["Welcome", "automation · signup + 30m"],
  "02": ["Signed up, never generated", "automation · no songs after 3d"],
  "03": ["Pack ladder", "campaign · active, never paid"],
  "04": ["Discount", "campaign · one code per recipient"],
  "05": ["Low balance", "automation · below user threshold"],
  "06": ["Win-back", "automation · inactive 30d"],
  "07": ["Receipt", "transactional · payment paid"],
  "08": ["Payment expired", "automation · checkout abandoned"],
  "09": ["Credits expiring", "automation · lot expires in 5d"],
  "10": ["Referral", "campaign · invite program"],
  "11": ["Stems spotlight", "campaign · feature adoption"],
  "12": ["Seasonal", "campaign · Khmer New Year"],
};

const files = fs
  .readdirSync(dir)
  .filter((f) => /^\d\d-.*\.html$/.test(f))
  .sort();

const items = files.map((file) => {
  const raw = fs.readFileSync(path.join(dir, file), "utf8");
  const bodyMatch = raw.match(/<body[^>]*>([\s\S]*)<\/body>/i);
  const prefix = file.slice(0, 2);
  const [title, meta] = META[prefix] || [file, ""];
  return {
    id: `t${prefix}`,
    panel: `p${prefix}`,
    file,
    title,
    meta,
    body: bodyMatch ? bodyMatch[1] : raw,
  };
});

const labels = items
  .map(
    (it) =>
      `<label for="${it.id}" title="${it.file}">${it.title}</label>`,
  )
  .join("\n      ");

const panels = items
  .map(
    (it) => `      <div class="panel" id="${it.panel}">
        <div class="panel-head">
          <strong>${it.title}</strong>
          <span>${it.meta} &middot; <code>${it.file}</code></span>
        </div>
        ${it.body}
      </div>`,
  )
  .join("\n");

const checked = items
  .map(
    (it) => `#${it.id}:checked ~ .tabbar label[for="${it.id}"] { background: var(--violet); border-color: var(--violet); color: #fff; }
    #${it.id}:checked ~ .panels #${it.panel} { display: block; }`,
  )
  .join("\n    ");

const inputs = items
  .map((it, i) => `<input type="radio" name="tpl" id="${it.id}"${i === 0 ? " checked" : ""} />`)
  .join("\n      ");

const html = `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CAMXORA — mail templates</title>
  <style>
    :root {
      --bg: #0a0e27;
      --panel: #0c1230;
      --border: #1f2547;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --violet: #7466f1;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 32px 20px 64px;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    header { max-width: 980px; margin: 0 auto 20px; }
    h1 { margin: 0 0 6px; font-size: 22px; }
    p.lead { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.6; max-width: 760px; }
    .hint {
      margin-top: 14px; padding: 10px 14px; border: 1px solid var(--border);
      border-radius: 8px; background: var(--panel); color: var(--muted);
      font-size: 12px; line-height: 1.6;
    }
    .hint code { color: #c4b5fd; font-family: ui-monospace, Menlo, Consolas, monospace; }

    .tabs { max-width: 980px; margin: 0 auto; }
    .tabs > input { position: absolute; opacity: 0; pointer-events: none; }

    .tabbar {
      display: flex; gap: 8px; overflow-x: auto; padding: 4px 0 18px;
      scrollbar-width: thin;
    }
    .tabbar label {
      flex: 0 0 auto; cursor: pointer; padding: 8px 14px; border-radius: 999px;
      border: 1px solid var(--border); color: var(--muted); font-size: 13px;
      white-space: nowrap; user-select: none;
    }
    .tabbar label:hover { border-color: var(--violet); color: var(--text); }

    .panels { border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
    .panel { display: none; background: #eef0f4; padding: 20px 16px 32px; }
    .panel-head {
      display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline;
      justify-content: space-between; max-width: 600px; margin: 0 auto 14px;
      color: #4b5563; font-size: 12px;
    }
    .panel-head strong { font-size: 13px; color: #111827; }
    .panel-head code { font-family: ui-monospace, Menlo, Consolas, monospace; color: #6b7280; }

    /* Center whatever the email body renders, without touching its inline styles. */
    .panel > table { margin: 0 auto; }
    .panel > div[style*="display:none"] { display: none !important; }

    ${checked}
  </style>
</head>
<body>
  <header>
    <h1>CAMXORA — mail templates</h1>
    <p class="lead">
      ${items.length} emails, one per tab. Built for real inboxes: 600px table layout, inline styles
      only, a text wordmark, and a light background that survives dark-mode clients.
    </p>
    <div class="hint">
      Placeholders such as <code>{{first_name}}</code>, <code>{{credits}}</code> and <code>{{code}}</code>
      appear literally here; at send time they are replaced per recipient.
    </div>
  </header>

  <div class="tabs">
      ${inputs}

      <nav class="tabbar">
      ${labels}
      </nav>

      <div class="panels">
${panels}
      </div>
  </div>
</body>
</html>
`;

const out = path.join(dir, "gallery.html");
fs.writeFileSync(out, html, "utf8");
console.log(`wrote ${out} (${items.length} templates, ${(html.length / 1024).toFixed(0)} KB)`);
