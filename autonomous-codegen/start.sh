#!/bin/bash
# start.sh

set -e

echo "🚀 Starting Autonomous Code Generator..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

# Check Ollama
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama not running. Starting..."
    ollama serve &
    sleep 3
fi

# Build and start
echo "🔨 Building containers..."
docker compose build

echo "▶️  Starting services..."
docker compose up -d

echo ""
echo "✅ Ready!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Docs:     http://localhost:8000/docs"
echo ""
echo "📋 Logs: docker compose logs -f backend"

