import test from "node:test";
import assert from "node:assert/strict";
import { handle, ACTORS } from "../src/index.js";

test("test env carries no real Apify token", () => {
  assert.equal(process.env.APIFY_TOKEN, undefined, "run tests with env -u APIFY_TOKEN");
});

const FAKE = "fake-token-for-tests";
const env = { APIFY_TOKEN: FAKE, PROXY_SECRET_RAPIDAPI: "rs", PROXY_SECRET_ZYLA: "zs" };
const req = (path, { method = "POST", headers = {}, body = "{}" } = {}) =>
  new Request("https://gw.example" + path, { method, headers, body: method === "POST" ? body : undefined });

test("lists all 15 Actors", () => assert.equal(ACTORS.length, 15));

test("rejects calls without the marketplace secret", async () => {
  let called = false;
  const r = await handle(req("/v1/sports-odds-api"), env, async () => { called = true; });
  assert.equal(r.status, 401); assert.equal(called, false);
});

test("rejects a wrong secret", async () => {
  const r = await handle(req("/v1/sports-odds-api", { headers: { "x-rapidapi-proxy-secret": "nope" } }), env, async () => assert.fail());
  assert.equal(r.status, 401);
});

test("rejects unknown Actors and other Apify paths", async () => {
  for (const p of ["/v1/someone-else", "/v2/acts/x/runs", "/v1/../users/me", "/actor-runs/abc"]) {
    const r = await handle(req(p, { headers: { "x-rapidapi-proxy-secret": "rs" } }), env, async () => assert.fail());
    assert.equal(r.status, 404, p);
  }
});

test("503 when the Apify token is not configured", async () => {
  const r = await handle(req("/v1/sports-odds-api", { headers: { "x-rapidapi-proxy-secret": "rs" } }), { PROXY_SECRET_RAPIDAPI: "rs" }, async () => assert.fail());
  assert.equal(r.status, 503);
});

test("forwards to the sync endpoint with caps and the token in a header only", async () => {
  let seen;
  const fake = async (url, init) => { seen = { url, init }; return new Response("[]", { status: 201, headers: { "content-type": "application/json" } }); };
  const r = await handle(req("/v1/ashby-jobs-scraper?maxItems=99999&timeout=9999", { headers: { "x-zyla-proxy-secret": "zs" }, body: '{"companies":["ramp"]}' }), env, fake);
  assert.equal(r.status, 201);
  assert.match(seen.url, /^https:\/\/api\.apify\.com\/v2\/acts\/publicrecords~ashby-jobs-scraper\/run-sync-get-dataset-items\?/);
  assert.match(seen.url, /maxItems=1000/); assert.match(seen.url, /timeout=280/);
  assert.ok(!seen.url.includes(FAKE));
  assert.equal(seen.init.headers.authorization, "Bearer " + FAKE);
  assert.equal(seen.init.headers["x-publicrecords-channel"], "zyla");
  assert.equal(seen.init.body, '{"companies":["ramp"]}');
});

test("rejects non-object bodies and GET", async () => {
  const h = { "x-rapidapi-proxy-secret": "rs" };
  assert.equal((await handle(req("/v1/sports-odds-api", { headers: h, body: "[1]" }), env, async () => assert.fail())).status, 400);
  assert.equal((await handle(req("/v1/sports-odds-api", { headers: h, body: "nope" }), env, async () => assert.fail())).status, 400);
  assert.equal((await handle(req("/v1/sports-odds-api", { method: "GET", headers: h }), env, async () => assert.fail())).status, 405);
});

test("health shows configured state without secrets", async () => {
  const r = await handle(req("/health", { method: "GET" }), env);
  const t = await r.text(); assert.ok(!t.includes(FAKE)); assert.equal(JSON.parse(t).configured, true);
});
