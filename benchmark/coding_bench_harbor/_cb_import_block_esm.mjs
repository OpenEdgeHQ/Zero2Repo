// Preloaded with `node --import` in the judge container. Registers the ESM
// resolve hooks with the ban configuration read from the environment. The
// CJS side is _cb_import_block.cjs (loaded with `--require`); both are
// idempotent so a harness that also inherits NODE_OPTIONS loads them once.
import { register } from "node:module";

const MARK = Symbol.for("coding_bench.import_block_esm");
if (!globalThis[MARK]) {
  globalThis[MARK] = true;
  const split = (raw) =>
    String(raw || "")
      .split(/[,:\n]/)
      .map((name) => name.trim().replace(/\/$/, ""))
      .filter(Boolean);
  const judgeBans = new Set(split(process.env.CODING_BENCH_JUDGE_BANS));
  const sideEffectRoots = [];
  if (judgeBans.has("socket") || judgeBans.has("network")) {
    sideEffectRoots.push("net", "dgram", "tls", "http", "https", "http2", "dns");
  }
  if (judgeBans.has("subprocess")) {
    sideEffectRoots.push("child_process");
  }
  register("./_cb_import_block_hooks.mjs", {
    parentURL: import.meta.url,
    data: {
      workspace: process.env.CODING_BENCH_WORKSPACE || "/app",
      banned: split(process.env.CODING_BENCH_IMPORT_BAN),
      sideEffectRoots,
    },
  });
}
