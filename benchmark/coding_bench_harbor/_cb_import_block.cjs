"use strict";

const Module = require("module");
const path = require("path");

const workspace = path.resolve(process.env.CODING_BENCH_WORKSPACE || "/app");
const banned = String(process.env.CODING_BENCH_IMPORT_BAN || "")
  .split(/[,:\n]/)
  .map((name) => name.trim().replace(/\/$/, ""))
  .filter(Boolean);
const judgeBans = new Set(
  String(process.env.CODING_BENCH_JUDGE_BANS || "")
    .split(/[,:\n]/)
    .map((name) => name.trim())
    .filter(Boolean),
);
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
  const text = String(request || "");
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

const original = Module._resolveFilename;
Module._resolveFilename = function patchedResolve(request, parent, isMain, options) {
  const root = requestRoot(request);
  if (root && fromWorkspace(parent)) {
    if (banned.includes(root)) {
      const err = new Error(
        `CODING_BENCH_IMPORT_BAN: workspace require of '${request}' is not allowed`,
      );
      err.code = "CODING_BENCH_IMPORT_BAN";
      throw err;
    }
    if (SIDE_EFFECT_ROOTS.has(root)) {
      const err = new Error(
        `CODING_BENCH_JUDGE_BANS: workspace require of '${request}' is not allowed`,
      );
      err.code = "CODING_BENCH_JUDGE_BANS";
      throw err;
    }
  }
  return original.call(this, request, parent, isMain, options);
};
