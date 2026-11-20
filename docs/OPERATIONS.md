# Operations and deployment

## Local development

`compose.yaml` starts only the PostGIS database for local development. Start the API, admin UI and public site with their normal development commands. Uploaded product files use `MEDIA_STORAGE_ROOT`; it defaults to the ignored `storage/` directory.

## Production Compose deployment

`compose.production.yaml` runs PostGIS, the API, the admin app, the public Next.js app and an Nginx reverse proxy. PostgreSQL is exposed only on host loopback (default port 5433) for maintenance and backups. Product files and PostgreSQL data use separate persistent Docker volumes. The API container runs as an unprivileged user.

The database, API, and both web apps have container health checks. The proxy waits for its upstreams to become healthy before starting. Container stdout/stderr logs use Docker's local JSON log driver, capped at three 10 MB files per service. This bounds local disk use; it is not a substitute for centralized log collection or alerting.

1. Copy `.env.example` to `.env`. Set unique database credentials, generate `ADMIN_TOKEN_SECRET` with `openssl rand -hex 32`, and set `PUBLIC_HOSTNAME`, `ADMIN_HOSTNAME` and `PUBLIC_BASE_URL` to real DNS names. Keep `.env` private.
2. Provide a TLS certificate covering both hostnames at `deployment/certs/fullchain.pem` and its private key at `deployment/certs/privkey.pem`. Certificate issuance and renewal are managed outside this Compose stack.
3. Point both DNS names to the host and allow inbound TCP 80 and 443. The proxy redirects HTTP to HTTPS.
4. Build and start PostGIS: `docker compose -f compose.production.yaml up -d --build database`.
5. Take and verify a database backup before applying migrations. Apply migrations explicitly with `docker compose -f compose.production.yaml run --rm backend alembic -c /app/alembic.ini upgrade head`. The application does not run migrations automatically at startup.
6. Start the application: `docker compose -f compose.production.yaml up -d --build` and check `https://ADMIN_HOSTNAME/health` and `https://PUBLIC_HOSTNAME/ready`.

The production Compose file is a deployment starting point. It does not obtain certificates, configure DNS/firewall rules, provide a managed secrets store, or configure external monitoring. Do not expose the database port beyond loopback.

The Nginx public host applies per-client-IP request limits to public scan creation (60 requests/minute with a burst of 30) and scan completion (120 requests/minute with a burst of 60). Excess requests receive HTTP 429. These limits are edge protection for the single-proxy deployment; review them against expected event traffic before increasing deployment scale. Requests forwarded through the configured Nginx proxy retain the client's source IP for these limits.

Both HTTPS hosts allow request bodies up to 110 MB so the admin media upload endpoint can receive its supported 100 MB video files plus multipart overhead. The API validates each upload against its media-type-specific limit.

## Same-Wi-Fi LAN release

`compose.lan.yaml` serves the public product site and admin console over the host's Wi-Fi address. HTTPS is available on ports 8443 (public) and 8444 (admin); HTTP ports 8080/8081 redirect to HTTPS, except the public port serves the local CA certificate needed for device trust. The stack reuses the existing local development PostGIS container and its data; it does not create or connect to production. It is intended for a private LAN preview only.

1. Confirm the development database container `qr-platform-db` is running and make a backup before applying any pending migrations.
2. Copy `.env.lan.example` to `.env.lan`. Set `LAN_BIND_ADDRESS` and `PUBLIC_BASE_URL` to the host's current Wi-Fi IPv4 address. Keep `.env.lan` private.
3. Generate a private local CA and a server certificate with `deployment/generate-lan-certificates.sh LAN_BIND_ADDRESS`. Keep `deployment/certs-lan/lan-root-ca-key.pem` on the host; install only `lan-root-ca.crt` on phones.
4. Apply pending migrations to the local development database with `docker compose --env-file .env.lan -f compose.lan.yaml run --rm backend alembic -c /app/alembic.ini upgrade head`.
5. Start the LAN services with `docker compose --env-file .env.lan -f compose.lan.yaml up -d --build`.
6. On Android, download `http://LAN_BIND_ADDRESS:8080/lan-root-ca.crt`; on iPhone/iPad, download `http://LAN_BIND_ADDRESS:8080/lan-root-ca.mobileconfig`. Verify the certificate fingerprint against the host before installing it. On iPhone/iPad, install the profile, then enable full trust under Certificate Trust Settings. On Android, install the certificate as a CA certificate in Security settings.
7. Open `https://LAN_BIND_ADDRESS:8443` for the product site and `https://LAN_BIND_ADDRESS:8444` for admin. Set the Public QR address in Administration to the public HTTPS URL so newly exported QR images use the secure site.

Geolocation is available only in a secure browser context; it also requires the device owner to grant the browser's location permission. The phone must trust the local CA or the certificate warning will prevent a secure connection. This LAN setup does not expose the database port to Wi-Fi clients. Do not configure router port forwarding for these web ports.

## Database backup

Install a PostgreSQL client at the same or newer major version than the server. The backup script writes PostgreSQL custom-format archives and a SHA-256 sidecar with restrictive file permissions. It never overwrites an existing backup.

For the production Compose database, run this from the repository root:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/backup_database.py \
  --host 127.0.0.1 --port 5433
```

For a database reachable at the configured `.env` address, omit the host and port options. Backups are written under `backups/`, which is excluded from Git.

Product media is stored separately from PostgreSQL. Stop the API and public site while taking a matching database/media backup so uploads cannot change between snapshots. For this Compose project, archive the `product_media` volume alongside the database backup:

```sh
set -e
docker compose -f compose.production.yaml stop backend public-web
trap 'docker compose -f compose.production.yaml start backend public-web' EXIT
PYTHONPATH=backend .venv/bin/python backend/scripts/backup_database.py \
  --host 127.0.0.1 --port 5433
mkdir -p backups
media_archive="backups/product_media_$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
docker run --rm \
  -v qr-platform-production-product-media:/source:ro \
  -v "$PWD/backups:/backup" \
  alpine:3.20 tar -czf "/backup/${media_archive#backups/}" -C /source .
sha256sum "$media_archive" > "$media_archive.sha256"
```

Keep both artifacts off-host. Restoring only the database does not restore media files.

## Restore drill

The restore script deliberately refuses both configured application databases. Create a disposable, empty database, then restore into it with an exact target confirmation:

```sh
PYTHONPATH=backend .venv/bin/python backend/scripts/restore_database.py backups/<archive>.dump \
  --target-database qr_platform_restore_check \
  --confirm-target qr_platform_restore_check
```

The target must already exist. The script refuses to restore if it contains non-extension tables, views, or sequences. `--allow-nonempty-target` is an explicit override for a deliberate replacement drill; it still requires the exact target-name confirmation. Verify the restored schema and application data before considering a backup usable. Production recovery requires a separately reviewed maintenance procedure; never point a restore drill at production.

## Recovery and retention

Keep database and media backups encrypted, access-controlled and on storage separate from the application host. Define retention and recovery-point objectives for the deployment. Periodically perform a restore drill against a disposable database and a separate media directory. Record the tested backup timestamp and checksum. A backup that has not been restored successfully is not a verified recovery point.
