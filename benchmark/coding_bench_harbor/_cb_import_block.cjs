"use strict";

// Judge-time Node import ban, CommonJS side (loaded with `node --require`).
// The ESM side is _cb_import_block_esm.mjs. Blocks a `require` whose caller
// lives under the candidate workspace when the request's package root is
// banned, or when the resolved file sits under a banned node_modules package.

const Module = require("module");
const path = require("path");

const MARK = Symbol.for("coding_bench.import_block_cjs");
if (!globalThis[MARK]) {
  globalThis[MARK] = true;

  const workspace = path.resolve(process.env.CODING_BENCH_WORKSPACE || "/app");
  const split = (raw) =>
    String(raw || "")
      .split(/[,:\n]/)
      .map((name) => name.trim().replace(/\/$/, ""))
      .filter(Boolean);
  const banned = split(process.env.CODING_BENCH_IMPORT_BAN);
  const judgeBans = new Set(split(process.env.CODING_BENCH_JUDGE_BANS));
  const SIDE_EFFECT_ROOTS = new Set();
  if (judgeBans.has("socket") || judgeBans.has("network")) {
    for (const name of ["net", "dgram", "tls", "http", "https", "http2", "dns"]) {
      SIDE_EFFECT_ROOTS.add(name);
    }
  }
  if (judgeBans.has("subprocess")) {
    SIDE_EFFECT_ROOTS.add("child_process");
  }

  function requestRoot(request) {
    let text = String(request || "");
    if (text.startsWith("node:")) {
      text = text.slice("node:".length);
    }
    if (text.startsWith("@")) {
      const parts = text.split("/").filter(Boolean);
      return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : text;
    }
    return text.split("/")[0];
  }

  function fromWorkspace(parent) {
    const filename = parent && parent.filename ? String(parent.filename) : "";
    if (!filename) {
      return false;
    }
    const resolved = path.resolve(filename);
    return resolved === workspace || resolved.startsWith(workspace + path.sep);
  }

  function bannedPackageOfPath(filename) {
    if (!filename || typeof filename !== "string" || !path.isAbsolute(filename)) {
      return null;
    }
    const parts = filename.split(path.sep);
    for (let index = 0; index < parts.length - 1; index += 1) {
      if (parts[index] !== "node_modules") {
        continue;
      }
      const name = parts[index + 1];
      const scoped =
        name && name.startsWith("@") && index + 2 < parts.length
          ? `${name}/${parts[index + 2]}`
          : name;
      if (banned.includes(scoped) || banned.includes(name)) {
        return scoped;
      }
    }
    return null;
  }

  function banError(kind, request) {
    const err = new Error(`${kind}: workspace require of '${request}' is not allowed`);
    err.code = kind;
    return err;
  }

  function checkRequest(request, parent) {
    if (!fromWorkspace(parent)) {
      return false;
    }
    const root = requestRoot(request);
    if (root && banned.includes(root)) {
      throw banError("CODING_BENCH_IMPORT_BAN", request);
    }
    if (root && SIDE_EFFECT_ROOTS.has(root)) {
      throw banError("CODING_BENCH_JUDGE_BANS", request);
    }
    return true;
  }

  // `node:`-prefixed builtins short-circuit inside Module._load before any
  // filename resolution, so the request check has to sit on _load as well.
  const originalLoad = Module._load;
  Module._load = function patchedLoad(request, parent, isMain) {
    checkRequest(request, parent);
    return originalLoad.call(this, request, parent, isMain);
  };

  const originalResolve = Module._resolveFilename;
  Module._resolveFilename = function patchedResolve(request, parent, isMain, options) {
    const inWorkspace = checkRequest(request, parent);
    const filename = originalResolve.call(this, request, parent, isMain, options);
    if (inWorkspace && bannedPackageOfPath(filename) !== null) {
      throw banError("CODING_BENCH_IMPORT_BAN", request);
    }
    return filename;
  };
}
