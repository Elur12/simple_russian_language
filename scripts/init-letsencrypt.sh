#!/usr/bin/env bash
# Initial Let's Encrypt certificate issuance for simplet.hamecte.ru.
#
# Usage:
#   EMAIL=you@example.com ./scripts/init-letsencrypt.sh            # production cert
#   EMAIL=you@example.com STAGING=1 ./scripts/init-letsencrypt.sh  # staging (test) cert
#
# Prerequisites:
#   - The domain simplet.hamecte.ru must resolve to this host.
#   - Ports 80 and 443 must be reachable from the internet.
#   - docker compose must be installed.

set -euo pipefail

DOMAIN="simplet.hamecte.ru"
EMAIL="${EMAIL:-}"
STAGING="${STAGING:-0}"

if [[ -z "$EMAIL" ]]; then
    echo "ERROR: Set EMAIL=you@example.com before running." >&2
    exit 1
fi

cd "$(dirname "$0")/.."

STAGING_FLAG=""
if [[ "$STAGING" == "1" ]]; then
    STAGING_FLAG="--staging"
    echo ">>> Using Let's Encrypt STAGING environment."
fi

echo ">>> Preparing nginx bootstrap config (HTTP-only, serves ACME challenge)."
# Temporarily swap the full app.conf out for bootstrap.conf so nginx can start
# before the certificate files exist.
if [[ -f nginx/conf.d/app.conf ]]; then
    mv nginx/conf.d/app.conf nginx/conf.d/app.conf.disabled
fi

cleanup() {
    if [[ -f nginx/conf.d/app.conf.disabled ]]; then
        mv nginx/conf.d/app.conf.disabled nginx/conf.d/app.conf
    fi
}
trap cleanup EXIT

echo ">>> Starting nginx in bootstrap mode."
docker compose up -d nginx

echo ">>> Waiting for nginx to respond on port 80..."
for i in {1..20}; do
    if curl -sf "http://${DOMAIN}/.well-known/acme-challenge/test" -o /dev/null || \
       curl -sf "http://${DOMAIN}/" -o /dev/null; then
        break
    fi
    sleep 1
done

echo ">>> Requesting certificate for ${DOMAIN}."
docker compose run --rm --entrypoint "" certbot \
    certbot certonly \
        --webroot -w /var/www/certbot \
        --email "${EMAIL}" \
        --agree-tos --no-eff-email \
        ${STAGING_FLAG} \
        -d "${DOMAIN}"

echo ">>> Restoring full nginx config and reloading."
cleanup
trap - EXIT

docker compose up -d nginx
docker compose exec nginx nginx -s reload

echo ">>> Done. Certificate stored in the letsencrypt_certs volume."
echo ">>> The certbot service will auto-renew every 12h."
