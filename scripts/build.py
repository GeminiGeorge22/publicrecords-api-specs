#!/usr/bin/env python3
"""Build OpenAPI 3.0 specs and a Postman v2.1 collection from the live public
Apify Store metadata of the publicrecords Actors. Tokenless: reads only public
GET endpoints. Never embeds a token; buyers supply their own Apify API token."""
import json, os, re, sys, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = pathlib.Path(os.environ.get("RAW_DIR", ROOT / "raw"))
KEEP = {"type","title","description","default","enum","items","minimum","maximum","minItems","maxItems","pattern","format","properties","required","nullable"}
API = "https://api.apify.com/v2"

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"publicrecords-specs-build"}), timeout=60) as r:
        return json.load(r)

def load(slug, kind):
    p = RAW / f"{kind}_{slug}.json"
    if p.exists():
        return json.loads(p.read_text())
    url = f"{API}/acts/publicrecords~{slug}" + ("/builds/default" if kind == "build" else "")
    d = get(url); RAW.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(d)); return d

def clean(s):
    if isinstance(s, list): return [clean(x) for x in s]
    if not isinstance(s, dict): return s
    out = {}
    for k, v in s.items():
        if k == "properties": out[k] = {pk: clean(pv) for pk, pv in v.items()}
        elif k == "enumTitles": out["x-enumTitles"] = v
        elif k == "required":
            if v: out[k] = v
        elif k in KEEP: out[k] = clean(v)
    if s.get("editor") == "proxy" or s.get("editor") == "json":
        out.setdefault("type", "object")
    if s.get("isSecret"): out["format"] = "password"; out["writeOnly"] = True
    return out

def actor(slug):
    a = load(slug, "act")["data"]; b = load(slug, "build")["data"]
    inp = (b.get("actorDefinition") or {}).get("input") or {"type":"object","properties":{}}
    schema = clean(inp); schema["type"] = "object"
    if inp.get("required"): schema["required"] = inp["required"]
    else: schema.pop("required", None)
    example = {}
    try: example = json.loads(a.get("exampleRunInput", {}).get("body") or "{}")
    except Exception: example = {}
    if not example:
        example = {k: v["prefill"] for k, v in (inp.get("properties") or {}).items() if "prefill" in v}
    return a, schema, example

def no_prices(text):
    assert "$" not in text, f"price-like text in public copy: {text[:80]}"
    return text

def openapi(slug, a, schema, example):
    desc = no_prices(a.get("seoDescription") or a.get("description") or "")
    store = f"https://apify.com/publicrecords/{slug}"
    return {
      "openapi": "3.0.3",
      "info": {"title": a["title"], "version": str(a.get("taggedBuilds",{}).get("latest",{}).get("buildNumber","")) or "1.0.0",
               "description": desc + f"\n\nRuns the Apify Actor publicrecords/{slug} ({store}) on the caller's own Apify account. "
                              "Authenticate with your own Apify API token (Bearer). Billing, if any, is shown on the Store page.",
               "contact": {"name": "publicrecords", "url": store}, "license": {"name": "MIT"}},
      "externalDocs": {"url": store},
      "servers": [{"url": "https://api.apify.com/v2"}],
      "security": [{"apifyToken": []}],
      "components": {
        "securitySchemes": {"apifyToken": {"type": "http", "scheme": "bearer", "description": "Your own Apify API token (Apify Console > Settings > API & Integrations)."}},
        "schemas": {"Input": schema,
                    "Run": {"type":"object","properties":{"data":{"type":"object","properties":{"id":{"type":"string"},"status":{"type":"string"},"defaultDatasetId":{"type":"string"}}}}}}},
      "paths": {
        f"/acts/publicrecords~{slug}/run-sync-get-dataset-items": {"post": {
            "operationId": "runSync_" + re.sub(r"\W", "_", slug), "summary": f"Run {a['title']} and return results",
            "description": "Starts a run, waits for it to finish (up to 300 s) and returns the dataset items.",
            "parameters": [{"name":"timeout","in":"query","schema":{"type":"integer"},"required":False},
                           {"name":"maxItems","in":"query","schema":{"type":"integer"},"required":False}],
            "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Input"}, "example": example}}},
            "responses": {"201": {"description": "Dataset items", "content": {"application/json": {"schema": {"type":"array","items":{"type":"object"}}}}}}}},
        f"/acts/publicrecords~{slug}/runs": {"post": {
            "operationId": "runAsync_" + re.sub(r"\W", "_", slug), "summary": f"Start {a['title']} (async)",
            "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Input"}, "example": example}}},
            "responses": {"201": {"description": "Run object", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Run"}}}}}}},
        "/actor-runs/{runId}": {"get": {"operationId": "getRun_" + re.sub(r"\W", "_", slug), "summary": "Get run status",
            "parameters": [{"name":"runId","in":"path","required":True,"schema":{"type":"string"}}],
            "responses": {"200": {"description": "Run object", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Run"}}}}}}},
        "/datasets/{datasetId}/items": {"get": {"operationId": "getItems_" + re.sub(r"\W", "_", slug), "summary": "Get run results",
            "parameters": [{"name":"datasetId","in":"path","required":True,"schema":{"type":"string"}},
                           {"name":"format","in":"query","schema":{"type":"string","enum":["json","csv","xlsx"]}}],
            "responses": {"200": {"description": "Items"}}}}}}

GATEWAY = "https://publicrecords-api-gateway.publicrecords.workers.dev"

def hosted(slug, a, schema, example):
    """Marketplace variant (RapidAPI, Zyla, API.market): the marketplace adds its own
    buyer key and proxy secret; no Apify token appears here or anywhere in this repo."""
    desc = no_prices(a.get("seoDescription") or a.get("description") or "")
    return {"openapi": "3.0.3",
      "info": {"title": a["title"], "version": "1.0.0", "description": desc + f"\n\nMore: https://apify.com/publicrecords/{slug}"},
      "servers": [{"url": GATEWAY}],
      "components": {"schemas": {"Input": schema}},
      "paths": {f"/v1/{slug}": {"post": {
        "operationId": "run_" + re.sub(r"\W", "_", slug), "summary": f"Run {a['title']}",
        "description": "Runs the job and returns the result rows as JSON (waits up to 280 s).",
        "parameters": [{"name":"maxItems","in":"query","required":False,"schema":{"type":"integer","maximum":1000}}],
        "requestBody": {"required": True, "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Input"}, "example": example}}},
        "responses": {"201": {"description": "Result rows", "content": {"application/json": {"schema": {"type":"array","items":{"type":"object"}}}}},
                      "400": {"description": "Bad input"}}}}}}

def postman(actors):
    items = []
    for slug, a, schema, example in actors:
        body = json.dumps(example, indent=2)
        def req(name, method, path, b=None, desc=""):
            r = {"name": name, "request": {"method": method, "header": [{"key":"Content-Type","value":"application/json"}] if b else [],
                 "url": {"raw": "{{baseUrl}}" + path, "host": ["{{baseUrl}}"], "path": [p for p in path.split("?")[0].strip("/").split("/")]},
                 "description": desc}}
            if b: r["request"]["body"] = {"mode": "raw", "raw": b, "options": {"raw": {"language": "json"}}}
            return r
        items.append({"name": a["title"], "description": no_prices(a.get("description","")) + f"\n\nStore page: https://apify.com/publicrecords/{slug}",
            "item": [req("Run and get results (sync)", "POST", f"/acts/publicrecords~{slug}/run-sync-get-dataset-items", body, "Waits up to 300 s, returns items."),
                     req("Start run (async)", "POST", f"/acts/publicrecords~{slug}/runs", body),
                     req("Get run status", "GET", "/actor-runs/{{runId}}"),
                     req("Get results", "GET", "/datasets/{{datasetId}}/items?format=json")]})
    return {"info": {"name": "publicrecords Apify Actors (Etsy, sports odds, jobs, government data)",
                     "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
                     "description": "Call the publicrecords Actors on Apify with your own Apify API token. Set the collection variable apifyToken (keep it as a secret / current value only; never commit it)."},
            "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{apifyToken}}", "type": "string"}]},
            "variable": [{"key": "baseUrl", "value": "https://api.apify.com/v2"}, {"key": "apifyToken", "value": "", "type": "secret"},
                         {"key": "runId", "value": ""}, {"key": "datasetId", "value": ""}],
            "item": items}

def main():
    slugs = [l.strip() for l in (ROOT / "actors.txt").read_text().split() if l.strip()]
    actors = []
    for s in slugs:
        a, schema, ex = actor(s); actors.append((s, a, schema, ex))
        (ROOT / "openapi" / f"{s}.json").write_text(json.dumps(openapi(s, a, schema, ex), indent=2) + "\n")
    for s_, a_, sc_, ex_ in actors:
        (ROOT / "hosted" / f"{s_}.json").write_text(json.dumps(hosted(s_, a_, sc_, ex_), indent=2) + "\n")
    (ROOT / "postman" / "publicrecords-actors.postman_collection.json").write_text(json.dumps(postman(actors), indent=2) + "\n")
    combined = {"openapi": "3.0.3",
        "info": {"title": "publicrecords Actors", "version": "1.0.0",
                 "description": "Etsy listings and shop sales, sports odds, ATS job postings, government tenders, grants, awards and council meetings, company social profiles and forecast calibration. Each operation runs one publicrecords Actor on the caller's own Apify account and returns result rows."},
        "servers": [{"url": API}], "security": [{"apifyToken": []}],
        "components": {"securitySchemes": {"apifyToken": {"type": "http", "scheme": "bearer"}}, "schemas": {}}, "paths": {}}
    for s_, a_, sc_, ex_ in actors:
        name = "Input_" + re.sub(r"\W", "_", s_)
        combined["components"]["schemas"][name] = sc_
        op = openapi(s_, a_, sc_, ex_)["paths"][f"/acts/publicrecords~{s_}/run-sync-get-dataset-items"]["post"]
        op["requestBody"]["content"]["application/json"]["schema"] = {"$ref": f"#/components/schemas/{name}"}
        op["description"] = no_prices(a_.get("description", ""))
        combined["paths"][f"/acts/publicrecords~{s_}/run-sync-get-dataset-items"] = {"post": op}
    (ROOT / "composio" / "publicrecords-openapi.json").write_text(json.dumps(combined, indent=2) + "\n")
    print(f"built {len(actors)} specs + 1 collection")

if __name__ == "__main__": main()
