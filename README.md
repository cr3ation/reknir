# Reknir - Swedish Bookkeeping Software

Modern, self-hosted bookkeeping system for Swedish businesses with full BAS kontoplan support.

## Features

<<<<<<< HEAD
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
=======
### Core Accounting
- ✅ Double-entry bookkeeping (verifikationer) with automatic numbering
- ✅ Swedish BAS 2024 kontoplan (45 accounts)
- ✅ Multiple fiscal years with account chart per year
- ✅ Automatic chart of accounts copying between years
- ✅ Balance sheet and income statement
- ✅ Monthly statistics and reports
- ✅ Transaction locking and audit trail

### Invoicing & Expenses
- ✅ Customer invoices with PDF generation
- ✅ Supplier invoices with attachments
- ✅ Employee expenses with receipt upload and approval workflow
- ✅ Automatic verification generation for invoices and expenses
- ✅ Payment tracking and automated posting

### VAT & Reporting
- ✅ VAT reporting with automatic period calculation (monthly/quarterly/yearly)
- ✅ XML export for Swedish Tax Agency (Skatteverket INK2R format)
- ✅ SIE4 import/export for integration with other accounting software

### Business Management
- ✅ Customer and supplier registry
- ✅ Posting templates with formula support (konteringsmallar)
- ✅ Company settings with logo upload
- ✅ Automatic VAT number calculation
- ✅ Default accounts system

### Tech
- ✅ PostgreSQL with automatic backups (7-year retention)
- ✅ Docker Compose deployment
- ✅ REST API with OpenAPI documentation
- ✅ Onboarding wizard for new companies
>>>>>>> main

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

<<<<<<< HEAD
# Initialize database with BAS kontoplan
docker compose exec backend python -m app.cli seed-bas
=======
# Run database migrations to create tables
docker compose exec backend alembic upgrade head
>>>>>>> main

# Access the application
# Frontend: http://localhost:5173
# API docs: http://localhost:8000/docs

# Follow the onboarding wizard to:
# 1. Create your company
# 2. Set up your fiscal year
# 3. Import BAS kontoplan (optional but recommended)
# 4. Get started with your bookkeeping!
```

## Documentation

| Document | Description |
|----------|-------------|
| [Quick Start](docs/QUICKSTART.md) | Setup guide for development and production |
| [Production Deployment](docs/PRODUCTION.md) | Detailed production deployment with HTTPS |
| [Architecture](docs/ARCHITECTURE.md) | System design and codebase overview |
| [Authentication Setup](docs/AUTH_SETUP.md) | Configure user authentication |
| [Contributing](CONTRIBUTING.md) | CI pipeline, code style, and contribution guidelines |

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
