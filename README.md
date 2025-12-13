# Reknir - Swedish Bookkeeping Software

Modern, self-hosted bookkeeping system for Swedish businesses with full BAS kontoplan support.

## Features

- Swedish BAS 2024 kontoplan
- Double-entry bookkeeping (verifikationer)
- Customer invoices with PDF generation
- Supplier invoices with attachment support
- Employee expense management with receipt uploads
- VAT reporting (momsrapport)
- Balance sheet and income statement
- SIE4 import/export for integration with other accounting software
- Multi-user authentication with role-based access
- PostgreSQL with automatic backups

## Tech Stack

- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Backend**: Python 3.11+ FastAPI + SQLAlchemy + Pydantic
- **Database**: PostgreSQL 16
- **Deployment**: Docker Compose

## Quick Start (Docker)

```bash
# Clone the repository
git clone <repo-url>
cd reknir

# Start all services
docker compose up -d

# Initialize database with BAS kontoplan
docker compose exec backend python -m app.cli seed-bas

# Access the application
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs
```

## Documentation

| Document | Description |
|----------|-------------|
| [Quick Start](docs/QUICKSTART.md) | Setup guide for development and production |
| [Production Deployment](docs/PRODUCTION.md) | Detailed production deployment with HTTPS |
| [Architecture](docs/ARCHITECTURE.md) | System design and codebase overview |
| [Authentication Setup](docs/AUTH_SETUP.md) | Configure user authentication |

## Development Setup

For local development without Docker:

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start PostgreSQL (via Docker or locally)
# Set database URL
export DATABASE_URL="postgresql://reknir:reknir@localhost:5432/reknir"

# Run migrations
alembic upgrade head

# Start development server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

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
├── docs/                 # Documentation
├── docker-compose.yml    # Development containers
└── docker-compose.prod.yml  # Production containers
```

## Swedish Accounting Compliance

This software follows Swedish accounting standards:
- **Bokföringslagen (BFL)**: 7-year retention, chronological recording, audit trails
- **BAS 2024 Kontoplan**: Standard Swedish chart of accounts
- **SIE4 Format**: Standard export format for accountants

## Support

For issues and questions, please open a GitHub issue.

## License

BSD 3-Clause License - see LICENSE file
