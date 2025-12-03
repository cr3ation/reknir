#!/bin/bash

# Reknir Reset Script
# Two reset options: Quick reset (default) or Full factory reset

set -e

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
read -p "Select option [1]: " RESET_TYPE
RESET_TYPE=${RESET_TYPE:-1}

if [ "$RESET_TYPE" != "1" ] && [ "$RESET_TYPE" != "2" ]; then
    echo "Invalid choice. Aborting."
    exit 1
fi

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
    echo "3. Waiting for database to be ready..."
    for i in {1..30}; do
        if docker compose ps postgres | grep -q "healthy"; then
            echo "   Database is ready!"
            break
        fi
        echo "   Waiting... ($i/30)"
        sleep 1
    done

    # Step 4: Run migrations
    echo ""
    echo "4. Running database migrations..."
    sleep 5  # Give backend time to start
    docker compose exec backend alembic upgrade head

    echo ""
    echo "=========================================="
    echo "  QUICK RESET COMPLETE!"
    echo "=========================================="

else
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
    echo "  FULL FACTORY RESET COMPLETE!"
    echo "=========================================="
fi

echo ""
echo "Services:"
echo "  - Backend:  http://localhost:8000"
echo "  - Frontend: http://localhost:5173"
echo "  - Database: localhost:5432"
echo ""
echo "The database is now empty and ready for onboarding."
echo "Open http://localhost:5173 in your browser to start."
echo ""
