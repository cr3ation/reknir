# Cloudflare Deployment Guide for Reknir

This guide explains how to deploy Reknir to a server and make it accessible via Cloudflare. There are two main approaches: **Cloudflare Tunnel** (recommended) and **traditional port forwarding**.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Production Setup](#production-setup)
3. [Option 1: Cloudflare Tunnel (Recommended)](#option-1-cloudflare-tunnel-recommended)
4. [Option 2: Traditional Port Forwarding](#option-2-traditional-port-forwarding)
5. [SSH Access and Port Forwarding](#ssh-access-and-port-forwarding)
6. [Security Considerations](#security-considerations)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Server Requirements
- Linux server (Ubuntu 22.04 LTS recommended)
- Docker and Docker Compose installed
- At least 2GB RAM, 2 CPU cores
- 20GB+ disk space
- Static IP address or dynamic DNS (for Option 2)

### Cloudflare Requirements
- Cloudflare account (free tier works)
- Domain name managed by Cloudflare
- For Cloudflare Tunnel: cloudflared installed

### Software Installation
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Log out and back in for group changes to take effect
```

---

## Production Setup

### 1. Clone Repository on Server
```bash
cd /opt
sudo git clone https://github.com/your-username/reknir.git
sudo chown -R $USER:$USER reknir
cd reknir
```

### 2. Create Production Docker Compose File

Create `docker-compose.prod.yml`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    container_name: reknir-db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-reknir}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # Set in .env file!
      POSTGRES_DB: ${POSTGRES_DB:-reknir}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    # DO NOT expose port 5432 in production unless needed for backups
    # ports:
    #   - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U reknir"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - reknir-internal

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.prod
    container_name: reknir-backend
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-reknir}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-reknir}
      CORS_ORIGINS: ${CORS_ORIGINS}  # Set to your domain
      DEBUG: "False"
      SECRET_KEY: ${SECRET_KEY}  # Generate a strong secret key
    # DO NOT expose port 8000 directly - use reverse proxy
    expose:
      - "8000"
    depends_on:
      postgres:
        condition: service_healthy
    volumes:
      - ./database:/database
      - ./backups:/backups
    restart: unless-stopped
    networks:
      - reknir-internal
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.prod
    container_name: reknir-frontend
    expose:
      - "80"
    depends_on:
      - backend
    restart: unless-stopped
    networks:
      - reknir-internal

  # Nginx reverse proxy
  nginx:
    image: nginx:alpine
    container_name: reknir-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
    networks:
      - reknir-internal

  # Automatic backup service (runs daily at 3 AM)
  backup:
    image: postgres:16-alpine
    container_name: reknir-backup
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-reknir}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB:-reknir}
      BACKUP_DIR: /backups
      BACKUP_KEEP_DAYS: 2555  # 7 years per Swedish law
    volumes:
      - ./backups:/backups
      - ./scripts/backup.sh:/backup.sh
    depends_on:
      - postgres
    entrypoint: /bin/sh -c "while true; do sleep 86400; /backup.sh; done"
    restart: unless-stopped
    networks:
      - reknir-internal

  # Cloudflare Tunnel (optional - for production public access)
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: reknir-cloudflared
    command: tunnel run
    environment:
      TUNNEL_TOKEN: ${TUNNEL_TOKEN}  # Set in .env.prod after creating tunnel
    restart: unless-stopped
    networks:
      - reknir-internal
    depends_on:
      - nginx
    # Note: This container needs no exposed ports!
    # It creates an outbound connection to Cloudflare

volumes:
  postgres_data:
    driver: local

networks:
  reknir-internal:
    driver: bridge
```

### 3. Create Production Dockerfiles

**backend/Dockerfile.prod**:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 reknir && chown -R reknir:reknir /app
USER reknir

# Run migrations and start server
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**frontend/Dockerfile.prod**:
```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build for production
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx config (we'll create this)
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**frontend/nginx.conf**:
```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # SPA routing - serve index.html for all routes
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 4. Create Nginx Reverse Proxy Configuration

Create `nginx/nginx.conf`:

```nginx
events {
    worker_connections 1024;
}

http {
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=general_limit:10m rate=30r/s;

    # Upstream backends
    upstream backend {
        server backend:8000;
    }

    upstream frontend {
        server frontend:80;
    }

    server {
        listen 80;
        server_name _;

        # Security headers
        add_header X-Frame-Options "SAMEORIGIN" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
        add_header Referrer-Policy "strict-origin-when-cross-origin" always;

        # Max upload size for SIE4 files and invoices
        client_max_body_size 10M;

        # API endpoints
        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }

        # API docs
        location /docs {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /redoc {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        # Frontend
        location / {
            limit_req zone=general_limit burst=50 nodelay;

            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    # HTTPS configuration (optional - Cloudflare handles SSL)
    # server {
    #     listen 443 ssl http2;
    #     server_name your-domain.com;
    #
    #     ssl_certificate /etc/nginx/ssl/cert.pem;
    #     ssl_certificate_key /etc/nginx/ssl/key.pem;
    #     ssl_protocols TLSv1.2 TLSv1.3;
    #     ssl_ciphers HIGH:!aNULL:!MD5;
    #
    #     # ... rest of config same as port 80
    # }
}
```

### 5. Create Production Environment File

Create `.env.prod`:

```bash
# Database
POSTGRES_USER=reknir
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD_123!
POSTGRES_DB=reknir

# Backend
SECRET_KEY=GENERATE_A_LONG_RANDOM_SECRET_KEY_HERE
DEBUG=False
CORS_ORIGINS=https://your-domain.com

# Frontend (used during build)
VITE_API_URL=https://your-domain.com

# Backup
BACKUP_KEEP_DAYS=2555

# Cloudflare Tunnel (optional - only needed if using Cloudflare Tunnel in Docker)
TUNNEL_TOKEN=your_tunnel_token_from_cloudflare_dashboard
```

**Generate strong passwords:**
```bash
# Generate PostgreSQL password
openssl rand -base64 32

# Generate secret key
openssl rand -hex 32
```

### 6. Update Frontend API URL

Update `frontend/src/services/api.ts` to use relative URLs in production:

```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || ''
```

Or create `frontend/.env.production`:
```bash
VITE_API_URL=https://your-domain.com
```

---

## Option 1: Cloudflare Tunnel (Recommended)

Cloudflare Tunnel creates a secure outbound connection from your server to Cloudflare without opening any inbound ports. This is the most secure option.

### Advantages
- ✅ No ports need to be opened on your firewall
- ✅ No static IP required
- ✅ Free DDoS protection
- ✅ Automatic SSL/TLS
- ✅ No exposure to port scanners
- ✅ Works behind NAT/firewalls

### Setup Steps

#### Method A: Using Docker (Recommended - Everything Containerized!)

This method keeps cloudflared inside Docker, so you don't need to install anything on your host system.

**1. Create Tunnel via Cloudflare Dashboard**

Go to [Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/):
- Navigate to **Networks** → **Tunnels**
- Click **Create a tunnel**
- Choose **Cloudflared**
- Name it `reknir` and click **Save tunnel**
- **Copy the tunnel token** (long string starting with `eyJ...`)

**2. Configure DNS in Cloudflare Dashboard**

In the tunnel configuration:
- Add a **Public Hostname**:
  - **Subdomain:** (leave empty for root domain or enter subdomain)
  - **Domain:** your-domain.com
  - **Type:** HTTP
  - **URL:** nginx:80 (or http://nginx:80)
- Click **Save**

**3. Add Tunnel Token to .env.prod**

Add to your `.env.prod` file:
```bash
TUNNEL_TOKEN=your_tunnel_token_here
```

**4. Start All Services (Including Cloudflared)**

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

That's it! The cloudflared container will:
- Start automatically with the rest of your services
- Connect to Cloudflare using the tunnel token
- Route traffic from your domain to nginx
- No ports exposed on the host (except SSH)

**5. Verify**

```bash
# Check all containers are running
docker compose -f docker-compose.prod.yml ps

# Check cloudflared logs
docker compose -f docker-compose.prod.yml logs cloudflared
```

Visit `https://your-domain.com` - you should see Reknir!

---

#### Method B: Installing cloudflared on Host (Alternative)

If you prefer to install cloudflared directly on the host system:

**1. Install cloudflared**

```bash
# Ubuntu/Debian
curl -L https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-archive-keyring.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-archive-keyring.gpg] https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt-get update
sudo apt-get install cloudflared
```

**2. Authenticate and Create Tunnel**

```bash
cloudflared tunnel login
cloudflared tunnel create reknir
```

**3. Configure Tunnel**

Create `~/.cloudflared/config.yml`:
```yaml
tunnel: <tunnel-id>
credentials-file: /home/<user>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: your-domain.com
    service: http://localhost:80
  - service: http_status:404
```

**4. Route DNS**

```bash
cloudflared tunnel route dns reknir your-domain.com
```

**5. Start Services**

```bash
# Start Reknir (without cloudflared service in docker-compose)
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Install and start cloudflared as system service
sudo cloudflared service install
sudo systemctl start cloudflared
sudo systemctl enable cloudflared
```

**Note:** With this method, remove or comment out the `cloudflared` service from your `docker-compose.prod.yml`.

---

#### Verify Tunnel Status

**For Docker method:**
```bash
docker compose -f docker-compose.prod.yml logs cloudflared
```

**For host installation:**
```bash
sudo systemctl status cloudflared
sudo journalctl -u cloudflared -f
```

You should see: `Connection <UUID> registered` - this means the tunnel is active!

### Cloudflare Dashboard Settings

1. **SSL/TLS Settings** (in Cloudflare dashboard):
   - SSL/TLS encryption mode: **Full** (not Full Strict, since we're using HTTP internally)
   - Always Use HTTPS: **On**
   - Minimum TLS Version: **TLS 1.2**

2. **Security Settings**:
   - Enable WAF (Web Application Firewall) - Free tier available
   - Enable DDoS protection - Automatic
   - Consider enabling Bot Fight Mode

3. **Speed Settings**:
   - Auto Minify: Enable HTML, CSS, JS
   - Brotli: On
   - Early Hints: On

---

## Option 2: Traditional Port Forwarding

This approach requires opening ports on your firewall and is less secure than Cloudflare Tunnel.

### Required Ports

- **Port 80** (HTTP): Required for initial setup and HTTP challenge
- **Port 443** (HTTPS): Required for secure traffic
- **Port 5432** (PostgreSQL): **DO NOT EXPOSE** - keep internal only

### Firewall Configuration

**UFW (Ubuntu):**
```bash
# Allow SSH (important!)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

**iptables:**
```bash
# Allow HTTP/HTTPS
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Save rules
sudo netfilter-persistent save
```

### Router Configuration

If your server is behind a router:

1. Log into your router's admin panel
2. Find "Port Forwarding" or "Virtual Servers" section
3. Forward these ports to your server's local IP:
   - External Port 80 → Internal IP:80
   - External Port 443 → Internal IP:443

### DNS Configuration

1. Go to Cloudflare dashboard
2. Navigate to DNS settings for your domain
3. Add an A record:
   - **Type:** A
   - **Name:** @ (or subdomain like "reknir")
   - **IPv4 address:** Your server's public IP
   - **Proxy status:** **Proxied** (orange cloud)
   - **TTL:** Auto

### Cloudflare Settings

Same as Cloudflare Tunnel option above.

### Start Services

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### Verify

Visit `https://your-domain.com`

---

## SSH Access and Port Forwarding

### SSH for Server Administration

**SSH (Port 22) must remain open** for server administration, regardless of which deployment option you choose.

**Configure SSH firewall rule:**
```bash
# UFW
sudo ufw allow 22/tcp

# Or limit to specific IP for extra security
sudo ufw allow from YOUR_IP_ADDRESS to any port 22 proto tcp
```

**Best practices:**
- Use SSH keys instead of passwords
- Disable root login
- Change default SSH port (optional but recommended)
- Use fail2ban to prevent brute force attacks

### SSH Port Forwarding for Development/Testing

When developing or testing on a remote server, you can use SSH tunneling to access services locally:

**Forward all Reknir ports to your local machine:**
```bash
ssh -L 5173:localhost:5173 \
    -L 8000:localhost:8000 \
    -L 5432:localhost:5432 \
    user@your-server.com
```

This creates tunnels:
- `localhost:5173` → Remote frontend (Vite dev server)
- `localhost:8000` → Remote backend (FastAPI)
- `localhost:5432` → Remote PostgreSQL (for database tools)

**Access services:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Backend docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432

**Keep tunnel alive:**
```bash
# Add to ~/.ssh/config
Host reknir-server
    HostName your-server.com
    User your-username
    LocalForward 5173 localhost:5173
    LocalForward 8000 localhost:8000
    LocalForward 5432 localhost:5432
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

Then simply:
```bash
ssh reknir-server
```

### SSH Port Forwarding vs Cloudflare Tunnel

**Important distinction:**

| Purpose | Solution | Ports Needed |
|---------|----------|--------------|
| **Server administration** | SSH (port 22) | Port 22 open |
| **Development/testing access** | SSH port forwarding | Port 22 open |
| **Production public access** | Cloudflare Tunnel | No ports open! |
| **Production public access** | Traditional setup | Ports 80, 443 open |

**For production:**
- **With Cloudflare Tunnel:** Only port 22 (SSH) needs to be open. Public access goes through Cloudflare Tunnel (no inbound ports for web traffic).
- **With traditional setup:** Ports 22 (SSH), 80 (HTTP), and 443 (HTTPS) need to be open.

**For development on remote server:**
- Port 22 (SSH) open
- Use SSH port forwarding to access services locally
- No need to expose ports 5173, 8000, or 5432 to the internet

### Security Note: Never Expose These Ports Publicly

**Never open these ports on your firewall for public access:**
- **Port 5432 (PostgreSQL):** Database should NEVER be exposed to the internet
- **Port 5173 (Vite dev server):** Development server, not production-ready
- **Port 8000 (FastAPI without reverse proxy):** Should be behind nginx in production

**These ports are for:**
- Internal Docker network communication (default)
- SSH port forwarding for development/testing (via localhost only)
- Local development on your own machine

### Securing SSH

**Generate SSH key (if you don't have one):**
```bash
# On your local machine
ssh-keygen -t ed25519 -C "your_email@example.com"
```

**Copy key to server:**
```bash
ssh-copy-id user@your-server.com
```

**Disable password authentication:**
```bash
# On server
sudo nano /etc/ssh/sshd_config

# Set these values:
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes

# Restart SSH
sudo systemctl restart sshd
```

**Install fail2ban for brute force protection:**
```bash
sudo apt-get install fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### Example: Development Workflow with SSH Tunneling

```bash
# 1. SSH into server with port forwarding
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 user@your-server.com

# 2. On server, start development environment
cd /opt/reknir
docker compose up -d

# 3. On your local machine (in a new terminal), access:
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8000/docs
# - Test the app just like it was running locally!

# 4. Make changes, test, commit, and push
git add .
git commit -m "Your changes"
git push
```

### Example: Production Access

**With Cloudflare Tunnel (recommended):**
```bash
# SSH for administration only
ssh user@your-server.com

# Public access the app:
# → Users visit: https://your-domain.com
# → Traffic goes through Cloudflare Tunnel
# → No ports open except SSH (22)
```

**With traditional setup:**
```bash
# SSH for administration
ssh user@your-server.com

# Public access the app:
# → Users visit: https://your-domain.com
# → Traffic goes directly to your server via ports 80/443
# → Ports 22, 80, 443 open
```

---

## Security Considerations

### 1. Strong Passwords

```bash
# Generate strong passwords for production
openssl rand -base64 32
```

Update `.env.prod` with strong passwords.

### 2. Firewall Rules

**For Cloudflare Tunnel (recommended):**
```bash
# Deny all except SSH
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH for administration
sudo ufw allow 80/tcp  # HTTP for Cloudflare Tunnel health checks
sudo ufw enable
```

**For Traditional Setup:**
```bash
# Deny all except necessary ports
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH for administration
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw enable
```

**Development/Testing on Remote Server:**
```bash
# Only need SSH - use SSH port forwarding for everything else
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp  # SSH (includes port forwarding)
sudo ufw enable

# Then use SSH tunneling to access services:
# ssh -L 5173:localhost:5173 -L 8000:localhost:8000 user@server
```

### 3. Database Security

**Never expose PostgreSQL port 5432 to the internet!**

Keep database communication internal to Docker network only.

### 4. Regular Updates

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Update Docker images
cd /opt/reknir
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### 5. Backup Strategy

Backups are automatically created daily and stored for 7 years (Swedish law requirement).

**Test your backups regularly:**
```bash
# List backups
ls -lh backups/

# Test restore (on a test database!)
docker compose -f docker-compose.prod.yml exec postgres psql -U reknir -d reknir < backups/reknir_backup_YYYYMMDD.sql
```

**Off-site backup:**
```bash
# Sync backups to cloud storage (example with rclone)
rclone sync /opt/reknir/backups remote:reknir-backups
```

### 6. Monitoring

Set up monitoring for:
- Disk space (backups can grow large)
- Database size
- Container health
- Failed login attempts

### 7. Swedish Data Protection (GDPR)

- Keep backups for 7 years as required by Swedish bookkeeping law
- Consider where your server is hosted (EU/EEA recommended)
- Implement proper access controls
- Regular security audits

### 8. Environment Variables

Never commit `.env.prod` to git!

Add to `.gitignore`:
```bash
echo ".env.prod" >> .gitignore
echo "*.env.prod" >> .gitignore
```

### 9. Rate Limiting

The nginx configuration includes rate limiting:
- API: 10 requests/second (burst 20)
- General: 30 requests/second (burst 50)

Adjust these in `nginx/nginx.conf` based on your needs.

---

## Troubleshooting

### Issue: "Backend är offline"

**Check if containers are running:**
```bash
docker compose -f docker-compose.prod.yml ps
```

**Check logs:**
```bash
# All logs
docker compose -f docker-compose.prod.yml logs

# Specific service
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs nginx
```

**Restart services:**
```bash
docker compose -f docker-compose.prod.yml restart
```

### Issue: CORS Errors

Update `CORS_ORIGINS` in `.env.prod`:
```bash
CORS_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

Restart backend:
```bash
docker compose -f docker-compose.prod.yml restart backend
```

### Issue: Database Connection Failed

**Check database is healthy:**
```bash
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U reknir
```

**Check DATABASE_URL is correct:**
```bash
docker compose -f docker-compose.prod.yml exec backend env | grep DATABASE_URL
```

**Check database logs:**
```bash
docker compose -f docker-compose.prod.yml logs postgres
```

### Issue: Cloudflare Tunnel Not Connecting

**Check tunnel status:**
```bash
cloudflared tunnel info reknir
```

**Check cloudflared logs:**
```bash
sudo journalctl -u cloudflared -f
```

**Verify tunnel configuration:**
```bash
cat ~/.cloudflared/config.yml
```

**Test local connectivity:**
```bash
curl http://localhost:80
```

### Issue: 502 Bad Gateway

This usually means nginx can't reach the backend.

**Check if backend is responding:**
```bash
docker compose -f docker-compose.prod.yml exec nginx curl http://backend:8000
```

**Check nginx logs:**
```bash
docker compose -f docker-compose.prod.yml logs nginx
```

### Issue: SSL/TLS Errors

**Cloudflare SSL mode:**
- Should be set to **Full** (not Full Strict) if using HTTP internally
- Or use **Full (Strict)** if you set up SSL certificates in nginx

**Check Cloudflare SSL/TLS settings:**
- Dashboard → SSL/TLS → Overview
- Ensure encryption mode is correct

### Performance Issues

**Check resource usage:**
```bash
docker stats
```

**Increase backend workers:**

In `docker-compose.prod.yml`, change:
```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Recommended: `workers = (2 × CPU cores) + 1`

### Database Maintenance

**Vacuum database (monthly):**
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U reknir -d reknir -c "VACUUM ANALYZE;"
```

**Check database size:**
```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U reknir -d reknir -c "SELECT pg_size_pretty(pg_database_size('reknir'));"
```

---

## Maintenance Commands

### Update Reknir

```bash
cd /opt/reknir
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod build
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

### View Logs

```bash
# All logs
docker compose -f docker-compose.prod.yml logs -f

# Last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100

# Specific service
docker compose -f docker-compose.prod.yml logs -f backend
```

### Backup Database Manually

```bash
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U reknir reknir > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Restore Database

```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U reknir reknir < backup_20241110_120000.sql
```

### Clean Up Docker

```bash
# Remove unused images
docker image prune -a

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune
```

---

## Quick Start Checklist

### For Cloudflare Tunnel (Docker Method - Recommended):

- [ ] Server with Docker installed
- [ ] Configure SSH access (key-based auth, disable password login)
- [ ] Configure firewall: `sudo ufw allow 22/tcp` (only SSH needed!)
- [ ] Clone repository to `/opt/reknir`
- [ ] Create production Dockerfiles and configs
- [ ] Create `.env.prod` with strong passwords
- [ ] Go to Cloudflare Zero Trust Dashboard → Networks → Tunnels
- [ ] Create tunnel named `reknir` and copy the tunnel token
- [ ] Add tunnel token to `.env.prod` as `TUNNEL_TOKEN=...`
- [ ] Configure Public Hostname in Cloudflare: your-domain.com → http://nginx:80
- [ ] Start all services: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d`
- [ ] Verify: `docker compose -f docker-compose.prod.yml logs cloudflared`
- [ ] Configure Cloudflare dashboard (SSL: Full, Always HTTPS: On)
- [ ] Install fail2ban for SSH protection
- [ ] Test: Visit `https://your-domain.com`

**Note:** No need to install cloudflared on host - it runs in Docker!

### For Traditional Setup:

- [ ] Server with Docker and static IP
- [ ] Configure SSH access (key-based auth, disable password login)
- [ ] Configure firewall: `sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp`
- [ ] Configure port forwarding on router (ports 22, 80, 443)
- [ ] Clone repository to `/opt/reknir`
- [ ] Create production Dockerfiles and configs
- [ ] Create `.env.prod` with strong passwords
- [ ] Add A record in Cloudflare DNS (proxied)
- [ ] Start services: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d`
- [ ] Configure Cloudflare dashboard (SSL: Full, Always HTTPS: On)
- [ ] Install fail2ban for SSH protection
- [ ] Test: Visit `https://your-domain.com`

---

## Support

For issues specific to:
- **Reknir**: Check GitHub issues or create a new one
- **Cloudflare Tunnel**: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- **Docker**: https://docs.docker.com/
- **Cloudflare DNS**: https://developers.cloudflare.com/dns/

---

## Additional Resources

- [Cloudflare Tunnel Documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Nginx Configuration](https://nginx.org/en/docs/)
- [Swedish Bookkeeping Law (Bokföringslagen)](https://www.riksdagen.se/sv/dokument-lagar/dokument/svensk-forfattningssamling/bokforingslag-19991078_sfs-1999-1078)
