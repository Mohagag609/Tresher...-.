#!/usr/bin/env bash
set -o errexit

echo "🔧 Starting build..."

# Clean old files
rm -rf instance/
rm -f *.db

# Install dependencies
pip install Flask werkzeug gunicorn

echo "✅ Build completed!"