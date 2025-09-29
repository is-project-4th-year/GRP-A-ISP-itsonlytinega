#!/usr/bin/env python
"""
Setup script for Verbal Coach Django project.
This script helps with initial project setup and database migrations.
"""

import os
import sys
import subprocess
import django
from django.core.management import execute_from_command_line

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"Running: {description}")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"Error: {e.stderr}")
        return False

def setup_environment():
    """Set up the environment and install dependencies."""
    print("🚀 Setting up Verbal Coach...")
    
    # Check if virtual environment exists
    if not os.path.exists('venv'):
        print("Creating virtual environment...")
        if not run_command('python -m venv venv', 'Virtual environment creation'):
            return False
    
    # Install requirements
    if not run_command('pip install -r requirements.txt', 'Installing requirements'):
        return False
    
    return True

def setup_database():
    """Set up the database and run migrations."""
    print("🗄️ Setting up database...")
    
    # Set Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'verbalcoach.settings')
    django.setup()
    
    # Make migrations
    if not run_command('python manage.py makemigrations', 'Creating migrations'):
        return False
    
    # Run migrations
    if not run_command('python manage.py migrate', 'Running migrations'):
        return False
    
    return True

def create_superuser():
    """Create a superuser account."""
    print("👤 Creating superuser account...")
    
    # Check if superuser already exists
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    if User.objects.filter(is_superuser=True).exists():
        print("✅ Superuser already exists")
        return True
    
    # Create superuser
    try:
        from django.core.management import call_command
        call_command('createsuperuser', interactive=False, 
                    email='admin@verbalcoach.com',
                    first_name='Admin',
                    last_name='User')
        print("✅ Superuser created successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to create superuser: {e}")
        return False

def download_spacy_model():
    """Download the SpaCy model."""
    print("📚 Downloading SpaCy model...")
    
    if not run_command('python -m spacy download en_core_web_sm', 'Downloading SpaCy model'):
        print("⚠️ SpaCy model download failed. You can install it manually later.")
        return False
    
    return True

def main():
    """Main setup function."""
    print("=" * 50)
    print("🎯 Verbal Coach Setup Script")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    
    # Setup steps
    steps = [
        ("Environment Setup", setup_environment),
        ("Database Setup", setup_database),
        ("Create Superuser", create_superuser),
        ("Download SpaCy Model", download_spacy_model),
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ Setup failed at: {step_name}")
            sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Create a .env file with your database credentials")
    print("2. Run: python manage.py runserver")
    print("3. Visit: http://127.0.0.1:8000")
    print("4. Login with: admin@verbalcoach.com")
    print("\nHappy coding! 🚀")

if __name__ == '__main__':
    main()


