#!/usr/bin/env bash
set -o errexit

echo "🔧 Starting build..."

# Install dependencies
pip install Flask werkzeug gunicorn

# Create directories
mkdir -p instance

# Initialize database
python fix_database.py

echo "✅ Build completed!"