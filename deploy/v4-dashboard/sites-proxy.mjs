// One-time Sites gateway update. Deploy only after origin protection and
// Git-linked production deployment have been verified. All routes retain the
// existing owner-private Sites dispatch authentication boundary.
export default { async fetch(request, env) {
  const path = new URL(request.url).pathname;
  if (!["GET", "HEAD"].includes(request.method)) return new Response("Read only",{status:405});
  const allowed = ["/","/index.html","/app.js","/style.css","/api/dashboard","/api/export","/api/health"].includes(path) || /^\/api\/evidence\/[a-f0-9]{64}$/.test(path);
  if (!allowed) return new Response("Not found",{status:404});
  const origin = env.BCT_ORIGIN_URL;
  const secret = env.BCT_ORIGIN_SECRET;
  if (origin !== "https://bct-v4-ci-origin.netlify.app" || typeof secret !== "string" || secret.length < 64) {
    return new Response("Deployment origin is not configured",{status:503,headers:{"Cache-Control":"no-store"}});
  }
  try {
    // Do not forward visitor cookies, identities, arbitrary headers or query
    // strings. Never follow redirects with the origin credential.
    const r = await fetch(origin + path,{method:request.method,redirect:"manual",
      headers:{"X-BCT-Origin-Secret":secret},signal:AbortSignal.timeout(20000)});
    if (r.status >= 300 && r.status < 400) return new Response("Origin redirect rejected",{status:502});
    const headers = new Headers(r.headers);
    headers.set("Cache-Control","private, no-store");
    headers.delete("Set-Cookie"); headers.delete("Location");
    return new Response(r.body,{status:r.status,headers});
  } catch { return new Response("Deployment origin unavailable",{status:503,headers:{"Cache-Control":"no-store"}}); }
}};
