import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";

export const DATA = path.resolve(process.env.VN_DATA_DIR || "./data");
export function newId() { return crypto.randomUUID(); }
export function validId(id) {
  if (typeof id !== "string" || !/^[a-zA-Z0-9-]{1,100}$/.test(id)) {
    throw new Error("Invalid identifier");
  }
  return id;
}
export async function init() {
  await fs.mkdir(path.join(DATA, "sessions"), { recursive: true });
  await fs.mkdir(path.join(DATA, "stories"), { recursive: true });
}
