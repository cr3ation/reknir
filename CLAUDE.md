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

### 1. Kontoplan (BAS)
- Import av BAS-kontoplan (svensk standard)
- Kontohantering med typer (Tillgång, Skuld, Intäkt, Kostnad)
- Kontoreskontra (huvudbok)
- Automatisk balansuppdatering

**Viktiga konton:**
- **1510** - Kundfordringar
- **1930** - Företagskonto/Bankgiro (standard bankkonto)
- **2440** - Leverantörsskulder
- **2641** - Ingående moms 25%
- **2890** - Upplupna kostnader (anställdas utlägg)
- **2610-2650** - Utgående moms
- **3xxx** - Intäktskonton
- **4xxx-8xxx** - Kostnadskonton

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

### 7. Standardkonton (Default Accounts)
- Mappning av konton till funktioner för automatisk bokföring
- Stöd för olika momssatser (25%, 12%, 6%, 0%)
- Företagsspecifika konfigurationer
- Automatisk initialisering vid BAS-import
- Manuell redigering via inställningar

**Standardkontotyper:**
- `revenue_25/12/6/0` - Intäktskonton per momssats
- `vat_outgoing_25/12/6` - Utgående moms
- `vat_incoming_25/12/6` - Ingående moms
- `accounts_receivable` - Kundfordringar (1510)
- `accounts_payable` - Leverantörsskulder (2440)
- `expense_default` - Standardkostnadskonto (6570)

**API Endpoints:**
- `GET /api/default-accounts/?company_id={id}` - Lista standardkonton
- `POST /api/default-accounts/` - Skapa standardkonto
- `PATCH /api/default-accounts/{id}` - Uppdatera standardkonto

**Validering:**
- Kontot måste existera i företagets kontoplan
- Ett standardkontotyp kan bara ha ett konto per företag
- Kan inte ta bort konto som används som standardkonto

**Routes:**
- `/settings` - Inställningar (fliken "Standardkonton")

### 8. Momsrapportering
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

### 11. Konteringsmallar (Posting Templates)
- Skapande av återanvändbara konteringsmallar
- Formelbaserade beräkningar med variabeln `{total}`
- Automatisk beräkning av konteringsrader
- Malleditor med drag-and-drop sortering
- Förutfyllda svenska standardmallar

**Formelexempel:**
- `{total}` - Totalbelopp
- `{total} * 0.25` - 25% av totalbelopp (t.ex. moms)
- `-{total}` - Negativt belopp
- `{total} * 1.25` - Totalbelopp plus 25%

**API Endpoints:**
- `POST /api/posting-templates/` - Skapa mall
- `GET /api/posting-templates/` - Lista mallar
- `GET /api/posting-templates/{id}` - Hämta mall
- `PUT /api/posting-templates/{id}` - Uppdatera mall
- `DELETE /api/posting-templates/{id}` - Ta bort mall
- `POST /api/posting-templates/{id}/execute` - Kör mall med belopp
- `PATCH /api/posting-templates/reorder` - Ändra sortering

**Routes:**
- `/settings` - Inställningar (fliken "Konteringsmallar")

### 12. Företagsinställningar
- Företagsinformation med automatiskt VAT-nummer
- Logotypuppladdning och visning
- Flikbaserad navigation (Företag, Konton, Standardkonton, Räkenskapsår, Mallar, Import)
- Hantering av standardkonton via grafiskt gränssnitt
- Hantering av kontoplan (Lägg till/ta bort/inaktivera konton)
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

**Kontohantering (Settings > Konton):**
- Redigera standardkonton via dropdown-menyer
- Visa alla företagets konton i tabell
- Lägg till konton från BAS 2024 referenslista
- Ta bort/inaktivera konton:
  - Konton med transaktioner markeras som inaktiva (kan aktiveras igen)
  - Konton utan transaktioner raderas permanent
  - Konton som är standardkonton kan inte tas bort
- Filtrering: Endast konton som inte redan finns visas vid tillägg

**API Endpoints:**
- `POST /api/companies/{id}/logo` - Ladda upp logotyp
- `GET /api/companies/{id}/logo` - Hämta logotyp
- `DELETE /api/companies/{id}/logo` - Ta bort logotyp
- `GET /api/companies/bas-accounts` - Hämta BAS 2024 referensdata
- `POST /api/companies/{id}/initialize-defaults` - Initiera standardkonton
- `POST /api/companies/{id}/seed-bas` - Importera BAS-kontoplan
- `POST /api/companies/{id}/seed-templates` - Importera standardmallar
- `POST /api/accounts/` - Skapa nytt konto
- `DELETE /api/accounts/{id}` - Ta bort eller inaktivera konto
- `PATCH /api/accounts/{id}` - Uppdatera konto (t.ex. aktivera igen)

**Routes:**
- `/settings` - Inställningar (flikbaserad vy)

## Standardkonfigurationer

### Bankkonto
**Konto 1930** används som standard för alla betalningar:
- Utläggsbetalningar
- Fakturainbetalningar
- Leverantörsfakturabetalningar

### Standardkonton
Systemet använder default accounts för automatisk bokföring. Dessa konfigureras per företag och kan redigeras via Inställningar > Standardkonton. Se **sektion 7** för mer information.

**Standardtyper (med typiska BAS-kontonummer):**
- `accounts_receivable` - Kundfordringar (1510)
- `accounts_payable` - Leverantörsskulder (2440)
- `vat_outgoing_25/12/6` - Utgående moms (2611/2621/2631)
- `vat_incoming_25/12/6` - Ingående moms (2641/2642/2645)
- `revenue_25/12/6/0` - Intäktskonton (3001/3002/3003/3044)
- `expense_default` - Standardkostnad (6570)

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
**Senast uppdaterad:** 2025-11-30

## Ändringslogg

### v1.2.0 (2025-11-30)
- ✅ Standardkonton-system (Default Accounts):
  - Dedicated tab i Settings för hantering av standardkonton
  - CREATE endpoint för nya standardkonton (`POST /api/default-accounts/`)
  - UPDATE endpoint för befintliga standardkonton (`PATCH /api/default-accounts/{id}`)
  - Strikt validering: endast befintliga konton kan användas
  - Modal-baserad redigering med editerings-ikoner
  - Skydd mot borttagning av konton som används som standardkonton
- ✅ Kontohantering i Settings:
  - Lägg till konton från BAS 2024 referensdata
  - Intelligent borttagning/inaktivering av konton
- ✅ BAS 2024 API-förbättringar:
  - Fixad route-ordning för `/api/companies/bas-accounts`
  - Konto 3044 (0% moms) tillagt till referensen
  - Uppdaterad label: "Försäljning 0% moms" (inte bara export)
- ✅ API-dokumentation: Swagger tags nu lowercase (`default-accounts`)

### v1.1.0 (2025-11-30)
- ✅ Konteringsmallar med formelbaserade beräkningar
- ✅ Företagslogotyp upload och PDF-integration
- ✅ Automatisk VAT-nummer beräkning
- ✅ Flikbaserad inställningssida
- ✅ Förbättrad faktura-PDF mall
- ✅ Etiketter på fakturarader

### v1.0.0 (2025-01-11)
- Initial release med grundläggande bokföringsfunktioner
