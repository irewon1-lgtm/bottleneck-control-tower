import { timingSafeEqual } from "node:crypto";
import snapshot from "./snapshot.mjs";

// The stable ChatGPT Site injects this server-only credential. Anonymous origin
// requests fail closed, including aliases, downloads and API paths.
export default async request => {
  const expected = Netlify.env.get("BCT_ORIGIN_SECRET");
  const supplied = request.headers.get("X-BCT-Origin-Secret") || "";
  const suppliedBytes = Buffer.from(supplied);
  const expectedBytes = Buffer.from(expected || "");
  const valid = typeof expected === "string" && expected.length >= 64 &&
    suppliedBytes.length === expectedBytes.length &&
    timingSafeEqual(suppliedBytes, expectedBytes);
  if (!valid) return new Response("Forbidden", {status:403,
    headers:{"Cache-Control":"private, no-store", "X-Content-Type-Options":"nosniff"}});
  return snapshot.fetch(request);
};
export const config = {path:"/*", preferStatic:false};
