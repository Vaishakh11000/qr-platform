from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    LocationPolicy,
    LocationPolicyAssignment,
    Product,
    ProductVersion,
    QRAllocation,
    QRCode,
    Region,
    ScanEvent,
)


class ScanError(Exception):
    pass


class QRTokenNotFound(ScanError):
    pass


class QRCodeInactive(ScanError):
    pass


class QRCodeUnallocated(ScanError):
    pass


class ProductUnavailable(ScanError):
    pass


class PublishedVersionUnavailable(ScanError):
    pass


@dataclass
class ScanStartResult:
    event: ScanEvent
    product: Product
    version: ProductVersion
    location_policy: LocationPolicy | None


def resolve_location_policy(
    db: Session,
    *,
    product_id,
    region_id=None,
) -> LocationPolicy | None:
    """
    Resolve the highest-priority active location policy.

    Priority:
      1. Region-specific policy, when a region is known.
      2. Product-specific policy.
      3. Global policy.

    Higher assignment.priority wins within the same scope.
    """

    region_depth: dict = {}
    current_region_id = region_id
    visited = set()
    depth = 0
    while current_region_id is not None and current_region_id not in visited:
        visited.add(current_region_id)
        region_depth[current_region_id] = depth
        current_region_id = db.scalar(
            select(Region.parent_id).where(Region.id == current_region_id)
        )
        depth += 1

    query = (
        select(LocationPolicy, LocationPolicyAssignment)
        .join(
            LocationPolicyAssignment,
            LocationPolicyAssignment.policy_id == LocationPolicy.id,
        )
        .where(
            LocationPolicy.is_active.is_(True),
            (
                (
                    (LocationPolicyAssignment.scope_type == "PRODUCT")
                    & (LocationPolicyAssignment.product_id == product_id)
                )
                | (
                    LocationPolicyAssignment.scope_type == "GLOBAL"
                )
                | (
                    (LocationPolicyAssignment.scope_type == "REGION")
                    & LocationPolicyAssignment.region_id.in_(tuple(region_depth))
                    & bool(region_depth)
                )
            ),
        )
    )
    candidates = db.execute(query).all()
    if not candidates:
        return None

    def candidate_order(candidate):
        policy, assignment = candidate
        if assignment.scope_type == "REGION":
            return (0, region_depth.get(assignment.region_id, 10**9), -assignment.priority, -policy.created_at.timestamp())
        if assignment.scope_type == "PRODUCT":
            return (1, 0, -assignment.priority, -policy.created_at.timestamp())
        return (2, 0, -assignment.priority, -policy.created_at.timestamp())

    return min(candidates, key=candidate_order)[0]


def begin_scan(
    db: Session,
    token: str,
    *,
    user_agent: str | None = None,
    ip_hash: str | None = None,
) -> ScanStartResult:
    """
    Resolve an active QR code and its current published product version.

    A pending ScanEvent is created only after the QR code, allocation,
    product, and published version have all been validated.
    """

    qr_code = db.scalar(
        select(QRCode).where(QRCode.token == token)
    )

    if qr_code is None:
        raise QRTokenNotFound()

    if qr_code.status != "ACTIVE":
        raise QRCodeInactive()

    allocation = db.scalar(
        select(QRAllocation).where(
            QRAllocation.qr_code_id == qr_code.id,
            QRAllocation.ended_at.is_(None),
        )
    )

    if allocation is None:
        raise QRCodeUnallocated()

    product = db.get(Product, allocation.product_id)

    if product is None or product.status != "ACTIVE":
        raise ProductUnavailable()

    if product.current_version_id is None:
        raise PublishedVersionUnavailable()

    version = db.scalar(
        select(ProductVersion).where(
            ProductVersion.id == product.current_version_id,
            ProductVersion.product_id == product.id,
            ProductVersion.status == "PUBLISHED",
            ProductVersion.published_at.is_not(None),
        )
    )

    if version is None:
        raise PublishedVersionUnavailable()

    policy = resolve_location_policy(
        db,
        product_id=product.id,
        region_id=allocation.region_id,
    )

    event = ScanEvent(
        qr_code_id=qr_code.id,
        allocation_id=allocation.id,
        product_id=product.id,
        region_id=allocation.region_id,
        product_version_id=version.id,
        location_policy_id=policy.id if policy else None,
        location_status="PENDING",
        result_status="PENDING",
        user_agent=user_agent,
        ip_hash=ip_hash,
    )

    try:
        db.add(event)
        db.commit()
        db.refresh(event)

    except IntegrityError:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise

    return ScanStartResult(
        event=event,
        product=product,
        version=version,
        location_policy=policy,
    )


class ScanEventNotFound(ScanError):
    pass


class ScanAlreadyCompleted(ScanError):
    pass


class InvalidScanLocation(ScanError):
    pass


def _location_confidence(accuracy_meters: float | None) -> str:
    if accuracy_meters is None:
        return "UNKNOWN"

    if accuracy_meters <= 50:
        return "HIGH"

    if accuracy_meters <= 500:
        return "MEDIUM"

    return "LOW"


def complete_scan(
    db: Session,
    scan_id,
    location_data,
):
    """
    Complete a pending scan using browser location information.

    The server enforces the stored location policy. IP geolocation
    is not fabricated when no lookup provider is configured.
    """

    from datetime import datetime, timezone

    from app.models import ScanClassification, ScanLocation
    from app.services.region_detection_service import resolve_scan_region

    event = db.execute(
        select(ScanEvent)
        .where(ScanEvent.id == scan_id)
        .with_for_update()
    ).scalar_one_or_none()

    if event is None:
        raise ScanEventNotFound()

    if event.result_status != "PENDING":
        raise ScanAlreadyCompleted()

    policy = (
        db.get(LocationPolicy, event.location_policy_id)
        if event.location_policy_id
        else None
    )

    if policy is not None and not policy.is_active:
        raise InvalidScanLocation()

    submitted_status = location_data.location_status

    detected_region = None
    classification = "UNKNOWN"

    if submitted_status == "GPS":
        if policy is not None and policy.method == "IP_ONLY":
            raise InvalidScanLocation()

        location_status = "GPS"
        accuracy = location_data.accuracy_meters

        if event.region_id is not None:
            detected_region, classification = resolve_scan_region(
                db,
                assigned_region_id=event.region_id,
                latitude=location_data.latitude,
                longitude=location_data.longitude,
                accuracy_meters=accuracy,
            )

        db.add(
            ScanLocation(
                scan_event_id=event.id,
                source="GPS",
                latitude=location_data.latitude,
                longitude=location_data.longitude,
                accuracy_meters=accuracy,
                resolved_region_id=(
                    detected_region.id if detected_region else None
                ),
                confidence=_location_confidence(accuracy),
            )
        )

        result_status = "ALLOWED"
        message = "Location received successfully."

    else:
        if submitted_status == "SKIPPED":
            location_status = "SKIPPED"
        elif submitted_status == "DENIED":
            location_status = "DENIED"
        else:
            location_status = "UNAVAILABLE"

        if policy is not None and policy.method in (
            "GPS_IP_FALLBACK",
            "IP_ONLY",
        ):
            # No IP geolocation provider is configured yet.
            location_status = "IP_LOOKUP_FAILED"

        if policy is not None and policy.requirement == "MANDATORY":
            result_status = "BLOCKED"
            if submitted_status == "DENIED":
                message = (
                    "Your browser has saved this site's location permission as blocked. "
                    "Open this site's browser settings, set Location to Allow, return here, "
                    "and tap Try again. Reloading alone does not reset a saved denial."
                )
                if policy.method in ("GPS_IP_FALLBACK", "IP_ONLY"):
                    message += (
                        " IP-based fallback is not configured on this deployment, so GPS is "
                        "needed for now."
                    )
            elif location_status == "IP_LOOKUP_FAILED":
                message = (
                    "Location verification is required, but IP-based location is not configured "
                    "on this deployment. A private Wi-Fi address cannot identify your region. "
                    "Use GPS from this site over HTTPS, or ask the site administrator to configure "
                    "an IP geolocation provider."
                )
            elif submitted_status == "UNAVAILABLE":
                message = (
                    "Your phone could not determine your location. Open this page over HTTPS, "
                    "enable device location services, and try again."
                )
            else:
                message = "Location is required to access this product."
        else:
            result_status = "ALLOWED"
            message = "Product access permitted without GPS location."

    if event.region_id is not None:
        db.add(
            ScanClassification(
                scan_event_id=event.id,
                assigned_region_id=event.region_id,
                detected_region_id=(
                    detected_region.id if detected_region else None
                ),
                classification=classification,
            )
        )

    event.location_status = location_status
    event.result_status = result_status
    event.completed_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(event)

    except Exception:
        db.rollback()
        raise

    return event, message
