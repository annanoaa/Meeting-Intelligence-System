#!/bin/bash

# KIU Meeting Intelligence System - Quick Setup Script

echo "🚀 Setting up KIU Meeting Intelligence System..."
echo "=================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "Please install Python 3.8+ and try again."
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your OpenAI API key!"
else
    echo "✅ .env file already exists"
fi

# Run setup checks
echo "🔍 Running system checks..."
python3 run.py check

echo "=================================================="
echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Edit .env file and add your OpenAI API key"
echo "2. Run: python3 run.py dev"
echo "3. Open: http://localhost:5000"
echo ""
echo "📚 For more information, see README.md"
echo "🎬 For demo instructions, see DEMO_SCRIPT.md" 