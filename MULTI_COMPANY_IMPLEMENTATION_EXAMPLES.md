# Multi-Company Implementation Examples

## 1. User Model (backend/app/models/user.py) - NEW FILE

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from datetime import datetime

class User(Base):
    """User account model for authentication"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    
    # Company association
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    
    # Role-based access control
    role = Column(String, default="user", nullable=False)  # "admin", "user", "readonly"
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Audit trail
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    company = relationship("Company")
    
    def __repr__(self):
        return f"<User {self.email} - {self.company_id}>"
```

---

## 2. Authentication Middleware (backend/app/main.py) - ADDITIONS

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt
from datetime import datetime, timedelta
from app.config import settings
from app.database import get_db

# JWT config
JWT_SECRET = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

def create_access_token(user_id: int, company_id: int):
    """Create JWT token with user and company info"""
    payload = {
        "user_id": user_id,
        "company_id": company_id,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.utcnow()
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def verify_token(token: str):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        company_id = payload.get("company_id")
        if user_id is None or company_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return {"user_id": user_id, "company_id": company_id}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)):
    """Dependency to get current user from token"""
    token = credentials.credentials
    return verify_token(token)

async def get_current_company_id(current_user: dict = Depends(get_current_user)):
    """Get current user's company_id from token"""
    return current_user["company_id"]
```

---

## 3. Auth Router (backend/app/routers/auth.py) - NEW FILE

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.main import create_access_token, verify_token
import bcrypt

router = APIRouter(prefix="/api/auth", tags=["auth"])

def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hash: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode(), hash.encode())

@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if email exists
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
        company_id=user_data.company_id,
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    """Login and get JWT token"""
    user = db.query(User).filter(User.email == email).first()
    
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is inactive")
    
    token = create_access_token(user.id, user.company_id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user.id,
        "company_id": user.company_id,
        "email": user.email
    }

@router.post("/refresh")
def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh access token"""
    new_token = create_access_token(current_user["user_id"], current_user["company_id"])
    return {"access_token": new_token, "token_type": "bearer"}
```

---

## 4. Example Router with Company Verification (backend/app/routers/customers.py) - MODIFIED

```python
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer
from app.main import get_current_company_id
from app.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate

router = APIRouter()

@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer: CustomerCreate, 
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id)
):
    """Create a new customer (must be in user's company)"""
    # company_id now comes from JWT token, not query param
    db_customer = Customer(
        **customer.model_dump(),
        company_id=company_id  # Force company_id from token
    )
    db.add(db_customer)
    db.commit()
    db.refresh(db_customer)
    return db_customer

@router.get("/", response_model=list[CustomerResponse])
def list_customers(
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id),
    active_only: bool = True
):
    """List all customers for user's company"""
    # company_id is validated from JWT token
    query = db.query(Customer).filter(Customer.company_id == company_id)
    
    if active_only:
        query = query.filter(Customer.active == True)
    
    return query.order_by(Customer.name).all()

@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: int, 
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id)
):
    """Get a specific customer (verify company ownership)"""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.company_id == company_id  # SECURITY: Verify company ownership
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer {customer_id} not found"
        )
    return customer

@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: int, 
    customer_update: CustomerUpdate, 
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id)
):
    """Update a customer (verify company ownership)"""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.company_id == company_id  # SECURITY: Verify company ownership
    ).first()
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    update_data = customer_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    db.commit()
    db.refresh(customer)
    return customer

@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: int, 
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id)
):
    """Delete a customer (verify company ownership)"""
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.company_id == company_id  # SECURITY: Verify company ownership
    ).first()
    
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    db.delete(customer)
    db.commit()
    return None
```

**Key changes from current implementation:**
- Remove `company_id: int = Query(...)` from function signature
- Add `company_id: int = Depends(get_current_company_id)` to extract from JWT
- Add `Customer.company_id == company_id` to WHERE clause for security
- Add comment `# SECURITY:` to highlight ownership checks

---

## 5. Frontend CompanyContext (frontend/src/contexts/CompanyContext.tsx) - NEW FILE

```typescript
import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { companyApi } from '@/services/api'
import type { Company } from '@/types'

interface CompanyContextType {
  companies: Company[]
  selectedCompany: Company | null
  setSelectedCompany: (company: Company | null) => void
  loadCompanies: () => Promise<void>
  loading: boolean
  switchCompany: (companyId: number) => void
}

const CompanyContext = createContext<CompanyContextType | undefined>(undefined)

export function CompanyProvider({ children }: { children: ReactNode }) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [selectedCompany, setSelectedCompany] = useState<Company | null>(null)
  const [loading, setLoading] = useState(false)

  // Load companies on mount
  useEffect(() => {
    loadCompanies()
  }, [])

  const loadCompanies = async () => {
    try {
      setLoading(true)
      const response = await companyApi.list()
      setCompanies(response.data)

      // Restore from localStorage or select first
      const savedCompanyId = localStorage.getItem('selectedCompanyId')
      let selected = response.data[0]

      if (savedCompanyId) {
        const found = response.data.find(c => c.id === parseInt(savedCompanyId))
        if (found) selected = found
      }

      setSelectedCompany(selected)
    } catch (error) {
      console.error('Failed to load companies:', error)
    } finally {
      setLoading(false)
    }
  }

  const switchCompany = (companyId: number) => {
    const company = companies.find(c => c.id === companyId)
    if (company) {
      setSelectedCompany(company)
      localStorage.setItem('selectedCompanyId', companyId.toString())
    }
  }

  return (
    <CompanyContext.Provider
      value={{
        companies,
        selectedCompany,
        setSelectedCompany,
        loadCompanies,
        loading,
        switchCompany
      }}
    >
      {children}
    </CompanyContext.Provider>
  )
}

export function useCompany() {
  const context = useContext(CompanyContext)
  if (context === undefined) {
    throw new Error('useCompany must be used within a CompanyProvider')
  }
  return context
}
```

---

## 6. Company Selector Component (frontend/src/components/CompanySelector.tsx) - NEW FILE

```typescript
import { useCompany } from '@/contexts/CompanyContext'
import { ChevronDown } from 'lucide-react'
import { useState } from 'react'

export default function CompanySelector() {
  const { companies, selectedCompany, switchCompany } = useCompany()
  const [isOpen, setIsOpen] = useState(false)

  if (!selectedCompany || companies.length <= 1) {
    return (
      <div className="px-4 py-3 text-sm font-medium text-gray-700">
        {selectedCompany?.name || 'Laddar...'}
      </div>
    )
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded"
      >
        <span className="truncate">{selectedCompany.name}</span>
        <ChevronDown className="w-4 h-4 ml-2 flex-shrink-0" />
      </button>

      {isOpen && (
        <div className="absolute bottom-full left-0 right-0 mb-1 bg-white border border-gray-200 rounded shadow-lg z-50">
          {companies.map(company => (
            <button
              key={company.id}
              onClick={() => {
                switchCompany(company.id)
                setIsOpen(false)
              }}
              className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 ${
                selectedCompany.id === company.id
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-gray-700'
              }`}
            >
              {company.name}
              <div className="text-xs text-gray-500">{company.org_number}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

---

## 7. Updated App.tsx with Auth Routing

```typescript
// In App.tsx, replace the main routing section:

function AppContent() {
  const { selectedCompany } = useCompany()
  const location = useLocation()

  const menuItems = [
    { path: '/', icon: Home, label: 'Översikt' },
    // ... other menu items
  ]

  if (!selectedCompany) {
    return <div>Laddar bolag...</div>
  }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-6 border-b border-gray-200">
          <h1 className="text-2xl font-bold text-primary-600">REKNIR</h1>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {menuItems.map((item) => (
            <Link key={item.path} to={item.path}>
              {/* ... menu items */}
            </Link>
          ))}
        </nav>

        {/* Company Selector */}
        <div className="p-4 border-t border-gray-200">
          <h3 className="text-xs font-semibold text-gray-500 mb-2">BOLAG</h3>
          <CompanySelector />
        </div>

        {/* User & Fiscal Year */}
        <div className="p-4 border-t border-gray-200">
          <h3 className="text-xs font-semibold text-gray-500 mb-2">RÄKENSKAPSÅR</h3>
          <FiscalYearSelector />
        </div>
      </div>

      {/* Main content with selected company */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            <Routes>
              <Route path="/" element={<Dashboard companyId={selectedCompany.id} />} />
              <Route path="/invoices" element={<Invoices companyId={selectedCompany.id} />} />
              {/* ... other routes passing companyId */}
            </Routes>
          </div>
        </main>
      </div>
    </div>
  )
}
```

---

## 8. Updated Dashboard.tsx with Props

```typescript
interface DashboardProps {
  companyId: number
}

export default function Dashboard({ companyId }: DashboardProps) {
  const [company, setCompany] = useState<Company | null>(null)
  const [accounts, setAccounts] = useState<Account[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [companyId])

  const loadData = async () => {
    try {
      // Get specific company instead of first one
      const companyRes = await companyApi.get(companyId)
      setCompany(companyRes.data)

      // Load accounts for this company
      const accountsRes = await accountApi.list(companyId)
      setAccounts(accountsRes.data)
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setLoading(false)
    }
  }

  // ... rest of component
}
```

---

## Summary of Changes

### What Changes:
1. ✅ Query params: `?company_id=1` becomes header auth token
2. ✅ Frontend: hardcoded first company becomes CompanyContext + selector
3. ✅ API: add company ownership verification to single-record endpoints

### What Stays the Same:
1. ✅ All existing business logic
2. ✅ Database schema (just add users table)
3. ✅ API response formats
4. ✅ Frontend page layouts

### Migration Path:
1. Add User model
2. Add auth router
3. Update existing routers to verify company ownership
4. Deploy backend
5. Update frontend contexts
6. Update frontend pages to use contexts
7. Deploy frontend

