#!/usr/bin/env python3
"""
Test script to verify frontend refresh on database changes
"""
import asyncio
import aiohttp
import json
import time

async def test_frontend_refresh():
    """Test that the frontend refreshes when database changes occur"""
    
    print("🧪 Testing frontend refresh on database changes...")
    
    # Test the notification endpoint
    async with aiohttp.ClientSession() as session:
        notification_url = "http://localhost:3000/api/notify_db_change"
        
        # Test fills notification
        payload = {
            "db_name": "fills",
            "timestamp": time.time(),
            "change_data": {"fills": 5}
        }
        
        print("📡 Sending fills notification...")
        async with session.post(notification_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Fills notification sent: {result}")
            else:
                print(f"❌ Fills notification failed: {response.status}")
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Test positions notification
        payload = {
            "db_name": "positions",
            "timestamp": time.time(),
            "change_data": {"market_positions": 3, "event_positions": 1}
        }
        
        print("📡 Sending positions notification...")
        async with session.post(notification_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Positions notification sent: {result}")
            else:
                print(f"❌ Positions notification failed: {response.status}")
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Test settlements notification
        payload = {
            "db_name": "settlements",
            "timestamp": time.time(),
            "change_data": {"settlements": 2}
        }
        
        print("📡 Sending settlements notification...")
        async with session.post(notification_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Settlements notification sent: {result}")
            else:
                print(f"❌ Settlements notification failed: {response.status}")
    
    print("\n📋 Instructions for manual verification:")
    print("1. Open the trade monitor in your browser")
    print("2. Open browser developer tools (F12)")
    print("3. Go to the Console tab")
    print("4. Run this test script again")
    print("5. Watch for WebSocket messages and table refresh logs")
    print("6. Verify that the tables update automatically")

if __name__ == "__main__":
    print("🧪 Testing frontend refresh system...")
    asyncio.run(test_frontend_refresh())
    print("✅ Test completed!") 