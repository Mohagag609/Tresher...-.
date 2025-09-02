#!/usr/bin/env bash
set -o errexit

echo "🔧 Starting build..."

# Install dependencies
pip install Flask werkzeug gunicorn

# Create directories
mkdir -p instance

# Remove old database if exists
rm -f instance/cashbook.db

# Initialize database with correct schema
python fix_database.py

echo "✅ Build completed!"