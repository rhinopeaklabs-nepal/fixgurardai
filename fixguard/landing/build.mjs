// Builds the marketing site: each page in src/pages is a body fragment with
// a small header comment; it is stamped into src/layout.html and written to
// dist/<path>/index.html so the URLs the old site used keep working.
//
// No dependencies. The asset query string is a content hash, so nginx can
// cache /assets/ for a year and a deploy still reaches every browser.

import { createHash } from "node:crypto";
import { cpSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const src = join(root, "src");
const out = join(root, "dist");

rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });
cpSync(join(src, "assets"), join(out, "assets"), { recursive: true });

const hash = (file) =>
  createHash("sha256").update(readFileSync(join(src, "assets", file))).digest("hex").slice(0, 10);
const versions = { css: hash("site.css"), js: hash("site.js") };

const layout = readFileSync(join(src, "layout.html"), "utf8");
const SITE = "https://fixguardai.online";

for (const file of readdirSync(join(src, "pages"))) {
  if (!file.endsWith(".html")) continue;
  const body = readFileSync(join(src, "pages", file), "utf8");
  const head = body.match(/^<!--([\s\S]*?)-->/);
  if (!head) throw new Error(`${file}: missing header comment`);
  const meta = Object.fromEntries(
    head[1]
      .trim()
      .split("\n")
      .map((l) => l.split(/:\s(.+)/).map((x) => x.trim()))
      .filter(([k]) => k),
  );
  for (const key of ["title", "description", "path"]) {
    if (!meta[key]) throw new Error(`${file}: header needs ${key}`);
  }

  let html = layout
    .replaceAll("{{title}}", meta.title)
    .replaceAll("{{description}}", meta.description)
    .replaceAll("{{canonical}}", SITE + (meta.path === "/" ? "/" : meta.path))
    .replaceAll("{{css}}", versions.css)
    .replaceAll("{{js}}", versions.js)
    .replace("{{content}}", body.slice(head[0].length).trim());

  // Mark the current page in the nav and the footer.
  html = html.replaceAll(`data-nav="${meta.path}"`, `data-nav="${meta.path}" aria-current="page"`);

  const target =
    meta.path === "/404" ? join(out, "404.html") : join(out, meta.path, "index.html");
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, html);
  console.log("built", meta.path);
}
