#!/usr/bin/env bash
set -euo pipefail
umask 077

version="${1:?Pass the seven-character source revision}"
[[ "$version" =~ ^[0-9a-f]{7}$ ]]
root="$HOME/axyro-portfolio"
release="$root/releases/$version"
gateway=axyro-work-reverse-proxy-1
live=/opt/axyro-work/release/infrastructure/migration/Caddyfile.domain-ready
backup="$root/Caddyfile.before-public-entry.$(date -u +%Y%m%dT%H%M%SZ)"
candidate="$root/Caddyfile.public-entry.candidate"
sudo -n true
mkdir -p "$release"
tar -xzf "$root/public-entry-$version.tar.gz" -C "$release"
sudo -n cat "$live" > "$backup"
for service in api frontend; do
    image=$(sudo -n docker inspect "axyro-portfolio-$service-1" --format '{{.Image}}')
    name=backend
    [[ "$service" != frontend ]] || name=frontend
    if ! sudo -n docker image inspect "axyro-portfolio-$name:before-public-entry" >/dev/null 2>&1; then
        sudo -n docker tag "$image" "axyro-portfolio-$name:before-public-entry"
    fi
done
cat > "$root/.env.public" <<'EOF'
PORTFOLIO_PUBLIC_ACCESS_ENABLED=true
EOF
cd "$release"
compose=(sudo -n docker compose --env-file "$root/.env.portfolio" --env-file "$root/.env.path"
    --env-file "$root/.env.public" -f docker-compose.portfolio.yml -f infrastructure/portfolio/compose.ingress.yml)
"${compose[@]}" config --format json | python3 -c '
import json, sys
s = json.load(sys.stdin)["services"]
e = s["api"]["environment"]
assert e["APP_ENV"] == "portfolio"
assert str(e["PORTFOLIO_PUBLIC_ACCESS_ENABLED"]).lower() == "true"
assert e["SESSION_COOKIE_PATH"] == "/portfolio/"
assert e["SESSION_COOKIE_NAME"] == "axyro_portfolio_session"
assert str(e["SESSION_COOKIE_SECURE"]).lower() == "true"
assert s["showcase-frontend"]["build"]["args"]["VITE_BASE_PATH"] == "/showcase/"
assert set(s["api"]["networks"]) == {"private"}
assert set(s["showcase-frontend"]["networks"]) == {"private"}
'
python3 - "$backup" "$candidate" <<'PY'
from pathlib import Path
import sys

previous, candidate = map(Path, sys.argv[1:])
source = previous.read_text()
marker = "(axyro_app) {"
assert source.count(marker) == 1
prefix, tail = source.split(marker, 1)
assert prefix.lstrip().startswith("(portfolio_path) {")
old_import = "    import portfolio_path\n"
assert tail.count(old_import) == 1
if "    import public_showcase\n" not in tail:
    tail = tail.replace(old_import, "    import public_showcase\n" + old_import, 1)
portfolio = Path("infrastructure/portfolio/portfolio.caddy").read_text()
showcase = Path("infrastructure/portfolio/showcase.caddy").read_text()
candidate.write_text(portfolio + "\n" + showcase + "\n" + marker + tail)
PY
sudo -n docker exec -i "$gateway" caddy validate --config - --adapter caddyfile < "$candidate"
"${compose[@]}" build api frontend showcase-frontend > "$root/public-build-$version.log" 2>&1
"${compose[@]}" up -d --no-deps --no-build api worker frontend showcase-frontend reverse-proxy
for attempt in $(seq 1 20); do
    if curl -fsS --max-time 3 http://127.0.0.1:19082/api/ready >/dev/null; then break; fi
    sleep 2
done
curl -fsS --max-time 5 http://127.0.0.1:19082/api/ready >/dev/null
curl -fsS --max-time 5 http://127.0.0.1:19082/ | grep -q '/showcase/assets/'
curl -fsS --max-time 5 http://127.0.0.1:19082/api/setup/status | python3 -c '
import json, sys
assert json.load(sys.stdin)["portfolio_public_access_enabled"] is True
'
sudo -n tee "$live" < "$candidate" >/dev/null
if ! sudo -n docker exec "$gateway" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile ||
   ! curl -fsS --max-time 10 https://axyro.tech/api/ready >/dev/null ||
   ! curl -fsS --max-time 10 https://axyro.tech/portfolio/api/ready >/dev/null ||
   ! curl -fsS --max-time 10 https://axyro.tech/ | grep -q '/showcase/assets/'; then
    sudo -n tee "$live" < "$backup" >/dev/null
    sudo -n docker exec "$gateway" caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
    printf 'Previous gateway configuration restored.\n' >&2
    exit 1
fi
printf '%s\n' "$version" > "$root/ui-rollback/current-ui-release"
printf 'Public landing and portfolio entry published. Gateway backup: %s\n' "$backup"
