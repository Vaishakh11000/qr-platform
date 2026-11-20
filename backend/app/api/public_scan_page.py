from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter()


SCAN_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="theme-color" content="#111827">
    <title>Product Information</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            padding: 24px;
            background: #f3f4f6;
            color: #111827;
            font-family: Arial, sans-serif;
        }
        main {
            max-width: 640px;
            margin: 40px auto;
            padding: 28px;
            background: white;
            border-radius: 14px;
            box-shadow: 0 4px 20px rgba(0,0,0,.07);
        }
        h1 { font-size: 25px; margin-top: 0; }
        p { line-height: 1.6; }
        button {
            padding: 12px 18px;
            border: 0;
            border-radius: 8px;
            background: #111827;
            color: white;
            font-size: 15px;
            cursor: pointer;
        }
        button:disabled { opacity: .5; cursor: wait; }
        #skip { margin-left: 8px; background: #e5e7eb; color: #111827; }
        #product { display: none; margin-top: 24px; }
        pre {
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            padding: 16px;
            background: #f9fafb;
            border-radius: 8px;
        }
        #status { color: #4b5563; }
        .error { color: #b91c1c; }
    </style>
</head>
<body>
<main>
    <h1 id="heading">Loading product information</h1>
    <p id="status">Please wait while this QR code is verified.</p>

    <div id="controls" hidden>
        <button id="allow">Share location</button>
        <button id="skip" hidden>Continue without location</button>
    </div>

    <section id="product">
        <h2 id="product-name"></h2>
        <pre id="product-content"></pre>
    </section>
</main>

<script>
(() => {
    const heading = document.getElementById("heading");
    const statusText = document.getElementById("status");
    const controls = document.getElementById("controls");
    const allowButton = document.getElementById("allow");
    const skipButton = document.getElementById("skip");
    const productSection = document.getElementById("product");

    let scanId = null;
    let submitting = false;

    function showError(message) {
        heading.textContent = "Unable to open product";
        statusText.textContent = message;
        statusText.className = "error";
        controls.hidden = true;
    }

    async function submitLocation(payload) {
        if (!scanId || submitting) return;
        submitting = true;

        allowButton.disabled = true;
        skipButton.disabled = true;
        statusText.textContent = "Processing your request...";

        try {
            const response = await fetch(
                `/api/v1/public/scans/${encodeURIComponent(scanId)}/location`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                }
            );

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || "Scan could not be completed.");
            }

            if (result.result_status !== "ALLOWED") {
                heading.textContent = "Location required";
                statusText.textContent = result.message;
                statusText.className = "error";
                submitting = false;
                allowButton.disabled = false;
                skipButton.disabled = false;
                allowButton.textContent = "Try location again";
                return;
            }

            if (!result.product) {
                showError("Product information is currently unavailable.");
                return;
            }

            heading.textContent = "Product information";
            statusText.textContent = result.message;
            controls.hidden = true;

            document.getElementById("product-name").textContent =
                result.product.content_snapshot.title ||
                result.product.name;

            document.getElementById("product-content").textContent =
                JSON.stringify(result.product.content_snapshot, null, 2);

            productSection.style.display = "block";

        } catch (error) {
            submitting = false;
            allowButton.disabled = false;
            skipButton.disabled = false;
            showError(error.message || "An unexpected error occurred.");
        }
    }

    function requestLocation() {
        if (!navigator.geolocation) {
            submitLocation({ location_status: "UNAVAILABLE" });
            return;
        }

        statusText.textContent = "Waiting for location permission...";

        navigator.geolocation.getCurrentPosition(
            position => {
                submitLocation({
                    location_status: "GPS",
                    latitude: position.coords.latitude,
                    longitude: position.coords.longitude,
                    accuracy_meters: position.coords.accuracy
                });
            },
            error => {
                submitLocation({
                    location_status:
                        error.code === error.PERMISSION_DENIED
                            ? "DENIED"
                            : "UNAVAILABLE"
                });
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,
                maximumAge: 0
            }
        );
    }

    async function startScan() {
        const token = decodeURIComponent(
            window.location.pathname.split("/").pop()
        );

        try {
            const response = await fetch("/api/v1/public/scans/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ token })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || "QR code could not be verified.");
            }

            scanId = result.scan_id;

            if (!result.location_requested) {
                await submitLocation({ location_status: "SKIPPED" });
                return;
            }

            controls.hidden = false;

            if (result.location_requirement === "SKIPPABLE") {
                skipButton.hidden = false;
            }

            if (result.location_method === "IP_ONLY") {
                await submitLocation({ location_status: "UNAVAILABLE" });
                return;
            }

        } catch (error) {
            showError(error.message || "Unable to start scan.");
        }
    }

    allowButton.addEventListener("click", requestLocation);

    skipButton.addEventListener("click", () => {
        submitLocation({ location_status: "SKIPPED" });
    });

    startScan();
})();
</script>
</body>
</html>
"""


@router.get("/q/{token}", response_class=HTMLResponse)
def public_qr_page(token: str):
    if not token or len(token) > 128:
        return HTMLResponse(
            "<h1>Invalid QR code</h1>",
            status_code=404,
        )

    return HTMLResponse(
        content=SCAN_PAGE,
        headers={"Cache-Control": "no-store"},
    )
