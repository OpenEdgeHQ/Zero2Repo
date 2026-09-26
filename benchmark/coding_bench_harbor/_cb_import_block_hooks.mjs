// Module customization hooks for the judge-time Node import ban (ESM side).
//
// Registered by _cb_import_block_esm.mjs through module.register(); runs on
// the hooks thread, so configuration arrives via initialize(data) rather than
// process.env. Blocks an `import` whose importer lives under the candidate
// workspace when the specifier's package root is banned, or when the resolved
// file sits under a banned node_modules package (deep-path imports).
import path from "node:path";
import { fileURLToPath } from "node:url";

let workspace = "/app";
let banned = [];
let sideEffectRoots = new Set();

export async function initialize(data) {
  workspace = path.resolve(String((data && data.workspace) || "/app"));
  banned = Array.isArray(data && data.banned) ? data.banned.slice() : [];
  sideEffectRoots = new Set(
    Array.isArray(data && data.sideEffectRoots) ? data.sideEffectRoots : [],
  );
}

function requestRoot(specifier) {
  let text = String(specifier || "");
  if (text.startsWith("node:")) {
    text = text.slice("node:".length);
  }
  if (text.startsWith("@")) {
    const parts = text.split("/").filter(Boolean);
    return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : text;
  }
  return text.split("/")[0];
}

function fileUrlToPath(url) {
  if (!url || !String(url).startsWith("file:")) {
    return null;
  }
  try {
    return path.resolve(fileURLToPath(url));
  } catch {
    return null;
  }
}

function fromWorkspace(parentURL) {
  const resolved = fileUrlToPath(parentURL);
  if (resolved === null) {
    return false;
  }
  return resolved === workspace || resolved.startsWith(workspace + path.sep);
}

function bannedPackageOfPath(filePath) {
  if (!filePath) {
    return null;
  }
  const parts = filePath.split(path.sep);
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

function banError(kind, specifier) {
  const err = new Error(
    `${kind}: workspace import of '${specifier}' is not allowed`,
  );
  err.code = kind;
  return err;
}

export async function resolve(specifier, context, nextResolve) {
  const importerInWorkspace = fromWorkspace(context && context.parentURL);
  if (importerInWorkspace) {
    const root = requestRoot(specifier);
    if (root && banned.includes(root)) {
      throw banError("CODING_BENCH_IMPORT_BAN", specifier);
    }
    if (root && sideEffectRoots.has(root)) {
      throw banError("CODING_BENCH_JUDGE_BANS", specifier);
    }
  }
  const result = await nextResolve(specifier, context);
  if (importerInWorkspace) {
    const hit = bannedPackageOfPath(fileUrlToPath(result && result.url));
    if (hit !== null) {
      throw banError("CODING_BENCH_IMPORT_BAN", specifier);
    }
  }
  return result;
}
