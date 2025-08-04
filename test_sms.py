#!/usr/bin/env python3

import os
import sys
import json
import requests
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import getpass

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_data_dir():
    """Get the data directory path."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend", "data")

def send_sms_alert(message: str) -> bool:
    """Send SMS alert to the phone number in user settings using Verizon email-to-SMS gateway."""
    try:
        # Get user settings to find phone number
        user_settings_path = os.path.join(get_data_dir(), "users", "user_0001", "user_info.json")
        
        if not os.path.exists(user_settings_path):
            print(f"⚠️ User settings file not found: {user_settings_path}")
            return False
        
        with open(user_settings_path, 'r') as f:
            user_settings = json.load(f)
        
        phone_number = user_settings.get("phone")
        if not phone_number:
            print("⚠️ No phone number found in user settings")
            return False
        
        # Clean phone number (remove spaces, parentheses, etc.)
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        
        # Ensure it's a 10-digit number
        if len(clean_phone) == 11 and clean_phone.startswith('1'):
            clean_phone = clean_phone[1:]
        elif len(clean_phone) != 10:
            print(f"❌ Invalid phone number format: {phone_number}")
            return False
        
        # Verizon email-to-SMS gateway
        verizon_email = f"{clean_phone}@vtext.com"
        
        print(f"📱 Sending SMS via Verizon gateway: {verizon_email}")
        print(f"📤 Message: {message}")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = "rec_io_system@localhost"
        msg['To'] = verizon_email
        msg['Subject'] = "REC IO System Alert"
        
        # Add body
        body = f"REC IO System Alert:\n\n{message}\n\nSent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg.attach(MIMEText(body, 'plain'))
        
        # Try multiple SMTP options
        print("\n🔧 Attempting to send SMS...")
        
        # Option 1: Try local SMTP (if available)
        try:
            server = smtplib.SMTP('localhost', 25)
            server.send_message(msg)
            server.quit()
            print("✅ SMS sent successfully via local SMTP!")
            return True
        except Exception as e:
            print(f"⚠️ Local SMTP not available: {e}")
        
        # Option 2: Prompt for Gmail credentials
        print("\n📧 Gmail SMTP Setup:")
        print("To use Gmail, you need:")
        print("1. Enable 2-factor authentication on your Gmail account")
        print("2. Generate an 'App Password' in Gmail settings")
        print("3. Use that app password (not your regular password)")
        
        use_gmail = input("\nWould you like to try Gmail SMTP? (y/n): ").lower().strip()
        
        if use_gmail == 'y':
            gmail_user = input("Enter your Gmail address: ").strip()
            gmail_password = getpass.getpass("Enter your Gmail App Password: ")
            
            try:
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(gmail_user, gmail_password)
                server.send_message(msg)
                server.quit()
                print("✅ SMS sent successfully via Gmail!")
                return True
            except Exception as e:
                print(f"❌ Gmail SMTP failed: {e}")
        
        # Option 3: Manual instructions
        print("\n📋 Manual SMS Setup:")
        print("Since automatic email sending isn't configured, you can:")
        print("1. Send an email manually to: " + verizon_email)
        print("2. Subject: REC IO System Alert")
        print("3. Body: " + body)
        print("\nThis will deliver as an SMS to your phone.")
        
        return False
        
    except Exception as e:
        print(f"❌ Error sending SMS alert: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing SMS Service...")
    
    # Test message
    test_message = f"🧪 SMS TEST - System Monitor Test at {datetime.now().strftime('%H:%M:%S')}"
    
    success = send_sms_alert(test_message)
    
    if success:
        print("✅ SMS test completed successfully")
    else:
        print("❌ SMS test failed - check manual instructions above") 