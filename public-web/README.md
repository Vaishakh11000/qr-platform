# Public product website

## Test a QR scan from a phone on the same Wi-Fi

1. Start PostgreSQL and the backend. The backend must listen on port `8000`; the public website proxies `/api/v1` requests to it.
2. Find the computer's Wi-Fi IP address, then run the website from this directory:

   ```sh
   API_INTERNAL_URL=http://127.0.0.1:8000 \
   NEXT_ALLOWED_DEV_ORIGINS=192.168.1.25 \
   npm run dev
   ```

   Replace `192.168.1.25` with the computer's current Wi-Fi IP. For multiple trusted development origins, separate them with commas.
3. Set the platform's **Public QR address** to `http://192.168.1.25:3000`, open that address from the phone, then scan or enter a QR code.

The development server must be reachable through the computer's firewall. `localhost` in a phone browser refers to the phone itself. Browsers generally require HTTPS for GPS location; an HTTP LAN address is suitable for page and QR-flow checks, but not reliable GPS permission testing. IP geolocation is not configured.

## Production

Production builds use the `public-web` service in `compose.production.yaml`. Set `PUBLIC_BASE_URL` to the public HTTPS hostname and `API_INTERNAL_URL` to the backend address reachable from the public-web container. See [Operations](../docs/OPERATIONS.md) for deployment and TLS requirements.
