#!/usr/bin/env python3
"""
Test script for database change notifications
"""
import asyncio
import aiohttp
import json
import time

async def test_db_notification():
    """Test the database change notification system"""
    
    # Test the notification endpoint
    async with aiohttp.ClientSession() as session:
        notification_url = "http://localhost:3000/api/notify_db_change"
        
        # Test fills notification
        payload = {
            "db_name": "fills",
            "timestamp": time.time(),
            "change_data": {"fills": 5}
        }
        
        print("🧪 Testing fills notification...")
        async with session.post(notification_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Fills notification successful: {result}")
            else:
                print(f"❌ Fills notification failed: {response.status}")
        
        # Test positions notification
        payload = {
            "db_name": "positions",
            "timestamp": time.time(),
            "change_data": {"market_positions": 3, "event_positions": 1}
        }
        
        print("🧪 Testing positions notification...")
        async with session.post(notification_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Positions notification successful: {result}")
            else:
                print(f"❌ Positions notification failed: {response.status}")
        
        # Test settlements notification
        payload = {
            "db_name": "settlements",
            "timestamp": time.time(),
            "change_data": {"settlements": 2}
        }
        
        print("🧪 Testing settlements notification...")
        async with session.post(notification_url, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                print(f"✅ Settlements notification successful: {result}")
            else:
                print(f"❌ Settlements notification failed: {response.status}")

if __name__ == "__main__":
    print("🧪 Testing database change notification system...")
    asyncio.run(test_db_notification())
    print("✅ Test completed!") 