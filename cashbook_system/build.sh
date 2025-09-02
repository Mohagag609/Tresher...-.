#!/usr/bin/env bash
set -o errexit

echo "🔧 Starting build..."

# Install only what we need
pip install Flask werkzeug gunicorn

echo "✅ Build completed!"