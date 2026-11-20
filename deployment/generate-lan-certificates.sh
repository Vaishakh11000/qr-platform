#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 LAN_IPV4_ADDRESS" >&2
  exit 2
fi

lan_ip="$1"
cert_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/certs-lan"

if ! python3 -c 'import ipaddress,sys; ipaddress.IPv4Address(sys.argv[1])' "$lan_ip"; then
  echo "Expected a valid IPv4 address." >&2
  exit 2
fi

if [[ -e "$cert_dir/lan-root-ca-key.pem" || -e "$cert_dir/lan-server-key.pem" || -e "$cert_dir/lan-fullchain.pem" ]]; then
  echo "LAN certificate files already exist in $cert_dir; refusing to overwrite them." >&2
  exit 1
fi

mkdir -p "$cert_dir"
umask 077

openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 1825 \
  -keyout "$cert_dir/lan-root-ca-key.pem" \
  -out "$cert_dir/lan-root-ca.crt" \
  -subj "/CN=QR Platform LAN Root CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "subjectKeyIdentifier=hash"

openssl req -new -newkey rsa:2048 -nodes -sha256 \
  -keyout "$cert_dir/lan-server-key.pem" \
  -out "$cert_dir/lan-server.csr" \
  -subj "/CN=$lan_ip"

cat > "$cert_dir/lan-server.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=IP:$lan_ip
subjectKeyIdentifier=hash
authorityKeyIdentifier=keyid,issuer
EOF

openssl x509 -req -sha256 -days 397 \
  -in "$cert_dir/lan-server.csr" \
  -CA "$cert_dir/lan-root-ca.crt" \
  -CAkey "$cert_dir/lan-root-ca-key.pem" \
  -CAcreateserial \
  -out "$cert_dir/lan-server.crt" \
  -extfile "$cert_dir/lan-server.ext"

cat "$cert_dir/lan-server.crt" "$cert_dir/lan-root-ca.crt" > "$cert_dir/lan-fullchain.pem"
openssl x509 -in "$cert_dir/lan-root-ca.crt" -outform DER -out "$cert_dir/lan-root-ca.der"
python3 - "$cert_dir/lan-root-ca.der" "$cert_dir/lan-root-ca.mobileconfig" <<'PY'
import plistlib
import sys
import uuid
from pathlib import Path

certificate = Path(sys.argv[1]).read_bytes()
payload_id = str(uuid.uuid4()).upper()
profile = {
    "PayloadContent": [{
        "PayloadContent": certificate,
        "PayloadDescription": "Install the QR Platform local certificate authority.",
        "PayloadDisplayName": "QR Platform LAN Root CA",
        "PayloadIdentifier": "com.qrplatform.lan.root-ca",
        "PayloadType": "com.apple.security.root",
        "PayloadUUID": payload_id,
        "PayloadVersion": 1,
    }],
    "PayloadDescription": "Trust the QR Platform development LAN HTTPS certificate.",
    "PayloadDisplayName": "QR Platform LAN Certificate",
    "PayloadIdentifier": "com.qrplatform.lan.ca-profile",
    "PayloadOrganization": "QR Platform Development",
    "PayloadRemovalDisallowed": False,
    "PayloadType": "Configuration",
    "PayloadUUID": str(uuid.uuid4()).upper(),
    "PayloadVersion": 1,
}
Path(sys.argv[2]).write_bytes(plistlib.dumps(profile, fmt=plistlib.FMT_XML))
PY
chmod 600 "$cert_dir/lan-root-ca-key.pem" "$cert_dir/lan-server-key.pem"
chmod 644 "$cert_dir/lan-root-ca.crt" "$cert_dir/lan-fullchain.pem" "$cert_dir/lan-root-ca.mobileconfig"
rm "$cert_dir/lan-root-ca.der" "$cert_dir/lan-server.csr" "$cert_dir/lan-server.ext" "$cert_dir/lan-root-ca.srl"

echo "LAN server certificate created for $lan_ip."
openssl x509 -in "$cert_dir/lan-root-ca.crt" -noout -fingerprint -sha256
echo "Android CA certificate: $cert_dir/lan-root-ca.crt"
echo "iPhone/iPad certificate profile: $cert_dir/lan-root-ca.mobileconfig"
echo "Keep lan-root-ca-key.pem private; never install it on client devices."
