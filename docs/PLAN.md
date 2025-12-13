# Swedish Bookkeeping Software - Comprehensive Development Plan

## Project Overview
A web-based bookkeeping (bokföring) system designed for Swedish businesses, with full compliance to Swedish accounting standards, AI-powered assistance, and comprehensive import/export capabilities.

## Core Requirements

### 1. Transaction Management (Verifikationer)
- **Accounting Entries (Bokföringsorder)**
  - Manual transaction entry with debit/credit posting
  - Multi-line transactions (compound entries)
  - Attachment support (receipts, invoices as PDF/images)
  - Transaction templates for common entries
  - Verification numbers (löpnummer) with series management
  - Transaction date vs booking date (transaktionsdatum vs bokföringsdatum)
  - Transaction locking after period closing

- **Chart of Accounts (Kontoplan)**
  - BAS 2024 kontoplan as default
  - Support for custom account modifications
  - Account types: Tillgångar, Skulder, Eget kapital, Intäkter, Kostnader
  - Cost centers (kostnadsställen) and projects support
  - Account balancing rules (IB/UB calculations)

### 2. VAT Management (Momsredovisning)
- **VAT Codes & Rates**
  - Standard rates: 25%, 12%, 6%
  - Exempt (momsfri)
  - Reverse charge (omvänd skattskyldighet)
  - EU transactions (gemenskapsförvärv/leverans)
  - Import/Export handling

- **VAT Reporting**
  - Automatic VAT report generation (momsdeklaration)
  - Period management (monthly/quarterly/annual)
  - Box mapping for Skatteverket forms
  - Digital submission format (XML for Skatteverket)
  - VAT reconciliation and verification

### 3. Expense Management (Utlägg)
- Employee expense claims
- Receipt capture and OCR
- Approval workflows
- Mileage and per diem calculations (traktamente)
- Reimbursement tracking
- VAT extraction from expenses
- Integration with transaction creation

### 4. Swedish Accounting Compliance

#### Account Structure (BAS Kontoplan)
- **Class 1**: Tillgångar (Assets)
- **Class 2**: Eget kapital och skulder (Equity & Liabilities)
- **Class 3**: Inkomster och intäkter (Revenue)
- **Class 4-5**: Kostnader för varor, material och lokaler (Operating expenses)
- **Class 6**: Övriga externa kostnader (Other external costs)
- **Class 7**: Personalkostnader (Personnel costs)
- **Class 8**: Diverse kostnader (Miscellaneous costs)

#### Compliance Rules
- **Bookkeeping Act (Bokföringslagen)**
  - 7-year retention requirement
  - Chronological transaction recording
  - Audit trail (verifikationskedja)
  - No retroactive modifications (only correcting entries)

- **Annual Accounts Act (Årsredovisningslagen)**
  - Balance sheet structure
  - Income statement format (K1, K2, K3 schemes)
  - Notes and disclosures

### 5. Import/Export Functionality

#### SIE Format Support
**SIE4 (Standard Import/Export Format)**
- Full SIE4 file generation for export
- Import from other accounting systems
- Support for all SIE post types:
  - #FLAGGA (file marker)
  - #PROGRAM, #FORMAT, #GEN
  - #SIETYP 4
  - #FNR (company ID)
  - #ORGNR (organization number)
  - #KONTO (accounts)
  - #IB (opening balances)
  - #UB (closing balances)
  - #VER (transactions/verifications)
  - #TRANS (transaction lines)

#### Tax Export Formats
- **VAT Declaration XML**
  - Skatteverket INK2R format
  - Direct digital submission support

- **Annual Report Data**
  - K-forms export (K10, K2, K3)
  - Bolagsverket submission format

#### Banking Integration
- Import bank statements (CSV, Bankgirot, Plusgirot)
- Automatic transaction matching
- Swedbank, SEB, Nordea, Handelsbanken formats

### 6. AI-Powered Features

#### Transaction Assistant
- **Intelligent Account Suggestions**
  - Analyze transaction description and amount
  - Suggest appropriate accounts based on:
    - Transaction history
    - Industry patterns
    - Swedish accounting conventions
  - VAT code recommendations
  - Cost center allocation suggestions

- **Natural Language Entry**
  - "Köpte kontorsmaterial för 2400 kr inkl moms"
  - AI parses and creates proper accounting entry
  - Handles complex scenarios with multiple accounts

- **Receipt OCR & Analysis**
  - Extract vendor, amount, date, VAT
  - Identify expense categories
  - Auto-generate verification entries

- **Anomaly Detection**
  - Identify unusual transactions
  - Balance verification
  - VAT calculation validation
  - Suggest corrections

#### MCP (Model Context Protocol) Integration
**Claude Desktop Integration**
- **Accounting Advisory Server**
  - Answer accounting questions in Swedish context
  - Explain tax implications
  - Guide on proper account usage
  - Interpret accounting rules (BFL, ÅRL)

- **Transaction Review Tool**
  - Expose MCP tools for:
    - `get_transaction_details`
    - `list_unbalanced_accounts`
    - `analyze_vat_period`
    - `suggest_corrections`

- **Document Analysis**
  - Analyze contracts for accounting implications
  - Review invoices for completeness
  - Check compliance with regulations

### 7. Technical Architecture

#### Frontend Stack
**Framework**: React with TypeScript
- **UI Library**: Tailwind CSS + shadcn/ui or Material-UI
- **State Management**: Zustand or Redux Toolkit
- **Forms**: React Hook Form with Zod validation
- **Data Tables**: TanStack Table
- **Charts**: Recharts or Chart.js
- **i18n**: Swedish localization with i18next

#### Backend Stack
**Framework**: Node.js with Express or Fastify (OR Python Django/FastAPI)
- **API**: RESTful + GraphQL (optional)
- **Authentication**: JWT + OAuth2
- **Database**: PostgreSQL (strong ACID compliance for accounting)
- **ORM**: Prisma (Node) or SQLAlchemy (Python)
- **File Storage**: MinIO or AWS S3 for receipts/documents
- **Task Queue**: Bull/BullMQ for async processing

#### AI Integration Layer
**LLM Integration**
- **Provider**: Anthropic Claude API (Sonnet 4.5)
- **Embeddings**: OpenAI or Cohere for semantic search
- **Vector DB**: Pinecone or pgvector for knowledge base
- **Prompt Management**: LangChain or custom framework

**MCP Server**
- Implement accounting-specific MCP server
- TypeScript-based server implementation
- Tools for transaction CRUD, reporting, analysis
- Expose to Claude Desktop

#### Database Schema (Key Tables)

```sql
-- Companies
companies (id, org_nr, name, fiscal_year_start, accounting_basis)

-- Chart of Accounts
accounts (id, company_id, account_number, name, type, vat_code, active)

-- Transactions/Verifications
verifications (id, company_id, verification_number, series, date, description, locked)

-- Transaction Lines
transaction_lines (id, verification_id, account_id, debit, credit, description, cost_center_id)

-- VAT Codes
vat_codes (id, code, name, rate, account_debit, account_credit)

-- VAT Periods
vat_periods (id, company_id, start_date, end_date, status, reported_date)

-- Expenses (Utlägg)
expenses (id, company_id, employee_id, date, amount, vat_amount, status, receipt_url)

-- File Attachments
attachments (id, verification_id, expense_id, file_path, file_type, uploaded_at)

-- AI Transaction Suggestions
ai_suggestions (id, transaction_id, suggested_account, confidence, reasoning)
```

#### Security & Compliance
- **Encryption**: At-rest (database) and in-transit (TLS)
- **Audit Logging**: All modifications tracked with user, timestamp
- **Role-Based Access**: Admin, Accountant, Read-only
- **Multi-tenancy**: Complete data isolation per company
- **Backup**: Daily automated backups with 7-year retention
- **GDPR Compliance**: Data portability, right to erasure (with legal accounting exceptions)

### 8. User Interface Design

#### Main Modules
1. **Dashboard**
   - Account balances summary
   - Recent transactions
   - Upcoming VAT deadlines
   - AI insights and alerts

2. **Transactions (Verifikationer)**
   - List view with filtering
   - Create/edit verification entry
   - Attachment viewer
   - AI assistant sidebar

3. **Chart of Accounts (Kontoplan)**
   - Tree view of accounts
   - Balance display (IB, changes, UB)
   - Account configuration

4. **VAT Management (Moms)**
   - Period selector
   - VAT report preview
   - Submit to Skatteverket
   - Historical declarations

5. **Expenses (Utlägg)**
   - Mobile-friendly expense submission
   - Receipt upload with camera
   - Approval queue
   - Reimbursement status

6. **Reports (Rapporter)**
   - Balance sheet (Balansräkning)
   - Income statement (Resultaträkning)
   - General ledger (Huvudbok)
   - Custom report builder

7. **Settings (Inställningar)**
   - Company information
   - Fiscal year management
   - User management
   - Integration configuration
   - AI assistant settings

### 9. Implementation Phases

#### Phase 1: Foundation (Months 1-2)
**Milestone**: Basic transaction management system

- [ ] Project setup (monorepo structure)
- [ ] Database schema implementation
- [ ] Authentication system
- [ ] Basic UI framework
- [ ] BAS kontoplan import
- [ ] Manual transaction entry (create, read, update)
- [ ] Basic account balancing
- [ ] Simple list/search views

**Deliverable**: Users can create companies, enter transactions manually, view basic account balances

#### Phase 2: Core Accounting (Months 3-4)
**Milestone**: Full Swedish accounting compliance

- [ ] Complete verification workflow
- [ ] Period opening/closing
- [ ] Transaction locking mechanism
- [ ] Attachment management
- [ ] Multi-series verification numbering
- [ ] Cost center support
- [ ] Account reconciliation tools
- [ ] Basic reporting (balance sheet, income statement)

**Deliverable**: Complete bookkeeping workflow following Swedish standards

#### Phase 3: VAT Management (Month 5)
**Milestone**: Automated VAT handling and reporting

- [ ] VAT code configuration system
- [ ] Automatic VAT calculations on transactions
- [ ] VAT report generation
- [ ] Period management (monthly/quarterly)
- [ ] Skatteverket XML export
- [ ] VAT reconciliation tools
- [ ] EU transaction support

**Deliverable**: Complete VAT declaration process with digital submission

#### Phase 4: Import/Export (Month 6)
**Milestone**: Interoperability with other systems

- [ ] SIE4 import parser
- [ ] SIE4 export generator
- [ ] Bank statement import (CSV)
- [ ] Bank-specific format parsers (Swedbank, SEB, etc.)
- [ ] Transaction matching algorithms
- [ ] K-form export preparation
- [ ] Data migration tools

**Deliverable**: Full SIE4 support and bank integrations

#### Phase 5: Expense Management (Month 7)
**Milestone**: Complete utlägg workflow

- [ ] Expense claim submission (web + mobile-optimized)
- [ ] Receipt upload and storage
- [ ] Basic OCR for receipt data extraction
- [ ] Approval workflow engine
- [ ] Mileage calculator (Swedish rates)
- [ ] Per diem calculator (traktamente)
- [ ] Expense-to-transaction conversion
- [ ] Reimbursement tracking

**Deliverable**: End-to-end expense management

#### Phase 6: AI Integration - Basic (Month 8)
**Milestone**: AI-assisted transaction entry

- [ ] Claude API integration
- [ ] Account suggestion engine
- [ ] Transaction description analysis
- [ ] Natural language transaction parsing
- [ ] Historical pattern learning
- [ ] Confidence scoring system
- [ ] AI suggestions UI components
- [ ] OCR enhancement with AI

**Deliverable**: AI suggests accounts and helps parse transactions

#### Phase 7: AI Integration - Advanced (Month 9)
**Milestone**: Full AI advisory and MCP

- [ ] MCP server implementation
- [ ] Accounting knowledge base
- [ ] MCP tools for transaction analysis
- [ ] Claude Desktop integration guide
- [ ] Anomaly detection system
- [ ] VAT validation AI
- [ ] Interactive accounting assistant
- [ ] Multi-turn conversation support

**Deliverable**: MCP-based accounting assistant available in Claude Desktop

#### Phase 8: Advanced Reporting (Month 10)
**Milestone**: Comprehensive reporting and analytics

- [ ] Custom report builder
- [ ] General ledger with drill-down
- [ ] Trial balance (RAR)
- [ ] Cash flow statement
- [ ] Key metrics dashboard
- [ ] Comparative reports (year-over-year)
- [ ] Export to Excel/PDF
- [ ] Scheduled report generation

**Deliverable**: Professional-grade reporting suite

#### Phase 9: Annual Reporting (Month 11)
**Milestone**: Year-end closing support

- [ ] Year-end closing wizard
- [ ] Depreciation calculations
- [ ] Accruals and deferrals management
- [ ] Inventory valuation
- [ ] K2/K3 forms (simplified annual reports)
- [ ] Notes and disclosures templates
- [ ] Bolagsverket export format
- [ ] AI-assisted note generation

**Deliverable**: Complete annual reporting within the system

#### Phase 10: Polish & Launch (Month 12)
**Milestone**: Production-ready system

- [ ] Performance optimization
- [ ] Security audit
- [ ] Comprehensive testing (unit, integration, E2E)
- [ ] User documentation (Swedish)
- [ ] Video tutorials
- [ ] Migration tools from competitors
- [ ] Beta user testing
- [ ] Launch preparation

**Deliverable**: Public launch

### 10. Key Technical Decisions

#### Programming Languages
**Recommended**: TypeScript/Node.js for full stack
- Unified language across frontend/backend
- Excellent for MCP server implementation
- Strong typing for accounting accuracy
- Rich ecosystem

**Alternative**: Python backend + TypeScript frontend
- Python excellent for data processing and AI
- Django/FastAPI mature frameworks
- But adds language complexity

#### Database
**PostgreSQL** (strongly recommended)
- ACID compliance critical for accounting
- JSON support for flexible fields
- pgvector for AI embeddings
- Excellent audit trail capabilities
- Mature backup and replication

#### Hosting & Infrastructure
**Recommended Stack**:
- **Application**: Vercel/Railway/Render (for Node) or AWS ECS
- **Database**: Managed PostgreSQL (AWS RDS, Railway, Supabase)
- **Storage**: AWS S3 or compatible (Backblaze B2, Cloudflare R2)
- **CDN**: Cloudflare
- **Monitoring**: Sentry, LogRocket, Grafana

#### AI Provider
**Anthropic Claude** (primary)
- Superior reasoning for accounting logic
- Excellent Swedish language support
- MCP built by Anthropic
- Strong context windows for document analysis

**Fallback**: OpenAI GPT-4
- For specific features if needed
- Good OCR capabilities

### 11. Compliance Checklist

#### Swedish Bokföringslagen (BFL) Requirements
- [x] 7-year data retention
- [x] Chronological transaction recording
- [x] Immutable transactions (only correcting entries)
- [x] Verification documentation attached
- [x] Organization number on all records
- [x] Swedish language support
- [x] Audit trail for all changes
- [x] Balance sheet equation enforcement (Assets = Liabilities + Equity)

#### Skatteverket Integration
- [x] VAT report format compliance
- [x] Digital submission support (future: direct API integration)
- [x] Correct box mapping for momsdeklaration
- [x] Proper rounding rules
- [x] Period management

#### Data Protection (GDPR)
- [x] Data encryption
- [x] Access controls
- [x] Data portability (SIE4 export)
- [x] Right to erasure (with accounting law exceptions noted)
- [x] Processing records
- [x] Privacy policy

### 12. Success Metrics

#### User Adoption
- Time to first transaction: < 10 minutes
- Daily active users per company: > 70%
- Transaction entry time: < 2 minutes average
- AI suggestion acceptance rate: > 60%

#### Accuracy
- Zero balance verification: 100%
- VAT calculation accuracy: 99.99%
- AI account suggestion accuracy: > 85%
- Bank reconciliation match rate: > 90%

#### Performance
- Page load time: < 2 seconds
- Transaction search: < 500ms
- Report generation: < 5 seconds for standard reports
- SIE4 export: < 10 seconds for 1 year of data

### 13. Competitive Analysis

#### Existing Swedish Solutions
**Fortnox**
- Market leader, comprehensive
- Legacy UI, complex for small businesses
- Limited AI features

**Visma eEkonomi**
- Strong in Nordics
- Good integrations
- Traditional approach

**Bokio**
- Modern, free tier
- Simple and user-friendly
- Limited advanced features

**Our Differentiation**:
1. **AI-First Design**: Native AI assistance throughout
2. **Modern UX**: Fast, intuitive, mobile-friendly
3. **MCP Integration**: Unique Claude Desktop integration
4. **Open Standards**: Strong SIE4 and open format support
5. **Developer-Friendly**: API-first, good documentation

### 14. Future Enhancements (Post-Launch)

#### Phase 11+ Features
- **Mobile Apps**: Native iOS/Android for expense management
- **E-invoicing**: Peppol integration for EU invoicing
- **Payroll**: Employee salary management and reporting
- **Inventory**: Stock management and COGS calculations
- **Multi-Currency**: Foreign transactions and exchange rates
- **Consolidation**: Multi-company group reporting
- **API Marketplace**: Third-party integrations
- **AI Audit**: Continuous compliance monitoring
- **Blockchain**: Immutable audit trail using blockchain
- **Real-time Collaboration**: Multiple users editing simultaneously

### 15. Risk Assessment & Mitigation

#### Technical Risks
| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Data loss | Critical | Low | Daily backups, replication, 7-year retention |
| Security breach | Critical | Medium | Security audits, penetration testing, encryption |
| Calculation errors | High | Medium | Extensive testing, AI validation, user review |
| Performance issues | Medium | Medium | Load testing, caching, database optimization |
| AI hallucinations | Medium | High | Human review required, confidence scores, logging |

#### Business Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| Regulatory changes | High | Modular design, quick update capability |
| Competition | Medium | Focus on differentiation (AI, UX) |
| User adoption | High | Free tier, excellent onboarding, documentation |
| Skatteverket API changes | Medium | Monitor announcements, maintain flexibility |

### 16. Development Team Requirements

#### Recommended Team Structure
- **1 Full-Stack Developer** (TypeScript/React/Node): Core application
- **1 Backend Developer** (Database, API, integrations)
- **1 Frontend Developer** (React, UI/UX)
- **1 AI/ML Engineer** (Claude integration, MCP, OCR)
- **1 Accountant/Domain Expert** (Swedish accounting, compliance)
- **1 Product Manager/Designer** (UX, feature priority)

**Alternatively**: 2-3 full-stack developers + 1 accountant advisor

#### Required Expertise
- Swedish accounting standards (BAS, BFL, ÅRL)
- TypeScript/JavaScript ecosystem
- PostgreSQL and database design
- AI/LLM integration
- Security best practices
- Swedish tax regulations

### 17. Budget Estimate (12-month development)

#### Development Costs (6-person team)
- Salaries/Contractors: ~300-400k SEK/month
- Total development: ~3.6-4.8M SEK

#### Infrastructure (Year 1)
- Hosting: ~10-20k SEK/month
- AI API costs: ~5-15k SEK/month (scales with usage)
- Tools & Services: ~5k SEK/month
- Total infrastructure: ~240-480k SEK

#### Other Costs
- Legal/compliance review: ~100k SEK
- Design/branding: ~50k SEK
- Testing/QA: ~100k SEK

**Total Year 1**: ~4-5.5M SEK

**Alternative Lean Approach** (2-3 developers, 12 months): ~1.5-2.5M SEK

### 18. Go-to-Market Strategy

#### Target Audience (Launch)
- Small businesses (enskild firma, HB, AB under 10 employees)
- Freelancers and consultants
- Startups needing modern accounting
- Tech-savvy entrepreneurs

#### Pricing Strategy
**Freemium Model**:
- **Free**: Up to 50 transactions/month, 1 company
- **Basic**: 299 SEK/month - Unlimited transactions, basic AI
- **Professional**: 599 SEK/month - Advanced AI, MCP, priority support
- **Enterprise**: Custom pricing - Multi-company, API access, dedicated support

#### Launch Plan
1. **Private Beta** (Month 11): 20-50 companies
2. **Public Beta** (Month 12): Open registration, free tier
3. **Official Launch** (Month 13): Marketing campaign, paid tiers
4. **Partnership**: Integrate with banks, invoice services

---

## Next Steps

### Immediate Actions
1. **Validate Plan**: Review with Swedish accountant for compliance
2. **Choose Tech Stack**: Finalize Node.js vs Python decision
3. **Setup Repository**: Monorepo structure (Turborepo or Nx)
4. **Design Database**: Detailed schema with Swedish accounting rules
5. **Create Wireframes**: Key UI screens for user flow
6. **Register Entity**: Company registration if commercializing
7. **Setup Infrastructure**: Development environment, CI/CD
8. **Begin Phase 1**: Start with authentication and basic transaction entry

### Critical Path
The critical path for MVP (Minimum Viable Product):
1. Transaction entry (2 months)
2. BAS kontoplan integration (included)
3. Basic reporting (1 month)
4. VAT management (1 month)
5. SIE4 export (2 weeks)

**MVP Timeline**: 4-5 months for core bookkeeping functionality

---

## Conclusion

This plan outlines a comprehensive, modern Swedish bookkeeping system with unique AI-powered features. The phased approach allows for iterative development and early user feedback. The MCP integration with Claude Desktop provides a unique differentiator in the market.

**Key Success Factors**:
1. ✅ Deep Swedish accounting compliance
2. ✅ Modern, intuitive UX
3. ✅ AI that genuinely helps (not just marketing)
4. ✅ Strong data security and privacy
5. ✅ Excellent documentation and support
6. ✅ Active community and ecosystem

**Timeline Summary**:
- **MVP**: 4-5 months (basic bookkeeping + VAT + SIE4)
- **Full v1.0**: 12 months (all core features + AI + MCP)
- **Market-ready**: 13 months (including beta testing)

This software has the potential to modernize Swedish bookkeeping with AI assistance while maintaining full compliance with Swedish regulations.
