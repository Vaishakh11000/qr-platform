# VINSAK seed import mapping

The importer uses the existing product, category, version, and media services. It adds no database columns and creates only draft products and draft versions.

## Field mapping

| Seed field | Platform field | Public behavior |
|---|---|---|
| `id` | Product SKU `VSAK-<normalized id>` | Stable identifier for repeat-safe imports |
| `name` | Product name and version snapshot `name` | Displayed as product title |
| `category` | Existing category hierarchy; product points at the leaf | Category tree is created as needed |
| `summary` | Product `short_description` and version snapshot | Shown as short description |
| `description` | Version snapshot `description` | Shown in the product overview |
| `applications` | Version snapshot `applications` | Shown in applications section |
| `specifications` | Version snapshot `specifications` | Shown as supplied; empty dictionaries stay empty |
| `source_url` | Version snapshot `source_url` | Used for an official source link only when HTTPS host is VINSAK or Rotatek |
| `example` | Not imported | Illustrative content is not presented as customer evidence |
| `data_quality_note` | Not imported | Internal source caveats are not exposed publicly |

Image and PDF media are attached to the draft version through the existing media service. Original filenames are retained. The manifest preserves source URLs. Media is copied to the app's configured media storage on apply.

## Source review caveats

Review the seed record's `data_quality_note` and `MEDIA_ASSETS_README.md` before publishing. In particular, SPEED-JET and DigiJet brochure details have source mismatches, VIS 1200 brochure naming differs from the listing, and the Roll Lifter listing contains copied text. Media licensing has not been confirmed. Video references are excluded.

## Safe use

From the repository root, run a read-only preview:

```sh
DEBUG=false PYTHONPATH=backend .venv/bin/python backend/scripts/import_vinsak_seed.py
```

Applying to a development database requires its name to include `dev` or `demo`; the script also requires its exact name as confirmation. Example only, after provisioning a dedicated database:

```sh
POSTGRES_DB=qr_platform_vinsak_demo DEBUG=false PYTHONPATH=backend .venv/bin/alembic -c backend/alembic.ini upgrade head
POSTGRES_DB=qr_platform_vinsak_demo DEBUG=false PYTHONPATH=backend .venv/bin/python backend/scripts/import_vinsak_seed.py --apply --confirm-database qr_platform_vinsak_demo
```

The user later explicitly requested that this catalogue be added to the configured primary page database. For that authorized operation, the importer requires both the exact configured database name and `--allow-primary-draft-import`:

```sh
DEBUG=false PYTHONPATH=backend .venv/bin/python backend/scripts/import_vinsak_seed.py --apply --confirm-database qr_platform --allow-primary-draft-import
```

The primary-database flag is intentionally explicit. The importer still refuses a non-local database and the dedicated pytest database, creates only drafts, and never publishes products. Confirm the target identity before using it.
