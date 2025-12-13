# Reknir - Quick Start Guide

Fast reference for common operations.

## Initial Setup

### First Time Production Deployment

```bash
# 1. Run setup script
./setup-production.sh

# 2. Deploy
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# 3. Watch logs
docker compose -f docker-compose.prod.yml logs -f

# 4. Verify tunnel connected (look for "Connection registered")
docker compose -f docker-compose.prod.yml logs cloudflared | grep -i "registered"

# 5. Visit your domain
# https://your-domain.com
```

---

## Daily Operations

### Check Status

```bash
# All containers
docker compose -f docker-compose.prod.yml ps

# Logs (all services)
docker compose -f docker-compose.prod.yml logs -f

# Logs (specific service)
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
docker compose -f docker-compose.prod.yml logs -f cloudflared
```

### Restart Services

```bash
# All services
docker compose -f docker-compose.prod.yml restart

# Specific service
docker compose -f docker-compose.prod.yml restart backend
docker compose -f docker-compose.prod.yml restart frontend
```

### Stop/Start

```bash
# Stop all
docker compose -f docker-compose.prod.yml stop

# Start all
docker compose -f docker-compose.prod.yml start

# Stop and remove containers
docker compose -f docker-compose.prod.yml down
```

---

## Updates & Maintenance

### Update Application

```bash
# 1. Pull latest code
git pull

# 2. Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# 3. Watch for errors
docker compose -f docker-compose.prod.yml logs -f backend
```

### Update System

```bash
# Update OS packages
sudo apt update && sudo apt upgrade -y

# Update Docker images
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Database Migrations

```bash
# Migrations run automatically on backend startup
# To run manually:
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Check current version
docker compose -f docker-compose.prod.yml exec backend alembic current
```

---

## Backups

### View Backups

```bash
# List all backups
ls -lh backups/

# View latest backup
ls -lt backups/ | head -n 2
```

### Create Manual Backup

```bash
# Create backup now
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U reknir reknir | gzip > backups/manual_$(date +%Y%m%d_%H%M%S).sql.gz

# Verify
ls -lh backups/
```

### Restore Backup

```bash
# ⚠️ WARNING: Overwrites current database!

# 1. Stop backend
docker compose -f docker-compose.prod.yml stop backend

# 2. Restore
gunzip -c backups/reknir_backup_YYYYMMDD_HHMMSS.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U reknir -d reknir

# 3. Start backend
docker compose -f docker-compose.prod.yml start backend
```

---

## Troubleshooting

### Container Not Running

```bash
# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs <service-name>

# Restart
docker compose -f docker-compose.prod.yml restart <service-name>
```

### Cloudflare Tunnel Issues

```bash
# Check tunnel logs
docker compose -f docker-compose.prod.yml logs cloudflared

# Should see: "Connection <UUID> registered"

# If not connected:
# 1. Verify TUNNEL_TOKEN in .env.prod
# 2. Check Cloudflare dashboard (tunnel should be "Healthy")
# 3. Restart cloudflared
docker compose -f docker-compose.prod.yml restart cloudflared
```

### 502 Bad Gateway

```bash
# Check backend is running
docker compose -f docker-compose.prod.yml ps backend

# Check backend logs for errors
docker compose -f docker-compose.prod.yml logs backend

# Test backend health
docker compose -f docker-compose.prod.yml exec nginx curl http://backend:8000/api/health
```

### Database Connection Errors

```bash
# Check postgres is running
docker compose -f docker-compose.prod.yml ps postgres

# Check postgres logs
docker compose -f docker-compose.prod.yml logs postgres

# Test connection
docker compose -f docker-compose.prod.yml exec backend \
  psql -h postgres -U reknir -d reknir -c "SELECT 1;"
```

### Clear Everything and Restart

```bash
# ⚠️ WARNING: This removes all containers and data!

# Stop and remove everything
docker compose -f docker-compose.prod.yml down -v

# Rebuild and start fresh
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Monitoring

### Resource Usage

```bash
# Real-time stats
docker stats

# Disk usage
df -h
docker system df
```

### Health Checks

```bash
# Nginx health
curl http://localhost/health

# API health (from within server)
curl http://localhost:80/api/health

# API health (from internet)
curl https://your-domain.com/api/health
```

---

## Useful Aliases

Add to `~/.bashrc` for quick access:

```bash
# Reknir aliases
alias reknir='cd /path/to/reknir'
alias reknir-logs='docker compose -f docker-compose.prod.yml logs -f'
alias reknir-status='docker compose -f docker-compose.prod.yml ps'
alias reknir-restart='docker compose -f docker-compose.prod.yml restart'
alias reknir-update='cd /path/to/reknir && git pull && docker compose -f docker-compose.prod.yml up -d --build'
alias reknir-backup='docker compose -f docker-compose.prod.yml exec postgres pg_dump -U reknir reknir | gzip > backups/manual_$(date +%Y%m%d_%H%M%S).sql.gz'

# Reload aliases
source ~/.bashrc
```

---

## Emergency Commands

### Force Restart Everything

```bash
docker compose -f docker-compose.prod.yml restart
```

### Rebuild Backend Only

```bash
docker compose -f docker-compose.prod.yml up -d --build --no-deps backend
```

### Rebuild Frontend Only

```bash
docker compose -f docker-compose.prod.yml up -d --build --no-deps frontend
```

### View Backend Shell

```bash
docker compose -f docker-compose.prod.yml exec backend bash
```

### View Database Shell

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U reknir -d reknir
```

---

## Configuration Files

| File | Purpose |
|------|---------|
| `.env.prod` | Production environment variables (secrets) |
| `docker-compose.prod.yml` | Production container orchestration |
| `nginx/nginx.conf` | Reverse proxy and rate limiting |
| `backend/Dockerfile.prod` | Backend production build |
| `frontend/Dockerfile.prod` | Frontend production build |
| `scripts/backup.sh` | Automatic backup script |

---

## Important URLs

| Service | URL |
|---------|-----|
| Production App | https://your-domain.com |
| API Docs | https://your-domain.com/docs |
| Health Check | https://your-domain.com/health |
| Cloudflare Dashboard | https://one.dash.cloudflare.com |

---

## Security Checklist

```bash
# ✅ Verify .env.prod permissions
ls -la .env.prod  # Should be: -rw------- (600)

# ✅ Verify firewall (only SSH)
sudo ufw status  # Should show: 22/tcp ALLOW

# ✅ Verify HTTPS
curl -I https://your-domain.com  # Should show: HTTP/2 200

# ✅ Verify tunnel connected
docker compose -f docker-compose.prod.yml logs cloudflared | grep -i "registered"

# ✅ Verify backups exist
ls -lh backups/  # Should show daily backups
```

---

## Need More Help?

📖 **Detailed Guide**: [PRODUCTION.md](PRODUCTION.md)
📖 **Codebase Guide**: [CLAUDE.md](CLAUDE.md)
📖 **Main README**: [README.md](README.md)

---

**Last Updated**: 2025-01-19
