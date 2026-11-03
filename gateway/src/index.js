// publicrecords API gateway for paid API marketplaces (RapidAPI, Zyla, API.market).
// The marketplace authenticates and bills the buyer, then forwards to this Worker with
// its own shared proxy secret. The Worker checks that secret, allows only the listed
// Actors' sync-run endpoint, and calls Apify with APIFY_TOKEN (a Worker secret, never in code).
export const ACTORS = ["etsy-search-scraper", "etsy-shop-velocity", "legistar-meetings-scraper", "company-social-profile-finder", "sports-odds-api", "eu-ted-notices-scraper", "smartrecruiters-jobs-scraper", "ashby-jobs-scraper", "lever-jobs-scraper", "greenhouse-jobs-scraper", "govcon-opportunity-feed", "grants-gov-scraper", "uk-find-a-tender-scraper", "usaspending-awards-scraper", "calibration-ledger"];
const HOST_HEADERS = { rapidapi: "x-rapidapi-proxy-secret", zyla: "x-zyla-proxy-secret", apimarket: "x-apimarket-proxy-secret" };
const MAX_ITEMS_CAP = 1000;
const TIMEOUT_CAP = 280;

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

export function whichHost(request, env) {
  for (const [host, header] of Object.entries(HOST_HEADERS)) {
    const secret = env["PROXY_SECRET_" + host.toUpperCase()];
    const got = request.headers.get(header);
    if (secret && got && timingSafeEqual(got, secret)) return host;
  }
  return null;
}

export async function handle(request, env, fetchImpl = fetch) {
  const url = new URL(request.url);
  if (url.pathname === "/health") return json(200, { ok: true, actors: ACTORS.length, configured: Boolean(env.APIFY_TOKEN) });
  const m = url.pathname.match(/^\/v1\/([a-z0-9-]+)$/);
  if (!m || !ACTORS.includes(m[1])) return json(404, { error: "unknown endpoint" });
  if (request.method !== "POST") return json(405, { error: "use POST with a JSON input body" });
  const host = whichHost(request, env);
  if (!host) return json(401, { error: "call this API through its marketplace listing" });
  if (!env.APIFY_TOKEN) return json(503, { error: "gateway not configured" });
  let input;
  try { input = await request.json(); } catch { return json(400, { error: "body must be JSON" }); }
  if (input === null || typeof input !== "object" || Array.isArray(input)) return json(400, { error: "body must be a JSON object" });
  const maxItems = Math.min(Number(url.searchParams.get("maxItems")) || MAX_ITEMS_CAP, MAX_ITEMS_CAP);
  const timeout = Math.min(Number(url.searchParams.get("timeout")) || TIMEOUT_CAP, TIMEOUT_CAP);
  const target = `https://api.apify.com/v2/acts/publicrecords~${m[1]}/run-sync-get-dataset-items?format=json&clean=true&maxItems=${maxItems}&timeout=${timeout}`;
  const upstream = await fetchImpl(target, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${env.APIFY_TOKEN}`, "x-publicrecords-channel": host },
    body: JSON.stringify(input),
  });
  const text = await upstream.text();
  return new Response(text, { status: upstream.status, headers: { "content-type": upstream.headers.get("content-type") || "application/json", "x-publicrecords-channel": host } });
}

export default { fetch: (request, env) => handle(request, env) };
