# VINSAK image and brochure assets

The asset manifest contains official image URLs, direct brochure PDF URLs, and selected official product-page references used to identify additional still images. Videos were excluded.

## Downloaded files

- 44 image files
- 8 brochure PDFs
- 7 product page references (not downloadable media)
- 52 downloaded image/PDF files total; see `download_report.csv` for per-file status and `asset_manifest.csv` for original URLs and filenames

Files are stored under `downloaded_assets/<product>/`. `download_assets.py` can refresh the local copies. Use the platform media upload workflow rather than hotlinking assets.

## Product data caveats

- SPEED-JET: brochure naming/specification content appears to refer to VIS 1200 I UV/AQ. Confirm the correct model association before publishing.
- DigiJet: brochure specifications differ from the product-page values in the product seed. Keep both source records distinct and flag for confirmation; do not silently merge.
- VIS 1200: brochure title says VIS 1200-K while the listing says VIS 1200. Confirm variant association.
- Roll Lifter: brochure identifies VRL-S-200; listing description appears copied from VIS 720-i.
- Some source galleries include variants or accessory images. Review each selected image before publishing.
- Permission/licensing for the intended use has not been confirmed. Preserve source URLs and original filenames.

## Integration

Use the existing product media upload and versioning workflow. The import script attaches images and PDFs to draft versions only. Review source caveats and licensing, then publish through the admin workflow. No videos are included.
