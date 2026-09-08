# 🔒 Shared Caddy — Multi-App HTTPS Setup

This project uses a **shared Caddy reverse proxy** that handles HTTPS for multiple apps on the same VPS. Any GitHub repo can deploy to the same machine and get automatic HTTPS — no manual cert management needed.

## How It Works

```
┌─────────────────────────────────────────────────────┐
│  VPS                                                │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │  Caddy (ports 80/443)                         │  │
│  │  - Auto Let's Encrypt certificates            │  │
│  │  - Routes by domain name                      │  │
│  │  - Shared across ALL apps                     │  │
│  └──────────┬────────────────────┬───────────────┘  │
│             │                    │                   │
│  ┌──────────▼──────┐  ┌─────────▼────────┐         │
│  │  telegram-7z-bot │  │  other-app       │         │
│  │  (port 8080)     │  │  (port 3000)     │         │
│  └─────────────────┘  └──────────────────┘         │
│                                                     │
│  Docker network: caddy (shared by all apps)         │
└─────────────────────────────────────────────────────┘
```

- **Caddy** runs once, handles all HTTPS certificates
- **Each app** connects to the `caddy` Docker network
- **Deploy workflows** automatically register domains with Caddy

## For App Owners

### Requirements

Your app must:
1. Run as a Docker container
2. Expose an HTTP port (no HTTPS needed — Caddy handles that)
3. Connect to the `caddy` Docker network

### Step 1: Add Caddy network to your `docker-compose.yml`

```yaml
services:
  your-app:
    image: your-app:latest
    container_name: your-app
    restart: unless-stopped
    env_file:
      - .env
    networks:
      - caddy

networks:
  caddy:
    external: true
```

### Step 2: Set GitHub Secrets

In your repo's **Settings → Secrets and variables → Actions**:

| Secret | Value | Required |
|--------|-------|----------|
| `VPS_HOST` | Your VPS IP or domain | ✅ |
| `VPS_USER` | SSH username (default: `root`) | ✅ |
| `VPS_SSH_PRIVATE_KEY` | SSH private key | ✅ |
| `ORIGIN_DOMAIN` | Your app's domain (e.g. `api.yourdomain.com`) | ✅ for HTTPS |
| `HOST_PORT` | Your app's internal port (e.g. `3000`) | Optional (default: 8080) |

### Step 3: Deploy workflow

Your deploy workflow must:
1. Create the shared Caddy network (idempotent — safe if it already exists)
2. Start Caddy if not running
3. Append your domain to `/opt/caddy/Caddyfile`
4. Reload Caddy
5. Deploy your app

**Copy this deploy script into your workflow:**

```yaml
- name: 🚀 Deploy via Docker
  env:
    VPS_HOST: ${{ secrets.VPS_HOST }}
    VPS_USER: ${{ secrets.VPS_USER || 'root' }}
    ORIGIN_DOMAIN: ${{ secrets.ORIGIN_DOMAIN || '' }}
    HOST_PORT: ${{ secrets.HOST_PORT || '8080' }}
  run: |
    DEPLOY_DIR="/opt/your-app"

    # Install Docker if not present
    ssh -p 22 ${VPS_USER}@${VPS_HOST} "command -v docker || (curl -fsSL https://get.docker.com | sh)"

    # Create deploy directory
    ssh -p 22 ${VPS_USER}@${VPS_HOST} "mkdir -p ${DEPLOY_DIR}/data /opt/caddy"

    # Copy files to VPS
    scp -P 22 docker-compose.yml ${VPS_USER}@${VPS_HOST}:${DEPLOY_DIR}/docker-compose.yml

    # Ensure shared Caddy network exists
    ssh -p 22 ${VPS_USER}@${VPS_HOST} "docker network create caddy 2>/dev/null || true"

    # Start shared Caddy if not running
    ssh -p 22 ${VPS_USER}@${VPS_HOST} "if ! docker ps --format '{{.Names}}' | grep -q '^caddy$'; then
      if [ ! -f /opt/caddy/Caddyfile ]; then
        cat > /opt/caddy/Caddyfile << 'CADDYEOF'
# Shared Caddyfile — managed by deployments
# Add new app domains below.
CADDYEOF
      fi
      docker run -d --name caddy --restart unless-stopped \
        -p 80:80 -p 443:443 \
        -v /opt/caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
        -v caddy_data:/data \
        -v caddy_config:/config \
        --network caddy \
        caddy:2-alpine
    fi"

    # Append your domain to the shared Caddyfile (skip if already present)
    if [ -n "$ORIGIN_DOMAIN" ]; then
      ssh -p 22 ${VPS_USER}@${VPS_HOST} "if ! grep -q '${ORIGIN_DOMAIN}' /opt/caddy/Caddyfile; then
        cat >> /opt/caddy/Caddyfile << 'CADDYEOF'
${ORIGIN_DOMAIN} {
    reverse_proxy your-app:${HOST_PORT}
}
CADDYEOF
        docker exec caddy caddy reload --config /etc/caddy/Caddyfile
        echo '✅ Caddy reloaded with new domain'
      else
        echo '⚠️ Domain ${ORIGIN_DOMAIN} already in Caddyfile'
      fi"
    fi

    # Deploy your app
    ssh -p 22 ${VPS_USER}@${VPS_HOST} "cd ${DEPLOY_DIR} && docker compose pull && docker compose up -d --remove-orphans"

    # Verify
    sleep 10
    ssh -p 22 ${VPS_USER}@${VPS_HOST} "docker ps --filter 'name=your-app' --filter 'status=running' | grep -q your-app && echo '✅ Running!' || echo '❌ Failed'"
```

### Step 4: Done!

Your app is now accessible at `https://your-domain.com` with automatic HTTPS.

## What Happens on First Deploy?

The deploy workflow handles everything automatically:

1. **Caddy network** — Created if it doesn't exist (`docker network create caddy`)
2. **Caddy container** — Started if not running (`docker run -d --name caddy ...`)
3. **Caddyfile** — Created at `/opt/caddy/Caddyfile` if missing
4. **Domain** — Appended to the Caddyfile
5. **Caddy reload** — Picks up the new domain

**No manual steps needed.** The first app to deploy sets up Caddy. Subsequent apps just add their domains.

## Shared Caddyfile Location

The Caddyfile lives at `/opt/caddy/Caddyfile` on the VPS. It looks like this:

```caddy
# Shared Caddyfile — managed by deployments
# Add new app domains below.

# Telegram 7z Bot
files.yourdomain.com {
    reverse_proxy bot:8080
}

# Other App
api.yourdomain.com {
    reverse_proxy other-app:3000
}

# Another App
app.yourdomain.com {
    reverse_proxy another-app:3000
}
```

Each app's domain is appended by its deploy workflow. Caddy auto-provisions SSL certs for all domains.

## Verifying Caddy

```bash
# Check Caddy is running
docker ps --filter name=caddy

# View Caddy logs
docker logs caddy

# Reload after manual Caddyfile edits
docker exec caddy caddy reload --config /etc/caddy/Caddyfile

# Check the Caddyfile
cat /opt/caddy/Caddyfile
```

## Troubleshooting

### Domain not resolving to HTTPS

1. Check DNS: `dig your-domain.com` — should point to the VPS IP
2. Check Caddy logs: `docker logs caddy`
3. Check firewall: ports 80 and 443 must be open

### Port conflict (another server on 80/443)

Change Caddy's ports in the deploy step:

```bash
docker run -d --name caddy --restart unless-stopped \
  -p 8080:80 -p 8443:443 \
  ...
```

### Caddy not starting

```bash
# Check if another container is using port 80/443
docker ps --format '{{.Names}} {{.Ports}}'

# Check Caddy logs for errors
docker logs caddy

# Restart Caddy
docker restart caddy
```

### App can't reach Caddy

Ensure your app connects to the `caddy` network:

```bash
# Check if your app is on the caddy network
docker network inspect caddy
```

## Manual Caddy Setup (Without Deploy Workflow)

If you prefer to set up Caddy manually:

```bash
# 1. Create network
docker network create caddy

# 2. Create initial Caddyfile
mkdir -p /opt/caddy
cat > /opt/caddy/Caddyfile << 'EOF'
# Shared Caddyfile
EOF

# 3. Start Caddy
docker run -d --name caddy --restart unless-stopped \
  -p 80:80 -p 443:443 \
  -v /opt/caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v caddy_data:/data \
  -v caddy_config:/config \
  --network caddy \
  caddy:2-alpine

# 4. Add your app's domain
cat >> /opt/caddy/Caddyfile << 'EOF'
your-domain.com {
    reverse_proxy your-app:3000
}
EOF

# 5. Reload Caddy
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```
