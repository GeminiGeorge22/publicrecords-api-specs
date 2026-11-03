# publicrecords API specs

OpenAPI 3.0 specs, a Postman collection and a Composio toolkit package for the
[publicrecords Actors on Apify](https://apify.com/publicrecords): Etsy listings and shop sales,
sports odds from Kambi-powered books, new job postings from Ashby, Greenhouse, Lever and
SmartRecruiters, US/EU/UK government tenders, grants and awards, city council meetings,
company social profiles and forecast calibration.

| Folder | What it is | Auth |
|---|---|---|
| `openapi/` | One spec per Actor against `api.apify.com/v2` | Your own Apify API token (Bearer) |
| `postman/` | Postman v2.1 collection, one folder per Actor | Collection variable `apifyToken` (empty; set your own) |
| `composio/` | Combined spec + toolkit metadata for Composio | Your own Apify API token |
| `hosted/` | Marketplace variant (RapidAPI, Zyla, API.market) via `gateway/` | The marketplace's own key |
| `gateway/` | Cloudflare Worker behind the marketplace listings | Marketplace proxy secret; Apify token as a Worker secret |

Everything is rebuilt from the public, tokenless Store endpoints:

```
python3 scripts/build.py
env -u APIFY_TOKEN python -m unittest discover -s test -v
```

A daily workflow (`drift.yml`) rebuilds from the live input schemas and fails on any difference.

Never commit an Apify token. Tests fail if `APIFY_TOKEN` is set in the environment.

## Postman

Import `postman/publicrecords-actors.postman_collection.json`, set `apifyToken` as the
current value (not the initial value), then run "Run and get results (sync)" in any folder.

License: MIT
