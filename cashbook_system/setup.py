#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

def setup():
    """Setup the application for Render deployment"""
    
    print("🔧 Starting setup process...")
    
    # Install requirements
    print("📦 Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Create directories
    print("📁 Creating directories...")
    os.makedirs("instance", exist_ok=True)
    os.makedirs("app/static/uploads", exist_ok=True)
    
    # Initialize database
    print("🗄️ Initializing database...")
    subprocess.check_call([sys.executable, "simple_init.py"])
    
    print("✅ Setup completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(setup())