# REKNIR - Svenska Bokföringssystem

## Översikt
Reknir är ett komplett bokföringssystem byggt för svenska företag med stöd för dubbel bokföring enligt svensk standard (BAS-kontoplan).

## Teknisk Stack

### Backend
- **FastAPI** - Python web framework
- **SQLAlchemy ORM** - Databashantering
- **PostgreSQL** - Databas
- **Alembic** - Databasmigrationer
- **Pydantic** - Datavalidering
- **WeasyPrint** - PDF-generering
- **Jinja2** - HTML-mallar för PDF

### Frontend
- **React 18** med TypeScript
- **React Router** - Routing
- **Axios** - HTTP-klient
- **Tailwind CSS** - Styling
- **Lucide React** - Ikoner

## Projektstruktur

```
reknir/
├── backend/
│   ├── app/
│   │   ├── models/           # SQLAlchemy modeller
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── routers/          # API endpoints
│   │   ├── services/         # Affärslogik
│   │   └── database.py       # Databaskonfiguration
│   ├── alembic/              # Databasmigrationer
│   └── main.py               # FastAPI application
├── frontend/
│   ├── src/
│   │   ├── pages/            # React sidor/komponenter
│   │   ├── services/         # API-klienter
│   │   ├── types/            # TypeScript typer
│   │   └── App.tsx           # Huvudapplikation
│   └── package.json
├── receipts/                 # Utläggskvitton
├── invoices/                 # Fakturabilagor
├── uploads/                  # Uppladdade filer (logotyper)
│   └── logos/                # Företagslogotyper
└── docker-compose.yml        # Container orchestration
```

## Huvudfunktioner

### 1. Räkenskapsår och Kontoplan

#### Räkenskapsår (Fiscal Years)
Varje företag kan ha flera räkenskapsår. Varje räkenskapsår har sin egen kontoplan.

**Viktiga principer:**
- Varje konto tillhör ett specifikt räkenskapsår
- Samma kontonummer kan finnas i flera år, men det är olika konton i systemet
- Verifikationer kopplas till konton i ett specifikt räkenskapsår
- Konton med transaktioner kan inte tas bort, endast inaktiveras

#### Skapa första räkenskapsåret
När ett företag skapas och dess första räkenskapsår läggs upp:
1. Systemet skapar en kontoplan baserad på BAS-mallen via `POST /api/companies/{id}/seed-bas?fiscal_year_id={fy_id}`
2. Alla konton skapas knutna till det första räkenskapsåret
3. Standardkonton (default accounts) initialiseras via `POST /api/companies/{id}/initialize-defaults`

#### Skapa nytt räkenskapsår
När ett nytt räkenskapsår skapas:
1. Skapa räkenskapsåret: `POST /api/fiscal-years/`
2. Kopiera kontoplanen från föregående år: `POST /api/fiscal-years/{new_fy_id}/copy-chart-of-accounts`
   - Systemet kopierar alla konton från senast avslutade året
   - Opening balance sätts till 0 för det nya året
   - Aktiv/inaktiv status bevaras
3. Default accounts fungerar automatiskt genom att matcha kontonummer

**API Endpoints:**
- `POST /api/fiscal-years/` - Skapa nytt räkenskapsår
- `GET /api/fiscal-years/?company_id={id}` - Lista räkenskapsår
- `GET /api/fiscal-years/current/by-company/{id}` - Hämta aktuellt räkenskapsår
- `POST /api/fiscal-years/{id}/copy-chart-of-accounts` - Kopiera kontoplan
- `POST /api/fiscal-years/{id}/assign-verifications` - Tilldela verifikationer

#### Kontoplan (BAS)
- Import av BAS-kontoplan (svensk standard)
- Kontohantering med typer (Tillgång, Skuld, Intäkt, Kostnad)
- Kontoreskontra (huvudbok)
- Automatisk balansuppdatering
- Konton är knutna till specifika räkenskapsår

**Viktiga konton:**
- **1510** - Kundfordringar
- **1930** - Företagskonto/Bankgiro (standard bankkonto)
- **2440** - Leverantörsskulder
- **2641** - Ingående moms 25%
- **2890** - Upplupna kostnader (anställdas utlägg)
- **2610-2650** - Utgående moms
- **3xxx** - Intäktskonton
- **4xxx-8xxx** - Kostnadskonton

**Kontohantering:**
- Konton kan läggas till, redigeras och inaktiveras per räkenskapsår
- Konton med transaktioner kan inte tas bort
- Aktiva/inaktiva konton styr vilka konton som visas i nya verifikationer

### 2. Verifikationer
- Automatisk numrering per serie (A, B, C, etc.)
- Dubbel bokföring (debet = kredit)
- Låsning av verifikationer
- Detaljvy med balansverifiering
- Koppling till fakturor och utlägg

**Routes:**
- `/verifications` - Lista
- `/verifications/:id` - Detaljvy

### 3. Kundfakturor (Utgående)
- Skapande av fakturor med rader
- PDF-generering
- Statusflöde: Draft → Sent → Paid
- Automatisk verifikation vid utskick
- Automatisk betalningsverifikation

**Bokföring vid utskick:**
```
Debet:  1510 Kundfordringar         [Total]
Kredit: 3xxx Intäktskonton          [Netto per rad]
Kredit: 26xx Utgående moms          [Moms per momssats]
```

**Bokföring vid betalning:**
```
Debet:  1930 Bankkonto              [Belopp]
Kredit: 1510 Kundfordringar         [Belopp]
```

**API Endpoints:**
- `POST /api/invoices/` - Skapa faktura
- `GET /api/invoices/{id}` - Hämta faktura
- `POST /api/invoices/{id}/send` - Skicka och bokför
- `POST /api/invoices/{id}/mark-paid` - Markera betald
- `GET /api/invoices/{id}/pdf` - Ladda ner PDF

**Routes:**
- `/invoices` - Lista
- `/invoices/:id` - Detaljvy

### 4. Leverantörsfakturor (Inkommande)
- Registrering av inkommande fakturor
- Filuppladdning (bilagor)
- Statusflöde: Draft → Sent (Bokförd) → Paid
- Automatisk verifikation vid bokföring
- Automatisk betalningsverifikation

**Bokföring vid registrering:**
```
Debet:  6xxx Kostnadskonton         [Netto per rad]
Debet:  2641 Ingående moms 25%      [Moms]
Kredit: 2440 Leverantörsskulder     [Total]
```

**Bokföring vid betalning:**
```
Debet:  2440 Leverantörsskulder     [Belopp]
Kredit: 1930 Bankkonto              [Belopp]
```

**API Endpoints:**
- `POST /api/supplier-invoices/` - Skapa leverantörsfaktura
- `GET /api/supplier-invoices/{id}` - Hämta faktura
- `POST /api/supplier-invoices/{id}/register` - Bokför
- `POST /api/supplier-invoices/{id}/mark-paid` - Markera betald
- `POST /api/supplier-invoices/{id}/upload-attachment` - Ladda upp bilaga
- `GET /api/supplier-invoices/{id}/attachment` - Ladda ner bilaga

**Routes:**
- `/invoices` - Lista (samma sida som kundfakturor)
- `/supplier-invoices/:id` - Detaljvy

### 5. Utlägg (Personalutlägg)
- Registrering av personalutlägg
- Kvittouppladdning (bilder, PDF)
- Statusflöde: Draft → Submitted → Approved → Paid
- Automatisk verifikation vid godkännande
- Automatisk betalningsverifikation

**Bokföring vid godkännande:**
```
Debet:  6xxx Kostnadskonto          [Netto]
Debet:  2641 Ingående moms          [Moms]
Kredit: 2890 Anställdas skuld       [Total]
```

**Bokföring vid betalning:**
```
Debet:  2890 Anställdas skuld       [Belopp]
Kredit: 1930 Bankkonto              [Belopp]
```

**API Endpoints:**
- `POST /api/expenses/` - Skapa utlägg
- `GET /api/expenses/{id}` - Hämta utlägg
- `POST /api/expenses/{id}/submit` - Skicka för godkännande
- `POST /api/expenses/{id}/approve` - Godkänn
- `POST /api/expenses/{id}/book` - Bokför
- `POST /api/expenses/{id}/mark-paid` - Markera betald
- `POST /api/expenses/{id}/upload-receipt` - Ladda upp kvitto
- `GET /api/expenses/{id}/receipt` - Ladda ner kvitto

**Routes:**
- `/expenses` - Lista
- `/expenses/:id` - Detaljvy

### 6. Kunder & Leverantörer
- Hantering av kundregister
- Hantering av leverantörsregister
- Koppling till fakturor

### 7. Momsrapportering
- Momsrapport per period
- Filtrering på datum
- Exkludera momsredovisningsverifikationer
- Periodsöversikt per år
- Export till Excel

**API Endpoints:**
- `GET /api/reports/vat-report` - Momsrapport
- `GET /api/reports/vat-periods` - Periodsöversikt

### 8. Finansiella Rapporter
- Balansräkning
- Resultaträkning
- Per räkenskapsår

### 9. SIE4 Import/Export
- Import av SIE4-filer
- Export till SIE4-format
- Kompatibelt med andra bokföringsprogram

### 10. Konteringsmallar (Posting Templates)
- Skapande av återanvändbara konteringsmallar
- Formelbaserade beräkningar med variabeln `{total}`
- Automatisk beräkning av konteringsrader
- Malleditor med drag-and-drop sortering
- Förutfyllda svenska standardmallar
- **Stöd för flera räkenskapsår:** Mallar refererar till konton via kontonummer och översätts automatiskt till rätt räkenskapsår vid användning

**Formelexempel:**
- `{total}` - Totalbelopp
- `{total} * 0.25` - 25% av totalbelopp (t.ex. moms)
- `-{total}` - Negativt belopp
- `{total} * 1.25` - Totalbelopp plus 25%

**Hantering av räkenskapsår:**
Mallar skapas med konton från ett specifikt räkenskapsår (vanligtvis det första). När mallen används:
1. Användaren anger vilket räkenskapsår de arbetar i
2. Systemet hittar motsvarande konton (samma kontonummer) i det valda räkenskapsåret
3. Verifikationsrader skapas med konton från det aktuella räkenskapsåret

Detta innebär att en mall skapad år 2024 automatiskt fungerar år 2025, förutsatt att motsvarande konton finns i båda åren.

**API Endpoints:**
- `POST /api/posting-templates/` - Skapa mall
- `GET /api/posting-templates/` - Lista mallar
- `GET /api/posting-templates/{id}` - Hämta mall
- `PUT /api/posting-templates/{id}` - Uppdatera mall
- `DELETE /api/posting-templates/{id}` - Ta bort mall
- `POST /api/posting-templates/{id}/execute` - Kör mall (kräver fiscal_year_id i request body)
- `PATCH /api/posting-templates/reorder` - Ändra sortering

**Routes:**
- `/settings` - Inställningar (fliken "Konteringsmallar")

### 11. Företagsinställningar
- Företagsinformation med automatiskt VAT-nummer
- Logotypuppladdning och visning
- Flikbaserad navigation (Företag, Konton, Räkenskapsår, Mallar, Import)
- Initialisering av standardkonton
- Import av BAS-kontoplan
- Import av standardmallar

**VAT-nummer:**
- Automatisk beräkning från organisationsnummer
- Format: SE + 10 siffror + 01
- Exempel: 556644-4354 → SE556644435401
- Visas på fakturor och i företagsinformation

**Logotyphantering:**
- Format: PNG, JPEG
- Max storlek: 5MB
- Förhandsvisning i inställningar
- Automatisk visning på faktura-PDF
- UUID-baserade filnamn för säkerhet

**API Endpoints:**
- `POST /api/companies/{id}/logo` - Ladda upp logotyp
- `GET /api/companies/{id}/logo` - Hämta logotyp
- `DELETE /api/companies/{id}/logo` - Ta bort logotyp
- `POST /api/companies/{id}/initialize-defaults` - Initiera standardkonton
- `POST /api/companies/{id}/seed-bas` - Importera BAS-kontoplan
- `POST /api/companies/{id}/seed-templates` - Importera standardmallar

**Routes:**
- `/settings` - Inställningar (flikbaserad vy)

## Standardkonfigurationer

### Bankkonto
**Konto 1930** används som standard för alla betalningar:
- Utläggsbetalningar
- Fakturainbetalningar
- Leverantörsfakturabetalningar

### Standardkonton
Systemet använder default accounts för automatisk bokföring:
- `ACCOUNTS_RECEIVABLE` - Kundfordringar (1510)
- `ACCOUNTS_PAYABLE` - Leverantörsskulder (2440)
- `VAT_OUTGOING_25` - Utgående moms 25% (2611)
- `VAT_OUTGOING_12` - Utgående moms 12% (2621)
- `VAT_OUTGOING_6` - Utgående moms 6% (2631)
- `VAT_INCOMING_25` - Ingående moms 25% (2641)
- `VAT_INCOMING_12` - Ingående moms 12% (2642)
- `VAT_INCOMING_6` - Ingående moms 6% (2645)
- `REVENUE_25` - Intäkt med 25% moms (3001)
- `REVENUE_12` - Intäkt med 12% moms (3002)
- `REVENUE_6` - Intäkt med 6% moms (3003)
- `REVENUE_0` - Intäkt utan moms (3100)
- `EXPENSE_DEFAULT` - Standardkostnad (6570)

## Arbetsflöden

### Workflow 1: Skicka Kundfaktura
1. Skapa faktura (Draft)
2. Lägg till fakturarader med moms
3. Klicka "Skicka och bokför"
   - Skapar verifikation
   - Status → Sent
   - Debiterar kundfordringar
   - Krediterar intäkter och moms
4. När kunden betalar: "Markera som betald"
   - Skapar betalningsverifikation
   - Status → Paid
   - Debiterar bankkonto 1930
   - Krediterar kundfordringar

### Workflow 2: Betala Leverantörsfaktura
1. Registrera leverantörsfaktura (Draft)
2. Lägg till fakturarader
3. Klicka "Bokför"
   - Skapar verifikation
   - Status → Sent
   - Debiterar kostnader och ingående moms
   - Krediterar leverantörsskulder
4. När betald: "Markera som betald"
   - Skapar betalningsverifikation
   - Status → Paid
   - Debiterar leverantörsskulder
   - Krediterar bankkonto 1930

### Workflow 3: Hantera Personalutlägg
1. Anställd skapar utlägg (Draft)
2. Laddar upp kvitto
3. Klickar "Skicka in för godkännande" (Submitted)
4. Chef godkänner (Approved)
5. Ekonomi klickar "Bokför"
   - Skapar verifikation
   - Debiterar kostnader och moms
   - Krediterar anställdas skuld 2890
6. När utbetald: "Markera som utbetald"
   - Skapar betalningsverifikation
   - Status → Paid
   - Debiterar anställdas skuld
   - Krediterar bankkonto 1930

## Viktiga Services

### `/backend/app/services/invoice_service.py`
- `create_invoice_verification()` - Bokför kundfaktura
- `create_invoice_payment_verification()` - Bokför fakturainbetalning
- `create_supplier_invoice_verification()` - Bokför leverantörsfaktura
- `create_supplier_invoice_payment_verification()` - Bokför leverantörsfakturabetalning

### `/backend/app/services/expense_service.py`
- `create_expense_verification()` - Bokför utlägg
- `create_expense_payment_verification()` - Bokför utläggsbetalning

### `/backend/app/services/default_account_service.py`
- `get_default_account()` - Hämta standardkonto
- `get_revenue_account_for_vat_rate()` - Hämta intäktskonto för momssats
- `get_vat_outgoing_account_for_rate()` - Hämta utgående momskonto

### `/backend/app/services/pdf_service.py`
- `generate_invoice_pdf()` - Genererar PDF från faktura med Jinja2-mall och WeasyPrint
- `save_invoice_pdf()` - Sparar genererad PDF till disk

## Databasschema

### Viktiga Tabeller
- `companies` - Företag
- `fiscal_years` - Räkenskapsår
- `accounts` - Kontoplan
- `verifications` - Verifikationer
- `transaction_lines` - Transaktionsrader (dubbel bokföring)
- `invoices` - Kundfakturor
- `invoice_lines` - Fakturarader
- `supplier_invoices` - Leverantörsfakturor
- `supplier_invoice_lines` - Leverantörsfakturarader
- `expenses` - Utlägg
- `customers` - Kunder
- `suppliers` - Leverantörer
- `default_accounts` - Standardkonton
- `posting_templates` - Konteringsmallar
- `posting_template_lines` - Konteringsmallrader

### Enum Types
- `InvoiceStatus`: draft, sent, paid, partial, overdue, cancelled
- `ExpenseStatus`: draft, submitted, approved, paid, rejected
- `AccountType`: asset, liability, equity, revenue, expense
- `AccountingBasis`: accrual, cash
- `VATReportingPeriod`: monthly, quarterly, yearly

## Utveckling

### Starta utvecklingsmiljö
```bash
docker compose up
```

### Backend körs på
- http://localhost:8000
- API docs: http://localhost:8000/docs

### Frontend körs på
- http://localhost:5173

### Kör migrationer
```bash
docker compose exec backend alembic upgrade head
```

### Skapa ny migration
```bash
docker compose exec backend alembic revision --autogenerate -m "beskrivning"
```

## Filuppladdning

### Kvitton (Utlägg)
- Lagrad i: `/app/receipts/`
- Docker volume: `./receipts:/app/receipts`
- Format: JPG, JPEG, PNG, PDF, GIF
- Unika filnamn: UUID

### Fakturabilagor (Leverantörsfakturor)
- Lagrad i: `/app/invoices/`
- Docker volume: `./invoices:/app/invoices`
- Format: JPG, JPEG, PNG, PDF, GIF
- Unika filnamn: UUID

### Företagslogotyper
- Lagrad i: `/app/uploads/logos/`
- Docker volume: `./uploads:/app/uploads`
- Format: PNG, JPEG
- Max storlek: 5MB
- Unika filnamn: `{company_id}_{uuid}.{ext}`
- Visas på faktura-PDF

## Säkerhet & Validering

### Backend
- Pydantic validering av all input
- SQLAlchemy ORM för SQL-injektion-skydd
- Enum-validering för statusar
- Foreign key constraints
- Decimal precision för monetära värden

### Frontend
- TypeScript för type safety
- Form validering
- File type validering vid uppladdning
- Bekräftelsedialoger för kritiska åtgärder

## Redigeringsbegränsningar

### Fakturor
- ❌ Kan inte redigera efter att den är betald
- ✅ Kan redigera innan betalning

### Utlägg
- ❌ Kan inte redigera efter bokföring (har verification_id)
- ❌ Kan inte redigera efter betalning
- ✅ Kan redigera i status draft eller submitted

### Verifikationer
- ❌ Kan inte redigera låsta verifikationer
- ✅ Kan redigera olåsta verifikationer

## Git Workflow

Alla ändringar görs på feature branches:
- `claude/fix-momsrapport-reknir-*`
- `claude/momsrapport-merged-*`

### Committing
```bash
git add .
git commit -m "Beskrivning av ändring"
git push -u origin branch-name
```

## API Authentication
Systemet har för närvarande ingen autentisering (single-company mode). Detta kan läggas till i framtiden med JWT tokens eller liknande.

## Framtida Förbättringar

### Planerade Funktioner
- [ ] Användarautentisering och roller
- [ ] Multi-company support
- [ ] Automatiska påminnelser för förfallna fakturor
- [ ] Bankkontointegrationer (BankID, Open Banking)
- [ ] Lönehantering
- [ ] Budgetering och prognoser
- [ ] Dashboard med nyckeltal
- [ ] PDF-export av rapporter
- [ ] E-postutskick av fakturor
- [ ] Automatisk momsredovisning
- [ ] Bokslut och årsbokslut
- [ ] Integration av konteringsmallar med faktura/utlägg-workflows
- [ ] Automatisk matchning av banktransaktioner

### Tekniska Förbättringar
- [ ] Caching (Redis)
- [ ] Bakgrundsjobb för tunga operationer (Celery)
- [ ] Fulltext-sökning (Elasticsearch)
- [ ] Audit log för alla ändringar
- [ ] Backup och disaster recovery
- [ ] Prestanda-optimering av stora datamängder
- [ ] WebSocket för realtidsuppdateringar

## Support & Dokumentation

### Svensk Bokföring
- BAS-kontoplan: https://www.bas.se/
- Bokföringsnämnden: https://www.bfn.se/
- Skatteverket: https://www.skatteverket.se/

### Teknisk Dokumentation
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- SQLAlchemy: https://docs.sqlalchemy.org/

## Licens
[Ange licens här]

## Kontakt
[Ange kontaktinformation här]

---

**Version:** 1.2.0
**Senast uppdaterad:** 2025-12-02

## Ändringslogg

### v1.2.0 (2025-12-02)
- ✅ Fullständigt stöd för flera räkenskapsår med separata kontoplaner
- ✅ Automatisk kopiering av kontoplan mellan räkenskapsår
- ✅ Konteringsmallar fungerar över räkenskapsår genom kontonummer-mappning
- ✅ Default accounts översätts automatiskt till rätt räkenskapsår
- ✅ Förbättrad dokumentation för räkenskapsår-hantering

### v1.1.0 (2025-11-30)
- ✅ Konteringsmallar med formelbaserade beräkningar
- ✅ Företagslogotyp upload och PDF-integration
- ✅ Automatisk VAT-nummer beräkning
- ✅ Flikbaserad inställningssida
- ✅ Förbättrad faktura-PDF mall
- ✅ Etiketter på fakturarader

### v1.0.0 (2025-01-11)
- Initial release med grundläggande bokföringsfunktioner
