import pytest

from sqlalchemy.exc import IntegrityError

from app.models import Region, RegionBoundary


def create_test_region(db_session, suffix):
    """Create a region for geography integrity tests."""

    region = Region(
        name=f"Test Region {suffix}",
        region_code=f"TEST-REGION-{suffix}",
        region_type="TEST",
    )

    db_session.add(region)
    db_session.flush()

    return region


@pytest.mark.integration
def test_region_code_must_be_unique(db_session):
    region = create_test_region(db_session, "DUPLICATE")

    duplicate = Region(
        name="Duplicate Region",
        region_code=region.region_code,
        region_type="TEST",
    )

    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_region_cannot_be_its_own_parent(db_session):
    region = create_test_region(db_session, "SELF-PARENT")

    region.parent_id = region.id

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_region_boundary_requires_existing_region(db_session):
    boundary = RegionBoundary(
        region_id="00000000-0000-0000-0000-000000000001",
        boundary="MULTIPOLYGON EMPTY",
    )

    db_session.add(boundary)

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.integration
def test_region_can_have_only_one_boundary(db_session):
    region = create_test_region(db_session, "DUPLICATE-BOUNDARY")

    first_boundary = RegionBoundary(
        region_id=region.id,
        boundary="MULTIPOLYGON EMPTY",
    )

    db_session.add(first_boundary)
    db_session.flush()

    duplicate_boundary = RegionBoundary(
        region_id=region.id,
        boundary="MULTIPOLYGON EMPTY",
    )

    db_session.add(duplicate_boundary)

    with pytest.raises(IntegrityError):
        db_session.flush()

@pytest.mark.integration
def test_region_boundary_accepts_valid_multipolygon(db_session):
    """A valid MULTIPOLYGON with SRID 4326 should be accepted."""

    region = create_test_region(db_session, "VALID-GEOMETRY")

    boundary = RegionBoundary(
        region_id=region.id,
        boundary=(
            "SRID=4326;"
            "MULTIPOLYGON((("
            "72.8000 19.0000,"
            "72.8100 19.0000,"
            "72.8100 19.0100,"
            "72.8000 19.0100,"
            "72.8000 19.0000"
            ")))"
        ),
    )

    db_session.add(boundary)
    db_session.flush()

    from sqlalchemy import text

    result = db_session.execute(
        text("""
            SELECT
                ST_GeometryType(boundary) AS geometry_type,
                ST_SRID(boundary) AS srid
            FROM app.region_boundaries
            WHERE region_id = :region_id
        """),
        {"region_id": region.id},
    ).mappings().one()

    assert result["geometry_type"] == "ST_MultiPolygon"
    assert result["srid"] == 4326


@pytest.mark.integration
def test_region_boundary_promotes_polygon_to_multipolygon(db_session):
    """
    PostGIS should promote a POLYGON to MULTIPOLYGON
    when storing it in the MULTIPOLYGON column.
    """

    region = create_test_region(db_session, "POLYGON-PROMOTION")

    boundary = RegionBoundary(
        region_id=region.id,
        boundary=(
            "SRID=4326;"
            "POLYGON(("
            "72.8000 19.0000,"
            "72.8100 19.0000,"
            "72.8100 19.0100,"
            "72.8000 19.0100,"
            "72.8000 19.0000"
            "))"
        ),
    )

    db_session.add(boundary)
    db_session.flush()

    from sqlalchemy import text

    result = db_session.execute(
        text("""
            SELECT
                ST_GeometryType(boundary) AS geometry_type,
                ST_SRID(boundary) AS srid,
                ST_NumGeometries(boundary) AS geometry_count
            FROM app.region_boundaries
            WHERE region_id = :region_id
        """),
        {"region_id": region.id},
    ).mappings().one()

    assert result["geometry_type"] == "ST_MultiPolygon"
    assert result["srid"] == 4326
    assert result["geometry_count"] == 1