#!/bin/bash
# Render build script for BioAgent Backend

set -e

echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Install bioagent core dependencies (from parent directory)
echo "📦 Installing BioAgent core dependencies..."
pip install anthropic>=0.40.0
pip install sentence-transformers>=2.2.0 || echo "⚠️ sentence-transformers optional"

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p /tmp/workspace
mkdir -p /tmp/uploads

echo "✅ Build complete!"
