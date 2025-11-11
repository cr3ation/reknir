# Multi-Company Support - Quick Reference

## Current Status: 60-70% Ready

### Database: ✅ READY
- [x] All tables have company_id or proper isolation
- [x] Foreign keys enforce company data isolation
- [x] Unique constraints per company
- No migration needed!

### API Backend: ✅ 85% READY
All routers accept `company_id: int = Query(...)`:
- accounts, verifications, customers, suppliers
- invoices, supplier_invoices, expenses
- reports (balance-sheet, income-statement, vat-report)
- fiscal-years, default-accounts

⚠️ Missing: Company ownership verification in single-record GET endpoints

### Frontend Services: ✅ READY
- API methods already accept companyId parameter
- No service changes needed!

### Frontend UI: ❌ NOT READY
- [x] Single-company hardcoded (gets first company)
- [ ] No CompanyContext
- [ ] No company selector UI
- [ ] No user authentication UI

### Authentication: ❌ MISSING
- No User model
- No auth middleware
- No JWT/session management
- No role-based access control

---

## Critical Missing Pieces (in order of priority)

1. **User Model** (blocks everything else)
   - Location: backend/app/models/
   - Add: id, email, password_hash, company_id, role, created_at

2. **JWT Authentication Middleware**
   - Location: backend/app/main.py
   - Extract user from token on every request
   - Add current_user to request context

3. **Company Ownership Verification** (security critical)
   - Location: All routers (accounts.py, customers.py, etc.)
   - Verify: get_customer(5) -> check customer.company_id == user.company_id

4. **CompanyContext** (unblocks frontend)
   - Location: frontend/src/contexts/CompanyContext.tsx
   - Similar to FiscalYearContext
   - Store selectedCompany, switch between companies

5. **Company Selector UI**
   - Location: frontend/src/components/
   - Dropdown in sidebar showing current company

---

## Files That Need Work

### Backend (15 files)

**Add User model & auth:**
- backend/app/models/user.py (NEW)
- backend/app/routers/auth.py (NEW)
- backend/app/main.py (add middleware)

**Add company verification to:**
- backend/app/routers/accounts.py
- backend/app/routers/customers.py
- backend/app/routers/suppliers.py
- backend/app/routers/invoices.py
- backend/app/routers/supplier_invoices.py
- backend/app/routers/expenses.py
- backend/app/routers/verifications.py
- backend/app/routers/reports.py
- backend/app/routers/default_accounts.py

### Frontend (12 files)

**Create new:**
- frontend/src/contexts/CompanyContext.tsx
- frontend/src/pages/Login.tsx
- frontend/src/components/CompanySelector.tsx

**Update to use CompanyContext:**
- frontend/src/App.tsx (add auth routing)
- frontend/src/pages/Dashboard.tsx
- frontend/src/pages/Invoices.tsx
- frontend/src/pages/Expenses.tsx
- frontend/src/pages/Customers.tsx
- frontend/src/pages/Accounts.tsx
- frontend/src/pages/Verifications.tsx
- frontend/src/pages/Reports.tsx

---

## Implementation Order

### Week 1: Authentication Foundation
1. Create User model
2. Implement JWT auth middleware
3. Create /api/auth endpoints
4. Add company verification to routers

### Week 2: Frontend Auth & Company Context
1. Create CompanyContext
2. Create Login page
3. Update App.tsx with PrivateRoute
4. Add auth header to API calls

### Week 3: Multi-Company UI
1. Add company selector dropdown
2. Update all pages to use CompanyContext
3. Test company switching

### Week 4: Security & Testing
1. Verify company isolation
2. Security testing
3. Documentation

---

## Effort Estimate: 66-98 hours (2-3 weeks)

- Backend: 25-38 hours
- Frontend: 41-60 hours

---

## What Already Works (Don't Break!)

- All bookkeeping operations
- Report generation
- Invoice/expense management
- SIE4 import/export
- VAT reporting
- Account management

---

## What Won't Work Without This

- Multiple users
- Multiple companies  
- User roles/permissions
- Data isolation (currently trust-based)
- Audit trails

---

## Key Success Criteria

- [ ] Users can log in with username/password
- [ ] Each user can access their assigned company only
- [ ] Users can switch between multiple companies
- [ ] GET /api/customers/5 returns 404 if customer not in user's company
- [ ] All data stays isolated by company
- [ ] No breaking changes to existing API format

---

## Database Schema for User Model

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    role = Column(String, default="user")  # "admin", "user", etc.
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    company = relationship("Company")
```

---

## Security Checklist

- [ ] User passwords hashed with bcrypt
- [ ] JWT tokens have expiration
- [ ] Refresh token endpoint exists
- [ ] All single-record GETs verify company ownership
- [ ] All DELETEs verify company ownership
- [ ] All PATCHes verify company ownership
- [ ] File uploads verified by company
- [ ] Audit logging for sensitive operations
- [ ] Rate limiting on auth endpoints
- [ ] HTTPS in production
