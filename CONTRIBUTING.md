# Contributing to Reknir

Thank you for your interest in contributing to Reknir! This guide will help you get started and ensure your contributions pass our CI checks.

## CI Pipeline Overview

Every pull request to `main` runs automated checks via GitHub Actions. All checks must pass before merging.

### What CI Checks

| Job | Checks | Commands |
|-----|--------|----------|
| **Backend** | Linting, formatting, tests | `ruff check .`, `ruff format --check .`, `pytest` |
| **Frontend** | Linting, type checking, build | `npm run lint`, `tsc --noEmit`, `npm run build` |
| **Docker Compose** | Full stack build | `docker compose build` |

## Running Checks Locally

Always run these checks before pushing to avoid CI failures.

### Backend (Python)

```bash
cd backend

# Build the Docker image
docker build -t reknir-backend .

# Run linting
docker run --rm reknir-backend ruff check .

# Check formatting
docker run --rm reknir-backend ruff format --check .

# Auto-fix linting issues
docker run --rm -v $(pwd):/app reknir-backend ruff check . --fix

# Auto-format code
docker run --rm -v $(pwd):/app reknir-backend ruff format .

# Run tests
docker run --rm -e SECRET_KEY=test-secret reknir-backend pytest -v
```

Or without Docker (requires Python 3.11+):

```bash
cd backend
pip install ruff pytest pytest-asyncio httpx
ruff check .
ruff format --check .
pytest -v
```

### Frontend (TypeScript/React)

```bash
cd frontend

# Build the Docker image
docker build -t reknir-frontend .

# Run ESLint
docker run --rm reknir-frontend npm run lint

# Type check
docker run --rm reknir-frontend npx tsc --noEmit

# Build
docker run --rm reknir-frontend npm run build
```

Or without Docker:

```bash
cd frontend
npm install
npm run lint
npx tsc --noEmit
npm run build
```

## Code Style Guidelines

### Frontend (TypeScript/React)

Our ESLint configuration enforces the following rules:

#### 1. Avoid `any` Type (Warning)

Use proper TypeScript types instead of `any`. If you must use `any`, consider using a more specific type or creating an interface.

```typescript
// Bad
function handleError(error: any) { ... }

// Good
interface ApiError {
  response?: {
    data?: {
      detail?: string
    }
  }
}
function handleError(error: ApiError) { ... }
```

For error handling in catch blocks, use our utility function:

```typescript
import { getErrorMessage } from '@/utils/errors'

try {
  await api.call()
} catch (error) {
  // Use the utility instead of error: any
  alert(getErrorMessage(error, 'Default error message'))
}
```

#### 2. useEffect Dependencies (Warning)

Always include all dependencies in useEffect, or use useCallback for functions:

```typescript
// Bad - missing dependency warning
useEffect(() => {
  loadData()
}, [selectedCompany])  // loadData is missing

// Good - use useCallback
const loadData = useCallback(async () => {
  // ... implementation
}, [selectedCompany])

useEffect(() => {
  loadData()
}, [loadData])
```

#### 3. Unused Variables (Error)

Remove unused imports and variables. Prefix intentionally unused parameters with underscore:

```typescript
// Error - unused variable
const unused = 'value'

// OK - underscore prefix for intentionally unused
function callback(_event: Event, data: Data) {
  console.log(data)
}
```

### Backend (Python)

Ruff enforces PEP 8 style with some additional rules. Key points:

- Line length: 88 characters (Black default)
- Use type hints for function arguments and return values
- Import sorting is automatic (use `ruff format`)

```python
# Good
async def get_company(company_id: int, db: Session) -> Company:
    """Fetch a company by ID."""
    return db.query(Company).filter(Company.id == company_id).first()
```

## Common CI Failures and Fixes

### Frontend: "Unexpected any. Specify a different type"

**Problem**: Using `any` type explicitly.

**Fix**: Create a proper interface or use the `getErrorMessage` utility for error handling.

### Frontend: "React Hook useEffect has a missing dependency"

**Problem**: A function or variable used in useEffect is not in the dependency array.

**Fix**: Either add the dependency or wrap the function in `useCallback`:

```typescript
const loadData = useCallback(async () => {
  // Your async logic
}, [dependency1, dependency2])

useEffect(() => {
  loadData()
}, [loadData])
```

### Backend: "Ruff format check failed"

**Problem**: Code is not formatted according to ruff rules.

**Fix**: Run `ruff format .` in the backend directory.

### Backend: "Ruff check failed"

**Problem**: Linting errors (unused imports, wrong import order, etc.).

**Fix**: Run `ruff check . --fix` to auto-fix most issues.

## Pull Request Checklist

Before submitting a PR, ensure:

- [ ] All CI checks pass locally
- [ ] New code includes appropriate TypeScript types (no `any`)
- [ ] React hooks have correct dependencies
- [ ] Python code is formatted with ruff
- [ ] Tests pass (if applicable)
- [ ] Documentation is updated (if needed)

## Questions?

If you're unsure about something or need help fixing a CI failure, feel free to open an issue or ask in your PR comments.
