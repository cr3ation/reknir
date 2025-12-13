# Nginx Reverse Proxy Configuration

This directory contains nginx configuration for production deployment.

## Files

- **nginx.conf**: Main reverse proxy configuration
  - Routes `/api/*` → Backend (FastAPI on port 8000)
  - Routes `/*` → Frontend (Vite on port 5173)
  - Includes rate limiting, security headers, and health checks

## Configuration Details

### Routing

- `http://yourdomain.com/` → Frontend React app
- `http://yourdomain.com/api/` → Backend API
- `http://yourdomain.com/docs` → FastAPI documentation
- `http://yourdomain.com/health` → Health check endpoint

### Security Features

- Rate limiting (API: 10 req/s, General: 30 req/s)
- Security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- CORS support
- 20MB upload limit for receipts/invoices

### SSL/TLS

For Cloudflare Tunnel: SSL is handled automatically by Cloudflare (recommended).

For traditional setup: Use Let's Encrypt or Cloudflare Origin Certificates.

## Usage

Nginx is included in `docker-compose.prod.yml` and runs automatically.

To test configuration:
```bash
docker exec reknir-nginx nginx -t
```

To reload configuration:
```bash
docker exec reknir-nginx nginx -s reload
```

## Monitoring

View nginx logs:
```bash
docker compose -f docker-compose.prod.yml logs nginx
```

Check health:
```bash
curl http://localhost/health
```

