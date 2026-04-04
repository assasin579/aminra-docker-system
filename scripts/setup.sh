#!/bin/bash

# AMINRA Docker Setup Script

set -e

echo "🐳 Setting up AMINRA Docker System..."

# Create secrets directory if not exists
mkdir -p secrets

# Check if API keys exist
if [ ! -f "secrets/openrouter_api_key.txt" ]; then
    echo "⚠️  OpenRouter API key not found. Please create secrets/openrouter_api_key.txt"
    exit 1
fi

if [ ! -f "secrets/deepseek_api_key.txt" ]; then
    echo "⚠️  DeepSeek API key not found. Please create secrets/deepseek_api_key.txt"
    exit 1
fi

# Copy source code to build contexts
echo "📁 Copying source code..."
cp -r /home/user/Documents/local-rag-system/* backend/
cp -r /home/user/Documents/aminra-web/* frontend/aminra-web/
cp -r /home/user/Documents/mukjizat-web/* frontend/mukjizat-web/

# Build and start services
echo "🔨 Building containers..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 30

# Check health
echo "🔍 Checking service health..."
docker-compose ps

echo "✅ AMINRA Docker System setup complete!"
echo ""
echo "🌐 Access URLs:"
echo "   - Aminra Frontend: http://localhost:3000"
echo "   - Mukjizat Frontend: http://localhost:3001"
echo "   - Backend API: http://localhost:8000"
echo "   - Qdrant DB: http://localhost:6333"
echo ""
echo "📊 View logs: docker-compose logs -f [service-name]"
echo "🛑 Stop services: docker-compose down"