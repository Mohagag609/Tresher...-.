#!/usr/bin/env bash
# exit on error
set -o errexit

echo "🔧 Starting build process..."

# Upgrade pip
echo "📦 Upgrading pip..."
python -m pip install --upgrade pip

# Install Python dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p instance
mkdir -p app/static/uploads

# Initialize database
echo "🗄️ Initializing database..."
python simple_init.py

echo "✅ Build completed successfully!"
echo "🚀 Ready to start the application"