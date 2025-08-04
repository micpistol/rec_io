#!/usr/bin/env python3
"""
User Notification Service
Core notification system for REC.IO trading platform
Sends SMS alerts via email-to-text gateway
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

# Make the notification function available for import
__all__ = ['send_user_notification', 'send_sms_via_email']

def get_user_info():
    """Get user info from settings."""
    try:
        user_settings_path = os.path.join(get_data_dir(), "users", "user_0001", "user_info.json")
        
        if not os.path.exists(user_settings_path):
            print(f"⚠️ User settings file not found: {user_settings_path}")
            print("Please create the user_info.json file with your phone number and email")
            return None, None
        
        with open(user_settings_path, 'r') as f:
            user_settings = json.load(f)
        
        phone_number = user_settings.get("phone")
        email_address = user_settings.get("email")
        
        if not phone_number:
            print("⚠️ No phone number found in user settings")
            print("Please add a 'phone' field to your user_info.json file")
        
        if not email_address:
            print("⚠️ No email address found in user settings")
            print("Please add an 'email' field to your user_info.json file")
        
        return phone_number, email_address
        
    except Exception as e:
        print(f"❌ Error reading user settings: {e}")
        return None, None

def get_phone_number():
    """Get phone number from user settings."""
    phone_number, _ = get_user_info()
    return phone_number

def clean_phone_number(phone_number):
    """Clean phone number for email gateway."""
    # Remove spaces, parentheses, etc.
    clean_phone = ''.join(filter(str.isdigit, phone_number))
    
    # Ensure it's a 10-digit number
    if len(clean_phone) == 11 and clean_phone.startswith('1'):
        clean_phone = clean_phone[1:]
    elif len(clean_phone) != 10:
        print(f"❌ Invalid phone number format: {phone_number}")
        return None
    
    return clean_phone

def send_sms_via_email(phone_number, message, carrier="verizon", notification_type="SYSTEM"):
    """Send SMS via email-to-text gateway."""
    try:
        clean_phone = clean_phone_number(phone_number)
        if not clean_phone:
            return False
        
        # Carrier email gateways
        carriers = {
            "verizon": f"{clean_phone}@vtext.com",
            "verizon_alt": f"{clean_phone}@vzwpix.com",  # Alternative Verizon gateway
            "att": f"{clean_phone}@txt.att.net",
            "tmobile": f"{clean_phone}@tmomail.net",
            "sprint": f"{clean_phone}@messaging.sprintpcs.com",
            "boost": f"{clean_phone}@myboostmobile.com",
            "cricket": f"{clean_phone}@sms.cricketwireless.net",
            "metro": f"{clean_phone}@mymetropcs.com",
            "uscellular": f"{clean_phone}@email.uscc.net"
        }
        
        if carrier not in carriers:
            print(f"❌ Unsupported carrier: {carrier}")
            print(f"Supported carriers: {', '.join(carriers.keys())}")
            return False
        
        email_address = carriers[carrier]
        
        print(f"📱 Sending SMS via {carrier} gateway: {email_address}")
        print(f"📤 Message: {message}")
        
        # Create simple text message with header
        msg = MIMEText("TEST", 'plain')
        msg['From'] = "rec_io_system@localhost"
        msg['To'] = email_address
        
        # Try to send the email using local Python SMTP server
        try:
            # Try local Python SMTP server (for testing)
            server = smtplib.SMTP('localhost', 1025)
            server.send_message(msg)
            server.quit()
            print("✅ SMS sent successfully via local Python SMTP server")
            return True
            
        except Exception as e:
            print(f"⚠️ Could not send via local Python SMTP server: {e}")
            
            # Fallback: Try Gmail SMTP
            try:
                smtp_server = "smtp.gmail.com"
                smtp_port = 587
                
                gmail_user = "rec.io.alerts@gmail.com"
                gmail_password = "jfnc adxj ubfz lrtw"  # App Password (without spaces)
                
                msg['From'] = gmail_user
                
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(gmail_user, gmail_password)
                
                server.send_message(msg)
                server.quit()
                
                print("✅ SMS sent successfully via Gmail SMTP")
                return True
                
            except Exception as gmail_error:
                print(f"⚠️ Could not send via Gmail SMTP: {gmail_error}")
                print("📧 Email gateway configured but requires SMTP setup")
                print(f"📧 Would send to: {email_address}")
                print(f"📧 Body: REC.IO TRADING ALERT: ALERT")
                return False
            
    except Exception as e:
        print(f"❌ Error sending SMS: {e}")
        return False

def send_email_notification(email_address, message, notification_type="SYSTEM"):
    """Send email notification."""
    try:
        print(f"📧 Sending email notification to: {email_address}")
        
        # Create email message
        msg = MIMEText(f"REC.IO TRADING ALERT: {message}", 'plain')
        msg['From'] = "rec.io.alerts@gmail.com"
        msg['To'] = email_address
        msg['Subject'] = f"REC.IO {notification_type} Alert"
        
        # Send via Gmail SMTP
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        gmail_user = "rec.io.alerts@gmail.com"
        gmail_password = "jfnc adxj ubfz lrtw"  # App Password (without spaces)
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(gmail_user, gmail_password)
        
        server.send_message(msg)
        server.quit()
        
        print("✅ Email notification sent successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email notification: {e}")
        return False

def test_sms_functionality():
    """Test SMS functionality."""
    print("🧪 Testing SMS Functionality")
    print("=" * 50)
    
    # Get phone number
    phone_number = get_phone_number()
    if not phone_number:
        print("\n📝 To set up SMS testing:")
        print("1. Create file: backend/data/users/user_0001/user_info.json")
        print("2. Add your phone number: {\"phone\": \"1234567890\"}")
        print("3. Run this script again")
        return False
    
    print(f"📱 Phone number found: {phone_number}")
    
    # Test message
    test_message = "🧪 REC.IO SMS Test - This is a test message from the trading system"
    
    # Test with different carriers
    carriers = ["verizon", "att", "tmobile"]
    
    for carrier in carriers:
        print(f"\n📡 Testing {carrier.upper()} gateway...")
        success = send_sms_via_email(phone_number, test_message, carrier)
        
        if success:
            print(f"✅ {carrier.upper()} test successful")
        else:
            print(f"❌ {carrier.upper()} test failed")
    
    return True

def send_user_notification(message, notification_type="SYSTEM"):
    """
    Send a user notification via SMS and email.
    
    Args:
        message (str): The message to send
        notification_type (str): Type of notification (SYSTEM, TRADE, ALERT, etc.)
    
    Returns:
        bool: True if sent successfully, False otherwise
    """
    # Format the message with notification type
    formatted_message = f"REC.IO TRADING ALERT: {message}"
    
    # Get user info
    phone_number, email_address = get_user_info()
    
    sms_success = False
    email_success = False
    
    # Send SMS if phone number is available
    if phone_number:
        # Try multiple carriers for better delivery
        carriers_to_try = ["verizon_alt", "verizon", "att", "tmobile"]
        sms_success = False
        
        for carrier in carriers_to_try:
            print(f"📱 Trying {carrier} gateway...")
            if send_sms_via_email(phone_number, formatted_message, carrier=carrier, notification_type=notification_type):
                sms_success = True
                print(f"✅ SMS sent successfully via {carrier}")
                break
            else:
                print(f"❌ Failed to send via {carrier}")
    else:
        print("⚠️ No phone number configured for SMS notifications")
    
    # Send email if email address is available
    if email_address:
        email_success = send_email_notification(email_address, message, notification_type)
    else:
        print("⚠️ No email address configured for email notifications")
    
    # Return success if either SMS or email was sent successfully
    if sms_success or email_success:
        print(f"✅ {notification_type} notification sent successfully")
        return True
    else:
        print(f"❌ Failed to send {notification_type} notification")
        return False

def main():
    """Main function."""
    if len(sys.argv) > 1:
        # Custom message provided
        message = " ".join(sys.argv[1:])
        print(f"📱 Sending custom message: {message}")
        
        # Determine notification type based on message content
        notification_type = "SYSTEM"
        if "TRADING SYSTEM ALERT" in message or "Critical services" in message:
            notification_type = "ALERT"
        elif "trade" in message.lower():
            notification_type = "TRADE"
        elif "test" in message.lower():
            notification_type = "TEST"
        
        success = send_user_notification(message, notification_type)
        
        if success:
            print("✅ SMS notification sent successfully")
        else:
            print("❌ Failed to send SMS notification")
            sys.exit(1)
    else:
        # Run test
        test_sms_functionality()

if __name__ == "__main__":
    main() 