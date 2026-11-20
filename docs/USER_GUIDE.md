# QR Platform user guide

This guide describes how catalogue records, QR codes, regions, location policies, forms, customer scans, analytics, and audit history fit together. The same guide is available inside the administrator console under **Need assistance? → View documentation**.

## How a customer scan reaches a product page

```text
Product → published version
   ↑
QR code ← active allocation → assigned region
   ↓
Customer opens QR URL → location policy → product page → assigned forms
                                           ↓
                              stored scan event and audit/report data
```

The QR code must be active and allocated, and the product must have a published version. A draft product version is not customer-visible. When a customer scans, the server resolves the current allocation and applicable location policy. Successful access shows the published product snapshot. A later product publish changes the current version used by new scans; existing scan records retain the version that was shown at scan time.

## Product catalogue and category hierarchy

### Categories

Categories can have parent and child categories. Use this tree to organize catalogue items. A product has one category assignment; a parent category does not automatically assign its category to products in child categories. Category hierarchy is separate from the region hierarchy used for scan policy and form assignment.

Deactivating a category keeps the category and existing product relationships in the database. Inactive categories remain visible in the catalogue for existing products, but they cannot be selected for new products or new category assignments. Existing products can still be edited without changing their inactive category. To move a product, assign an active category or clear the category first.

### Products and versions

Each product has an identity (name, SKU, category, description) and a sequence of content versions:

```text
Product
├── Version 1 (draft → published → retired when replaced)
├── Version 2 (draft → published → current)
└── Product media attached to a draft version or the product
```

Create and edit a draft, review its preview and media, then publish it. Publishing makes that version current and retires the previous published version. Published versions are immutable; make a new version to change public content. Product media can be images, videos, or PDF documents, with file-type and size limits enforced by the API.

The customer site shows published content only. If a QR scan says the product is not available, check that the code is allocated and active, the product is not archived, and a version has been published.

## QR batches and allocations

```text
QR batch
├── QR code 1 ── current allocation → product + region
├── QR code 2 ── current allocation → product + region
└── …
```

Generate codes in **QR Batches**. If you choose a product and region during generation, the generated codes receive that allocation. Otherwise, use **Allocate / reassign** on the batch. Batch operations affect active codes in that batch; allocation history is retained for audit and scan history.

An allocation connects one QR code to one product and one region at a time. Reassigning changes the current target for future scans, while earlier scans keep their recorded product, version, and region. The batch page reports whether active codes are unallocated, consistently allocated, mixed, or retired.

Use **Share / export** to download:

- A printable PDF with numbered labels and token suffixes.
- A PNG ZIP or SVG ZIP with individual QR images and a CSV manifest.

The manifest identifies each image and includes its scan URL plus its current product and region when allocated. Only active codes are included. QR URLs are access links; share the exported archive only with people who should have the codes. Retire a batch to revoke its active codes.

## Region hierarchy and geographic boundaries

Regions form a parent-child tree, for example:

```text
Country
└── State
    └── District
        └── Sales territory
```

Set a parent in **Regions** to place a region in the hierarchy. This relationship controls policy and form cascading. A region may also have a geographic boundary: a valid two-dimensional WGS84 MultiPolygon. The boundary is geographic data; setting a parent does not draw, merge, or validate the child's shape against the parent's shape.

During GPS classification, the platform finds active regions whose boundaries cover the reported point and selects the deepest matching region in the hierarchy. If multiple matching regions at that deepest level are siblings, the result is ambiguous and reported as unknown. A location only receives a geographic classification when the GPS accuracy value is present and no worse than 500 metres.

When a QR code is allocated to a region, a detected region that is that region or one of its descendants counts as a match. A point outside the assigned region's subtree is a mismatch; no unambiguous boundary match is unknown. Review parent relationships and boundaries together when a classification is unexpected.

## Location policies and precedence

A location policy defines whether location is mandatory or skippable, and the location method. Assign it at one of three scopes:

- **Region:** applies to that region and its descendants.
- **Product:** applies to scans for that product.
- **Global:** applies to all scans if no more specific policy applies.

For a scan, the QR allocation supplies the product and assigned region. Resolution order is:

1. The closest active matching region policy: the allocated region, then its parent, then successive ancestors.
2. The product policy.
3. The global policy.

An inactive policy is ignored. A region policy takes precedence over product and global policies. Priority is stored on an assignment, but there can be only one assignment for an exact global, product, or region target at a time, so priority normally does not change which rule wins. Use the region tree and scope precedence to express which location should win; priority does not override them.

### Location methods

- **GPS required:** the customer browser must provide GPS when the policy requests location.
- **GPS with IP fallback:** GPS is attempted first, but this deployment does not have an IP geolocation provider configured. If GPS is unavailable, the fallback cannot determine a location.
- **IP only:** also requires an IP geolocation provider, which is not configured in this deployment. A private Wi-Fi address cannot identify a geographic region.

For local phone testing, open the HTTPS LAN site, trust its local certificate authority on the phone, enable the phone's location service, and allow location for the site. Reloading cannot clear a browser's saved denial; change the site permission in browser settings and start a new scan. A skippable policy permits access without location when location is skipped or unavailable; it does not establish a region match.

## Forms and assignment hierarchy

Forms are versioned separately from products:

```text
Form → draft version → published version → scope assignment
```

Create a form, define fields, publish a version, then assign that published version as required or optional. You can create a new version without changing already published versions. Replacing an assignment for the same form and exact scope deactivates the previous assignment and preserves its history.

For each form, public scans choose the closest applicable assignment using region, then product, then global precedence. A region assignment cascades down to descendant regions. Distinct forms from different applicable scopes can all appear on the product page; the hierarchy selects one effective assignment per form. Required or optional labels describe the expected response collection; the product page remains visible, and required field validation applies when a form is submitted. Admin submissions are paginated, and CSV export covers all pages.

## Scan analytics and audit history

**Scan Analytics** filters stored events by UTC date range, product, QR code, region, scan outcome, and location outcome. Date ranges are limited to 366 days. Summary totals and daily trends cover all matching events; product, region, and QR breakdowns show up to 100 rows each. CSV exports state the applied filters and the breakdown limit.

**Audit Logs** records administrative changes with actor, action, entity, timestamps, and before/after values where available. Filters and CSV export include all matching pages. Audit date filters and exported timestamps use UTC. System-generated events may have no administrator account.

## Administration and integration status

In **Administration and settings**, set the Public QR address to the address reachable by customers; newly generated QR URLs and exports use it. Changing this address does not change already printed QR codes. Confirm the address, HTTPS certificate, DNS, and phone access before distributing a batch.

The platform's status cards describe real integration state. IP geolocation and outbound email/push delivery are not connected in this release. Production deployment also needs external DNS, TLS certificate issuance/renewal, a backup and restore process, and monitoring. See [Operations](OPERATIONS.md) before deployment.

## Common checks

| Symptom | Check |
| --- | --- |
| QR says it has no product | Check the batch's current allocation and confirm the code is active. |
| Product page is unavailable | Confirm the product is not archived and has a published version. |
| Phone cannot open a localhost QR | Set the Public QR address to a host address the phone can reach on the same Wi-Fi, or a real public HTTPS hostname. |
| Browser location remains denied | Change this site's location permission in browser settings, then start a new scan. |
| GPS/IP fallback does not work | GPS can work over trusted HTTPS with permission; IP geolocation is not configured. |
| Region check is unknown | Check boundary coverage, GPS accuracy, active status, and overlapping sibling boundaries at the same hierarchy depth. |
| New product cannot use a category | Confirm the category is active; inactive categories remain attached to existing products only. |
