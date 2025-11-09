# Invoice Management Feature - Implementation Summary

**Date**: 2024-11-09
**Status**: ✅ Complete
**Version**: 0.2.0

## Overview

Complete invoice management system for Swedish bookkeeping with automatic verification creation for both outgoing (customer) and incoming (supplier) invoices.

## Features Implemented

### 📤 Outgoing Invoices (Kundfakturor)

**Customer Management**:
- Full CRUD for customer register
- Customer details: name, org number, contact info, address
- Payment terms configuration
- Active/inactive status

**Invoice Creation**:
- Sequential invoice numbering per series
- Multiple invoice lines with VAT calculation
- VAT rates: 25%, 12%, 6%, 0% (exempt)
- Revenue account assignment per line
- Customer reference and notes
- Automatic totals calculation

**Invoice Workflow**:
1. **Draft** → Create invoice
2. **Send** → Automatic verification created:
   ```
   Debit:  1510 Kundfordringar (Customer receivables)
   Credit: 3xxx Revenue accounts (per line)
   Credit: 26xx Utgående moms (Output VAT by rate)
   ```
3. **Mark Paid** → Payment verification created:
   ```
   Debit:  1930 Företagskonto (Bank account)
   Credit: 1510 Kundfordringar
   ```

**Status Tracking**:
- Draft - Not sent yet
- Sent - Invoice sent, awaiting payment
- Partial - Partially paid
- Paid - Fully paid
- Overdue - Past due date (future enhancement)
- Cancelled - Cancelled invoice

### 📥 Incoming Invoices (Leverantörsfakturor)

**Supplier Management**:
- Full CRUD for supplier register
- Supplier details including bank account info
- Payment terms
- Active/inactive status

**Invoice Registration**:
- Supplier invoice number tracking
- Internal tracking number (sequential)
- Multiple invoice lines with expense categorization
- VAT extraction (ingående moms)
- OCR number support
- Attachment path for scanned invoices

**Invoice Workflow**:
1. **Draft** → Register invoice details
2. **Register** → Automatic verification created:
   ```
   Debit:  6xxx Expense accounts (per line)
   Debit:  2640 Ingående moms (Input VAT)
   Credit: 2440 Leverantörsskulder (Accounts payable)
   ```
3. **Mark Paid** → Payment verification created:
   ```
   Debit:  2440 Leverantörsskulder
   Credit: 1930 Företagskonto (Bank account)
   ```

## Database Schema

### New Tables

**customers**: Customer register
**suppliers**: Supplier register
**invoices**: Outgoing invoices
**invoice_lines**: Outgoing invoice line items
**supplier_invoices**: Incoming invoices
**supplier_invoice_lines**: Incoming invoice line items

### Key Fields

**Invoice**:
- Automatic invoice numbering
- VAT calculation and tracking
- Payment status and amounts
- Links to verifications (invoice + payment)
- Timestamps for audit trail

**Invoice Lines**:
- Quantity, unit price, VAT rate
- Account assignment for proper categorization
- Calculated totals (net, VAT, total)

## API Endpoints

### Customers
```
GET    /api/customers/              List customers
POST   /api/customers/              Create customer
GET    /api/customers/{id}          Get customer
PATCH  /api/customers/{id}          Update customer
DELETE /api/customers/{id}          Delete customer
```

### Suppliers
```
GET    /api/suppliers/              List suppliers
POST   /api/suppliers/              Create supplier
GET    /api/suppliers/{id}          Get supplier
PATCH  /api/suppliers/{id}          Update supplier
DELETE /api/suppliers/{id}          Delete supplier
```

### Outgoing Invoices
```
GET    /api/invoices/               List invoices
POST   /api/invoices/               Create invoice
GET    /api/invoices/{id}           Get invoice
PATCH  /api/invoices/{id}           Update invoice
POST   /api/invoices/{id}/send      Send invoice (create verification)
POST   /api/invoices/{id}/mark-paid Mark as paid (create payment verification)
DELETE /api/invoices/{id}           Delete draft invoice
```

### Supplier Invoices
```
GET    /api/supplier-invoices/               List supplier invoices
POST   /api/supplier-invoices/               Create supplier invoice
GET    /api/supplier-invoices/{id}           Get supplier invoice
PATCH  /api/supplier-invoices/{id}           Update supplier invoice
POST   /api/supplier-invoices/{id}/register  Register (create verification)
POST   /api/supplier-invoices/{id}/mark-paid Mark as paid (create payment)
DELETE /api/supplier-invoices/{id}           Delete draft invoice
```

## Business Logic

### Automatic Verification Creation

**Service Layer** (`app/services/invoice_service.py`):
- `create_invoice_verification()` - Outgoing invoice posting
- `create_invoice_payment_verification()` - Outgoing payment
- `create_supplier_invoice_verification()` - Incoming invoice posting
- `create_supplier_invoice_payment_verification()` - Incoming payment

**Key Features**:
- Automatic account lookup (1510, 2440, 2640, 26xx)
- VAT splitting by rate
- Account balance updates
- Error handling for missing accounts

### VAT Handling

**Output VAT (Outgoing Invoices)**:
- Automatic mapping to correct VAT accounts:
  - 25% → 2611 (Utgående moms 25%)
  - 12% → 2612 (Utgående moms 12%)
  - 6% → 2613 (Utgående moms 6%)

**Input VAT (Supplier Invoices)**:
- All input VAT → 2640 (Ingående moms)
- Deductible from output VAT

## Frontend Integration

**New Page**: `/invoices`
**Navigation**: Added "Fakturor" menu item

**Features**:
- List view for outgoing invoices
- List view for supplier invoices
- Status badges with color coding
- Swedish currency formatting
- Placeholder buttons for create/register

**API Integration**:
- TypeScript types for all invoice entities
- Complete API client methods
- Error handling

## Swedish Accounting Compliance

✅ **Proper Account Usage**:
- 1510 Kundfordringar (Customer receivables)
- 2440 Leverantörsskulder (Accounts payable)
- 2640 Ingående moms (Input VAT)
- 2611-2613 Utgående moms (Output VAT)
- 3xxx Revenue accounts
- 6xxx Expense accounts

✅ **Double-Entry Bookkeeping**:
- All automatic verifications balance
- Debit = Credit enforced

✅ **Audit Trail**:
- Links to verification IDs
- Timestamps on all changes
- Cannot modify paid invoices

## Example Workflow

### Creating and Paying an Outgoing Invoice

**1. Create Customer**:
```bash
POST /api/customers/
{
  "company_id": 1,
  "name": "Acme AB",
  "org_number": "556677-8899",
  "payment_terms_days": 30
}
```

**2. Create Invoice**:
```bash
POST /api/invoices/
{
  "company_id": 1,
  "customer_id": 1,
  "invoice_date": "2024-11-09",
  "due_date": "2024-12-09",
  "invoice_lines": [
    {
      "description": "Consulting services",
      "quantity": 10,
      "unit": "tim",
      "unit_price": 1000,
      "vat_rate": 25,
      "account_id": 20  // Account 3000 (Revenue)
    }
  ]
}
```

**Result**: Invoice draft created with total 12,500 SEK (10,000 + 2,500 VAT)

**3. Send Invoice**:
```bash
POST /api/invoices/1/send
```

**Result**: Verification created automatically:
```
Ver A-1  2024-11-09  Faktura F1 - Acme AB
  1510  Kundfordringar              12,500  (Debit)
  3000  Försäljning                          10,000  (Credit)
  2611  Utgående moms 25%                     2,500  (Credit)
```

**4. Mark as Paid**:
```bash
POST /api/invoices/1/mark-paid
{
  "paid_date": "2024-12-09"
}
```

**Result**: Payment verification created:
```
Ver A-2  2024-12-09  Betalning faktura F1 - Acme AB
  1930  Företagskonto              12,500  (Debit)
  1510  Kundfordringar                      12,500  (Credit)
```

## File Structure

```
backend/
├── app/
│   ├── models/
│   │   ├── customer.py          # Customer & Supplier models
│   │   └── invoice.py           # Invoice models
│   ├── schemas/
│   │   ├── customer.py          # Customer & Supplier schemas
│   │   └── invoice.py           # Invoice schemas
│   ├── routers/
│   │   ├── customers.py         # Customer endpoints
│   │   ├── suppliers.py         # Supplier endpoints
│   │   ├── invoices.py          # Invoice endpoints
│   │   └── supplier_invoices.py # Supplier invoice endpoints
│   └── services/
│       └── invoice_service.py   # Business logic
└── alembic/versions/
    └── 002_add_invoices.py      # Database migration

frontend/
├── src/
│   ├── types/index.ts           # TypeScript types (updated)
│   ├── services/api.ts          # API client (updated)
│   └── pages/
│       └── Invoices.tsx         # Invoice management page
```

## Next Steps (Future Enhancements)

### Phase 1: UI Completion
- [ ] Invoice creation form
- [ ] Customer/supplier management UI
- [ ] Invoice detail view
- [ ] Edit draft invoices
- [ ] Payment marking UI

### Phase 2: PDF Generation
- [ ] Swedish invoice PDF template
- [ ] PDF download endpoint
- [ ] Email sending integration

### Phase 3: Advanced Features
- [ ] Credit invoices (kreditfaktura)
- [ ] Recurring invoices
- [ ] Invoice templates
- [ ] Batch payment import
- [ ] Overdue tracking and reminders
- [ ] OCR for supplier invoices
- [ ] AI-powered expense categorization

### Phase 4: Integration
- [ ] E-invoicing (Peppol)
- [ ] Direct bank integration
- [ ] Accounting software export (Fortnox, Visma)

## Testing

**API Testing**:
- All endpoints documented in FastAPI /docs
- Test via Swagger UI at http://localhost:8000/docs

**Required Accounts** (from BAS import):
- 1510 Kundfordringar
- 1930 Företagskonto
- 2440 Leverantörsskulder
- 2611 Utgående moms 25%
- 2612 Utgående moms 12%
- 2613 Utgående moms 6%
- 2640 Ingående moms
- 3000 Försäljning (or other 3xxx)
- 6xxx Expense accounts

## Performance Notes

- Invoice numbering uses database queries (could be optimized with sequences)
- Verification creation is transactional (atomic)
- Account balance updates happen inline (consider async for scale)
- No caching implemented yet

## Known Limitations

- No PDF generation (Phase 2)
- No email sending
- No recurring invoices
- No credit invoices
- No invoice templates
- Simple UI (list view only)
- No OCR for supplier invoices
- No overdue calculation

## Success Metrics

✅ Create and track customer invoices
✅ Automatic accounting entries on invoice send
✅ Payment tracking with automatic entries
✅ Supplier invoice management
✅ VAT calculation and tracking
✅ Full API coverage
✅ TypeScript types and API client

**Invoice system is production-ready for API usage!**
**UI completion needed for end-user workflows.**

---

## Migration

Run database migration:
```bash
docker-compose exec backend alembic upgrade head
```

Or manually:
```bash
cd backend
alembic upgrade head
```

This creates all invoice tables and enums.

## Summary

Complete invoice management system implemented with:
- ✅ Full database schema
- ✅ Complete API endpoints
- ✅ Automatic verification creation
- ✅ Swedish compliance
- ✅ Frontend integration (basic)
- ⏳ UI forms (planned)
- ⏳ PDF generation (planned)

**Ready for real business use via API!**
