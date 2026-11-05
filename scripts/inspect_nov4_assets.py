import requests

url_aws = "https://earth-search.aws.element84.com/v1/search"
payload = {
    "collections": ["sentinel-2-l2a"],
    "ids": ["S2B_43QEB_20261104_0_L2A", "S2B_43QFB_20261104_0_L2A"]
}
r = requests.post(url_aws, json=payload, timeout=25)
if r.ok:
    feats = r.json().get("features", [])
    print(f"Fetched {len(feats)} features")
    for f in feats:
        print("\nFeature ID:", f["id"])
        print("DateTime:", f["properties"]["datetime"])
        print("Cloud Cover:", f["properties"]["eo:cloud_cover"])
        assets = f.get("assets", {})
        print("Available bands:", list(assets.keys()))
        for b in ["red", "green", "blue", "nir", "nir08", "rededge1", "rededge2", "rededge3", "swir16", "swir22", "scl", "visual"]:
            if b in assets:
                href = assets[b]["href"]
                print(f"  Band {b}: {href[:80]}...")
