#!/bin/bash
# Simple Docker test script

echo "🐳 Building and testing orchestration service..."

# Build and start services
docker-compose -f docker-compose.test.yml up -d --build

echo "⏳ Waiting for services to start..."
sleep 30

echo "🧪 Running tests inside orchestration container..."
docker-compose -f docker-compose.test.yml exec orchestration python test_orchestration.py

echo "🧹 Cleaning up..."
docker-compose -f docker-compose.test.yml down
