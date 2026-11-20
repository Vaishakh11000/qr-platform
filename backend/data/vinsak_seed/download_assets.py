#!/usr/bin/env python3
"""Download official VINSAK product images and brochures from asset_manifest.json.
Run from a network-enabled development machine. Product-page references are not downloaded.
"""
import csv, json, re, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "asset_manifest.json"
OUT = HERE / "downloaded_assets"

def slug(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "product"

def main():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = [x for x in data["assets"] if x["asset_type"] in ("image", "brochure_pdf")]
    results = []
    for item in records:
        url = item["url"]
        filename = url.split("?", 1)[0].rstrip("/").split("/")[-1] or ("brochure.pdf" if item["asset_type"] == "brochure_pdf" else "image")
        folder = OUT / slug(item["product"])
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / filename
        status = "EXISTS" if dest.exists() and dest.stat().st_size else "PENDING"
        error = ""
        if status == "PENDING":
            try:
                req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; VINSAKAssetFetcher/1.0)"})
                with urlopen(req, timeout=30) as response:
                    content_type = response.headers.get("Content-Type", "")
                    payload = response.read()
                if not payload:
                    raise ValueError("empty response")
                if item["asset_type"] == "brochure_pdf" and not (payload.startswith(b"%PDF") or "pdf" in content_type.lower()):
                    raise ValueError(f"unexpected content type: {content_type}")
                if item["asset_type"] == "image" and not content_type.lower().startswith("image/"):
                    raise ValueError(f"unexpected content type: {content_type}")
                dest.write_bytes(payload)
                status = "DOWNLOADED"
            except Exception as exc:
                status, error = "FAILED", str(exc)
        results.append({"product": item["product"], "asset_type": item["asset_type"], "url": url, "local_path": str(dest.relative_to(HERE)) if status in ("DOWNLOADED", "EXISTS") else "", "status": status, "error": error})
        print(f"{status:10} {item['product']}: {filename}" + (f" ({error})" if error else ""))
    report = HERE / "download_report.csv"
    with report.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["product", "asset_type", "url", "local_path", "status", "error"])
        w.writeheader(); w.writerows(results)
    counts = {s: sum(r["status"] == s for r in results) for s in ("DOWNLOADED", "EXISTS", "FAILED")}
    print(f"\nSummary: {counts}. Report: {report}")
    return 1 if counts["FAILED"] else 0

if __name__ == "__main__":
    raise SystemExit(main())
