#!/bin/bash

# Reknir Factory Reset Script
# This script removes all containers, volumes, and images related to this project
# and rebuilds everything from scratch.

set -e

echo "=========================================="
echo "  REKNIR FACTORY RESET"
echo "=========================================="
echo ""
echo "WARNING: This will:"
echo "  - Stop and remove containers: reknir-backend, reknir-frontend, reknir-db, reknir-backup"
echo "  - Remove volumes: postgres_data, reknir_postgres_data (DATABASE WILL BE DELETED)"
echo "  - Remove images: reknir-backend, reknir-frontend"
echo "  - Remove network: reknir-network"
echo "  - Rebuild all images from scratch"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Starting factory reset..."
echo ""

# Step 1: Stop and remove all containers and volumes
echo "1. Stopping and removing containers and volumes..."
docker compose down -v

# Step 2: Remove project-specific images
echo ""
echo "2. Removing project images..."
docker rmi reknir-backend 2>/dev/null || echo "   (reknir-backend image not found, skipping...)"
docker rmi reknir-frontend 2>/dev/null || echo "   (reknir-frontend image not found, skipping...)"

# Step 3: Remove network if it still exists
echo ""
echo "3. Removing network..."
docker network rm reknir-network 2>/dev/null || echo "   (Network already removed)"

# Step 4: Clean up any dangling images from this project
echo ""
echo "4. Cleaning up dangling images..."
docker image prune -f

# Step 5: Rebuild images
echo ""
echo "5. Rebuilding images..."
docker compose build --no-cache

# Step 6: Start containers
echo ""
echo "6. Starting containers..."
docker compose up -d

# Step 7: Wait for database to be healthy
echo ""
echo "7. Waiting for database to be ready..."
for i in {1..30}; do
    if docker compose ps postgres | grep -q "healthy"; then
        echo "   Database is ready!"
        break
    fi
    echo "   Waiting... ($i/30)"
    sleep 1
done

# Step 8: Run migrations
echo ""
echo "8. Running database migrations..."
sleep 5  # Give backend time to start
docker compose exec backend alembic upgrade head

echo ""
echo "=========================================="
echo "  FACTORY RESET COMPLETE!"
echo "=========================================="
echo ""
echo "Services:"
echo "  - Backend:  http://localhost:8000"
echo "  - Frontend: http://localhost:5173"
echo "  - Database: localhost:5432"
echo ""
echo "The database is now empty and ready for onboarding."
echo "Open http://localhost:5173 in your browser to start."
echo ""
