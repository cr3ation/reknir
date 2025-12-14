# Reknir - Quick Start Guide

Complete guide for setting up Reknir for development and production.

## Development Setup

### Prerequisites

- **Docker & Docker Compose** - [Install Docker](https://docs.docker.com/get-docker/)

### 1. Start Services

```bash
git clone <repo-url>
cd reknir

# Start all services (database, backend, frontend)
docker compose up -d

# Verify services are running
docker compose ps
```

This starts:
- PostgreSQL database on port 5432
- FastAPI backend on port 8000
- React frontend on port 5173

### 2. Initialize Database

```bash
# Run migrations (usually automatic, but run manually if needed)
docker compose exec backend alembic upgrade head

# Import BAS 2024 kontoplan
docker compose exec backend python -m app.cli seed-bas
```

### 3. Access the Application

- **Frontend**: http://localhost:5173
- **API Docs**: http://localhost:8000/docs

### 4. Stop Services

```bash
# Stop all services
docker compose down

# Stop and delete data (WARNING: removes database!)
docker compose down -v
```

---

## Development Without Docker

For local development with hot-reload:

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Database (start PostgreSQL via Docker or locally)
export DATABASE_URL="postgresql://reknir:reknir@localhost:5432/reknir"
alembic upgrade head

# Start with hot-reload
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Production Deployment

For detailed production setup with HTTPS and Cloudflare Tunnel, see [PRODUCTION.md](PRODUCTION.md).

### Quick Production Start

```bash
# 1. Run setup script
./setup-production.sh

# 2. Deploy
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# 3. Verify
docker compose -f docker-compose.prod.yml logs -f
```

---

## Operations Reference

### Check Status

```bash
# Development
docker compose ps
docker compose logs -f

# Production
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
```

### Restart Services

```bash
# Development
docker compose restart

# Production
docker compose -f docker-compose.prod.yml restart
docker compose -f docker-compose.prod.yml restart backend  # specific service
```

### Database Migrations

```bash
# Development
docker compose exec backend alembic upgrade head
docker compose exec backend alembic current  # check version

# Production
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## Backups

### Create Backup

```bash
# Development
docker compose exec postgres pg_dump -U reknir reknir > backup_$(date +%Y%m%d).sql

# Production
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U reknir reknir | gzip > backups/manual_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Restore Backup

```bash
# Development
docker compose exec -T postgres psql -U reknir reknir < backup_20241109.sql

# Production (stop backend first!)
docker compose -f docker-compose.prod.yml stop backend
gunzip -c backups/backup_file.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres psql -U reknir -d reknir
docker compose -f docker-compose.prod.yml start backend
```

---

## Troubleshooting

### Database Connection Issues

```bash
docker compose ps postgres
docker compose logs postgres
docker compose restart backend  # if database wasn't ready
```

### Backend Not Starting

```bash
docker compose logs backend
# Common: database not ready - wait and restart
docker compose restart backend
```

### Frontend Not Loading

```bash
docker compose logs frontend
docker compose up -d --build frontend  # rebuild if needed
```

### Production: Cloudflare Tunnel Issues

```bash
docker compose -f docker-compose.prod.yml logs cloudflared
# Should see: "Connection <UUID> registered"
# If not: check TUNNEL_TOKEN in .env.prod
```

### Production: 502 Bad Gateway

```bash
docker compose -f docker-compose.prod.yml ps backend
docker compose -f docker-compose.prod.yml logs backend
```

---

## Useful Commands

### Database Shell

```bash
# Development
docker compose exec postgres psql -U reknir -d reknir

# Production
docker compose -f docker-compose.prod.yml exec postgres psql -U reknir -d reknir
```

### Backend Shell

```bash
# Development
docker compose exec backend bash

# Production
docker compose -f docker-compose.prod.yml exec backend bash
```

### Update Application

```bash
git pull
docker compose up -d --build                    # development
docker compose -f docker-compose.prod.yml up -d --build  # production
```

---

## Running Tests

All tests run in Docker - no local Python/Node setup needed.

```bash
# Backend: lint
docker compose exec backend ruff check .

# Backend: format check
docker compose exec backend ruff format --check .

# Backend: run tests
docker compose exec backend pytest -v

# Frontend: lint
docker compose exec frontend npm run lint

# Frontend: type check
docker compose exec frontend npx tsc --noEmit
```

Or rebuild and run tests in a fresh container:

```bash
docker compose build backend
docker compose run --rm backend pytest -v
```

---

## More Documentation

- [README.md](../README.md) - Project overview
- [PRODUCTION.md](PRODUCTION.md) - Detailed production deployment
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [AUTH_SETUP.md](AUTH_SETUP.md) - Authentication configuration
- [CLAUDE.md](CLAUDE.md) - Codebase reference
