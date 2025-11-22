# Reknir - Swedish Bookkeeping Software

Modern, self-hosted bookkeeping system for Swedish businesses with full BAS kontoplan support.

## Features (MVP)

- ✅ Swedish BAS 2024 kontoplan
- ✅ Double-entry bookkeeping (verifikationer)
- ✅ Transaction management with audit trail
- ✅ Balance sheet and income statement
- ✅ SIE4 export for årsredovisning
- ✅ PostgreSQL with automatic backups

## Tech Stack

- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Backend**: Python 3.11+ FastAPI + SQLAlchemy + Pydantic
- **Database**: PostgreSQL 16
- **Deployment**: Docker Compose

## Quick Start

### Prerequisites
- Docker and Docker Compose
- (For development: Node.js 18+, Python 3.11+)

### Development Setup (Local)

```bash
# Clone the repository
git clone <repo-url>
cd reknir

# Start all services
docker-compose up -d

# Initialize database with BAS kontoplan
docker-compose exec backend python -m app.cli seed-bas

# Access the application
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
```

### Production Deployment

For production deployment with Cloudflare Tunnel, HTTPS, and automatic backups:

📖 **See [PRODUCTION.md](PRODUCTION.md) for complete production deployment guide**

Quick production start:
```bash
# Run interactive setup script
./setup-production.sh

# Deploy with production configuration
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

### Development Setup

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up database
export DATABASE_URL="postgresql://reknir:reknir@localhost:5432/reknir"
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Database Backups

Automatic daily backups are configured in Docker Compose:
- Location: `./backups/`
- Retention: 7 years (Swedish law requirement)
- Manual backup: `docker-compose exec postgres pg_dump -U reknir reknir > backup.sql`

## Project Structure

```
reknir/
├── frontend/              # React + TypeScript frontend
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── pages/        # Page components
│   │   ├── services/     # API clients
│   │   └── types/        # TypeScript types
│   └── package.json
├── backend/              # Python FastAPI backend
│   ├── app/
│   │   ├── models/       # SQLAlchemy models
│   │   ├── routers/      # API endpoints
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── main.py       # FastAPI app
│   ├── alembic/          # Database migrations
│   └── requirements.txt
├── database/
│   └── seeds/            # Initial data (BAS kontoplan)
├── docker-compose.yml
└── README.md
```

## Configuration

Environment variables (see `.env.example`):

- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: For future auth (currently not used)
- `CORS_ORIGINS`: Allowed frontend origins

## Swedish Accounting Compliance

This software follows Swedish accounting standards:
- **Bokföringslagen (BFL)**: 7-year retention, chronological recording, audit trails
- **BAS 2024 Kontoplan**: Standard Swedish chart of accounts
- **SIE4 Format**: Standard export format for accountants

## Support

For issues and questions, please open a GitHub issue.

## License

MIT License - see LICENSE file
