#!/usr/bin/env python3
"""Import the VINSAK sample catalogue through the platform service layer.

The default is a read-only dry run. Applying requires a local, separately named
development/demo database and an exact database-name confirmation. Products and
versions are created as drafts and are never published by this script.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import Product, ProductCategory
from app.schemas.category import CategoryCreate
from app.schemas.product import ProductCreate
from app.schemas.product_version import ProductVersionCreate
from app.services.category_service import create_category, list_categories
from app.services.media_service import (
    create_product_media,
    list_product_media,
    resolve_storage_path,
)
from app.services.media_storage import store_upload
from app.services.product_service import create_product, list_products
from app.services.product_version_service import (
    create_product_version,
    list_product_versions,
)


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "vinsak_seed"
PRODUCTS_PATH = DATA_DIR / "vinsak_products.json"
ASSETS_PATH = DATA_DIR / "asset_manifest.json"
DOWNLOAD_REPORT_PATH = DATA_DIR / "download_report.csv"
ASSET_DIR = DATA_DIR / "downloaded_assets"


def stable_sku(external_id: str) -> str:
    """Return a deterministic platform SKU for the source record ID."""
    suffix = re.sub(r"[^A-Za-z0-9]+", "-", external_id).strip("-").upper()
    return f"VSAK-{suffix}"


def build_product_snapshot(source: dict) -> dict:
    """Map only customer-safe source fields to the existing version format."""
    return {
        "name": source["name"],
        "short_description": source["summary"],
        "description": source["description"],
        "applications": list(source.get("applications") or []),
        "specifications": dict(source.get("specifications") or {}),
        "source_url": source["source_url"],
    }


def asset_product_id(asset_label: str, products: list[dict]) -> str | None:
    normalized_label = re.sub(r"[^a-z0-9]+", "", asset_label.lower())
    matches = []
    for product in products:
        normalized_name = re.sub(r"[^a-z0-9]+", "", product["name"].lower())
        normalized_id = re.sub(r"[^a-z0-9]+", "", product["id"].lower())
        if (
            normalized_label == normalized_name
            or normalized_label == normalized_id
            or normalized_label in normalized_name
        ):
            matches.append(product["id"])
    return matches[0] if len(matches) == 1 else None


def load_seed() -> tuple[list[dict], list[dict]]:
    products = json.loads(PRODUCTS_PATH.read_text(encoding="utf-8"))["products"]
    manifest = json.loads(ASSETS_PATH.read_text(encoding="utf-8"))["assets"]
    return products, manifest


def media_filename(asset: dict) -> str:
    return asset["url"].split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]


def media_file_path(asset: dict) -> Path:
    folder = re.sub(r"[^a-z0-9]+", "_", asset["product"].lower()).strip("_") or "product"
    return ASSET_DIR / folder / media_filename(asset)


def downloaded_asset_paths(assets: list[dict]) -> list[tuple[dict, Path]]:
    return [(asset, media_file_path(asset)) for asset in assets]


def report_download_status() -> dict[str, int]:
    if not DOWNLOAD_REPORT_PATH.exists():
        return {"DOWNLOADED": 0, "EXISTS": 0, "FAILED": 0, "MISSING": 0}
    with DOWNLOAD_REPORT_PATH.open(newline="", encoding="utf-8") as report_file:
        rows = list(csv.DictReader(report_file))
    counts = {key: sum(row.get("status") == key for row in rows) for key in ("DOWNLOADED", "EXISTS", "FAILED")}
    counts["MISSING"] = sum(
        not (DATA_DIR / row.get("local_path", "")).is_file()
        for row in rows
        if row.get("status") in {"DOWNLOADED", "EXISTS"}
    )
    return counts


def validate_apply_target(confirmed_database: str, allow_primary_drafts: bool) -> None:
    host = settings.postgres_host.strip("[]").lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing import: the configured database host is not local.")

    database = settings.postgres_db
    if database == settings.test_postgres_db:
        raise SystemExit("Refusing import into the shared pytest database; use a separate development database.")

    lower_name = database.lower()
    if not allow_primary_drafts and not any(tag in lower_name for tag in ("dev", "demo")):
        raise SystemExit("Refusing import: database name must include 'dev' or 'demo'.")

    if confirmed_database != database:
        raise SystemExit(
            f"Confirm the exact target by passing --confirm-database {database}."
        )


def all_products(db) -> list[Product]:
    products: list[Product] = []
    offset = 0
    while True:
        page = list_products(db, offset=offset, limit=100)
        products.extend(page)
        if len(page) < 100:
            return products
        offset += len(page)


def all_categories(db) -> list[ProductCategory]:
    categories: list[ProductCategory] = []
    offset = 0
    while True:
        page = list_categories(db, offset=offset, limit=100, is_active=True)
        categories.extend(page)
        if len(page) < 100:
            return categories
        offset += len(page)


def ensure_category_path(db, source_path: list[str], categories: list[ProductCategory]) -> ProductCategory | None:
    parent_id = None
    leaf = None
    for name in source_path:
        found = next(
            (
                category
                for category in categories
                if category.parent_id == parent_id and category.name.casefold() == name.casefold()
            ),
            None,
        )
        if found is None:
            found = create_category(
                db,
                CategoryCreate(name=name, parent_id=parent_id),
            )
            categories.append(found)
        parent_id = found.id
        leaf = found
    return leaf


def version_matches_seed(version, source: dict) -> bool:
    snapshot = version.content_snapshot
    return (
        version.status == "DRAFT"
        and snapshot.get("name") == source["name"]
        and snapshot.get("source_url") == source["source_url"]
    )


def attach_assets(db, product: Product, version, assets: list[dict], seed_products: list[dict]) -> tuple[int, int]:
    existing = list_product_media(db, product.id, version_id=version.id)
    existing_names = {item.original_filename.casefold() for item in existing}
    uploaded = skipped = 0

    for asset, path in downloaded_asset_paths(assets):
        if not path.is_file():
            print(f"MISSING  {product.sku}: {path.relative_to(DATA_DIR)}")
            skipped += 1
            continue

        filename = media_filename(asset)
        if filename.casefold() in existing_names:
            skipped += 1
            continue

        media_type = "DOCUMENT" if asset["asset_type"] == "brochure_pdf" else "IMAGE"
        media_file = path.open("rb")
        upload = UploadFile(file=media_file, filename=filename)
        stored = None
        try:
            stored = asyncio.run(store_upload(upload, media_type))
            create_product_media(
                db,
                product.id,
                media_type,
                stored,
                version_id=version.id,
                display_order=len(existing) + uploaded,
                alt_text=(f"{product.name} product image" if media_type == "IMAGE" else None),
            )
            existing_names.add(filename.casefold())
            uploaded += 1
            print(f"MEDIA    {product.sku}: {filename}")
        except Exception:
            if stored is not None:
                try:
                    resolve_storage_path(stored.storage_key).unlink(missing_ok=True)
                except (OSError, ValueError):
                    pass
            raise
        finally:
            media_file.close()

    return uploaded, skipped


def run_import() -> dict[str, int]:
    seed_products, manifest = load_seed()
    assets_by_seed_id: dict[str, list[dict]] = {item["id"]: [] for item in seed_products}
    for asset in manifest:
        seed_id = asset_product_id(asset["product"], seed_products)
        if seed_id is None:
            raise ValueError(f"Asset label does not match one seed product: {asset['product']}")
        if asset.get("asset_type") in {"image", "brochure_pdf"}:
            assets_by_seed_id[seed_id].append(asset)

    stats = {"products_created": 0, "versions_created": 0, "assets_uploaded": 0, "assets_skipped": 0, "conflicts_skipped": 0}
    with SessionLocal() as db:
        products = all_products(db)
        categories = all_categories(db)
        by_sku = {product.sku.casefold(): product for product in products}
        by_name = {product.name.casefold(): product for product in products}

        for source in seed_products:
            sku = stable_sku(source["id"])
            product = by_sku.get(sku.casefold())
            if product is not None and product.name != source["name"]:
                print(f"CONFLICT {sku}: existing product name differs; leaving it unchanged.")
                stats["conflicts_skipped"] += 1
                continue

            name_conflict = by_name.get(source["name"].casefold())
            if product is None and name_conflict is not None:
                print(f"CONFLICT {source['name']}: product exists under another SKU; leaving it unchanged.")
                stats["conflicts_skipped"] += 1
                continue

            if product is None:
                leaf_category = ensure_category_path(db, source.get("category") or [], categories)
                product = create_product(
                    db,
                    ProductCreate(
                        sku=sku,
                        name=source["name"],
                        category_id=leaf_category.id if leaf_category else None,
                        short_description=source.get("summary"),
                    ),
                )
                products.append(product)
                by_sku[sku.casefold()] = product
                by_name[product.name.casefold()] = product
                stats["products_created"] += 1
                print(f"PRODUCT  {sku}: draft created")

            versions = list_product_versions(db, product.id)
            version = next((item for item in versions if version_matches_seed(item, source)), None)
            if version is None:
                if versions or product.status != "DRAFT":
                    print(f"SKIPPED  {sku}: existing content is not an empty draft; it was not changed.")
                    stats["conflicts_skipped"] += 1
                    continue
                version = create_product_version(
                    db,
                    product.id,
                    ProductVersionCreate(content_snapshot=build_product_snapshot(source)),
                )
                stats["versions_created"] += 1
                print(f"VERSION  {sku}: draft version {version.version_number} created")

            uploaded, skipped = attach_assets(db, product, version, assets_by_seed_id[source["id"]], seed_products)
            stats["assets_uploaded"] += uploaded
            stats["assets_skipped"] += skipped

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the draft import. Default is a read-only dry run.")
    parser.add_argument("--confirm-database", default="", help="Exact configured database name required with --apply.")
    parser.add_argument(
        "--allow-primary-draft-import",
        action="store_true",
        help="Explicitly allow draft-only writes to the configured primary database.",
    )
    args = parser.parse_args()

    products, assets = load_seed()
    print(f"VINSAK seed: {len(products)} products, {len(assets)} media references.")
    print(f"Downloaded assets: {report_download_status()}.")
    if not args.apply:
        print("Dry run only. No database or media storage was changed.")
        print("Mapping: VSAK-<source id> SKU; category path hierarchy; summary/description/applications/specifications in a draft version; source_url retained; example and data_quality_note excluded.")
        return 0

    validate_apply_target(args.confirm_database, args.allow_primary_draft_import)
    stats = run_import()
    print(f"Import complete (drafts only): {stats}")
    print("No products were published.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit("Import interrupted. Re-run safely; the importer resumes drafts and skips existing media files.")
