
-- =========================================================
-- QR PLATFORM - INITIAL DATABASE SCHEMA
-- PostgreSQL 17 + PostGIS 3.5
-- Schema: app
-- =========================================================

SET search_path TO app, public;

-- ---------------------------------------------------------
-- 1. ADMINISTRATION
-- ---------------------------------------------------------

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(80) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id UUID,
    old_values JSONB,
    new_values JSONB,
    ip_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_audit_admin_time
ON audit_logs(admin_id, created_at DESC);

CREATE INDEX ix_audit_entity
ON audit_logs(entity_type, entity_id, created_at DESC);


-- ---------------------------------------------------------
-- 2. PRODUCT CATALOGUE
-- ---------------------------------------------------------

CREATE TABLE product_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    parent_id UUID REFERENCES product_categories(id) ON DELETE RESTRICT,
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE INDEX ix_categories_parent
ON product_categories(parent_id);

CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sku VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    category_id UUID REFERENCES product_categories(id) ON DELETE RESTRICT,
    short_description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    current_version_id UUID,
    created_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (status IN ('DRAFT', 'ACTIVE', 'ARCHIVED'))
);

CREATE INDEX ix_products_category ON products(category_id);
CREATE INDEX ix_products_status ON products(status);

CREATE TABLE product_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL,
    content_snapshot JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    created_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    published_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,

    UNIQUE(product_id, version_number),
    UNIQUE(id, product_id),

    CHECK (version_number > 0),
    CHECK (status IN ('DRAFT', 'PUBLISHED', 'RETIRED')),
    CHECK (
        (status = 'DRAFT' AND published_at IS NULL)
        OR
        (status IN ('PUBLISHED', 'RETIRED') AND published_at IS NOT NULL)
    )
);

ALTER TABLE products
ADD CONSTRAINT fk_product_current_version
FOREIGN KEY (current_version_id, id)
REFERENCES product_versions(id, product_id)
ON DELETE RESTRICT;

CREATE INDEX ix_product_versions_product
ON product_versions(product_id, version_number DESC);

CREATE TABLE product_media (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    version_id UUID,
    media_type VARCHAR(20) NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    original_filename VARCHAR(255) NOT NULL,
    mime_type VARCHAR(150) NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    checksum_sha256 CHAR(64),
    display_order INTEGER NOT NULL DEFAULT 0,
    alt_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    FOREIGN KEY (version_id, product_id)
        REFERENCES product_versions(id, product_id)
        ON DELETE RESTRICT,

    CHECK (media_type IN ('IMAGE', 'VIDEO', 'DOCUMENT')),
    CHECK (file_size_bytes >= 0)
);

CREATE INDEX ix_product_media_order
ON product_media(product_id, display_order);


-- ---------------------------------------------------------
-- 3. GEOGRAPHY
-- ---------------------------------------------------------

CREATE TABLE regions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    region_code VARCHAR(50) NOT NULL UNIQUE,
    region_type VARCHAR(50) NOT NULL,
    parent_id UUID REFERENCES regions(id) ON DELETE RESTRICT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (parent_id IS NULL OR parent_id <> id)
);

CREATE INDEX ix_regions_parent ON regions(parent_id);
CREATE INDEX ix_regions_type ON regions(region_type);

CREATE TABLE region_boundaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    region_id UUID NOT NULL UNIQUE REFERENCES regions(id) ON DELETE RESTRICT,
    boundary GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_region_boundary_geom
ON region_boundaries USING GIST(boundary);


-- ---------------------------------------------------------
-- 4. QR BATCHES AND QR CODES
-- ---------------------------------------------------------

CREATE TABLE qr_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_code VARCHAR(100) NOT NULL UNIQUE,
    requested_product_id UUID REFERENCES products(id) ON DELETE RESTRICT,
    requested_region_id UUID REFERENCES regions(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL,
    generation_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,

    CHECK (quantity > 0),
    CHECK (generation_status IN ('PENDING', 'GENERATED', 'FAILED'))
);

CREATE TABLE qr_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES qr_batches(id) ON DELETE RESTRICT,
    token VARCHAR(128) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deactivated_at TIMESTAMPTZ,

    CHECK (status IN ('ACTIVE', 'INACTIVE', 'REVOKED')),
    CHECK (
        (status = 'ACTIVE' AND deactivated_at IS NULL)
        OR
        (status <> 'ACTIVE' AND deactivated_at IS NOT NULL)
    )
);

CREATE INDEX ix_qr_batch ON qr_codes(batch_id);
CREATE INDEX ix_qr_status ON qr_codes(status);


-- ---------------------------------------------------------
-- 5. QR ALLOCATION HISTORY
-- ---------------------------------------------------------

CREATE TABLE qr_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qr_code_id UUID NOT NULL REFERENCES qr_codes(id) ON DELETE RESTRICT,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    region_id UUID NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    assigned_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    reason TEXT,

    UNIQUE(id, qr_code_id, product_id, region_id),

    CHECK (ended_at IS NULL OR ended_at > assigned_at),

    EXCLUDE USING GIST (
        qr_code_id WITH =,
        tstzrange(assigned_at, ended_at, '[)') WITH &&
    )
);

CREATE UNIQUE INDEX uq_qr_active_allocation
ON qr_allocations(qr_code_id)
WHERE ended_at IS NULL;

CREATE INDEX ix_allocation_product
ON qr_allocations(product_id, assigned_at DESC);

CREATE INDEX ix_allocation_region
ON qr_allocations(region_id, assigned_at DESC);

CREATE INDEX ix_allocation_history
ON qr_allocations(qr_code_id, assigned_at DESC);


-- ---------------------------------------------------------
-- 6. LOCATION POLICIES
-- ---------------------------------------------------------

CREATE TABLE location_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    requirement VARCHAR(20) NOT NULL,
    method VARCHAR(30) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (requirement IN ('MANDATORY', 'SKIPPABLE')),
    CHECK (method IN ('GPS_REQUIRED', 'GPS_IP_FALLBACK', 'IP_ONLY'))
);

CREATE TABLE location_policy_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES location_policies(id) ON DELETE RESTRICT,
    scope_type VARCHAR(20) NOT NULL,
    product_id UUID REFERENCES products(id) ON DELETE RESTRICT,
    region_id UUID REFERENCES regions(id) ON DELETE RESTRICT,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (
        (scope_type = 'GLOBAL' AND product_id IS NULL AND region_id IS NULL)
        OR
        (scope_type = 'PRODUCT' AND product_id IS NOT NULL AND region_id IS NULL)
        OR
        (scope_type = 'REGION' AND region_id IS NOT NULL AND product_id IS NULL)
    ),

    CHECK (priority >= 0)
);

CREATE UNIQUE INDEX uq_location_global
ON location_policy_assignments(scope_type)
WHERE scope_type = 'GLOBAL';

CREATE UNIQUE INDEX uq_location_product
ON location_policy_assignments(product_id)
WHERE scope_type = 'PRODUCT';

CREATE UNIQUE INDEX uq_location_region
ON location_policy_assignments(region_id)
WHERE scope_type = 'REGION';

CREATE INDEX ix_location_policy
ON location_policy_assignments(policy_id);


-- ---------------------------------------------------------
-- 7. SCAN EVENTS
-- ---------------------------------------------------------

CREATE TABLE scan_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qr_code_id UUID NOT NULL REFERENCES qr_codes(id) ON DELETE RESTRICT,

    allocation_id UUID,
    product_id UUID,
    region_id UUID,

    product_version_id UUID,
    location_policy_id UUID REFERENCES location_policies(id) ON DELETE SET NULL,

    location_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    result_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',

    user_agent TEXT,
    ip_hash TEXT,
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,

    FOREIGN KEY (allocation_id, qr_code_id, product_id, region_id)
        REFERENCES qr_allocations(id, qr_code_id, product_id, region_id)
        ON DELETE RESTRICT,

    FOREIGN KEY (product_version_id, product_id)
        REFERENCES product_versions(id, product_id)
        ON DELETE RESTRICT,

    CHECK (
        (allocation_id IS NULL AND product_id IS NULL AND region_id IS NULL)
        OR
        (allocation_id IS NOT NULL AND product_id IS NOT NULL AND region_id IS NOT NULL)
    ),

    CHECK (
        location_status IN (
            'PENDING', 'GPS', 'IP_DERIVED', 'SKIPPED',
            'DENIED', 'UNAVAILABLE', 'IP_LOOKUP_FAILED', 'UNCERTAIN'
        )
    ),

    CHECK (
        result_status IN ('PENDING', 'ALLOWED', 'BLOCKED', 'ERROR')
    )
);

CREATE INDEX ix_scan_qr_time
ON scan_events(qr_code_id, scanned_at DESC);

CREATE INDEX ix_scan_product_time
ON scan_events(product_id, scanned_at DESC);

CREATE INDEX ix_scan_region_time
ON scan_events(region_id, scanned_at DESC);

CREATE INDEX ix_scan_time
ON scan_events(scanned_at DESC);

CREATE INDEX ix_scan_result_time
ON scan_events(result_status, scanned_at DESC);

CREATE INDEX ix_scan_location_status
ON scan_events(location_status, scanned_at DESC);


-- ---------------------------------------------------------
-- 8. SCAN LOCATION DATA
-- ---------------------------------------------------------

CREATE TABLE scan_locations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_event_id UUID NOT NULL UNIQUE REFERENCES scan_events(id) ON DELETE RESTRICT,
    source VARCHAR(20) NOT NULL,
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    accuracy_meters NUMERIC(12,2),
    resolved_region_id UUID REFERENCES regions(id) ON DELETE RESTRICT,
    confidence VARCHAR(20),
    resolved_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (source IN ('GPS', 'IP')),

    CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR
        (
            latitude BETWEEN -90 AND 90
            AND longitude BETWEEN -180 AND 180
        )
    ),

    CHECK (accuracy_meters IS NULL OR accuracy_meters >= 0),

    CHECK (
        confidence IS NULL
        OR confidence IN ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')
    )
);

CREATE INDEX ix_scan_location_region
ON scan_locations(resolved_region_id);


-- ---------------------------------------------------------
-- 9. SCAN CLASSIFICATION
-- ---------------------------------------------------------

CREATE TABLE scan_classifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_event_id UUID NOT NULL UNIQUE REFERENCES scan_events(id) ON DELETE RESTRICT,
    assigned_region_id UUID NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    detected_region_id UUID REFERENCES regions(id) ON DELETE RESTRICT,
    classification VARCHAR(30) NOT NULL,
    classified_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (
        classification IN ('MATCH', 'MISMATCH', 'UNKNOWN', 'NOT_CHECKED')
    )
);

CREATE INDEX ix_scan_classification
ON scan_classifications(classification, classified_at DESC);


-- ---------------------------------------------------------
-- 10. FORMS
-- ---------------------------------------------------------

CREATE TABLE forms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(150) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE form_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_id UUID NOT NULL REFERENCES forms(id) ON DELETE RESTRICT,
    version_number INTEGER NOT NULL,
    schema JSONB NOT NULL,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE(form_id, version_number),
    UNIQUE(id, form_id),

    CHECK (version_number > 0)
);

CREATE TABLE form_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    form_version_id UUID NOT NULL REFERENCES form_versions(id) ON DELETE RESTRICT,
    scope_type VARCHAR(20) NOT NULL,
    product_id UUID REFERENCES products(id) ON DELETE RESTRICT,
    region_id UUID REFERENCES regions(id) ON DELETE RESTRICT,
    requirement VARCHAR(20) NOT NULL DEFAULT 'OPTIONAL',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CHECK (
        (scope_type = 'GLOBAL' AND product_id IS NULL AND region_id IS NULL)
        OR
        (scope_type = 'PRODUCT' AND product_id IS NOT NULL AND region_id IS NULL)
        OR
        (scope_type = 'REGION' AND region_id IS NOT NULL AND product_id IS NULL)
    ),

    CHECK (requirement IN ('MANDATORY', 'OPTIONAL', 'DISABLED'))
);

CREATE INDEX ix_form_assignment_product
ON form_assignments(product_id)
WHERE scope_type = 'PRODUCT';

CREATE INDEX ix_form_assignment_region
ON form_assignments(region_id)
WHERE scope_type = 'REGION';

CREATE TABLE form_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_event_id UUID NOT NULL REFERENCES scan_events(id) ON DELETE RESTRICT,
    form_assignment_id UUID NOT NULL REFERENCES form_assignments(id) ON DELETE RESTRICT,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_form_submission_scan
ON form_submissions(scan_event_id);

CREATE TABLE form_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id UUID NOT NULL REFERENCES form_submissions(id) ON DELETE RESTRICT,
    field_key VARCHAR(100) NOT NULL,
    answer JSONB NOT NULL,

    UNIQUE(submission_id, field_key)
);


-- ---------------------------------------------------------
-- 11. ANALYTICS
-- ---------------------------------------------------------

CREATE TABLE analytics_daily (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    region_id UUID NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    total_scans BIGINT NOT NULL DEFAULT 0,
    gps_scans BIGINT NOT NULL DEFAULT 0,
    ip_scans BIGINT NOT NULL DEFAULT 0,
    skipped_scans BIGINT NOT NULL DEFAULT 0,
    mismatch_scans BIGINT NOT NULL DEFAULT 0,

    UNIQUE(report_date, product_id, region_id),

    CHECK (
        total_scans >= 0
        AND gps_scans >= 0
        AND ip_scans >= 0
        AND skipped_scans >= 0
        AND mismatch_scans >= 0
    )
);

CREATE INDEX ix_analytics_date
ON analytics_daily(report_date DESC);


-- ---------------------------------------------------------
-- 12. SYSTEM SETTINGS
-- ---------------------------------------------------------

CREATE TABLE system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    setting_key VARCHAR(100) NOT NULL UNIQUE,
    setting_value JSONB NOT NULL,
    updated_by UUID REFERENCES admin_users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ---------------------------------------------------------
-- END INITIAL SCHEMA
-- ---------------------------------------------------------
