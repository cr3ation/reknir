# Reknir MCP Server - Användningsexempel

## Installation & Setup

### 1. Installera MCP servern

```bash
cd mcp-server
pip install -e .
```

### 2. Skapa .env fil

```bash
cp .env.example .env
```

Redigera `.env`:
```
REKNIR_API_URL=http://localhost:8000
REKNIR_COMPANY_ID=1
```

### 3. Konfigurera Claude Desktop

På Mac: `~/Library/Application Support/Claude/claude_desktop_config.json`
På Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Lägg till:
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

**OBS:** Byt `/absolute/path/to/reknir/mcp-server` till den faktiska sökvägen!

### 4. Starta om Claude Desktop

Efter att ha lagt till konfigurationen, starta om Claude Desktop så att MCP-servern laddas.

## Användningsexempel

### Exempel 1: Scanna och lägg in faktura

```
Du: [Laddar upp bild på faktura från Elgiganten]

Kan du läsa denna faktura och lägga in den i Reknir?

Claude: Jag läser fakturan och ser:

Leverantör: Elgiganten AB
Org.nr: 556314-2250
Fakturanummer: 2024-12345
Datum: 2024-11-10
Förfallodatum: 2024-12-10

Fakturarader:
1. Bärbar dator HP EliteBook - 1 st × 12 995 kr (moms 25%)
2. Datormus Logitech MX - 2 st × 495 kr (moms 25%)

Summa exkl. moms: 13 985 kr
Moms 25%: 3 496.25 kr
Totalt: 17 481.25 kr

Jag kollar om leverantören finns i systemet...

[MCP: find_supplier med org_number "556314-2250"]

Leverantören finns redan registrerad!

Vilka konton ska jag använda för dessa inköp?
- Datorer brukar vara konto 5060 (Datorer)
- Datortillbehör brukar vara konto 5069 (Övrig kontorsutrustning)

Vill du att jag lägger in fakturan med dessa konton?

Du: Ja, gör det!

Claude:
[MCP: create_supplier_invoice]
[MCP: register_invoice]

✓ Faktura inlagd och bokförd!

Leverantörsfaktura 2024-12345 från Elgiganten AB
- Konto 5060 (Datorer): 12 995 kr + 3 248.75 moms
- Konto 5069 (Övrig utrustning): 990 kr + 247.50 moms
- Leverantörsskuld: 17 481.25 kr

Fakturan är nu bokförd och visas i leverantörsskulder.
Förfallodatum: 2024-12-10

Vill du att jag markerar den som betald också?
```

### Exempel 2: Hitta leverantör

```
Du: Finns leverantören "Telia" i systemet?

Claude: [MCP: find_supplier med name "Telia"]

Ja, hittade leverantör:
- Namn: Telia Sverige AB
- Org.nr: 556430-0142
- ID: 15
- Aktiv: Ja
- Email: faktura@telia.se

Vill du se fakturor från Telia?
```

### Exempel 3: Skapa ny leverantör

```
Du: Lägg till ny leverantör: Kontorsmaterial Nordic AB, org.nr 559876-5432

Claude: [MCP: find_supplier med org_number "559876-5432"]

Leverantören finns inte i systemet. Ska jag skapa den?

Du: Ja

Claude: [MCP: create_supplier]

✓ Leverantör skapad!
- ID: 47
- Namn: Kontorsmaterial Nordic AB
- Org.nr: 559876-5432

Leverantören är nu registrerad och kan användas för fakturor.
```

### Exempel 4: Sök rätt kontokod

```
Du: Vilket konto ska jag använda för hyra?

Claude: [MCP: search_accounts med query "hyra"]

Hittade följande konton:

5010 - Lokalhyra
  Typ: expense, Balans: 120 000.00 SEK (ID: 234)

5020 - Hyra av inventarier och verktyg
  Typ: expense, Balans: 15 000.00 SEK (ID: 235)

5030 - Värme, el, vatten och bränsle
  Typ: expense, Balans: 8 500.00 SEK (ID: 236)

För kontorshyra använder du konto 5010 (ID: 234).
För hyra av utrustning använder du konto 5020 (ID: 235).
```

### Exempel 5: Lista fakturor

```
Du: Visa mina obetalda fakturor

Claude: [MCP: list_supplier_invoices med status "sent"]

Obetalda leverantörsfakturor (5 st):

📤 2024-12345 - Elgiganten AB - 17 481.25 SEK (sent)
📤 INV-9876 - Telia Sverige AB - 2 495.00 SEK (sent)
📤 F-2024-001 - Office Depot - 3 890.50 SEK (sent)
📤 2024-456 - Vattenfall - 1 250.00 SEK (sent)
📤 INV-2024-789 - Google Sweden AB - 8 900.00 SEK (sent)

Total skuld: 34 016.75 SEK

Vill du se detaljer för någon av dessa?
```

### Exempel 6: Markera faktura som betald

```
Du: Jag betalade Elgiganten-fakturan idag

Claude: [MCP: list_supplier_invoices med supplier_name "Elgiganten"]

Hittade faktura från Elgiganten:
- Fakturanummer: 2024-12345
- Belopp: 17 481.25 SEK
- Status: sent (obetald)

[MCP: mark_invoice_paid]

✓ Faktura markerad som betald!

Betalning registrerad:
- Faktura: 2024-12345
- Datum: 2024-11-11
- Belopp: 17 481.25 SEK

Verifikation skapad och leverantörsskuld minskad.
```

### Exempel 7: Företagsinformation

```
Du: Visa info om företaget

Claude: [MCP: get_company_info]

Företagsinformation:

ID: 1
Namn: Mitt Företag AB
Org. Number: 556789-1234
Adress: Storgatan 1
Postnummer: 123 45
Stad: Stockholm
Telefon: 08-123 456 78
Email: info@mittforetag.se

Räkenskapsår: 2024-01-01 to 2024-12-31
Bokföringsmetod: accrual
Momsredovisning: quarterly

Använd company_id=1 i andra verktyg.
```

## Tips för bästa resultat

### 1. Fakturabilder
- Fotografera eller scanna fakturan tydligt
- Se till att all text är läsbar
- Inkludera hela fakturan (inte beskuren)

### 2. Kommunicera tydligt
- "Lägg in denna faktura" - Claude förstår och använder rätt verktyg
- "Vilken leverantör har org.nr..." - Claude söker automatiskt
- "Bokför fakturan" - Claude använder register_invoice

### 3. Granska innan bokföring
- Claude visar alltid en sammanfattning innan bokföring
- Du kan korrigera kontokoder innan fakturan bokförs
- Säg "vänta" eller "nej" för att stoppa processen

### 4. Flera företag
Om du har flera företag i Reknir:
```
Du: Lägg in fakturan för företag 2

Claude: [MCP: get_company_info med company_id=2]
[MCP: create_supplier_invoice med company_id=2]
```

## Felsökning

### "Reknir client not initialized"
- Kontrollera att Reknir backend körs (http://localhost:8000)
- Verifiera .env filen har rätt REKNIR_API_URL

### "Company ID not found"
- Kontrollera REKNIR_COMPANY_ID i .env
- Kör `get_company_info` eller `list_companies` för att se tillgängliga företag

### "MCP server not responding"
- Starta om Claude Desktop
- Kontrollera `cwd` i claude_desktop_config.json är korrekt absolut sökväg
- Kolla loggar i Claude Desktop (Help → Show Logs)

## Avancerade användningsfall

### Automatisk kontokodning med AI
```
Du: När jag får fakturor för kaffe och fika, vilket konto ska användas?

Claude: [MCP: search_accounts med query "representation"]

För kaffe och fika till personal:
- 6420 - Personalrepresentation (interna möten med fika)

För kundmöten med fika:
- 6330 - Representation (externa kunder och partners)

Jag kommer ihåg detta och använder rätt konto automatiskt!
```

### Batch-inmatning
```
Du: Jag har 5 fakturor att lägga in:
1. Elgiganten - dator 12 995 kr
2. Telia - abonnemang 2 495 kr
3. Circle K - bensin 850 kr
4. ICA - kontorsmat 450 kr
5. Vattenfall - el 1 250 kr

Claude: Perfekt! Jag lägger in dessa en i taget:

[Processar alla 5 fakturor med rätt kontokoder automatiskt]

✓ Alla 5 fakturor inlagda och bokförda!
Total skuld tillagd: 18 040 kr
```

## Nästa steg

- Lägg till fler verktyg (utlägg, kundfakturor, rapporter)
- Integrera med OCR för bättre fakturaläsning
- Bygg webhooks för automatisk fakturaimport från email
- Lägg till budgetkontroll ("Varnar om kostnader över budget")

Lycka till med din bokföring! 🚀
