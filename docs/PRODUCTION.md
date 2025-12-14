# Reknir - Production Deployment Guide

Complete guide for deploying Reknir to production with Cloudflare Tunnel on a single server.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
- [Cloudflare Tunnel Configuration](#cloudflare-tunnel-configuration)
- [Deployment](#deployment)
- [Post-Deployment](#post-deployment)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [Backup & Recovery](#backup--recovery)

---

## Overview

This production setup uses:
- **Docker Compose** for container orchestration
- **Cloudflare Tunnel** for secure HTTPS access (no exposed ports!)
- **Nginx** as reverse proxy and gateway
- **PostgreSQL** with automatic backups
- **Production-optimized** builds for frontend and backend

### Key Benefits
✅ **No open ports** - Only SSH needed (port 22)
✅ **Free HTTPS** - Automatic SSL via Cloudflare
✅ **DDoS protection** - Cloudflare edge network
✅ **Automatic backups** - Daily PostgreSQL dumps (7 years retention)
✅ **Rate limiting** - Built into nginx configuration

---

## Architecture

```
Internet
   ↓
Cloudflare Edge Network (HTTPS, DDoS protection)
   ↓
Cloudflare Tunnel (encrypted)
   ↓
Your Server (no exposed ports except SSH)
   ↓
   └─> Nginx Gateway (port 80, internal only)
        ├─> /api → Backend (FastAPI on port 8000)
        └─> /    → Frontend (Nginx serving static React build)
```

### Container Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    reknir-internal network              │
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                  │
│  │  PostgreSQL  │◄───│   Backend    │                  │
│  │  (port 5432) │    │  (port 8000) │                  │
│  └──────┬───────┘    └──────▲───────┘                  │
│         │                     │                          │
│         │              ┌──────┴───────┐                 │
│  ┌──────▼───────┐     │   Frontend   │                 │
│  │    Backup    │     │  (port 80)   │                 │
│  │   Service    │     └──────▲───────┘                 │
│  └──────────────┘            │                          │
│                        ┌─────┴────────┐                 │
│                        │  Nginx       │                 │
│                        │  Gateway     │                 │
│                        │  (port 80)   │                 │
│                        └─────▲────────┘                 │
│                              │                           │
│                    ┌─────────┴────────┐                 │
│                    │  Cloudflared     │                 │
│                    │  (no ports)      │                 │
│                    └─────────▲────────┘                 │
└──────────────────────────────┼──────────────────────────┘
                               │
                    Cloudflare Tunnel (encrypted)
                               │
                          Internet
```

---

## Prerequisites

### 1. Server Requirements

**Minimum:**
- 2 CPU cores
- 4 GB RAM
- 20 GB SSD storage
- Ubuntu 22.04 LTS or similar

**Recommended:**
- 4 CPU cores
- 8 GB RAM
- 50 GB SSD storage

### 2. Domain Requirements

- A domain managed by Cloudflare (free tier works!)
- Access to Cloudflare dashboard
- DNS pointed to Cloudflare nameservers

### 3. Software Requirements

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installation
docker --version
docker compose version
```

---

## Initial Setup

### Step 1: Clone Repository

```bash
# Clone the repository
git clone <your-repo-url> reknir
cd reknir
```

### Step 2: Run Setup Script

The interactive setup script will guide you through configuration:

```bash
# Make script executable
chmod +x setup-production.sh

# Run setup script
./setup-production.sh
```

The script will:
1. Prompt for your domain name
2. Generate secure database password
3. Generate application secret key
4. Guide you through Cloudflare Tunnel creation
5. Create `.env.prod` file with all configuration

**Manual Setup (Alternative)**

If you prefer manual setup:

```bash
# Copy example environment file
cp .env.prod.example .env.prod

# Generate secure passwords
openssl rand -base64 32  # For POSTGRES_PASSWORD
openssl rand -hex 32     # For SECRET_KEY

# Edit .env.prod and fill in all values
nano .env.prod
```

### Step 3: Secure Environment File

```bash
# Set restrictive permissions
chmod 600 .env.prod

# Verify it's in .gitignore (should already be there)
grep .env.prod .gitignore
```

---

## Cloudflare Tunnel Configuration

### Step 1: Create Tunnel

1. Go to [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com)
2. Navigate to **Networks** → **Tunnels**
3. Click **Create a tunnel**
4. Select **Cloudflared**
5. Name it: `reknir`
6. Click **Save tunnel**
7. **Copy the tunnel token** (starts with `eyJ...`)

### Step 2: Configure Public Hostname

In the Cloudflare Tunnel configuration:

1. **Public Hostname** section
2. **Subdomain**: (leave empty for root domain or enter subdomain)
3. **Domain**: Select your domain (e.g., `reknir.botbox.se`)
4. **Type**: `HTTP`
5. **URL**: `nginx:80` ⚠️ Important - this is the internal container name!
6. Click **Save hostname**

### Step 3: Add Token to Environment

```bash
# Edit .env.prod
nano .env.prod

# Add your token
TUNNEL_TOKEN=eyJhIjoiZDk5ZWVjN2VhOWFhNDkxNjQyOTk2MWEzMzUwMzRkYzciLCJ0IjoiYjA0MDhiMDctN2VjMC00NjMyLTliZDEtNDcwZDdmNjc0MjY5IiwicyI6Ik9XTTFOelJtT0RndE5EWmxZeTAwTWpjekxUaGlaRFF0WVdJeU9XRmtaVFZoT0dReiJ9
```

### Step 4: Configure Cloudflare SSL

1. Go to **SSL/TLS** → **Overview**
2. Set encryption mode to: **Full** (not Full Strict)
3. Enable **Always Use HTTPS**
4. Set **Minimum TLS Version**: TLS 1.2

---

## Deployment

### Build and Start Services

```bash
# Build and start all containers
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# This will start:
# - postgres (database)
# - backend (FastAPI with migrations)
# - frontend (nginx serving React build)
# - nginx (reverse proxy gateway)
# - cloudflared (Cloudflare tunnel)
# - backup (daily PostgreSQL backups)
```

### Monitor Deployment

```bash
# Watch all logs
docker compose -f docker-compose.prod.yml logs -f

# Watch specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f cloudflared

# Check all containers are running
docker compose -f docker-compose.prod.yml ps
```

### Verify Cloudflare Tunnel

```bash
# Check cloudflared logs
docker compose -f docker-compose.prod.yml logs cloudflared

# Look for this message:
# "Connection <UUID> registered"
```

If you see "Connection registered", the tunnel is working! 🎉

---

## Post-Deployment

### 1. Test Application

Visit your domain (e.g., `https://reknir.botbox.se`)

You should see:
- ✅ HTTPS padlock in browser
- ✅ Reknir login/dashboard page
- ✅ No certificate warnings

### 2. Test API

```bash
# Test API endpoint
curl https://your-domain.com/api/health

# Should return: {"status": "healthy"}
```

### 3. Initialize Database (First Time Only)

```bash
# Seed BAS kontoplan if needed
docker compose -f docker-compose.prod.yml exec backend python -m app.cli seed-bas
```

### 4. Configure Firewall

Since everything goes through Cloudflare Tunnel, you only need SSH:

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

**No other ports needed!** 🔒

### 5. Create Admin User (if applicable)

```bash
# If your app has user management
docker compose -f docker-compose.prod.yml exec backend python -m app.cli create-admin
```

---

## Maintenance

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100
```

### Restart Services

```bash
# Restart all services
docker compose -f docker-compose.prod.yml restart

# Restart specific service
docker compose -f docker-compose.prod.yml restart backend
```

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# Check logs
docker compose -f docker-compose.prod.yml logs -f
```

### Stop Services

```bash
# Stop all services
docker compose -f docker-compose.prod.yml down

# Stop and remove volumes (⚠️ DANGER - deletes database!)
docker compose -f docker-compose.prod.yml down -v
```

### Database Migrations

Database migrations run automatically on backend startup, but you can run them manually:

```bash
# Run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Check current version
docker compose -f docker-compose.prod.yml exec backend alembic current

# View migration history
docker compose -f docker-compose.prod.yml exec backend alembic history
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Check logs for errors
docker compose -f docker-compose.prod.yml logs <service-name>

# Common issues:
# - Environment variables not set correctly
# - Database not ready (wait for healthcheck)
# - Port conflicts (check with: sudo netstat -tulpn)
```

### Cloudflare Tunnel Not Connecting

```bash
# Check cloudflared logs
docker compose -f docker-compose.prod.yml logs cloudflared

# Common issues:
# - Wrong tunnel token (check .env.prod)
# - Network connectivity issues
# - Tunnel deleted in Cloudflare dashboard

# Restart cloudflared
docker compose -f docker-compose.prod.yml restart cloudflared
```

### 502 Bad Gateway

This usually means nginx can't reach the backend:

```bash
# Check backend is running
docker compose -f docker-compose.prod.yml ps backend

# Check backend logs
docker compose -f docker-compose.prod.yml logs backend

# Check nginx logs
docker compose -f docker-compose.prod.yml logs nginx

# Verify network
docker compose -f docker-compose.prod.yml exec nginx ping -c 3 backend
```

### Database Connection Errors

```bash
# Check PostgreSQL is running
docker compose -f docker-compose.prod.yml ps postgres

# Check PostgreSQL logs
docker compose -f docker-compose.prod.yml logs postgres

# Test connection from backend
docker compose -f docker-compose.prod.yml exec backend psql -h postgres -U reknir -d reknir -c "SELECT 1;"
```

### Frontend Shows Blank Page

```bash
# Check browser console for errors (F12)

# Common issues:
# - VITE_API_URL incorrect (should be /api)
# - CORS issues (check backend CORS_ORIGINS)
# - Frontend build failed

# Rebuild frontend
docker compose -f docker-compose.prod.yml up -d --build frontend
```

### Check Container Health

```bash
# View container details
docker compose -f docker-compose.prod.yml ps

# Inspect specific container
docker inspect reknir-backend

# Check resource usage
docker stats
```

---

## Security

### Best Practices

✅ **Firewall**: Only port 22 (SSH) exposed
✅ **HTTPS**: Automatic via Cloudflare
✅ **Secrets**: Stored in .env.prod (chmod 600)
✅ **Updates**: Regular security updates
✅ **Backups**: Encrypted off-site storage
✅ **Rate Limiting**: Built into nginx config

### Security Checklist

```bash
# 1. Verify .env.prod permissions
ls -la .env.prod  # Should show: -rw------- (600)

# 2. Verify .env.prod is not in git
git status .env.prod  # Should be ignored

# 3. Check firewall status
sudo ufw status

# 4. Verify HTTPS is working
curl -I https://your-domain.com

# 5. Test rate limiting
for i in {1..50}; do curl https://your-domain.com/api/health; done
```

### Update System Packages

```bash
# Update system
sudo apt update
sudo apt upgrade -y

# Update Docker images
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Rotate Secrets

```bash
# Generate new secrets
openssl rand -hex 32  # New SECRET_KEY
openssl rand -base64 32  # New POSTGRES_PASSWORD

# Update .env.prod
nano .env.prod

# Restart services
docker compose -f docker-compose.prod.yml up -d --force-recreate
```

---

## Backup & Recovery

### Automatic Backups

Backups run automatically daily at 3 AM:

- **Location**: `./backups/`
- **Format**: `reknir_backup_YYYYMMDD_HHMMSS.sql.gz`
- **Retention**: 2555 days (7 years - Swedish law)
- **Compression**: gzip

```bash
# Check backup files
ls -lh backups/

# View backup service logs
docker compose -f docker-compose.prod.yml logs backup
```

### Manual Backup

```bash
# Create immediate backup
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U reknir reknir | gzip > backups/manual_backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Verify backup
ls -lh backups/
```

### Restore from Backup

```bash
# ⚠️ WARNING: This will overwrite current database!

# Stop backend
docker compose -f docker-compose.prod.yml stop backend

# Restore backup
gunzip -c backups/reknir_backup_20250119_030000.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U reknir -d reknir

# Restart backend
docker compose -f docker-compose.prod.yml start backend
```

### Off-Site Backup

**Recommended**: Store backups off-site for disaster recovery.

```bash
# Example: rsync to remote server
rsync -avz --delete ./backups/ user@backup-server:/backups/reknir/

# Example: Upload to cloud storage (AWS S3)
aws s3 sync ./backups/ s3://my-bucket/reknir-backups/ --storage-class GLACIER

# Example: Encrypted backup to cloud
tar czf - ./backups/ | \
  gpg --encrypt --recipient you@email.com | \
  aws s3 cp - s3://my-bucket/reknir-encrypted.tar.gz.gpg
```

### Backup Verification

```bash
# Test restore in separate container
docker run --rm -e POSTGRES_PASSWORD=test postgres:16-alpine \
  bash -c "psql -U postgres -c 'CREATE DATABASE test;' && \
  gunzip -c /backups/latest.sql.gz | psql -U postgres test"
```

---

## Monitoring

### Health Checks

```bash
# Nginx health endpoint
curl http://localhost/health

# API health endpoint
curl https://your-domain.com/api/health

# Check all containers
docker compose -f docker-compose.prod.yml ps
```

### Resource Monitoring

```bash
# Real-time resource usage
docker stats

# Disk usage
df -h
docker system df

# Check logs size
du -sh /var/lib/docker/containers/*/
```

### Log Rotation

```bash
# Configure Docker log rotation
sudo nano /etc/docker/daemon.json
```

Add:
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
# Restart Docker
sudo systemctl restart docker
```

---

## Performance Tuning

### Backend Workers

Backend runs with 4 workers by default. Adjust based on CPU:

```dockerfile
# backend/Dockerfile.prod
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Rule of thumb**: (2 x CPU cores) + 1

### PostgreSQL Tuning

```bash
# Edit postgres settings (for large databases)
# Add to docker-compose.prod.yml postgres environment:
POSTGRES_SHARED_BUFFERS: 256MB
POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB
POSTGRES_WORK_MEM: 16MB
```

### Nginx Caching

Already configured in `nginx/nginx.conf`:
- Static assets: 1 year cache
- API responses: no cache
- Rate limiting: 10 req/s for API, 30 req/s general

---

## Cost Estimation

### Free Tier (Recommended for Start)

- **Server**: $5-10/month (DigitalOcean, Hetzner, etc.)
- **Cloudflare**: Free (includes tunnel, DDoS, SSL)
- **Domain**: $10-15/year
- **Total**: ~$5-10/month

### Scaling Up

As you grow:
- Upgrade server resources
- Add Redis for caching
- Add more backend workers
- Consider managed PostgreSQL

---

## Support & Resources

### Documentation

- Main README: [`README.md`](../README.md)
- Codebase Guide: [`CLAUDE.md`](CLAUDE.md)
- Setup Scripts: `setup-production.sh`

### Useful Commands

```bash
# Quick reference
docker compose -f docker-compose.prod.yml ps        # Status
docker compose -f docker-compose.prod.yml logs -f    # Logs
docker compose -f docker-compose.prod.yml restart    # Restart
docker compose -f docker-compose.prod.yml exec backend bash  # Shell

# Shortcuts (add to ~/.bashrc)
alias reknir-logs='docker compose -f docker-compose.prod.yml logs -f'
alias reknir-status='docker compose -f docker-compose.prod.yml ps'
alias reknir-restart='docker compose -f docker-compose.prod.yml restart'
```

### Getting Help

1. Check this documentation
2. Review logs: `docker compose -f docker-compose.prod.yml logs`
3. Check Cloudflare Tunnel status in dashboard
4. Open GitHub issue with logs and error messages

---

## License

BSD 3-Clause License - See LICENSE file for details

---

**Last Updated**: 2025-01-19
**Version**: 1.0.0
