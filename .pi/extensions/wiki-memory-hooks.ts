/**
 * Wiki Memory Dream Agent Lifecycle Hooks
 *
 * Replaces the legacy Claude Code plugin.json hooks (SessionStart, PreCompact,
 * SessionEnd) with Pi-native TypeScript extension hooks.
 *
 * Events:
 *   session_start           → Log that hooks are active
 *   resources_discover      → Register wiki skill path for auto-discovery
 *   before_agent_start      → Inject wiki index as context message
 *   session_before_compact  → Run dream agent (sleep-time compute before compaction)
 *   session_shutdown        → Run dream agent (capture session knowledge on exit)
 *
 * Install:
 *   cp this-file ~/.pi/agent/extensions/wiki-memory-hooks.ts   (global)
 *   or place at .pi/extensions/wiki-memory-hooks.ts             (project-local)
 *   then run /reload in pi or restart pi.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { existsSync, readFileSync, readdirSync } from "fs";
import { dirname, join } from "path";
import { homedir } from "os";
import { fileURLToPath } from "url";

const EXTENSION_DIR = dirname(fileURLToPath(import.meta.url));
const ROOT_MARKER = join(EXTENSION_DIR, "wiki-memory-root.json");

function resolveProjectRoot(): string {
  if (process.env.WIKI_MEMORY_ROOT && existsSync(join(process.env.WIKI_MEMORY_ROOT, "dream", "dream_agent.py"))) {
    return process.env.WIKI_MEMORY_ROOT;
  }

  if (existsSync(ROOT_MARKER)) {
    try {
      const marker = JSON.parse(readFileSync(ROOT_MARKER, "utf-8"));
      if (typeof marker.root === "string" && existsSync(join(marker.root, "dream", "dream_agent.py"))) {
        return marker.root;
      }
    } catch {
      // invalid marker; continue to conventional fallbacks
    }
  }

  const candidates = [
    join(homedir(), "code", "wiki-memory"),
    join(process.cwd(), "wiki-memory"),
    process.cwd(),
  ];

  for (const candidate of candidates) {
    if (existsSync(join(candidate, "dream", "dream_agent.py"))) {
      return candidate;
    }
  }

  return process.env.WIKI_MEMORY_ROOT ?? process.cwd();
}

const PROJECT_ROOT = resolveProjectRoot();
const DREAM_AGENT = join(PROJECT_ROOT, "dream", "dream_agent.py");
const SKILL_DIR = join(PROJECT_ROOT, "skill");
const AI_WIKI = process.env.AI_WIKI ?? join(homedir(), "ai-wiki");
const WIKI_INDEX = join(AI_WIKI, "pages", "index.md");
const WIKI_SKILLS = join(AI_WIKI, ".meta", "skills");

export default function (pi: ExtensionAPI) {
  // ─── session_start: Log that hooks are active ──────────────────
  pi.on("session_start", async (_event, ctx) => {
    if (ctx.hasUI) {
      ctx.ui.notify("🧠 Wiki-memory dream hooks active", "info");
    }
  });

  // ─── resources_discover: Register wiki skill path ──────────────
  pi.on("resources_discover", async () => ({
    skillPaths: [SKILL_DIR],
  }));

  // ─── before_agent_start: Inject wiki index into context ────────
  pi.on("before_agent_start", async () => {
    const parts: string[] = [];

    if (existsSync(WIKI_INDEX)) {
      const content = readFileSync(WIKI_INDEX, "utf-8")
        .split("\n")
        .slice(0, 60)
        .join("\n");
      parts.push(`<wiki-index>\n${content}\n</wiki-index>`);
    }

    if (existsSync(WIKI_SKILLS)) {
      try {
        const files = readdirSync(WIKI_SKILLS).filter((f: string) => f.endsWith(".md"));
        for (const file of files.slice(0, 5)) {
          const content = readFileSync(join(WIKI_SKILLS, file), "utf-8")
            .split("\n")
            .slice(0, 40)
            .join("\n");
          parts.push(`<wiki-skill file="${file}">\n${content}\n</wiki-skill>`);
        }
      } catch {
        // skill directory might not exist yet
      }
    }

    if (parts.length === 0) return;

    return {
      message: {
        customType: "wiki-memory-context",
        content: parts.join("\n\n"),
        display: false,
      },
    };
  });

  // ─── session_before_compact: Sleep-time compute ────────────────
  pi.on("session_before_compact", async (_event, ctx) => {
    if (!existsSync(DREAM_AGENT)) return;

    if (ctx.hasUI) {
      ctx.ui.notify("🧠 Running dream agent pre-compact...", "info");
    }

    try {
      const result = await pi.exec("python3", [DREAM_AGENT, "--quiet", "--idle", "60"], {
        timeout: 65_000,
        env: {
          ...process.env,
          WIKI_MEMORY_ROOT: PROJECT_ROOT,
          AI_WIKI,
        },
      });
      if (result.code !== 0 && ctx.hasUI) {
        ctx.ui.notify(`⚠️ Dream agent: ${result.stderr?.slice(0, 200) ?? "unknown error"}`, "warning");
      }
    } catch {
      if (ctx.hasUI) {
        ctx.ui.notify("⚠️ Dream agent: process error", "warning");
      }
    }
  });

  // ─── session_shutdown: Fire-and-forget dream cycle ─────────────
  pi.on("session_shutdown", async (_event, ctx) => {
    if (!existsSync(DREAM_AGENT)) return;

    const { spawn } = await import("child_process");
    const child = spawn("python3", [DREAM_AGENT, "--quiet"], {
      detached: true,
      stdio: "ignore",
      env: {
        ...process.env,
        WIKI_MEMORY_ROOT: PROJECT_ROOT,
        AI_WIKI,
      },
    });
    child.unref();

    if (ctx.hasUI) {
      ctx.ui.notify("🧠 Dream agent dispatched (fire-and-forget)", "info");
    }
  });
}
