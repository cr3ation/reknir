# Reknir Multi-Company Support Analysis

## Executive Summary

Reknir is currently designed in **single-company mode** (MVP state). The codebase already has significant multi-company foundations in place, with company_id foreign keys throughout the database models. However, the frontend is hardcoded to use the first company, and authentication/user management is not yet implemented.

The system is **well-positioned for multi-company support** - approximately 60-70% of the infrastructure is already in place.

---

## 1. DATABASE MODELS - CURRENT STATE

### Models WITH company_id (7/8 transaction-related models)

✅ **ALREADY IMPLEMENTED - Company isolation via company_id foreign key:**

| Model | Table | company_id | Status |
|-------|-------|-----------|--------|
| Account | accounts | Yes | Ready |
| Verification | verifications | Yes | Ready |
| TransactionLine | transaction_lines | No (via verification) | Ready |
| Invoice | invoices | Yes | Ready |
| InvoiceLine | invoice_lines | No (via invoice) | Ready |
| SupplierInvoice | supplier_invoices | Yes | Ready |
| SupplierInvoiceLine | supplier_invoice_lines | No (via supplier_invoice) | Ready |
| Expense | expenses | Yes | Ready |
| Customer | customers | Yes | Ready |
| Supplier | suppliers | Yes | Ready |
| FiscalYear | fiscal_years | Yes | Ready |
| DefaultAccount | default_accounts | Yes | Ready |
| Company | companies | N/A | Primary entity |

**Key Finding:** All transaction and master data tables already have company_id or are properly isolated through parent relationships.

### Database Integrity
- ✅ Foreign key constraints enforce company data isolation at DB level
- ✅ Cascade delete rules properly configured (delete company = delete all related data)
- ✅ Unique constraints per company (e.g., account_number per company)

---

## 2. BACKEND API ROUTERS - CURRENT STATE

### Router Analysis (13 routers total)

**Status: 85% ready for multi-company**

#### Routers ALREADY requiring company_id query parameter:
- ✅ `/api/accounts/` - has `company_id: int = Query(...)`
- ✅ `/api/verifications/` - has `company_id: int = Query(...)`
- ✅ `/api/customers/` - has `company_id: int = Query(...)`
- ✅ `/api/suppliers/` - has `company_id: int = Query(...)`
- ✅ `/api/invoices/` - has `company_id: int = Query(...)`
- ✅ `/api/supplier-invoices/` - has `company_id: int = Query(...)`
- ✅ `/api/expenses/` - has `company_id: int = Query(...)`
- ✅ `/api/reports/balance-sheet` - has `company_id: int = Query(...)`
- ✅ `/api/reports/income-statement` - has `company_id: int = Query(...)`
- ✅ `/api/reports/vat-report` - has `company_id: int = Query(...)`
- ✅ `/api/reports/vat-periods` - has `company_id: int = Query(...)`
- ✅ `/api/fiscal-years/` - has `company_id: int = Query(...)`
- ✅ `/api/default-accounts/` - has `company_id: int = Query(...)`

#### Routers with company context in operations:
- ✅ `/api/companies/` - company CRUD + seed-bas operations
- ✅ `/api/sie4/import/{company_id}` - uses company_id in path
- ✅ `/api/sie4/export/{company_id}` - uses company_id in path

**Key Finding:** API layer is already multi-company ready! All list endpoints require company_id parameter.

### Code Quality Issues Found:
⚠️ **GET endpoints for individual records** (e.g., `GET /api/customers/{customer_id}`) don't verify company ownership
- Anyone with a customer_id can fetch any customer from any company
- Should add company ownership verification for security

---

## 3. FRONTEND - CURRENT STATE

### Current Implementation
- ⚠️ **Single-company hardcoded mode**
- Dashboard.tsx: `const companiesRes = await companyApi.list(); const comp = companiesRes.data[0]`
- Invoices.tsx: Same pattern - gets first company
- Expenses.tsx: Same pattern
- Customers.tsx: Same pattern
- Reports.tsx: Same pattern (needs verification)

### What Frontend Services Support
✅ All API service methods accept `companyId: number` parameter:
```typescript
accountApi.list(companyId: number)
invoiceApi.list(companyId: number)
customerApi.list(companyId: number)
verificationApi.list(companyId: number)
reportApi.balanceSheet(companyId: number)
// ... etc
```

### Frontend Contexts
- ✅ FiscalYearContext exists and is company-aware
- ❌ NO CompanyContext - this needs to be created
- ❌ NO UserContext - needed for multi-company + auth

### UI Components Missing
- ❌ Company switcher in header/sidebar
- ❌ Company selector during app initialization
- ❌ Multi-company aware routing
- ❌ User authentication UI
- ❌ Company/user management pages

---

## 4. AUTHENTICATION & USER MANAGEMENT

### Current State
❌ **NO AUTHENTICATION IMPLEMENTED**
- No auth files found in codebase
- System assumes single user (single company)
- No user roles/permissions
- No session management
- No API key/token validation

### What Needs to Be Added:
- User model (with company association)
- Role-based access control (RBAC) or permission model
- JWT tokens or session management
- Authentication middleware in FastAPI
- User login/logout UI
- User context in frontend

---

## 5. DATA MODEL RELATIONSHIPS

### Company as Root Entity

```
Company (Root)
├── Accounts (1510, 1930, 2440, etc.)
│   └── TransactionLines (via Verification)
├── Verifications (A1, A2, B1, etc.)
│   └── TransactionLines
├── FiscalYears (2024, 2025, etc.)
│   └── Verifications (back_populates)
├── DefaultAccounts (revenue_25, vat_outgoing_25, etc.)
│   └── Maps to Accounts
├── Invoices (customer)
│   ├── InvoiceLines
│   ├── invoice_verification_id
│   └── payment_verification_id
├── SupplierInvoices (supplier)
│   ├── SupplierInvoiceLines
│   ├── invoice_verification_id
│   └── payment_verification_id
├── Expenses
│   ├── expense_account_id
│   ├── vat_account_id
│   ├── verification_id
│   └── payment_verification_id (implicit)
├── Customers
│   └── Invoices (back_populates)
└── Suppliers
    └── SupplierInvoices (back_populates)
```

**Key Finding:** Company is the proper root entity with correct cascade relationships.

---

## 6. WHAT'S ALREADY IN PLACE (The Good News)

### Database Layer ✅
- All tables properly isolated with company_id
- Foreign key constraints enforce isolation
- Unique constraints per company (account_number per company, not globally)
- Data models are clean and ready

### API Layer ✅
- 13/13 routers already accept company_id parameter
- Query logic filters by company_id
- Most endpoints are multi-company compatible
- Report endpoints already support per-company filtering
- SIE4 import/export supports per-company operations

### Infrastructure ✅
- BAS kontoplan can be seeded per company
- Default accounts can be configured per company
- Fiscal years per company (already supported)
- All business logic services are company-aware

### Frontend Services ✅
- API wrapper methods accept companyId parameter
- Service layer is ready for multi-company

---

## 7. WHAT STILL NEEDS TO BE ADDED (The Work)

### Backend Changes

#### 1. Authentication & Authorization (40% of work)
- [ ] Create User model with company_id and role fields
- [ ] Add authentication middleware (JWT/session)
- [ ] Add role-based access control decorators
- [ ] Add company ownership verification to all GET endpoints
- [ ] Create /api/auth endpoints (login, logout, refresh token)
- [ ] Add user CRUD endpoints (/api/users/)
- [ ] Add endpoints for user invitation/management

#### 2. API Security Improvements (20% of work)
- [ ] Add company ownership checks to all single-record GET endpoints
- [ ] Ensure DELETE endpoints verify company ownership
- [ ] Ensure PATCH endpoints verify company ownership
- [ ] Create dependency injection for "current_company" from auth token
- [ ] Add validation that company_id in query matches user's company

#### 3. File Upload Security (10% of work)
- [ ] Verify company ownership for receipt uploads (/expenses/{id}/upload-receipt)
- [ ] Verify company ownership for invoice attachments (/supplier-invoices/{id}/upload-attachment)
- [ ] Organize uploaded files by company in filesystem

### Frontend Changes

#### 1. Company Context & State Management (25% of work)
- [ ] Create CompanyContext similar to FiscalYearContext
- [ ] Create selectedCompany state that persists
- [ ] Create useCompany() hook
- [ ] Store company preference in localStorage

#### 2. Authentication & User Interface (35% of work)
- [ ] Create login page
- [ ] Create logout functionality
- [ ] Create user registration/setup
- [ ] Add authentication header to all API calls
- [ ] Handle 401 responses and redirect to login
- [ ] Add user info display in sidebar
- [ ] Create user settings page

#### 3. Company Switching UI (15% of work)
- [ ] Add company selector dropdown in sidebar/header
- [ ] Show current company name
- [ ] Allow switching between companies user has access to
- [ ] Persist company selection
- [ ] Update all pages to use selected company

#### 4. Update All Pages (25% of work)
- [ ] Dashboard.tsx: use selectedCompany instead of first company
- [ ] Invoices.tsx: use selectedCompany
- [ ] Expenses.tsx: use selectedCompany
- [ ] Customers.tsx: use selectedCompany
- [ ] Accounts.tsx: use selectedCompany
- [ ] Verifications.tsx: use selectedCompany
- [ ] Reports.tsx: use selectedCompany
- [ ] Settings.tsx: update for multi-company

#### 5. Route Protection (10% of work)
- [ ] Create PrivateRoute component
- [ ] Protect all pages behind authentication
- [ ] Allow Setup page for unauthenticated users
- [ ] Redirect to login if not authenticated

---

## 8. RECOMMENDED IMPLEMENTATION ROADMAP

### Phase 1: Backend Foundation (Week 1-2)
1. Create User model
2. Implement JWT authentication
3. Add auth endpoints (login, register, refresh)
4. Add auth middleware to FastAPI
5. Add company ownership verification to endpoints

### Phase 2: Frontend Authentication (Week 2-3)
1. Create CompanyContext
2. Create login page
3. Add authentication to API calls
4. Create PrivateRoute wrapper
5. Update App.tsx routing logic

### Phase 3: Multi-Company UI (Week 3)
1. Add company selector in sidebar
2. Update all pages to use CompanyContext
3. Test company switching
4. Add user profile page

### Phase 4: Testing & Polish (Week 4)
1. Security testing (verify company isolation)
2. UI/UX improvements
3. Error handling
4. Documentation

---

## 9. KEY FILES TO MODIFY

### Backend Files (Priority Order)

**High Priority:**
1. `/home/user/reknir/backend/app/models/` - Add User model
2. `/home/user/reknir/backend/app/routers/accounts.py` - Add company ownership check
3. `/home/user/reknir/backend/app/routers/customers.py` - Add company ownership check
4. `/home/user/reknir/backend/app/routers/suppliers.py` - Add company ownership check
5. `/home/user/reknir/backend/app/main.py` - Add auth middleware

**Medium Priority:**
6. `/home/user/reknir/backend/app/routers/invoices.py` - Add company ownership check
7. `/home/user/reknir/backend/app/routers/supplier_invoices.py` - Add company ownership check
8. `/home/user/reknir/backend/app/routers/expenses.py` - Add company ownership check
9. `/home/user/reknir/backend/app/routers/verifications.py` - Add company ownership check
10. `/home/user/reknir/backend/app/routers/reports.py` - Add company ownership check

### Frontend Files (Priority Order)

**High Priority:**
1. `/home/user/reknir/frontend/src/contexts/CompanyContext.tsx` - CREATE NEW
2. `/home/user/reknir/frontend/src/pages/Login.tsx` - CREATE NEW
3. `/home/user/reknir/frontend/src/App.tsx` - Update routing logic
4. `/home/user/reknir/frontend/src/App.tsx` - Add PrivateRoute component

**Medium Priority:**
5. `/home/user/reknir/frontend/src/pages/Dashboard.tsx` - Use CompanyContext
6. `/home/user/reknir/frontend/src/pages/Invoices.tsx` - Use CompanyContext
7. `/home/user/reknir/frontend/src/pages/Expenses.tsx` - Use CompanyContext
8. `/home/user/reknir/frontend/src/pages/Customers.tsx` - Use CompanyContext
9. `/home/user/reknir/frontend/src/pages/Accounts.tsx` - Use CompanyContext
10. `/home/user/reknir/frontend/src/pages/Verifications.tsx` - Use CompanyContext
11. `/home/user/reknir/frontend/src/pages/Reports.tsx` - Use CompanyContext
12. `/home/user/reknir/frontend/src/services/api.ts` - Add auth header to requests

---

## 10. SECURITY CONSIDERATIONS

### Critical Issues to Address
1. ⚠️ **Single-record endpoints don't verify company ownership**
   - GET /api/customers/5 returns customer 5 from ANY company
   - Need to verify customer.company_id matches user's company

2. ⚠️ **No user/company relationship in database**
   - Can't restrict which companies a user can access
   - Need User model with company_id or user_company mapping table

3. ⚠️ **No authentication at all**
   - Anyone can access any company's data
   - Need JWT tokens or session management

### Recommended Security Improvements
- Add auth middleware that extracts user from JWT token
- Add company_id to token claims
- Create dependency injection for "current_user" and "current_company"
- Verify company_id matches between request params and user's allowed companies
- Add audit logging for data access and modifications
- Add rate limiting
- Use HTTPS in production

---

## 11. ESTIMATED EFFORT

### Backend Changes
- User model & auth: 10-15 hours
- API security improvements: 8-12 hours
- File upload security: 2-3 hours
- Testing: 5-8 hours
- **Subtotal: 25-38 hours**

### Frontend Changes
- Context & state management: 5-8 hours
- Authentication UI: 8-12 hours
- Company switching UI: 5-7 hours
- Update all pages: 15-20 hours
- Route protection: 3-5 hours
- Testing: 5-8 hours
- **Subtotal: 41-60 hours**

### **Total Estimated Effort: 66-98 hours (2-3 weeks for one developer)**

---

## 12. CURRENT SINGLE-COMPANY LIMITATIONS

### What Works Today
- ✅ All bookkeeping operations (verifications, invoices, etc.)
- ✅ Reports generation
- ✅ Account management
- ✅ Customer/supplier management
- ✅ Expense tracking
- ✅ SIE4 import/export
- ✅ VAT reporting

### What Doesn't Work Without Auth
- ❌ Multiple users using the system simultaneously
- ❌ Multiple companies
- ❌ User roles/permissions
- ❌ Audit trails
- ❌ Company data isolation (trust-based only)

---

## 13. MIGRATION PATH FOR EXISTING DATA

If the system has been in use with single company:
1. Existing data already has company_id = 1 (first company created)
2. No data migration needed - just add authentication layer
3. Create additional users and assign to company 1
4. Later, additional companies can be created and managed

---

## 14. CONCLUSION

**The good news:** Reknir is 60-70% ready for multi-company support. The database schema and API endpoints are already well-designed for it.

**The work needed:** 
- Authentication system (most important)
- Frontend company context and UI
- Company ownership verification in API endpoints
- File upload security

**Recommendation:** Start with Phase 1 (authentication) since it's blocking everything else. Once you have a User model and JWT auth, the rest becomes straightforward.

The fact that company_id is already throughout the data models and API layer is excellent - it means the original developers planned for multi-company from the start, even if the MVP is single-company only.
