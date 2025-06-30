#!/usr/bin/env python3
"""
Production run script for KIU Meeting Intelligence System
"""
import os
import sys
from flask import Flask
from app import app, init_database
from config import config, Config

def create_app(config_name=None):
    """Create and configure the Flask application"""
    
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    # Configure the app
    app.config.from_object(config[config_name])
    
    # Validate configuration
    try:
        Config.validate_config()
        print(f"✅ Configuration validated for {config_name} environment")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)
    
    # Initialize database
    try:
        init_database()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        sys.exit(1)
    
    return app

def run_development():
    """Run in development mode"""
    print("🚀 Starting KIU Meeting Intelligence System in development mode...")
    print("📝 Make sure to set your OPENAI_API_KEY in the .env file")
    print("🌐 Application will be available at http://localhost:5000")
    
    app = create_app('development')
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )

def run_production():
    """Run in production mode"""
    print("🚀 Starting KIU Meeting Intelligence System in production mode...")
    
    app = create_app('production')
    
    # In production, you should use a proper WSGI server
    # This is just for demonstration
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        debug=False,
        threaded=True
    )

def run_tests():
    """Run the test suite"""
    import pytest
    
    print("🧪 Running test suite...")
    exit_code = pytest.main([
        'tests/',
        '-v',
        '--tb=short',
        '--color=yes'
    ])
    
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return exit_code

def check_requirements():
    """Check if all requirements are satisfied"""
    print("🔍 Checking requirements...")
    
    try:
        import flask
        import openai
        import sqlite3
        import numpy
        import pandas
        import sklearn
        import requests
        import pytest
        
        print("✅ All required packages are installed")
        
        # Check OpenAI API key
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("⚠️  OPENAI_API_KEY not found in environment variables")
            print("   Please create a .env file with your OpenAI API key")
            return False
        elif api_key.startswith('sk-'):
            print("✅ OpenAI API key format looks correct")
        else:
            print("⚠️  OpenAI API key format might be incorrect")
        
        return True
        
    except ImportError as e:
        print(f"❌ Missing requirement: {e}")
        print("   Please run: pip install -r requirements.txt")
        return False

def print_help():
    """Print usage help"""
    print("""
KIU Meeting Intelligence System

Usage:
    python run.py [command]

Commands:
    dev         Run in development mode (default)
    prod        Run in production mode  
    test        Run test suite
    check       Check requirements and configuration
    help        Show this help message

Examples:
    python run.py              # Run in development mode
    python run.py dev          # Run in development mode
    python run.py test         # Run tests
    python run.py check        # Check setup
    
Environment Variables:
    OPENAI_API_KEY             # Your OpenAI API key (required)
    FLASK_ENV                  # Environment (development/production)
    SECRET_KEY                 # Flask secret key
    
For more information, see README.md
""")

if __name__ == '__main__':
    # Parse command line arguments
    command = sys.argv[1] if len(sys.argv) > 1 else 'dev'
    
    if command in ['help', '-h', '--help']:
        print_help()
    
    elif command == 'check':
        if check_requirements():
            print("✅ System is ready to run!")
        else:
            print("❌ Please fix the issues above before running")
            sys.exit(1)
    
    elif command == 'test':
        if not check_requirements():
            print("❌ Requirements not satisfied")
            sys.exit(1)
        
        exit_code = run_tests()
        sys.exit(exit_code)
    
    elif command == 'dev':
        if not check_requirements():
            print("❌ Requirements not satisfied")
            sys.exit(1)
        
        run_development()
    
    elif command == 'prod':
        if not check_requirements():
            print("❌ Requirements not satisfied")
            sys.exit(1)
        
        run_production()
    
    else:
        print(f"❌ Unknown command: {command}")
        print_help()
        sys.exit(1) 