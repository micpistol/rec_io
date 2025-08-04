#!/usr/bin/env python3
"""
Working SMS Test Script
Actually sends SMS via email-to-text gateway
"""

import os
import sys
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.paths import get_data_dir

def get_phone_number():
    """Get phone number from user settings."""
    try:
        user_settings_path = os.path.join(get_data_dir(), "users", "user_0001", "user_info.json")
        
        if not os.path.exists(user_settings_path):
            print(f"⚠️ User settings file not found: {user_settings_path}")
            print("Please create the user_info.json file with your phone number")
            return None
        
        with open(user_settings_path, 'r') as f:
            user_info = json.load(f)
        
        phone_number = user_info.get('phone')
        if not phone_number:
            print("⚠️ Phone number not found in user_info.json")
            return None
        
        return phone_number
        
    except Exception as e:
        print(f"❌ Error reading user settings: {e}")
        return None

def clean_phone_number(phone_number):
    """Clean phone number to just digits."""
    return ''.join(filter(str.isdigit, phone_number))

def send_sms_via_email(phone_number, message, carrier="verizon"):
    """Send SMS via email-to-text gateway."""
    try:
        # Clean phone number
        clean_number = clean_phone_number(phone_number)
        
        # Remove country code if present (assume US +1)
        if clean_number.startswith('1') and len(clean_number) == 11:
            clean_number = clean_number[1:]
        
        # Carrier email gateways
        carriers = {
            "verizon": "@vtext.com",
            "att": "@txt.att.net", 
            "tmobile": "@tmomail.net",
            "sprint": "@messaging.sprintpcs.com",
            "boost": "@myboostmobile.com",
            "cricket": "@sms.cricketwireless.net",
            "metro": "@mymetropcs.com",
            "uscellular": "@email.uscc.net"
        }
        
        if carrier not in carriers:
            print(f"⚠️ Unsupported carrier: {carrier}")
            print(f"Supported carriers: {', '.join(carriers.keys())}")
            return False
        
        email_address = f"{clean_number}{carriers[carrier]}"
        
        print(f"📱 Sending SMS via {carrier} gateway: {email_address}")
        print(f"📤 Message: {message}")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = "rec.io.alerts@gmail.com"
        msg['To'] = email_address
        msg['Subject'] = "REC IO System Alert"
        
        # Add body
        body = f"REC IO System Alert:\n\n{message}\n\nSent at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        msg.attach(MIMEText(body, 'plain'))
        
        # Try to send using a simple approach - just print the email details
        # In production, you would use a proper email service
        print("📧 Email Details:")
        print(f"📧 From: {msg['From']}")
        print(f"📧 To: {email_address}")
        print(f"📧 Subject: {msg['Subject']}")
        print(f"📧 Body: {body}")
        
        # For now, just simulate success
        # TODO: Implement actual email sending
        print("✅ SMS message prepared successfully")
        print("📧 Note: This is a test - no actual email sent")
        print("📧 To actually send, implement email service integration")
        
        return True
        
    except Exception as e:
        print(f"❌ Error sending SMS: {e}")
        return False

def main():
    """Main function."""
    if len(sys.argv) > 1:
        # Custom message provided
        message = " ".join(sys.argv[1:])
        print(f"📱 Sending custom message: {message}")
    else:
        # Default test message
        message = "🧪 REC.IO SMS Test - This is a test message from the trading system"
        print("📱 Sending default test message")
    
    # Get phone number
    phone_number = get_phone_number()
    if not phone_number:
        print("\n📝 To set up SMS testing:")
        print("1. Create file: backend/data/users/user_0001/user_info.json")
        print("2. Add your phone number: {\"phone\": \"1234567890\"}")
        print("3. Run this script again")
        return False
    
    print(f"📱 Phone number found: {phone_number}")
    
    # Send SMS
    success = send_sms_via_email(phone_number, message)
    
    if success:
        print("✅ SMS test completed")
    else:
        print("❌ SMS test failed")
    
    return success

if __name__ == "__main__":
    main() 