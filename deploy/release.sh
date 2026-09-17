#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f .env ]; then
    umask 077
    {
        printf 'POSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 24)"
        printf 'BACKEND_BIND=%s\n' "$(tailscale ip -4)"
    } > .env
fi

set -a
. ./.env
set +a

docker compose pull
docker compose up -d --remove-orphans

for _ in $(seq 1 30); do
    if curl -fsS "http://${BACKEND_BIND}:8000/health" | grep -q '"status":"ok"'; then
        echo "health ok"
        if [ "${PRUNE_IMAGES:-true}" = "true" ]; then
            docker image prune -f > /dev/null
        fi
        exit 0
    fi
    sleep 2
done

echo "the api did not answer /health within 60s" >&2
docker compose ps --format '{{.Service}} {{.Status}}'
docker compose logs --tail=50 backend
exit 1
