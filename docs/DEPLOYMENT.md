# Reknir Production Deployment Guide

Complete guide for deploying Reknir to production with Cloudflare Tunnel and nginx.

## Architecture

```
Internet → Cloudflare Tunnel → nginx (port 80) → {
    /api/* → Backend (FastAPI on port 8000)
    /*     → Frontend (Vite on port 5173)
}
```

**Single hostname setup**: All traffic goes through one domain (e.g., `reknir.yourdomain.com`)

## Prerequisites

- Ubuntu 24.04 LTS server (VM or bare metal)
- Domain managed by Cloudflare
- Minimum 4GB RAM, 2 CPU cores, 32GB disk

## Step 1: Prepare Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Install cloudflared
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared -y

# Install useful tools
sudo apt install htop ncdu curl wget -y
```

## Step 2: Clone Repository

```bash
cd ~
git clone https://github.com/joakimeriksson/reknir.git
cd reknir

# Checkout your branch (or use main)
git checkout claude/multi-user-admin-setup-011CV5Th44NuvaSjAxfG9EVP
```

## Step 3: Configure Environment

```bash
# Create production environment file
cp .env.production.example .env.production

# Edit with your values
nano .env.production
```

**Required changes in `.env.production`:**
- `POSTGRES_PASSWORD`: Strong password for database
- `SECRET_KEY`: Generate with `openssl rand -hex 32`
- `CORS_ORIGINS`: Your domain (e.g., `https://reknir.yourdomain.com`)

**Create frontend environment:**
```bash
cat > frontend/.env << 'EOF'
VITE_API_URL=/api
EOF
```

## Step 4: Setup Cloudflare Tunnel

### Option A: Dashboard Method (Recommended)

1. **Go to Cloudflare Dashboard**:
   - Navigate to: **Zero Trust** → **Networks** → **Tunnels**
   - Click **Create a tunnel**

2. **Configure Tunnel**:
   - Name: `reknir-prod`
   - Save tunnel

3. **Add Public Hostname**:
   - Subdomain: `reknir` (or your choice)
   - Domain: Select your domain
   - Service Type: `HTTP`
   - URL: `localhost:80`
   - Save

4. **Install Connector**:
   - Copy the docker run command from the dashboard
   - It will look like:
   ```bash
   docker run -d --name cloudflared-tunnel \
     --restart=unless-stopped \
     --network host \
     cloudflare/cloudflared:latest tunnel run \
     --token eyJhIjoiXXXXXXXXXXXXXXXX...
   ```
   - Run this command on your server

### Option B: CLI Method

```bash
# Login to Cloudflare
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create reknir-prod

# Add DNS route (replace yourdomain.com)
cloudflared tunnel route dns reknir-prod reknir.yourdomain.com

# Create config
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <tunnel-id-from-create-command>
credentials-file: /home/<username>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: reknir.yourdomain.com
    service: http://localhost:80
  - service: http_status:404
EOF

# Install as service
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

## Step 5: Start Services

```bash
cd ~/reknir

# Start production stack
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Check all containers are running
docker compose -f docker-compose.prod.yml ps

# You should see:
# - reknir-db         (postgres)
# - reknir-backend    (fastapi)
# - reknir-frontend   (vite)
# - reknir-nginx      (nginx reverse proxy)
# - reknir-backup     (backup service)
```

## Step 6: Initialize Database

```bash
# Run migrations
docker exec reknir-backend alembic upgrade head

# Verify database
docker exec reknir-db psql -U reknir -d reknir -c "SELECT count(*) FROM alembic_version;"
```

## Step 7: Verify Deployment

```bash
# Check tunnel is connected
cloudflared tunnel list
# Should show connections for reknir-prod

# Check local services
curl http://localhost/health          # Should return "healthy"
curl http://localhost/api/docs        # Should return HTML
curl http://localhost/                # Should return HTML

# Check containers
docker compose -f docker-compose.prod.yml logs --tail=50

# Monitor resources
docker stats
```

## Step 8: Access Application

Visit your domain: `https://reknir.yourdomain.com`

- **Frontend**: `https://reknir.yourdomain.com/`
- **API Docs**: `https://reknir.yourdomain.com/docs`
- **Health Check**: `https://reknir.yourdomain.com/health`

## Post-Deployment

### Setup Automated Backups

Backups run automatically daily at 3 AM. To manually backup:

```bash
# Create backup script
cat > ~/manual-backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="$HOME/reknir/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup database
docker exec reknir-db pg_dump -U reknir reknir | gzip > "$BACKUP_DIR/manual_db_$DATE.sql.gz"

# Backup files
tar -czf "$BACKUP_DIR/manual_files_$DATE.tar.gz" -C ~/reknir receipts invoices

echo "Backup completed: $DATE"
ls -lh "$BACKUP_DIR"/manual_*
EOF

chmod +x ~/manual-backup.sh

# Run manual backup
~/manual-backup.sh
```

### Monitoring

```bash
# Watch logs in real-time
docker compose -f docker-compose.prod.yml logs -f

# Check specific service
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx

# Check resource usage
docker stats
htop

# Check disk usage
df -h
du -sh ~/reknir/*
```

### Updates

```bash
cd ~/reknir

# Pull latest code
git pull

# Rebuild and restart
docker compose -f docker-compose.prod.yml --env-file .env.production down
docker compose -f docker-compose.prod.yml --env-file .env.production build --no-cache
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Run migrations
docker exec reknir-backend alembic upgrade head
```

## Security

### Firewall Setup

```bash
# Enable firewall (only SSH needed - cloudflared uses outbound only)
sudo ufw allow 22/tcp
sudo ufw enable
sudo ufw status
```

### SSH Hardening

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Recommended settings:
# PermitRootLogin no
# PasswordAuthentication no  (if using SSH keys)
# Port 22  (or change to non-standard port)

# Restart SSH
sudo systemctl restart sshd
```

### Regular Updates

```bash
# Create update script
cat > ~/update-system.sh << 'EOF'
#!/bin/bash
echo "=== System Update $(date) ==="
sudo apt update && sudo apt upgrade -y
sudo apt autoremove -y

echo "=== Docker Update ==="
cd ~/reknir
docker compose -f docker-compose.prod.yml --env-file .env.production pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

echo "=== Cleanup ==="
docker system prune -f

echo "=== Done ==="
EOF

chmod +x ~/update-system.sh

# Schedule weekly updates (optional)
# crontab -e
# Add: 0 3 * * 0 /home/user/update-system.sh >> /home/user/update.log 2>&1
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs

# Check specific service
docker compose -f docker-compose.prod.yml logs backend

# Restart specific service
docker compose -f docker-compose.prod.yml restart backend
```

### Database Connection Issues

```bash
# Check database is running
docker compose -f docker-compose.prod.yml ps postgres

# Connect to database
docker exec -it reknir-db psql -U reknir -d reknir

# Check database size
docker exec reknir-db psql -U reknir -d reknir -c "SELECT pg_size_pretty(pg_database_size('reknir'));"
```

### Tunnel Not Working

```bash
# Check tunnel status
cloudflared tunnel list
cloudflared tunnel info reknir-prod

# Restart tunnel (if using docker)
docker restart cloudflared-tunnel

# Or restart service
sudo systemctl restart cloudflared

# Check tunnel logs
docker logs cloudflared-tunnel
# Or
sudo journalctl -u cloudflared -f
```

### 502 Bad Gateway

```bash
# Check nginx is running
docker compose -f docker-compose.prod.yml ps nginx

# Check nginx logs
docker compose -f docker-compose.prod.yml logs nginx

# Check backend is accessible from nginx
docker exec reknir-nginx wget -O- http://backend:8000/docs

# Restart nginx
docker compose -f docker-compose.prod.yml restart nginx
```

### High Resource Usage

```bash
# Check resource usage
docker stats

# Check disk space
df -h
du -sh ~/reknir/* | sort -h

# Clean old backups (keeps last 30 days)
find ~/reknir/backups -name "*.gz" -mtime +30 -delete

# Clean docker
docker system prune -a --volumes
```

## Performance Tuning

### Nginx Worker Processes

Edit `nginx/nginx.conf`:
```nginx
events {
    worker_connections 2048;  # Increase for high traffic
}
```

### Backend Workers

Edit `docker-compose.prod.yml`:
```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Recommended workers: `(CPU cores * 2) + 1`

### Database Connection Pooling

Add to backend environment in `docker-compose.prod.yml`:
```yaml
environment:
  DB_POOL_SIZE: 20
  DB_MAX_OVERFLOW: 10
```

## Maintenance

### Daily Tasks
- Check `docker compose -f docker-compose.prod.yml ps` - all services running
- Monitor disk space: `df -h`
- Check logs for errors: `docker compose -f docker-compose.prod.yml logs --tail=100`

### Weekly Tasks
- Review backups: `ls -lh ~/reknir/backups/`
- Update system: `sudo apt update && sudo apt upgrade -y`
- Check resource usage: `docker stats`

### Monthly Tasks
- Update Docker images: Pull and rebuild
- Review and clean old backups
- Check security updates

## Support

For issues or questions:
- Check logs: `docker compose -f docker-compose.prod.yml logs`
- Review this guide
- Check GitHub issues: https://github.com/joakimeriksson/reknir/issues

## License

See LICENSE file in repository.
