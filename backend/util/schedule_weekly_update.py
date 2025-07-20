#!/usr/bin/env python3
"""
SCHEDULE WEEKLY UPDATE
Sets up a cron job to run the weekly update every Saturday at 11:59:59 PM.
"""

import os
import subprocess
from pathlib import Path

def setup_cron_job():
    """Set up the cron job for weekly updates."""
    
    # Get the absolute path to the weekly update script
    script_path = Path(__file__).parent / "weekly_update.py"
    script_path = script_path.resolve()
    
    # Get the Python executable path
    python_path = subprocess.check_output(["which", "python3"], text=True).strip()
    
    # Create the cron command
    cron_command = f"59 23 * * 6 {python_path} {script_path} >> {script_path.parent.parent}/logs/weekly_update_cron.log 2>&1"
    
    print("🔧 Setting up weekly update cron job...")
    print(f"Script path: {script_path}")
    print(f"Python path: {python_path}")
    print(f"Cron command: {cron_command}")
    
    # Check if cron job already exists
    try:
        existing_crontab = subprocess.check_output(["crontab", "-l"], text=True)
        if "weekly_update.py" in existing_crontab:
            print("⚠️ Weekly update cron job already exists!")
            print("Current crontab:")
            print(existing_crontab)
            return False
    except subprocess.CalledProcessError:
        # No existing crontab
        pass
    
    # Add the cron job
    try:
        # Get current crontab
        try:
            current_crontab = subprocess.check_output(["crontab", "-l"], text=True)
        except subprocess.CalledProcessError:
            current_crontab = ""
        
        # Add our new job
        new_crontab = current_crontab + f"\n# Weekly data update - runs every Saturday at 11:59:59 PM\n{cron_command}\n"
        
        # Write the new crontab
        subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
        
        print("✅ Weekly update cron job installed successfully!")
        print("The script will run every Saturday at 11:59:59 PM")
        
        # Show the current crontab
        print("\nCurrent crontab:")
        subprocess.run(["crontab", "-l"])
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install cron job: {e}")
        return False

def remove_cron_job():
    """Remove the weekly update cron job."""
    
    try:
        # Get current crontab
        current_crontab = subprocess.check_output(["crontab", "-l"], text=True)
        
        # Remove lines containing weekly_update.py
        lines = current_crontab.split('\n')
        filtered_lines = [line for line in lines if "weekly_update.py" not in line and line.strip()]
        
        # Write the filtered crontab
        new_crontab = '\n'.join(filtered_lines) + '\n'
        subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
        
        print("✅ Weekly update cron job removed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to remove cron job: {e}")
        return False

def show_cron_status():
    """Show the current cron job status."""
    
    try:
        crontab = subprocess.check_output(["crontab", "-l"], text=True)
        print("📋 Current crontab:")
        print(crontab)
        
        if "weekly_update.py" in crontab:
            print("✅ Weekly update cron job is installed")
        else:
            print("❌ Weekly update cron job is NOT installed")
            
    except subprocess.CalledProcessError:
        print("❌ No crontab found")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "install":
            setup_cron_job()
        elif command == "remove":
            remove_cron_job()
        elif command == "status":
            show_cron_status()
        else:
            print("Usage: python schedule_weekly_update.py [install|remove|status]")
    else:
        print("🔧 Weekly Update Scheduler")
        print("=" * 40)
        print("Commands:")
        print("  install  - Install the weekly update cron job")
        print("  remove   - Remove the weekly update cron job")
        print("  status   - Show current cron job status")
        print()
        print("The weekly update will run every Saturday at 11:59:59 PM")
        print("Logs will be saved to backend/logs/weekly_update_*.log") 