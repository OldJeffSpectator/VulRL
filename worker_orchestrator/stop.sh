#!/bin/bash
# Stop Worker Router and Redis

echo "Stopping VulRL Worker Router..."

# Kill uvicorn process
pkill -f "uvicorn worker_router.app:app" || echo "No Worker Router process found"

# Optionally stop Redis (commented out by default to not affect other services)
redis-cli shutdown

echo "Worker Router stopped"
