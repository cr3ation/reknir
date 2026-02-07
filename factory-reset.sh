#!/bin/bash

# Reknir Reset Script
# Three reset options:
#   1) Quick reset (default)
#   2) Full factory reset
#   3) Quick reset with pre-populated demo data

set -e

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
DEMO_EMAIL="demo@reknir.se"
DEMO_PASSWORD="demo1234"
DEMO_NAME="Demo User"

# Global variables for seeding
TOKEN=""
COMPANY_ID=""
FISCAL_YEAR_2025_ID=""
FISCAL_YEAR_2026_ID=""

# ============================================
# Helper Functions
# ============================================

wait_for_database() {
    echo "Waiting for database to be ready..."
    for i in {1..30}; do
        if docker compose ps postgres | grep -q "healthy"; then
            echo "   Database is ready!"
            return 0
        fi
        echo "   Waiting... ($i/30)"
        sleep 1
    done
    echo "ERROR: Database not ready after 30 seconds"
    exit 1
}

wait_for_api() {
    echo "Waiting for API to be ready..."
    for i in {1..60}; do
        if curl -sf "${API_BASE_URL}/docs" -o /dev/null 2>&1; then
            echo "   API is ready!"
            return 0
        fi
        echo "   Waiting... ($i/60)"
        sleep 1
    done
    echo "ERROR: API not available after 60 seconds"
    exit 1
}

api_post() {
    local endpoint=$1
    local data=$2

    if [ -n "$TOKEN" ]; then
        response=$(curl -sfL -X POST \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $TOKEN" \
            -d "$data" \
            "${API_BASE_URL}${endpoint}" 2>&1)
    else
        response=$(curl -sfL -X POST \
            -H "Content-Type: application/json" \
            -d "$data" \
            "${API_BASE_URL}${endpoint}" 2>&1)
    fi

    if [ $? -ne 0 ]; then
        echo "ERROR: API call failed: POST $endpoint"
        echo "Response: $response"
        exit 1
    fi
    echo "$response"
}

api_post_form() {
    local endpoint=$1
    local data=$2

    response=$(curl -sfL -X POST \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "$data" \
        "${API_BASE_URL}${endpoint}" 2>&1)

    if [ $? -ne 0 ]; then
        echo "ERROR: API call failed: POST $endpoint"
        exit 1
    fi
    echo "$response"
}

get_account_id() {
    local account_number=$1
    local fiscal_year_id=$2

    result=$(curl -sfL \
        -H "Authorization: Bearer $TOKEN" \
        "${API_BASE_URL}/api/accounts?company_id=${COMPANY_ID}&fiscal_year_id=${fiscal_year_id}" \
        | jq -r ".[] | select(.account_number == ${account_number}) | .id")

    echo "$result"
}

# ============================================
# Reset Functions
# ============================================

do_quick_reset() {
    echo ""
    echo "Starting quick reset..."
    echo ""

    # Step 1: Stop and remove containers and volumes
    echo "1. Stopping and removing containers and database..."
    docker compose down -v

    # Step 2: Start containers (using existing images)
    echo ""
    echo "2. Starting containers..."
    docker compose up -d

    # Step 3: Wait for database to be healthy
    echo ""
    echo "3. Waiting for database..."
    wait_for_database

    # Step 4: Run migrations
    echo ""
    echo "4. Running database migrations..."
    sleep 5  # Give backend time to start
    docker compose exec backend alembic upgrade head
}

do_full_reset() {
    echo ""
    echo "Starting full factory reset..."
    echo ""

    # Step 1: Stop and remove all containers and volumes
    echo "1. Stopping and removing containers and database..."
    docker compose down -v

    # Step 2: Remove project-specific images
    echo ""
    echo "2. Removing images..."
    docker rmi reknir-backend 2>/dev/null || echo "   (reknir-backend image not found)"
    docker rmi reknir-frontend 2>/dev/null || echo "   (reknir-frontend image not found)"

    # Step 3: Remove network if it still exists
    echo ""
    echo "3. Removing network..."
    docker network rm reknir-network 2>/dev/null || echo "   (Network already removed)"

    # Step 4: Clean up any dangling images
    echo ""
    echo "4. Cleaning up dangling images..."
    docker image prune -f

    # Step 5: Rebuild images
    echo ""
    echo "5. Rebuilding images from scratch..."
    docker compose build --no-cache

    # Step 6: Start containers
    echo ""
    echo "6. Starting containers..."
    docker compose up -d

    # Step 7: Wait for database to be healthy
    echo ""
    echo "7. Waiting for database..."
    wait_for_database

    # Step 8: Run migrations
    echo ""
    echo "8. Running database migrations..."
    sleep 5  # Give backend time to start
    docker compose exec backend alembic upgrade head
}

# ============================================
# Demo Data Seeding
# ============================================

seed_demo_data() {
    echo ""
    echo "=========================================="
    echo "  SEEDING DEMO DATA"
    echo "=========================================="
    echo ""

    # Wait for API to be ready
    wait_for_api

    # Step 1: Register admin user
    echo "Creating admin user..."
    api_post "/api/auth/register" "{
        \"email\": \"${DEMO_EMAIL}\",
        \"password\": \"${DEMO_PASSWORD}\",
        \"full_name\": \"${DEMO_NAME}\"
    }" > /dev/null
    echo "   Created user: ${DEMO_EMAIL}"

    # Step 2: Login to get token
    echo "Logging in..."
    login_response=$(api_post_form "/api/auth/login" "username=${DEMO_EMAIL}&password=${DEMO_PASSWORD}")
    TOKEN=$(echo "$login_response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)
    if [ -z "$TOKEN" ]; then
        echo "ERROR: Failed to get access token"
        exit 1
    fi
    echo "   Login successful"

    # Step 3: Create company
    echo "Creating company..."
    company_response=$(api_post "/api/companies" '{
        "name": "Demo Företag AB",
        "org_number": "556677-1234",
        "address": "Demovägen 1",
        "postal_code": "11122",
        "city": "Stockholm",
        "phone": "08-123 45 67",
        "email": "info@demoforetag.se",
        "fiscal_year_start": "2025-01-01",
        "fiscal_year_end": "2025-12-31",
        "accounting_basis": "cash",
        "vat_reporting_period": "yearly",
        "payment_type": "bank_account",
        "clearing_number": "1234",
        "account_number": "567 890 123-4"
    }')
    COMPANY_ID=$(echo "$company_response" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created company: Demo Företag AB (ID: ${COMPANY_ID})"

    # Step 4: Create fiscal year 2025
    echo "Creating fiscal year 2025..."
    fy_response=$(api_post "/api/fiscal-years" "{
        \"company_id\": ${COMPANY_ID},
        \"year\": 2025,
        \"label\": \"2025\",
        \"start_date\": \"2025-01-01\",
        \"end_date\": \"2025-12-31\",
        \"is_closed\": false
    }")
    FISCAL_YEAR_2025_ID=$(echo "$fy_response" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created fiscal year 2025 (ID: ${FISCAL_YEAR_2025_ID})"

    # Step 5: Seed BAS 2024 accounts
    echo "Seeding BAS 2024 chart of accounts..."
    api_post "/api/companies/${COMPANY_ID}/seed-bas?fiscal_year_id=${FISCAL_YEAR_2025_ID}" "{}" > /dev/null
    echo "   BAS 2024 accounts created"

    # Step 5.5: Seed posting templates
    echo "Seeding posting templates..."
    api_post "/api/companies/${COMPANY_ID}/seed-templates" "{}" > /dev/null
    echo "   Posting templates created"

    # Step 6: Create 5 customers
    echo "Creating customers..."

    customer1=$(api_post "/api/customers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"Andersson Konsult AB\",
        \"org_number\": \"556111-1111\",
        \"contact_person\": \"Anna Andersson\",
        \"email\": \"anna@andersson-konsult.se\",
        \"phone\": \"070-111 11 11\",
        \"address\": \"Konsultgatan 1\",
        \"postal_code\": \"11111\",
        \"city\": \"Stockholm\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    CUSTOMER1_ID=$(echo "$customer1" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: Andersson Konsult AB"

    customer2=$(api_post "/api/customers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"Bergström & Partners HB\",
        \"org_number\": \"916234-5678\",
        \"contact_person\": \"Björn Bergström\",
        \"email\": \"bjorn@bergstrom-partners.se\",
        \"phone\": \"070-222 22 22\",
        \"address\": \"Partnergatan 2\",
        \"postal_code\": \"22222\",
        \"city\": \"Göteborg\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    CUSTOMER2_ID=$(echo "$customer2" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: Bergström & Partners HB"

    customer3=$(api_post "/api/customers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"Carlsson IT Solutions AB\",
        \"org_number\": \"559012-3456\",
        \"contact_person\": \"Carl Carlsson\",
        \"email\": \"carl@carlsson-it.se\",
        \"phone\": \"070-333 33 33\",
        \"address\": \"IT-vägen 3\",
        \"postal_code\": \"33333\",
        \"city\": \"Malmö\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    CUSTOMER3_ID=$(echo "$customer3" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: Carlsson IT Solutions AB"

    customer4=$(api_post "/api/customers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"Dahl Transport AB\",
        \"org_number\": \"556789-0123\",
        \"contact_person\": \"David Dahl\",
        \"email\": \"david@dahl-transport.se\",
        \"phone\": \"070-444 44 44\",
        \"address\": \"Transportgatan 4\",
        \"postal_code\": \"44444\",
        \"city\": \"Uppsala\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    CUSTOMER4_ID=$(echo "$customer4" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: Dahl Transport AB"

    customer5=$(api_post "/api/customers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"Eriksson Bygg AB\",
        \"org_number\": \"556456-7890\",
        \"contact_person\": \"Erik Eriksson\",
        \"email\": \"erik@eriksson-bygg.se\",
        \"phone\": \"070-555 55 55\",
        \"address\": \"Byggvägen 5\",
        \"postal_code\": \"55555\",
        \"city\": \"Västerås\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    CUSTOMER5_ID=$(echo "$customer5" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: Eriksson Bygg AB"

    # Step 7: Create 5 invoices
    echo "Creating invoices..."

    # Invoice 1 - Will be paid
    invoice1=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER1_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2025-01-15\",
        \"due_date\": \"2025-02-15\",
        \"reference\": \"Projekt Alpha\",
        \"our_reference\": \"Demo User\",
        \"invoice_lines\": [
            {
                \"description\": \"Konsulttjänster januari\",
                \"quantity\": 40,
                \"unit\": \"h\",
                \"unit_price\": 1200,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE1_ID=$(echo "$invoice1" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 1 (48 000 SEK)"

    # Invoice 2 - Will be paid
    invoice2=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER2_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2025-02-01\",
        \"due_date\": \"2025-03-01\",
        \"reference\": \"Projekt Beta\",
        \"our_reference\": \"Demo User\",
        \"invoice_lines\": [
            {
                \"description\": \"Rådgivning\",
                \"quantity\": 20,
                \"unit\": \"h\",
                \"unit_price\": 1500,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Dokumentation\",
                \"quantity\": 10,
                \"unit\": \"h\",
                \"unit_price\": 1000,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE2_ID=$(echo "$invoice2" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 2 (40 000 SEK)"

    # Invoice 3 - Will be paid
    invoice3=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER3_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2025-03-10\",
        \"due_date\": \"2025-04-10\",
        \"reference\": \"IT-support Q1\",
        \"our_reference\": \"Demo User\",
        \"invoice_lines\": [
            {
                \"description\": \"IT-support\",
                \"quantity\": 1,
                \"unit\": \"st\",
                \"unit_price\": 15000,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Licensavgift\",
                \"quantity\": 5,
                \"unit\": \"st\",
                \"unit_price\": 2000,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE3_ID=$(echo "$invoice3" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 3 (25 000 SEK)"

    # Invoice 4 - Unpaid
    invoice4=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER4_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2025-04-01\",
        \"due_date\": \"2025-05-01\",
        \"reference\": \"Transport april\",
        \"our_reference\": \"Demo User\",
        \"invoice_lines\": [
            {
                \"description\": \"Transporttjänster\",
                \"quantity\": 3,
                \"unit\": \"st\",
                \"unit_price\": 8000,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE4_ID=$(echo "$invoice4" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 4 (24 000 SEK) - unpaid"

    # Invoice 5 - Unpaid
    invoice5=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER5_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2025-04-15\",
        \"due_date\": \"2025-05-15\",
        \"reference\": \"Byggprojekt\",
        \"our_reference\": \"Demo User\",
        \"invoice_lines\": [
            {
                \"description\": \"Projektledning\",
                \"quantity\": 80,
                \"unit\": \"h\",
                \"unit_price\": 950,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE5_ID=$(echo "$invoice5" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 5 (76 000 SEK) - unpaid"

    # Step 8: Send all invoices
    echo "Sending invoices..."
    api_post "/api/invoices/${INVOICE1_ID}/send" "{}" > /dev/null
    api_post "/api/invoices/${INVOICE2_ID}/send" "{}" > /dev/null
    api_post "/api/invoices/${INVOICE3_ID}/send" "{}" > /dev/null
    api_post "/api/invoices/${INVOICE4_ID}/send" "{}" > /dev/null
    api_post "/api/invoices/${INVOICE5_ID}/send" "{}" > /dev/null
    echo "   All invoices sent"

    # Step 9: Mark 3 invoices as paid
    echo "Registering payments for invoices 1-3..."
    api_post "/api/invoices/${INVOICE1_ID}/mark-paid" "{\"paid_date\": \"2025-02-10\", \"paid_amount\": 60000}" > /dev/null
    echo "   Invoice 1 paid"
    api_post "/api/invoices/${INVOICE2_ID}/mark-paid" "{\"paid_date\": \"2025-02-25\", \"paid_amount\": 50000}" > /dev/null
    echo "   Invoice 2 paid"
    api_post "/api/invoices/${INVOICE3_ID}/mark-paid" "{\"paid_date\": \"2025-04-05\", \"paid_amount\": 31250}" > /dev/null
    echo "   Invoice 3 paid"

    # Step 10: Create 3 suppliers
    echo "Creating suppliers..."

    supplier1=$(api_post "/api/suppliers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"Kontorsmaterial AB\",
        \"org_number\": \"556111-2222\",
        \"contact_person\": \"Kent Kontorsson\",
        \"email\": \"order@kontorsmaterial.se\",
        \"phone\": \"08-111 22 33\",
        \"address\": \"Kontorsgatan 10\",
        \"postal_code\": \"11111\",
        \"city\": \"Stockholm\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    SUPPLIER1_ID=$(echo "$supplier1" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: Kontorsmaterial AB"

    supplier2=$(api_post "/api/suppliers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"IT-Lösningar Sverige AB\",
        \"org_number\": \"556333-4444\",
        \"contact_person\": \"Ingrid IT-sson\",
        \"email\": \"faktura@itlosningar.se\",
        \"phone\": \"08-333 44 55\",
        \"address\": \"Servervägen 5\",
        \"postal_code\": \"22222\",
        \"city\": \"Göteborg\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    SUPPLIER2_ID=$(echo "$supplier2" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: IT-Lösningar Sverige AB"

    supplier3=$(api_post "/api/suppliers" "{
        \"company_id\": ${COMPANY_ID},
        \"name\": \"Fastighetsservice Stockholm AB\",
        \"org_number\": \"556555-6666\",
        \"contact_person\": \"Fredrik Fastighet\",
        \"email\": \"faktura@fastighetsservice.se\",
        \"phone\": \"08-555 66 77\",
        \"address\": \"Hyresvägen 15\",
        \"postal_code\": \"33333\",
        \"city\": \"Stockholm\",
        \"country\": \"Sverige\",
        \"payment_terms_days\": 30
    }")
    SUPPLIER3_ID=$(echo "$supplier3" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created: Fastighetsservice Stockholm AB"

    # Step 11: Create 6 supplier invoices with various statuses
    echo "Creating supplier invoices..."

    # Supplier Invoice 1 - Draft (not registered)
    sinv1=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER1_ID},
        \"supplier_invoice_number\": \"KM-2025-001\",
        \"invoice_date\": \"2025-04-01\",
        \"due_date\": \"2025-05-01\",
        \"reference\": \"Kontorsartiklar Q2\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Kopieringspapper A4\",
                \"quantity\": 50,
                \"unit_price\": 200,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Pennor och kontorsmaterial\",
                \"quantity\": 1,
                \"unit_price\": 1500,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV1_ID=$(echo "$sinv1" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created supplier invoice 1 (11 500 SEK) - Draft"

    # Supplier Invoice 2 - Registered, unpaid
    sinv2=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER2_ID},
        \"supplier_invoice_number\": \"IT-2025-042\",
        \"invoice_date\": \"2025-03-15\",
        \"due_date\": \"2025-04-15\",
        \"reference\": \"Molntjänster mars\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Azure molntjänster mars\",
                \"quantity\": 1,
                \"unit_price\": 8500,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Support och underhåll\",
                \"quantity\": 5,
                \"unit_price\": 1200,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV2_ID=$(echo "$sinv2" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    api_post "/api/supplier-invoices/${SINV2_ID}/register" "{}" > /dev/null
    echo "   Created supplier invoice 2 (14 500 SEK) - Registered, unpaid"

    # Supplier Invoice 3 - Registered, partially paid
    sinv3=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER3_ID},
        \"supplier_invoice_number\": \"FS-2025-118\",
        \"invoice_date\": \"2025-02-01\",
        \"due_date\": \"2025-03-01\",
        \"reference\": \"Hyra februari\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Lokalhyra februari\",
                \"quantity\": 1,
                \"unit_price\": 25000,
                \"vat_rate\": 0
            },
            {
                \"description\": \"Fastighetsskötsel\",
                \"quantity\": 1,
                \"unit_price\": 3000,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV3_ID=$(echo "$sinv3" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    api_post "/api/supplier-invoices/${SINV3_ID}/register" "{}" > /dev/null
    api_post "/api/supplier-invoices/${SINV3_ID}/mark-paid" "{\"paid_date\": \"2025-02-28\", \"paid_amount\": 15000}" > /dev/null
    echo "   Created supplier invoice 3 (28 750 SEK) - Partially paid (15 000 SEK)"

    # Supplier Invoice 4 - Registered, fully paid
    sinv4=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER1_ID},
        \"supplier_invoice_number\": \"KM-2025-002\",
        \"invoice_date\": \"2025-01-10\",
        \"due_date\": \"2025-02-10\",
        \"reference\": \"Kontorsartiklar januari\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Skrivbordsmaterial\",
                \"quantity\": 1,
                \"unit_price\": 4500,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV4_ID=$(echo "$sinv4" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    api_post "/api/supplier-invoices/${SINV4_ID}/register" "{}" > /dev/null
    api_post "/api/supplier-invoices/${SINV4_ID}/mark-paid" "{\"paid_date\": \"2025-02-05\", \"paid_amount\": 5625}" > /dev/null
    echo "   Created supplier invoice 4 (5 625 SEK) - Fully paid"

    # Supplier Invoice 5 - Registered, unpaid, overdue
    sinv5=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER2_ID},
        \"supplier_invoice_number\": \"IT-2025-015\",
        \"invoice_date\": \"2025-01-01\",
        \"due_date\": \"2025-01-31\",
        \"reference\": \"Licenser Q1\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Microsoft 365-licenser\",
                \"quantity\": 10,
                \"unit_price\": 350,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Antiviruslicenser\",
                \"quantity\": 10,
                \"unit_price\": 150,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV5_ID=$(echo "$sinv5" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    api_post "/api/supplier-invoices/${SINV5_ID}/register" "{}" > /dev/null
    echo "   Created supplier invoice 5 (6 250 SEK) - Registered, unpaid (overdue)"

    # Supplier Invoice 6 - Cancelled
    sinv6=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER3_ID},
        \"supplier_invoice_number\": \"FS-2025-099\",
        \"invoice_date\": \"2025-01-15\",
        \"due_date\": \"2025-02-15\",
        \"reference\": \"Felaktig faktura\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Extra tjänst (feldebiterad)\",
                \"quantity\": 1,
                \"unit_price\": 5000,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV6_ID=$(echo "$sinv6" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    api_post "/api/supplier-invoices/${SINV6_ID}/cancel" "{}" > /dev/null
    echo "   Created supplier invoice 6 (6 250 SEK) - Cancelled"

    # Step 12: Create 3 manual verifications for 2025
    echo "Creating manual verifications for 2025..."

    # Get account IDs for 2025
    ACC_5010=$(get_account_id 5010 $FISCAL_YEAR_2025_ID)  # Lokalhyra
    ACC_6110=$(get_account_id 6110 $FISCAL_YEAR_2025_ID)  # Kontorsmaterial
    ACC_1930=$(get_account_id 1930 $FISCAL_YEAR_2025_ID)  # Bank
    ACC_8300=$(get_account_id 8300 $FISCAL_YEAR_2025_ID)  # Ränteintäkter

    # Verification 1: Rent payment
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2025_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2025-01-31\",
        \"description\": \"Hyra januari\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_5010}, \"debit\": 15000, \"credit\": 0, \"description\": \"Lokalhyra januari\"},
            {\"account_id\": ${ACC_1930}, \"debit\": 0, \"credit\": 15000, \"description\": \"Betalning via bank\"}
        ]
    }" > /dev/null
    echo "   Created: Hyra januari (15 000 SEK)"

    # Verification 2: Office supplies
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2025_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2025-02-15\",
        \"description\": \"Kontorsmaterial\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_6110}, \"debit\": 2500, \"credit\": 0, \"description\": \"Kontorsmaterial\"},
            {\"account_id\": ${ACC_1930}, \"debit\": 0, \"credit\": 2500, \"description\": \"Betalning via bank\"}
        ]
    }" > /dev/null
    echo "   Created: Kontorsmaterial (2 500 SEK)"

    # Verification 3: Bank interest income
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2025_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2025-03-31\",
        \"description\": \"Ränteintäkter Q1\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_1930}, \"debit\": 150, \"credit\": 0, \"description\": \"Ränta bank\"},
            {\"account_id\": ${ACC_8300}, \"debit\": 0, \"credit\": 150, \"description\": \"Ränteintäkter\"}
        ]
    }" > /dev/null
    echo "   Created: Ränteintäkter Q1 (150 SEK)"

    # Step 13: Create fiscal year 2026
    echo "Creating fiscal year 2026..."
    fy2026_response=$(api_post "/api/fiscal-years" "{
        \"company_id\": ${COMPANY_ID},
        \"year\": 2026,
        \"label\": \"2026\",
        \"start_date\": \"2026-01-01\",
        \"end_date\": \"2026-12-31\",
        \"is_closed\": false
    }")
    FISCAL_YEAR_2026_ID=$(echo "$fy2026_response" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created fiscal year 2026 (ID: ${FISCAL_YEAR_2026_ID})"

    # Step 14: Copy chart of accounts to 2026
    echo "Copying chart of accounts to 2026..."
    api_post "/api/fiscal-years/${FISCAL_YEAR_2026_ID}/copy-chart-of-accounts?source_fiscal_year_id=${FISCAL_YEAR_2025_ID}" "{}" > /dev/null
    echo "   Chart of accounts copied"

    # Step 15: Create customer invoices for 2026
    echo "Creating customer invoices for 2026..."

    invoice2026_1=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER1_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2026-01-10\",
        \"due_date\": \"2026-02-10\",
        \"reference\": \"Konsulttjänster januari\",
        \"invoice_lines\": [
            {
                \"description\": \"Projektledning\",
                \"quantity\": 40,
                \"unit\": \"h\",
                \"unit_price\": 1200,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE2026_1_ID=$(echo "$invoice2026_1" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 2026-1 (60 000 SEK)"

    invoice2026_2=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER2_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2026-01-20\",
        \"due_date\": \"2026-02-20\",
        \"reference\": \"Revision Q4 2025\",
        \"invoice_lines\": [
            {
                \"description\": \"Bokslutsgranskning\",
                \"quantity\": 16,
                \"unit\": \"h\",
                \"unit_price\": 1500,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Årsredovisning\",
                \"quantity\": 8,
                \"unit\": \"h\",
                \"unit_price\": 1500,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE2026_2_ID=$(echo "$invoice2026_2" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 2026-2 (45 000 SEK)"

    invoice2026_3=$(api_post "/api/invoices" "{
        \"company_id\": ${COMPANY_ID},
        \"customer_id\": ${CUSTOMER3_ID},
        \"invoice_series\": \"F\",
        \"invoice_date\": \"2026-02-01\",
        \"due_date\": \"2026-03-01\",
        \"reference\": \"Support februari\",
        \"invoice_lines\": [
            {
                \"description\": \"IT-support månadspris\",
                \"quantity\": 1,
                \"unit\": \"st\",
                \"unit_price\": 8500,
                \"vat_rate\": 25
            }
        ]
    }")
    INVOICE2026_3_ID=$(echo "$invoice2026_3" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created invoice 2026-3 (10 625 SEK)"

    # Send 2026 invoices
    echo "Sending 2026 invoices..."
    api_post "/api/invoices/${INVOICE2026_1_ID}/send" "{}" > /dev/null
    api_post "/api/invoices/${INVOICE2026_2_ID}/send" "{}" > /dev/null
    api_post "/api/invoices/${INVOICE2026_3_ID}/send" "{}" > /dev/null
    echo "   All 2026 invoices sent"

    # Mark first 2026 invoice as paid
    echo "Registering payment for 2026 invoice..."
    api_post "/api/invoices/${INVOICE2026_1_ID}/mark-paid" "{\"paid_date\": \"2026-02-05\", \"paid_amount\": 60000}" > /dev/null
    echo "   Invoice 2026-1 paid"

    # Step 16: Create supplier invoices for 2026
    echo "Creating supplier invoices for 2026..."

    sinv2026_1=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER1_ID},
        \"supplier_invoice_number\": \"KM-2026-001\",
        \"invoice_date\": \"2026-01-15\",
        \"due_date\": \"2026-02-15\",
        \"reference\": \"Kontorsartiklar januari\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Skrivarpapper A4\",
                \"quantity\": 10,
                \"unit_price\": 350,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Kontorsstolar\",
                \"quantity\": 2,
                \"unit_price\": 2500,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV2026_1_ID=$(echo "$sinv2026_1" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created supplier invoice 2026-1 (10 625 SEK)"

    sinv2026_2=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER2_ID},
        \"supplier_invoice_number\": \"IT-2026-008\",
        \"invoice_date\": \"2026-01-31\",
        \"due_date\": \"2026-02-28\",
        \"reference\": \"Molntjänster januari\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Azure hosting\",
                \"quantity\": 1,
                \"unit_price\": 4500,
                \"vat_rate\": 25
            },
            {
                \"description\": \"Microsoft 365\",
                \"quantity\": 5,
                \"unit_price\": 150,
                \"vat_rate\": 25
            }
        ]
    }")
    SINV2026_2_ID=$(echo "$sinv2026_2" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created supplier invoice 2026-2 (6 562 SEK)"

    sinv2026_3=$(api_post "/api/supplier-invoices/" "{
        \"company_id\": ${COMPANY_ID},
        \"supplier_id\": ${SUPPLIER3_ID},
        \"supplier_invoice_number\": \"FS-2026-015\",
        \"invoice_date\": \"2026-02-01\",
        \"due_date\": \"2026-03-01\",
        \"reference\": \"Hyra februari 2026\",
        \"supplier_invoice_lines\": [
            {
                \"description\": \"Lokalhyra\",
                \"quantity\": 1,
                \"unit_price\": 15000,
                \"vat_rate\": 0
            }
        ]
    }")
    SINV2026_3_ID=$(echo "$sinv2026_3" | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2)
    echo "   Created supplier invoice 2026-3 (15 000 SEK) - Rent"

    # Register and pay first supplier invoice
    api_post "/api/supplier-invoices/${SINV2026_1_ID}/register" "{}" > /dev/null
    api_post "/api/supplier-invoices/${SINV2026_1_ID}/mark-paid" "{\"paid_date\": \"2026-02-10\", \"paid_amount\": 10625}" > /dev/null
    echo "   Supplier invoice 2026-1 registered and paid"

    # Register second (unpaid)
    api_post "/api/supplier-invoices/${SINV2026_2_ID}/register" "{}" > /dev/null
    echo "   Supplier invoice 2026-2 registered (unpaid)"

    # Step 17: Create manual verifications for 2026
    echo "Creating manual verifications for 2026..."

    # Get account IDs for 2026
    ACC_5010_2026=$(get_account_id 5010 $FISCAL_YEAR_2026_ID)  # Lokalhyra
    ACC_6570_2026=$(get_account_id 6570 $FISCAL_YEAR_2026_ID)  # Bankkostnader
    ACC_6540_2026=$(get_account_id 6540 $FISCAL_YEAR_2026_ID)  # IT-tjänster
    ACC_6110_2026=$(get_account_id 6110 $FISCAL_YEAR_2026_ID)  # Kontorsmaterial
    ACC_6211_2026=$(get_account_id 6211 $FISCAL_YEAR_2026_ID)  # Telefon
    ACC_6230_2026=$(get_account_id 6230 $FISCAL_YEAR_2026_ID)  # Mobiltelefon
    ACC_5410_2026=$(get_account_id 5410 $FISCAL_YEAR_2026_ID)  # Förbrukningsinventarier
    ACC_7210_2026=$(get_account_id 7210 $FISCAL_YEAR_2026_ID)  # Löner
    ACC_7510_2026=$(get_account_id 7510 $FISCAL_YEAR_2026_ID)  # Arbetsgivaravgifter
    ACC_1930_2026=$(get_account_id 1930 $FISCAL_YEAR_2026_ID)  # Bank

    # Verification 1: January rent 2026
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-01-31\",
        \"description\": \"Hyra januari 2026\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_5010_2026}, \"debit\": 15000, \"credit\": 0, \"description\": \"Lokalhyra januari\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 15000, \"description\": \"Betalning via bank\"}
        ]
    }" > /dev/null
    echo "   Created: Hyra januari 2026 (15 000 SEK)"

    # Verification 2: Bank fees January
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-01-15\",
        \"description\": \"Bankavgifter januari\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_6570_2026}, \"debit\": 250, \"credit\": 0, \"description\": \"Bankavgifter\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 250, \"description\": \"Betalning via bank\"}
        ]
    }" > /dev/null
    echo "   Created: Bankavgifter januari (250 SEK)"

    # Verification 3: Salary January
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-01-25\",
        \"description\": \"Lön januari 2026\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_7210_2026}, \"debit\": 35000, \"credit\": 0, \"description\": \"Bruttolön\"},
            {\"account_id\": ${ACC_7510_2026}, \"debit\": 10990, \"credit\": 0, \"description\": \"Arbetsgivaravgifter 31.42%\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 45990, \"description\": \"Utbetalning\"}
        ]
    }" > /dev/null
    echo "   Created: Lön januari (45 990 SEK)"

    # Verification 4: Office supplies
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-01-20\",
        \"description\": \"Kontorsmaterial Staples\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_6110_2026}, \"debit\": 1850, \"credit\": 0, \"description\": \"Papper, pennor, pärmar\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 1850, \"description\": \"Kortbetalning\"}
        ]
    }" > /dev/null
    echo "   Created: Kontorsmaterial (1 850 SEK)"

    # Verification 5: Phone bill
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-01-28\",
        \"description\": \"Telefonräkning januari\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_6211_2026}, \"debit\": 899, \"credit\": 0, \"description\": \"Mobilabonnemang\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 899, \"description\": \"Autogiro\"}
        ]
    }" > /dev/null
    echo "   Created: Telefonräkning (899 SEK)"

    # Verification 6: Internet February
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-02-05\",
        \"description\": \"Bredband februari\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_6230_2026}, \"debit\": 599, \"credit\": 0, \"description\": \"Fiber 100/100\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 599, \"description\": \"Autogiro\"}
        ]
    }" > /dev/null
    echo "   Created: Bredband (599 SEK)"

    # Verification 7: IT services February
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-02-10\",
        \"description\": \"IT-support februari\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_6540_2026}, \"debit\": 5000, \"credit\": 0, \"description\": \"IT-konsulttjänster\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 5000, \"description\": \"Betalning via bank\"}
        ]
    }" > /dev/null
    echo "   Created: IT-support (5 000 SEK)"

    # Verification 8: Salary February
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-02-25\",
        \"description\": \"Lön februari 2026\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_7210_2026}, \"debit\": 35000, \"credit\": 0, \"description\": \"Bruttolön\"},
            {\"account_id\": ${ACC_7510_2026}, \"debit\": 10990, \"credit\": 0, \"description\": \"Arbetsgivaravgifter 31.42%\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 45990, \"description\": \"Utbetalning\"}
        ]
    }" > /dev/null
    echo "   Created: Lön februari (45 990 SEK)"

    # Verification 9: February rent
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-02-28\",
        \"description\": \"Hyra februari 2026\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_5010_2026}, \"debit\": 15000, \"credit\": 0, \"description\": \"Lokalhyra februari\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 15000, \"description\": \"Betalning via bank\"}
        ]
    }" > /dev/null
    echo "   Created: Hyra februari (15 000 SEK)"

    # Verification 10: Equipment purchase
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-02-20\",
        \"description\": \"Datormus och tangentbord\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_5410_2026}, \"debit\": 1299, \"credit\": 0, \"description\": \"Logitech MX Keys + Master 3\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 1299, \"description\": \"Kortbetalning\"}
        ]
    }" > /dev/null
    echo "   Created: Förbrukningsinventarier (1 299 SEK)"

    # Verification 12: Bank fees February
    api_post "/api/verifications" "{
        \"company_id\": ${COMPANY_ID},
        \"fiscal_year_id\": ${FISCAL_YEAR_2026_ID},
        \"series\": \"A\",
        \"transaction_date\": \"2026-02-28\",
        \"description\": \"Bankavgifter februari\",
        \"transaction_lines\": [
            {\"account_id\": ${ACC_6570_2026}, \"debit\": 250, \"credit\": 0, \"description\": \"Månadsavgift\"},
            {\"account_id\": ${ACC_1930_2026}, \"debit\": 0, \"credit\": 250, \"description\": \"Betalning via bank\"}
        ]
    }" > /dev/null
    echo "   Created: Bankavgifter februari (250 SEK)"
}

# ============================================
# Main Menu
# ============================================

echo "=========================================="
echo "  REKNIR RESET"
echo "=========================================="
echo ""
echo "Choose reset option:"
echo ""
echo "  1) Quick Reset (RECOMMENDED)"
echo "     - Removes containers and database"
echo "     - Keeps existing images (faster)"
echo "     - Restarts with empty migrated database"
echo ""
echo "  2) Full Factory Reset"
echo "     - Removes containers, database AND images"
echo "     - Rebuilds everything from scratch"
echo "     - Takes longer"
echo ""
echo "  3) Quick Reset with Demo Data"
echo "     - Same as Quick Reset"
echo "     - Plus: Creates demo company, customers, suppliers, invoices"
echo "     - Login: ${DEMO_EMAIL} / ${DEMO_PASSWORD}"
echo ""
read -p "Select option [1]: " RESET_TYPE
RESET_TYPE=${RESET_TYPE:-1}

if [ "$RESET_TYPE" != "1" ] && [ "$RESET_TYPE" != "2" ] && [ "$RESET_TYPE" != "3" ]; then
    echo "Invalid choice. Aborting."
    exit 1
fi

# ============================================
# Option 1: Quick Reset
# ============================================
if [ "$RESET_TYPE" = "1" ]; then
    echo ""
    echo "=========================================="
    echo "  QUICK RESET"
    echo "=========================================="
    echo ""
    echo "This will:"
    echo "  ✓ Stop and remove containers"
    echo "  ✓ Remove database volume (all data deleted)"
    echo "  ✓ Restart with empty migrated database"
    echo "  ✗ Keep existing images (no rebuild)"
    echo ""
    read -p "Continue? [Y/n]: " CONFIRM
    CONFIRM=${CONFIRM:-Y}

    if [ "$CONFIRM" != "Y" ] && [ "$CONFIRM" != "y" ]; then
        echo "Aborted."
        exit 0
    fi

    do_quick_reset

    echo ""
    echo "=========================================="
    echo "  QUICK RESET COMPLETE!"
    echo "=========================================="

# ============================================
# Option 2: Full Factory Reset
# ============================================
elif [ "$RESET_TYPE" = "2" ]; then
    echo ""
    echo "=========================================="
    echo "  FULL FACTORY RESET"
    echo "=========================================="
    echo ""
    echo "This will:"
    echo "  ✓ Stop and remove containers"
    echo "  ✓ Remove database volume (all data deleted)"
    echo "  ✓ Remove images"
    echo "  ✓ Remove network"
    echo "  ✓ Rebuild everything from scratch"
    echo ""
    read -p "Are you sure? (type 'yes'): " CONFIRM

    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi

    do_full_reset

    echo ""
    echo "=========================================="
    echo "  FULL FACTORY RESET COMPLETE!"
    echo "=========================================="

# ============================================
# Option 3: Quick Reset with Demo Data
# ============================================
elif [ "$RESET_TYPE" = "3" ]; then
    echo ""
    echo "=========================================="
    echo "  QUICK RESET WITH DEMO DATA"
    echo "=========================================="
    echo ""
    echo "This will:"
    echo "  ✓ Stop and remove containers"
    echo "  ✓ Remove database volume (all data deleted)"
    echo "  ✓ Restart with empty migrated database"
    echo "  ✓ Create demo user, company, customers, suppliers, invoices"
    echo "  ✗ Keep existing images (no rebuild)"
    echo ""
    read -p "Continue? [Y/n]: " CONFIRM
    CONFIRM=${CONFIRM:-Y}

    if [ "$CONFIRM" != "Y" ] && [ "$CONFIRM" != "y" ]; then
        echo "Aborted."
        exit 0
    fi

    do_quick_reset
    seed_demo_data

    echo ""
    echo "=========================================="
    echo "  DEMO DATA CREATED!"
    echo "=========================================="
    echo ""
    echo "Login credentials:"
    echo "  Email:    ${DEMO_EMAIL}"
    echo "  Password: ${DEMO_PASSWORD}"
    echo ""
    echo "Company: Demo Företag AB"
    echo "  - Accounting method: Cash (kontantmetoden)"
    echo "  - VAT reporting: Yearly (årsmoms)"
    echo ""
    echo "Data created:"
    echo "  - Fiscal Years: 2025, 2026"
    echo "  - Customers: 5"
    echo "  - Customer invoices: 8 (5 in 2025: 3 paid, 2 unpaid | 3 in 2026: 1 paid, 2 unpaid)"
    echo "  - Suppliers: 3"
    echo "  - Supplier invoices: 9 (6 in 2025 | 3 in 2026: 1 paid, 1 approved, 1 draft)"
    echo "  - Manual verifications: 14 (3 in 2025, 11 in 2026)"
fi

echo ""
echo "Services:"
echo "  - Backend:  http://localhost:8000"
echo "  - Frontend: http://localhost:5173"
echo "  - Database: localhost:5432"
echo ""
if [ "$RESET_TYPE" = "3" ]; then
    echo "Open http://localhost:5173 and login with:"
    echo "  ${DEMO_EMAIL} / ${DEMO_PASSWORD}"
else
    echo "The database is now empty and ready for onboarding."
    echo "Open http://localhost:5173 in your browser to start."
fi
echo ""
