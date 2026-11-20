# VINSAK Product Seed Data — Codex Integration Pack

## Purpose
Use this package as sample product content for the QR Platform customer-facing product information website and admin product-management interface.

## Source and scope
- Main listing: https://vinsak.com/products/
- Extracted: 18 November 2026
- The listing contained 14 product entries at the time captured.
- Product detail pages were opened where available; Rotatek pages are included where VINSAK's listing linked to Rotatek.
- The JSON preserves source URLs and records source-data caveats.
- `example` fields are illustrative demonstrations written for this project. They are not claims about VINSAK customers or deployments.
- Missing specifications are intentionally left empty rather than invented.
- Some source pages have inconsistent or malformed text. Review each `data_quality_note` before publishing.

## Included files
- `vinsak_products.json`: canonical structured seed data.
- `vinsak_products.csv`: flattened product overview for quick review.
- `IMPORT_MAPPING.md`: implementation mapping and safe preview/apply instructions.
- `downloaded_assets/`: downloaded official images and brochure PDFs.
- `download_report.csv`: per-asset download results.

## Suggested product record mapping
The implemented field mapping, draft-only importer, and safe preview/apply instructions are in `IMPORT_MAPPING.md`. Products use the leaf of the source category hierarchy because the current product model has one category relation. No schema migration is required.

## Important data handling
- Do not invent prices, stock, warranties, availability, certifications, lead times, customer names, performance guarantees, or regional availability.
- Do not treat illustrative examples as actual customer case studies.
- Keep technical values and units exactly as supplied by the source.
- For products with no verified specifications, show a product overview and a contact/enquiry CTA rather than fabricated specs.
- Product photos should be fetched from official VINSAK pages only after identifying the actual image assets and checking permitted use. Do not hotlink guessed image paths.
- Treat the JSON as seed/demo content, not as production data. Use the admin workflow to create/publish records and QR allocations.


## Media supplement
See `asset_manifest.json`, `asset_manifest.csv`, and `MEDIA_ASSETS_README.md` for official image URLs, brochure PDF links, and product page references. Images and PDFs have been downloaded into `downloaded_assets/`; video assets are excluded. Use the existing media/version workflow to attach assets. Licensing has not been confirmed.


## Media scope
This package includes product image and brochure PDF references only. Video assets are intentionally excluded. See `MEDIA_ASSETS_README.md` for asset counts and source caveats. The downloader can refresh files with `python backend/data/vinsak_seed/download_assets.py` from the repository root on a network-enabled machine.
