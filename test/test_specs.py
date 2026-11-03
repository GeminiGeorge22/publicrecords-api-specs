import glob, json, os, pathlib, re, unittest
ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN_RE = re.compile(r"apify_api_[A-Za-z0-9]{20,}")

class Specs(unittest.TestCase):
    def test_env_has_no_token(self):
        self.assertIsNone(os.environ.get("APIFY_TOKEN"), "run tests with env -u APIFY_TOKEN")

    def test_all_valid_openapi(self):
        from openapi_spec_validator import validate
        files = glob.glob(str(ROOT / "openapi/*.json")) + glob.glob(str(ROOT / "hosted/*.json")) + [str(ROOT / "composio/publicrecords-openapi.json")]
        self.assertEqual(len(files), 31)
        for f in files:
            validate(json.load(open(f)))

    def test_no_token_or_price_anywhere(self):
        for f in glob.glob(str(ROOT / "**/*.json"), recursive=True):
            t = open(f).read()
            self.assertIsNone(TOKEN_RE.search(t), f)
            d = json.loads(t)
            info = d.get("info", {})
            self.assertNotIn("$", info.get("description", ""), f)

    def test_postman_uses_buyer_token_variable(self):
        c = json.load(open(ROOT / "postman/publicrecords-actors.postman_collection.json"))
        self.assertEqual(c["auth"]["bearer"][0]["value"], "{{apifyToken}}")
        v = {x["key"]: x["value"] for x in c["variable"]}
        self.assertEqual(v["apifyToken"], "")
        self.assertEqual(len(c["item"]), 15)

    def test_hosted_specs_have_no_security_and_point_at_gateway(self):
        for f in glob.glob(str(ROOT / "hosted/*.json")):
            d = json.load(open(f))
            self.assertNotIn("securitySchemes", d["components"])
            self.assertTrue(d["servers"][0]["url"].startswith("https://publicrecords-api-gateway."))

if __name__ == "__main__":
    unittest.main()
