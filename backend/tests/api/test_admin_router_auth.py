import pytest


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/categories"),
        ("get", "/api/v1/products"),
        ("get", "/api/v1/forms"),
        ("post", "/api/v1/forms"),
        ("get", "/api/v1/forms/assignments"),
        (
            "get",
            "/api/v1/products/00000000-0000-0000-0000-000000000001/versions",
        ),
        (
            "get",
            "/api/v1/products/00000000-0000-0000-0000-000000000001/media",
        ),
        ("get", "/api/v1/qr/batches"),
        ("get", "/api/v1/qr/codes/00000000-0000-0000-0000-000000000001"),
        ("get", "/api/v1/search?q=products"),
        (
            "get",
            "/api/v1/qr/codes/00000000-0000-0000-0000-000000000001/allocation",
        ),
    ],
)
def test_administrative_routes_require_authentication(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
