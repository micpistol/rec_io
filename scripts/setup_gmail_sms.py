#!/usr/bin/env python3
"""
Gmail SMS Setup Script
Helps configure Gmail SMTP credentials for SMS functionality
"""

import os
import sys
import getpass
from pathlib import Path

def setup_gmail_credentials():
    """Set up Gmail credentials for SMS functionality."""
    print("📧 Gmail SMS Setup")
    print("=" * 50)
    
    print("\n📋 To use Gmail for SMS, you need:")
    print("1. A Gmail account")
    print("2. An App Password (not your regular password)")
    print("\n🔐 To create an App Password:")
    print("1. Go to https://myaccount.google.com/security")
    print("2. Enable 2-Step Verification if not already enabled")
    print("3. Go to 'App passwords'")
    print("4. Generate a new app password for 'Mail'")
    print("5. Use that 16-character password below")
    
    print("\n" + "=" * 50)
    
    # Get Gmail credentials
    gmail_user = input("Enter your Gmail address: ").strip()
    
    if not gmail_user or '@gmail.com' not in gmail_user:
        print("❌ Please enter a valid Gmail address")
        return False
    
    print("\n🔐 Enter your Gmail App Password (16 characters):")
    gmail_password = getpass.getpass("App Password: ").strip()
    
    if not gmail_password or len(gmail_password) != 16:
        print("❌ App Password should be 16 characters")
        return False
    
    # Create environment file
    env_file = Path(".env")
    env_content = f"""# Gmail SMTP Configuration for SMS
GMAIL_USER={gmail_user}
GMAIL_APP_PASSWORD={gmail_password}
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        
        print(f"\n✅ Gmail credentials saved to {env_file}")
        print("🔒 File permissions set to user-only")
        
        # Set file permissions to user-only
        os.chmod(env_file, 0o600)
        
        print("\n📱 To test SMS functionality:")
        print("1. Load the environment: source .env")
        print("2. Run: python scripts/test_sms.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return False

def test_gmail_connection():
    """Test Gmail SMTP connection."""
    print("\n🧪 Testing Gmail SMTP Connection")
    print("=" * 50)
    
    # Load environment variables
    gmail_user = os.getenv('GMAIL_USER')
    gmail_password = os.getenv('GMAIL_APP_PASSWORD')
    
    if not gmail_user or not gmail_password:
        print("❌ Gmail credentials not found")
        print("Please run: python scripts/setup_gmail_sms.py")
        return False
    
    try:
        import smtplib
        
        # Test connection
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.quit()
        
        print("✅ Gmail SMTP connection successful")
        print("📧 Ready to send SMS via email gateway")
        return True
        
    except Exception as e:
        print(f"❌ Gmail SMTP connection failed: {e}")
        print("🔧 Please check your credentials and try again")
        return False

def main():
    """Main function."""
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_gmail_connection()
    else:
        setup_gmail_credentials()

if __name__ == "__main__":
    main() 