// Copy rules from CLAUDE.md: no em dashes, and never "AI-powered", "smart" or "magic".
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "../..");
const targets = ["web/src", "web/index.html", "backend/boardroom", "backend/migrations", "backend/tests", "backend/evals",
  "OPEN.md", "docs/epics", "render.yaml", ".github", "README.md"];
const banned = [/—/, /\bAI-powered\b/i, /\bsmart\b/i, /\bmagic\b/i];
const skip = new Set(["node_modules", "dist", "__pycache__", ".venv"]);

function* files(path) {
  const stat = statSync(path, { throwIfNoEntry: false });
  if (!stat) return;
  if (stat.isFile()) { yield path; return; }
  for (const name of readdirSync(path)) {
    if (!skip.has(name)) yield* files(join(path, name));
  }
}

let failures = 0;
for (const target of targets) {
  for (const file of files(join(root, target))) {
    if (file.endsWith("tokens.css") || file.endsWith("check-copy.mjs")) continue;
    readFileSync(file, "utf8").split("\n").forEach((line, i) => {
      if (line.includes("copy-check: allow")) return;
      for (const rule of banned) {
        if (rule.test(line)) {
          console.error(`${file.replace(root + "/", "")}:${i + 1}: ${rule} ${line.trim()}`);
          failures++;
        }
      }
    });
  }
}
if (failures) process.exit(1);
console.log("Copy check passed");
