#!/bin/bash

# Reknir Production Setup Script
# This script creates a .env.prod file for production deployment with Cloudflare Tunnel

set -e

echo "========================================="
echo "  Reknir Production Setup"
echo "  Cloudflare Tunnel Edition"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if .env.prod already exists
if [ -f .env.prod ]; then
    echo -e "${YELLOW}Warning: .env.prod file already exists!${NC}"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled. Your existing .env.prod file was not modified."
        exit 0
    fi
    # Backup existing .env.prod
    BACKUP_FILE=".env.prod.backup.$(date +%Y%m%d_%H%M%S)"
    cp .env.prod "$BACKUP_FILE"
    echo -e "${GREEN}✓ Backed up existing .env.prod to $BACKUP_FILE${NC}"
fi

echo ""
echo "This script will guide you through setting up Reknir for production."
echo "You'll need:"
echo "  • A domain name managed by Cloudflare"
echo "  • Access to Cloudflare Zero Trust Dashboard"
echo ""
read -p "Press Enter to continue..."
echo ""

# ========================================
# Step 1: Domain Configuration
# ========================================
echo -e "${BLUE}Step 1: Domain Configuration${NC}"
echo "========================================="
echo ""
read -p "Enter your domain name (e.g., reknir.example.com): " DOMAIN_NAME

while [ -z "$DOMAIN_NAME" ]; do
    echo -e "${RED}Domain name cannot be empty!${NC}"
    read -p "Enter your domain name: " DOMAIN_NAME
done

echo -e "${GREEN}✓ Domain: ${DOMAIN_NAME}${NC}"
echo ""

# ========================================
# Step 2: Generate Database Password
# ========================================
echo -e "${BLUE}Step 2: Database Security${NC}"
echo "========================================="
echo ""

# Check if openssl is available
if command -v openssl &> /dev/null; then
    DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    echo -e "${GREEN}✓ Generated strong database password${NC}"
else
    echo -e "${YELLOW}Warning: openssl not found, using fallback random generation${NC}"
    DB_PASSWORD=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)
fi

echo "Database password: ${DB_PASSWORD}"
echo ""

# ========================================
# Step 3: Generate Secret Key
# ========================================
echo -e "${BLUE}Step 3: Application Security${NC}"
echo "========================================="
echo ""

if command -v openssl &> /dev/null; then
    SECRET_KEY=$(openssl rand -hex 32)
    echo -e "${GREEN}✓ Generated application secret key${NC}"
else
    echo -e "${YELLOW}Warning: openssl not found, using fallback random generation${NC}"
    SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-f0-9' | fold -w 64 | head -n 1)
fi

echo "Secret key: ${SECRET_KEY:0:20}... (truncated for display)"
echo ""

# ========================================
# Step 4: Cloudflare Tunnel Setup
# ========================================
echo -e "${BLUE}Step 4: Cloudflare Tunnel Configuration${NC}"
echo "========================================="
echo ""
echo "To create a Cloudflare Tunnel:"
echo ""
echo "1. Go to: ${GREEN}https://one.dash.cloudflare.com${NC}"
echo "2. Navigate to: Networks → Tunnels"
echo "3. Click: Create a tunnel"
echo "4. Choose: Cloudflared"
echo "5. Name it: ${GREEN}reknir${NC}"
echo "6. Click: Save tunnel"
echo "7. Copy the tunnel token (starts with 'eyJ...')"
echo ""
echo "Then configure the Public Hostname:"
echo "8. Subdomain: (leave empty for root or enter subdomain)"
echo "9. Domain: ${GREEN}${DOMAIN_NAME}${NC}"
echo "10. Type: HTTP"
echo "11. URL: ${GREEN}nginx:80${NC}"
echo "12. Click: Save"
echo ""
read -p "Press Enter when you're ready to paste the tunnel token..."
echo ""
read -p "Paste your Cloudflare Tunnel Token: " TUNNEL_TOKEN

while [ -z "$TUNNEL_TOKEN" ]; do
    echo -e "${RED}Tunnel token cannot be empty!${NC}"
    read -p "Paste your Cloudflare Tunnel Token: " TUNNEL_TOKEN
done

# Basic validation - Cloudflare tokens typically start with 'eyJ'
if [[ ! $TUNNEL_TOKEN =~ ^eyJ ]]; then
    echo -e "${YELLOW}Warning: Token doesn't look like a typical Cloudflare token (should start with 'eyJ')${NC}"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

echo -e "${GREEN}✓ Tunnel token configured${NC}"
echo ""

# ========================================
# Step 5: Review Configuration
# ========================================
echo -e "${BLUE}Step 5: Review Configuration${NC}"
echo "========================================="
echo ""
echo "Domain:               https://${DOMAIN_NAME}"
echo "Database User:        reknir"
echo "Database Name:        reknir"
echo "Database Password:    ${DB_PASSWORD:0:10}... (hidden)"
echo "Secret Key:           ${SECRET_KEY:0:20}... (hidden)"
echo "Tunnel Token:         ${TUNNEL_TOKEN:0:20}... (hidden)"
echo "Backup Retention:     2555 days (7 years - Swedish law)"
echo ""
read -p "Does this look correct? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled. Please run the script again."
    exit 1
fi

# ========================================
# Create .env.prod file
# ========================================
echo ""
echo "Creating .env.prod file..."

cat > .env.prod << EOF
# ========================================
# REKNIR PRODUCTION CONFIGURATION
# ========================================
# Generated: $(date)
# Domain: ${DOMAIN_NAME}
#
# IMPORTANT: Keep this file secure and never commit to version control!
#

# ========================================
# Database Configuration
# ========================================
POSTGRES_USER=reknir
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_DB=reknir

# ========================================
# Backend Configuration
# ========================================
SECRET_KEY=${SECRET_KEY}
DEBUG=False

# CORS Origins - Production domain
CORS_ORIGINS=https://${DOMAIN_NAME}

# ========================================
# Frontend Configuration
# ========================================
VITE_API_URL=https://${DOMAIN_NAME}

# ========================================
# Cloudflare Tunnel Configuration
# ========================================
TUNNEL_TOKEN=${TUNNEL_TOKEN}

# ========================================
# Backup Configuration
# ========================================
# Keep backups for 7 years (Swedish law requirement)
BACKUP_KEEP_DAYS=2555
EOF

echo -e "${GREEN}✓ .env.prod file created successfully!${NC}"
echo ""

# ========================================
# Security Reminder
# ========================================
echo -e "${YELLOW}=========================================${NC}"
echo -e "${YELLOW}  SECURITY REMINDERS${NC}"
echo -e "${YELLOW}=========================================${NC}"
echo ""
echo "1. NEVER commit .env.prod to git (already in .gitignore)"
echo "2. Keep a secure backup of .env.prod in a password manager"
echo "3. Restrict file permissions:"
echo "   ${GREEN}chmod 600 .env.prod${NC}"
echo ""

# Set secure permissions
chmod 600 .env.prod
echo -e "${GREEN}✓ Set .env.prod permissions to 600 (owner read/write only)${NC}"
echo ""

# ========================================
# Next Steps
# ========================================
echo "========================================="
echo -e "${BLUE}  Next Steps${NC}"
echo "========================================="
echo ""
echo "1. Verify Cloudflare settings:"
echo "   • Dashboard → SSL/TLS → Overview"
echo "   • Set encryption mode to: ${GREEN}Full${NC} (not Full Strict)"
echo "   • Enable 'Always Use HTTPS'"
echo ""
echo "2. Configure firewall (only SSH needed!):"
echo "   ${GREEN}sudo ufw allow 22/tcp${NC}"
echo "   ${GREEN}sudo ufw enable${NC}"
echo ""
echo "3. Deploy Reknir:"
echo "   ${GREEN}docker compose -f docker-compose.prod.yml --env-file .env.prod up -d${NC}"
echo ""
echo "4. Monitor deployment:"
echo "   ${GREEN}docker compose -f docker-compose.prod.yml logs -f${NC}"
echo ""
echo "5. Check Cloudflare Tunnel status:"
echo "   ${GREEN}docker compose -f docker-compose.prod.yml logs cloudflared${NC}"
echo "   Look for: 'Connection registered'"
echo ""
echo "6. Test your deployment:"
echo "   ${GREEN}https://${DOMAIN_NAME}${NC}"
echo ""
echo "For detailed instructions, see: ${GREEN}CLOUDFLARE.md${NC}"
echo ""
echo -e "${GREEN}Setup complete! 🎉${NC}"
echo ""
