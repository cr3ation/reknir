# Reknir MCP Server

MCP (Model Context Protocol) server för Reknir bokföringssystem. Låter AI-assistenter (som Claude) interagera med Reknir för att automatisera bokföringsuppgifter.

## Användningsområden

- 📸 **Fakturascanning** - Ladda upp fakturabilder, AI läser och lägger in dem automatiskt
- 📊 **Bokföringsfrågor** - "Hur mycket moms har jag betalat i Q3?"
- 🤖 **Automatisk kategorisering** - AI föreslår rätt kontokoder
- 📝 **Snabb inmatning** - "Lägg in en faktura från Elgiganten för 2499 kr..."

## Installation

### 1. Installera beroenden

```bash
cd mcp-server
pip install -e .
```

### 2. Konfigurera miljövariabler

```bash
cp .env.example .env
# Redigera .env med rätt REKNIR_API_URL och COMPANY_ID
```

### 3. Starta servern (för testning)

```bash
python -m src.server
```

### 4. Integrera med Claude Desktop

Lägg till i din Claude Desktop konfiguration (`~/Library/Application Support/Claude/claude_desktop_config.json` på Mac):

```json
{
  "mcpServers": {
    "reknir": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/absolute/path/to/reknir/mcp-server",
      "env": {
        "REKNIR_API_URL": "http://localhost:8000",
        "REKNIR_COMPANY_ID": "1"
      }
    }
  }
}
```

## Tillgängliga verktyg

### Leverantörer
- `find_supplier` - Hitta leverantör (org.nr, namn)
- `create_supplier` - Skapa ny leverantör
- `list_suppliers` - Lista alla leverantörer

### Fakturor
- `create_supplier_invoice` - Skapa leverantörsfaktura med rader
- `list_supplier_invoices` - Lista fakturor
- `register_invoice` - Bokför faktura
- `mark_invoice_paid` - Markera som betald

### Konton
- `list_accounts` - Lista alla konton
- `search_accounts` - Sök konto (nummer, namn, typ)
- `get_account_balance` - Hämta kontosaldo

### Företag
- `get_company_info` - Hämta företagsinformation
- `list_companies` - Lista alla företag

## Exempel: Fakturascanning

```
Du: *laddar upp bild på faktura*
Lägg in denna faktura i Reknir

Claude: Jag läser fakturan och ser:
- Leverantör: Kontorsmaterial AB (556789-1234)
- Fakturanr: 12345
- Datum: 2024-11-10
- Rader:
  * Papper A4: 450 kr + 112.50 moms
  * Pennor: 150 kr + 37.50 moms
- Total: 750 kr

Ska jag lägga in den?

Du: Ja!

Claude: [Använder MCP-verktyg]
✓ Leverantör hittad (ID: 23)
✓ Faktura skapad (INV-12345)
✓ Rader tillagda (konto 6071 - Kontorsmaterial)
✓ Bokförd!

Klar! Leverantörsskuld 750 kr registrerad.
```

## Utveckling

Projektstruktur:
```
mcp-server/
├── src/
│   ├── server.py          # Huvudserver
│   ├── client.py          # Reknir API-klient
│   └── tools/             # MCP-verktyg
│       ├── suppliers.py
│       ├── invoices.py
│       ├── accounts.py
│       └── companies.py
├── pyproject.toml         # Python dependencies
├── README.md
└── .env.example
```

## Krav

- Python 3.10+
- Reknir backend (körs på http://localhost:8000)
- Claude Desktop (för användning)

## Licens

Samma som Reknir huvudprojekt
