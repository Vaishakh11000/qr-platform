from fastapi import APIRouter
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.location_policies import router as location_policies_router
from app.api.v1.auth import router as auth_router

from app.api.v1.categories import router as categories_router
from app.api.v1.products import router as products_router
from app.api.v1.regions import router as regions_router
from app.api.v1.product_versions import router as product_versions_router
from app.api.v1.product_media import router as product_media_router
from app.api.v1.qr import router as qr_router
from app.api.v1.qr_allocations import router as qr_allocations_router
from app.api.v1.public_scans import router as public_scans_router
from app.api.v1.public_scan_media import router as public_scan_media_router
from app.api.v1.forms import router as forms_router
from app.api.v1.public_forms import router as public_forms_router
from app.api.v1.administration import router as administration_router
from app.api.v1.administration import settings_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.search import router as search_router


api_router = APIRouter()
api_router.include_router(dashboard_router)
api_router.include_router(audit_logs_router)
api_router.include_router(auth_router)
api_router.include_router(location_policies_router)

api_router.include_router(categories_router)
api_router.include_router(products_router)
api_router.include_router(regions_router)
api_router.include_router(product_versions_router)
api_router.include_router(product_media_router)
api_router.include_router(qr_router)
api_router.include_router(qr_allocations_router)
api_router.include_router(public_scans_router)
api_router.include_router(public_scan_media_router)
api_router.include_router(forms_router)
api_router.include_router(public_forms_router)
api_router.include_router(administration_router)
api_router.include_router(settings_router)
api_router.include_router(analytics_router)
api_router.include_router(search_router)
