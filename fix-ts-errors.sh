#!/bin/bash

# Fix TypeScript build errors for production

# Fix unused ExternalLink in InvitationManager.tsx
sed -i 's/, ExternalLink//' frontend/src/components/InvitationManager.tsx

# Fix unused useEffect in FiscalYearContext.tsx
sed -i 's/, useEffect//' frontend/src/contexts/FiscalYearContext.tsx

# Fix unused Save in Customers.tsx
sed -i 's/, Save//' frontend/src/pages/Customers.tsx

# Fix unused Trash2 in ExpenseDetail.tsx
sed -i 's/, Trash2//' frontend/src/pages/ExpenseDetail.tsx

# Fix unused useRef in Expenses.tsx
sed -i 's/useState, useRef,/useState,/' frontend/src/pages/Expenses.tsx

echo "Fixed unused imports!"
echo "Now fixing null/undefined type issues..."

# Fix null to undefined conversions - we'll update the type definitions to accept null
# This is easier than changing all the code

# Update Expense type to accept null for account IDs
sed -i 's/expense_account_id?: number/expense_account_id?: number | null/' frontend/src/types/index.ts
sed -i 's/vat_account_id?: number/vat_account_id?: number | null/' frontend/src/types/index.ts

echo "Done fixing TypeScript errors!"
