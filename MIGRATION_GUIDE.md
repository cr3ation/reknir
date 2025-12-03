# Migration Guide: Fiscal Year-Aware Accounts

## Översikt
Konton är nu kopplade till specifika räkenskapsår. Varje konto har både `company_id` och `fiscal_year_id`.

## Ändringar i Backend Services

### ✅ Genomfört

#### 1. Account Model
- Lagt till `fiscal_year_id` kolumn (NOT NULL, foreign key till fiscal_years)
- Behållit `company_id` för enkel filtrering
- Uppdaterat relationships

#### 2. Schemas
- `AccountCreate` kräver nu både `company_id` och `fiscal_year_id`
- `AccountResponse` returnerar både fält

#### 3. API Endpoints

**Accounts Router:**
- `GET /api/accounts/` - Kräver nu både `company_id` OCH `fiscal_year_id`
- `GET /api/accounts/balances` - Samma som ovan
- `POST /api/accounts/` - Kräver `fiscal_year_id` i body
- `DELETE /api/accounts/{id}` - Ny endpoint, raderar konto om det inte har transaktioner

**Fiscal Years Router:**
- `POST /api/fiscal-years/{id}/copy-chart-of-accounts` - Kopierar kontoplan från föregående år

**Companies Router:**
- `POST /api/companies/{id}/seed-bas?fiscal_year_id={fy_id}` - Kräver nu fiscal_year_id parameter

#### 4. default_account_service.py
Alla funktioner uppdaterade att ta `fiscal_year_id`:
- `get_default_account(db, company_id, fiscal_year_id, account_type)`
- `get_revenue_account_for_vat_rate(db, company_id, fiscal_year_id, vat_rate)`
- `get_vat_outgoing_account_for_rate(db, company_id, fiscal_year_id, vat_rate)`
- `get_vat_incoming_account_for_rate(db, company_id, fiscal_year_id, vat_rate)`
- `initialize_default_accounts_from_existing(db, company_id, fiscal_year_id)`

### ✅ Backend-uppdateringar - GENOMFÖRDA!

#### invoice_service.py - ✅ KLART
- ✅ Skapat hjälpfunktion `get_fiscal_year_for_date(db, company_id, transaction_date)`
- ✅ Uppdaterat `create_invoice_verification` - hämtar fiscal_year från invoice_date
- ✅ Uppdaterat `create_invoice_payment_verification` - hämtar fiscal_year från paid_date
- ✅ Uppdaterat `create_supplier_invoice_verification` - hämtar fiscal_year från invoice_date
- ✅ Uppdaterat `create_supplier_invoice_payment_verification` - hämtar fiscal_year från paid_date
- ✅ Alla anrop till default_account_service inkluderar nu fiscal_year.id
- ✅ Alla Account-queries filtrerar på fiscal_year_id

#### expense_service.py - ✅ KLART
- ✅ Lagt till `get_fiscal_year_for_date` funktion
- ✅ Uppdaterat `create_expense_verification` - hämtar fiscal_year från expense_date
- ✅ Uppdaterat `create_expense_payment_verification` - hämtar fiscal_year från paid_date
- ✅ Alla verifikationer har fiscal_year_id

#### sie4_service.py - ✅ KLART
- ✅ `import_sie4()` tar nu `fiscal_year_id` parameter
- ✅ `export_sie4()` tar nu `fiscal_year_id` parameter
- ✅ Alla Account-queries filtrerar på fiscal_year_id
- ✅ Konton skapas med rätt fiscal_year_id
- ✅ Verifikationer skapas med rätt fiscal_year_id
- ✅ Anropar `initialize_default_accounts_from_existing()` med fiscal_year_id

#### verifications.py - ✅ KLART
- ✅ Schema uppdaterad: `VerificationCreate` kräver nu `fiscal_year_id`
- ✅ Schema uppdaterad: `VerificationResponse` returnerar `fiscal_year_id`
- ✅ `create_verification()` sätter fiscal_year_id från request

#### reports.py - ✅ KLART
- ✅ `get_balance_sheet()` - tar fiscal_year_id parameter
- ✅ `get_income_statement()` - tar fiscal_year_id parameter
- ✅ `get_trial_balance()` - tar fiscal_year_id parameter
- ✅ `get_vat_report()` - tar fiscal_year_id parameter
- ✅ `get_vat_debug()` - tar fiscal_year_id parameter
- ✅ `get_monthly_statistics()` - tar fiscal_year_id parameter
- ✅ Alla Account-queries filtrerar på fiscal_year_id

#### companies.py - ✅ KLART
- ✅ `seed_bas_accounts()` - tar fiscal_year_id parameter (redan gjort)
- ✅ `seed_posting_templates()` - använder första fiscal_year för att hitta konton

#### default_accounts.py - ✅ INGEN ÄNDRING BEHÖVS
- Account hämtas endast via ID (som redan finns i DefaultAccount)

#### posting_templates.py - ✅ INGEN ÄNDRING BEHÖVS
- Verifierar bara att account_id finns, behöver inte filtrera på fiscal_year

## Ändringar i Frontend

### ✅ Frontend-uppdateringar - GENOMFÖRDA!

#### api.ts - ✅ KLART
- ✅ `accountApi.list()` - tar nu både `companyId` och `fiscalYearId`
- ✅ `reportApi.balanceSheet()` - tar `fiscalYearId`
- ✅ `reportApi.incomeStatement()` - tar `fiscalYearId`
- ✅ `reportApi.vatReport()` - tar `fiscalYearId`
- ✅ `reportApi.vatPeriods()` - tar `fiscalYearId`
- ✅ `reportApi.monthlyStatistics()` - tar `fiscalYearId`
- ✅ `sie4Api.import()` - tar `fiscalYearId`
- ✅ `sie4Api.export()` - tar `fiscalYearId`

#### Accounts.tsx - ✅ KLART
- ✅ Använder `useFiscalYear()` hook
- ✅ Visar `FiscalYearSelector` i header
- ✅ Laddar konton för valt räkenskapsår
- ✅ Uppdaterar vid byte av räkenskapsår

#### Reports.tsx - ✅ KLART
- ✅ Använder `useFiscalYear()` hook
- ✅ Visar `FiscalYearSelector` i header
- ✅ Alla rapporter filtrerar på valt räkenskapsår
- ✅ Momsrapport använder fiscal_year_id
- ✅ XML-export inkluderar fiscal_year_id

#### Settings.tsx - ✅ KLART
- ✅ Använder `useFiscalYear()` hook
- ✅ SIE4 import kräver valt räkenskapsår
- ✅ SIE4 export kräver valt räkenskapsår
- ✅ Laddar konton för valt räkenskapsår
- ✅ Visar felmeddelande om inget räkenskapsår är valt

#### Verifications.tsx - ✅ KLART
- ✅ Använder `useFiscalYear()` hook
- ✅ Laddar konton för valt räkenskapsår
- ✅ CreateVerificationModal tar `fiscalYearId` prop
- ✅ Nya verifikationer skapas med `fiscal_year_id`
- ✅ Modal kräver valt räkenskapsår

#### Dashboard.tsx - ✅ KLART
- ✅ Använder `useFiscalYear()` hook
- ✅ Laddar konton för valt räkenskapsår
- ✅ Månatlig statistik använder fiscal_year_id

### FiscalYearContext & FiscalYearSelector - ✅ FINNS REDAN
- ✅ FiscalYearContext hanterar räkenskapsårsval
- ✅ FiscalYearSelector visar dropdown för att välja räkenskapsår
- ✅ Auto-väljer aktuellt räkenskapsår vid företagsbyte

### ✅ Onboarding Flow - GENOMFÖRT!

**Setup.tsx - Komplett 4-stegs wizard:**
- ✅ Steg 1: Skapa företag med grundläggande information
  - Företagsnamn, organisationsnummer
  - Redovisningsmetod (bokföringsmässiga grunder/kontantmetod)
  - Momsperiod (månadsvis/kvartalsvis/årsvis)
- ✅ Steg 2: Ange räkenskapsår
  - Föreslår innevarande år (1 jan - 31 dec)
  - Validerar att perioden är cirka 12 månader
  - Anpassningsbar till vilket datum som helst
- ✅ Steg 3: Välj kontoplan
  - Alternativ 1: "Ja, skapa kontoplan" (importerar BAS2024, 43 konton, standardkonton, mallar)
  - Alternativ 2: "Nej, hoppa över" (tom start, kan importera senare)
- ✅ Steg 4: Bekräftelse och auto-redirect till dashboard

**Funktioner:**
- ✅ Progressindikator med ikoner och färgkodning
- ✅ Formulärvalidering (12-månaders check, required fields)
- ✅ Felhantering med användarvänliga meddelanden
- ✅ Laddningsstatus under varje steg
- ✅ Fiscal year-aware BAS-import
- ✅ Auto-initialisering av default accounts och templates

### Återstående Arbete:

**Inga kända återstående uppgifter.** Hela fiscal year-migrationen är genomförd!

## Testplan

### 1. Grundläggande Flöde
```bash
# 1. Skapa företag
POST /api/companies/
{
  "name": "Test AB",
  "org_number": "556644-4354",
  ...
}

# 2. Skapa räkenskapsår
POST /api/fiscal-years/
{
  "company_id": 1,
  "year": 2025,
  "label": "2025",
  "start_date": "2025-01-01",
  "end_date": "2025-12-31"
}

# 3. Importera BAS-kontoplan
POST /api/companies/1/seed-bas?fiscal_year_id=1

# 4. Hämta konton
GET /api/accounts/?company_id=1&fiscal_year_id=1

# 5. Skapa faktura (verifierar att rätt konton används)
POST /api/invoices/
...

# 6. Skapa nästa räkenskapsår
POST /api/fiscal-years/
{
  "company_id": 1,
  "year": 2026,
  "label": "2026",
  "start_date": "2026-01-01",
  "end_date": "2026-12-31"
}

# 7. Kopiera kontoplan
POST /api/fiscal-years/2/copy-chart-of-accounts

# 8. Verifiera att båda årens konton finns
GET /api/accounts/?company_id=1&fiscal_year_id=1
GET /api/accounts/?company_id=1&fiscal_year_id=2
```

### 2. Testa Fakturering över Årsskifte
- Skapa faktura i december 2025
- Skapa faktura i januari 2026
- Verifiera att rätt konton används (från rätt år)

### 3. Testa Default Accounts
- Verifiera att default accounts fungerar över flera år
- Testa att ändra kontonummer i år 2026
- Verifiera att default account fortfarande fungerar

## Kända Begränsningar

1. **Default Accounts är företags-vida:**
   - DefaultAccount-tabellen har INTE fiscal_year_id
   - Den sparar account_id till ETT specifikt konto (oftast från första året)
   - get_default_account() översätter till rätt år genom att leta upp kontonummer

2. **Posting Templates:**
   - Konteringsmallar har INTE fiscal_year-awareness än
   - De refererar direkt till account_id
   - Kan behöva uppdateras i framtiden

## Framtida Förbättringar

1. **Årsbokslut:**
   - Funktion för att kopiera slutbalanser till nästa års ingående balanser
   - Automatisk avstämning mellan år

2. **Kontohistorik:**
   - Visa hur ett konto (kontonummer) har ändrats över åren
   - Jämför balanser mellan år

3. **Multi-Year Reports:**
   - Balansräkning/Resultaträkning över flera år
   - Jämförelser mellan år
