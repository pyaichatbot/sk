#!/usr/bin/env python3
"""
Simple Orchestration Test
=========================

Basic test for orchestration service in Docker.
"""

import asyncio
import json
import httpx
from datetime import datetime

async def test_orchestration():
    """Test orchestration service"""
    print("🧪 Testing Orchestration Service...")
    
    orchestration_url = "http://localhost:8001"
    
    try:
        # Test health
        async with httpx.AsyncClient() as client:
            health_response = await client.get(f"{orchestration_url}/health", timeout=10.0)
            print(f"Health Status: {health_response.status_code}")
            
            if health_response.status_code == 200:
                print("✅ Orchestration service is healthy")
                health_data = health_response.json()
                print(f"   Service: {health_data.get('service', 'unknown')}")
                print(f"   Status: {health_data.get('status', 'unknown')}")
            else:
                print("❌ Orchestration service is unhealthy")
                return False
        
        # Test orchestration patterns
        patterns = ["sequential", "concurrent", "handoff", "group_chat", "magentic"]
        
        for pattern in patterns:
            print(f"Testing {pattern} pattern...")
            
            try:
                async with httpx.AsyncClient() as pattern_client:
                    response = await pattern_client.post(
                        f"{orchestration_url}/orchestrate",
                        json={
                            "message": f"Test message for {pattern} pattern",
                            "user_id": "test_user",
                            "session_id": f"test_session_{pattern}",
                            "pattern": pattern,
                            "streaming": False
                        },
                        headers={"Authorization": "Bearer test_token"},
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        print(f"✅ {pattern} pattern: SUCCESS")
                        print(f"   Response: {response_data.get('content', 'No content')[:100]}...")
                        print(f"   Pattern: {response_data.get('pattern', 'unknown')}")
                        print(f"   Duration: {response_data.get('duration_ms', 0)}ms")
                    else:
                        print(f"❌ {pattern} pattern: FAILED ({response.status_code})")
                        print(f"   Error: {response.text}")
                        
            except Exception as e:
                print(f"❌ {pattern} pattern: ERROR - {str(e)}")
        
        print("🎉 Orchestration testing completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    asyncio.run(test_orchestration())
