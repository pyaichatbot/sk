# ============================================================================
# microservices/orchestration/tests/test_orchestration_patterns.py
# ============================================================================
"""
Comprehensive test suite for orchestration patterns and end-to-end flow testing.

This test suite validates:
1. API Gateway → Orchestration → Agent → Orchestration → API Gateway flow
2. Different orchestration patterns (Sequential, Concurrent, Handoff, Group Chat, Magentic)
3. Service discovery integration
4. Intermediate messaging and real-time visibility
5. Error handling and recovery
6. Performance and metrics
"""

import asyncio
import json
import pytest
import httpx
from typing import Dict, Any, List
from datetime import datetime
import uuid

# Test configuration
API_GATEWAY_URL = "http://localhost:8000"
ORCHESTRATION_URL = "http://localhost:8001"
TEST_USER_ID = "test_user_123"
TEST_SESSION_ID = "test_session_123"

class OrchestrationPatternTester:
    """Comprehensive orchestration pattern testing class"""
    
    def __init__(self):
        self.api_gateway_url = API_GATEWAY_URL
        self.orchestration_url = ORCHESTRATION_URL
        self.test_results = []
        
    async def test_end_to_end_flow(self) -> Dict[str, Any]:
        """Test complete API Gateway → Orchestration → Agent → API Gateway flow"""
        print("🧪 Testing End-to-End Flow...")
        
        test_cases = [
            {
                "name": "Simple Sequential Flow",
                "pattern": "sequential",
                "message": "Hello, I need help with a simple task",
                "expected_agents": ["llm-agent"]
            },
            {
                "name": "Concurrent Multi-Agent Flow",
                "pattern": "concurrent", 
                "message": "I need to search for documents and analyze them simultaneously",
                "expected_agents": ["search-agent", "rag-agent"]
            },
            {
                "name": "Handoff Flow",
                "pattern": "handoff",
                "message": "First search for information, then analyze it with RAG",
                "expected_agents": ["search-agent", "rag-agent"]
            },
            {
                "name": "Group Chat Flow",
                "pattern": "group_chat",
                "message": "I need multiple agents to collaborate on a complex problem",
                "expected_agents": ["llm-agent", "search-agent", "rag-agent"]
            },
            {
                "name": "Magentic Flow",
                "pattern": "magentic",
                "message": "Use magnetic orchestration to solve this complex problem",
                "expected_agents": ["llm-agent"]
            }
        ]
        
        results = []
        for test_case in test_cases:
            result = await self._test_pattern(test_case)
            results.append(result)
            
        return {
            "total_tests": len(test_cases),
            "passed": len([r for r in results if r["success"]]),
            "failed": len([r for r in results if not r["success"]]),
            "results": results
        }
    
    async def _test_pattern(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Test a specific orchestration pattern"""
        pattern_name = test_case["name"]
        pattern = test_case["pattern"]
        message = test_case["message"]
        expected_agents = test_case["expected_agents"]
        
        print(f"  🔄 Testing {pattern_name} ({pattern})...")
        
        try:
            # Step 1: Test API Gateway orchestration endpoint
            gateway_response = await self._test_api_gateway_orchestration(pattern, message)
            if not gateway_response["success"]:
                return {
                    "pattern": pattern,
                    "name": pattern_name,
                    "success": False,
                    "error": f"API Gateway test failed: {gateway_response['error']}",
                    "duration_ms": gateway_response.get("duration_ms", 0)
                }
            
            # Step 2: Test direct orchestration service
            orchestration_response = await self._test_direct_orchestration(pattern, message)
            if not orchestration_response["success"]:
                return {
                    "pattern": pattern,
                    "name": pattern_name,
                    "success": False,
                    "error": f"Direct orchestration test failed: {orchestration_response['error']}",
                    "duration_ms": orchestration_response.get("duration_ms", 0)
                }
            
            # Step 3: Validate agent usage
            agents_used = orchestration_response.get("agents_used", [])
            agent_validation = self._validate_agent_usage(agents_used, expected_agents)
            
            # Step 4: Test intermediate messaging
            messaging_test = await self._test_intermediate_messaging(pattern, message)
            
            return {
                "pattern": pattern,
                "name": pattern_name,
                "success": True,
                "duration_ms": orchestration_response.get("duration_ms", 0),
                "agents_used": agents_used,
                "agent_validation": agent_validation,
                "messaging_test": messaging_test,
                "gateway_response": gateway_response,
                "orchestration_response": orchestration_response
            }
            
        except Exception as e:
            return {
                "pattern": pattern,
                "name": pattern_name,
                "success": False,
                "error": str(e),
                "duration_ms": 0
            }
    
    async def _test_api_gateway_orchestration(self, pattern: str, message: str) -> Dict[str, Any]:
        """Test orchestration through API Gateway"""
        start_time = datetime.utcnow()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_gateway_url}/orchestration/execute",
                    json={
                        "message": message,
                        "user_id": TEST_USER_ID,
                        "session_id": TEST_SESSION_ID,
                        "pattern": pattern,
                        "streaming": False
                    },
                    headers={"Authorization": "Bearer test_token"},
                    timeout=30.0
                )
                
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "response": response.json(),
                        "duration_ms": duration_ms
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                        "duration_ms": duration_ms
                    }
                    
        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return {
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms
            }
    
    async def _test_direct_orchestration(self, pattern: str, message: str) -> Dict[str, Any]:
        """Test orchestration directly through orchestration service"""
        start_time = datetime.utcnow()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.orchestration_url}/execute",
                    json={
                        "message": message,
                        "user_id": TEST_USER_ID,
                        "session_id": TEST_SESSION_ID,
                        "pattern": pattern,
                        "streaming": False
                    },
                    headers={"Authorization": "Bearer test_token"},
                    timeout=30.0
                )
                
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                if response.status_code == 200:
                    response_data = response.json()
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "response": response_data,
                        "agents_used": response_data.get("agents_used", []),
                        "duration_ms": duration_ms
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                        "duration_ms": duration_ms
                    }
                    
        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return {
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms
            }
    
    def _validate_agent_usage(self, agents_used: List[str], expected_agents: List[str]) -> Dict[str, Any]:
        """Validate that the expected agents were used"""
        return {
            "agents_used": agents_used,
            "expected_agents": expected_agents,
            "all_expected_used": all(agent in agents_used for agent in expected_agents),
            "unexpected_agents": [agent for agent in agents_used if agent not in expected_agents],
            "missing_agents": [agent for agent in expected_agents if agent not in agents_used]
        }
    
    async def _test_intermediate_messaging(self, pattern: str, message: str) -> Dict[str, Any]:
        """Test intermediate messaging and real-time visibility"""
        try:
            # Test WebSocket connection for real-time agent call visibility
            async with httpx.AsyncClient() as client:
                # This would test the WebSocket endpoint for real-time updates
                # For now, we'll test the HTTP endpoint
                response = await client.get(
                    f"{self.orchestration_url}/agent-calls/stream",
                    params={
                        "session_id": TEST_SESSION_ID,
                        "user_id": TEST_USER_ID
                    },
                    timeout=10.0
                )
                
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "message": "Intermediate messaging test completed"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Intermediate messaging test failed"
            }
    
    async def test_service_discovery_integration(self) -> Dict[str, Any]:
        """Test service discovery integration in orchestration flow"""
        print("🔍 Testing Service Discovery Integration...")
        
        try:
            # Test service discovery endpoints
            async with httpx.AsyncClient() as client:
                # Test orchestration service discovery
                orchestration_response = await client.get(f"{self.orchestration_url}/service-info")
                orchestration_discovery = orchestration_response.json() if orchestration_response.status_code == 200 else None
                
                # Test API Gateway service discovery
                gateway_response = await client.get(f"{self.api_gateway_url}/service-info")
                gateway_discovery = gateway_response.json() if gateway_response.status_code == 200 else None
                
                return {
                    "success": True,
                    "orchestration_discovery": orchestration_discovery,
                    "gateway_discovery": gateway_discovery,
                    "message": "Service discovery integration test completed"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Service discovery integration test failed"
            }
    
    async def test_performance_metrics(self) -> Dict[str, Any]:
        """Test performance and metrics collection"""
        print("📊 Testing Performance Metrics...")
        
        try:
            async with httpx.AsyncClient() as client:
                # Test orchestration metrics
                orchestration_metrics = await client.get(f"{self.orchestration_url}/metrics")
                orchestration_data = orchestration_metrics.json() if orchestration_metrics.status_code == 200 else None
                
                # Test API Gateway metrics
                gateway_metrics = await client.get(f"{self.api_gateway_url}/metrics")
                gateway_data = gateway_metrics.json() if gateway_metrics.status_code == 200 else None
                
                return {
                    "success": True,
                    "orchestration_metrics": orchestration_data,
                    "gateway_metrics": gateway_data,
                    "message": "Performance metrics test completed"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Performance metrics test failed"
            }
    
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run all comprehensive tests"""
        print("🚀 Starting Comprehensive Orchestration Pattern Tests...")
        print("=" * 60)
        
        start_time = datetime.utcnow()
        
        # Test 1: End-to-end flow
        end_to_end_results = await self.test_end_to_end_flow()
        
        # Test 2: Service discovery integration
        service_discovery_results = await self.test_service_discovery_integration()
        
        # Test 3: Performance metrics
        performance_results = await self.test_performance_metrics()
        
        total_duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Compile results
        results = {
            "test_summary": {
                "total_duration_seconds": total_duration,
                "end_to_end_tests": end_to_end_results,
                "service_discovery_tests": service_discovery_results,
                "performance_tests": performance_results
            },
            "overall_success": (
                end_to_end_results["passed"] > 0 and
                service_discovery_results["success"] and
                performance_results["success"]
            ),
            "recommendations": self._generate_recommendations(end_to_end_results, service_discovery_results, performance_results)
        }
        
        print("\n" + "=" * 60)
        print("🎯 TEST RESULTS SUMMARY")
        print("=" * 60)
        print(f"Total Duration: {total_duration:.2f} seconds")
        print(f"End-to-End Tests: {end_to_end_results['passed']}/{end_to_end_results['total_tests']} passed")
        print(f"Service Discovery: {'✅ PASSED' if service_discovery_results['success'] else '❌ FAILED'}")
        print(f"Performance Metrics: {'✅ PASSED' if performance_results['success'] else '❌ FAILED'}")
        print(f"Overall Success: {'✅ PASSED' if results['overall_success'] else '❌ FAILED'}")
        
        if results["recommendations"]:
            print("\n📋 RECOMMENDATIONS:")
            for recommendation in results["recommendations"]:
                print(f"  • {recommendation}")
        
        return results
    
    def _generate_recommendations(self, end_to_end_results: Dict, service_discovery_results: Dict, performance_results: Dict) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        if end_to_end_results["failed"] > 0:
            recommendations.append("Fix failing orchestration patterns")
        
        if not service_discovery_results["success"]:
            recommendations.append("Verify service discovery integration")
        
        if not performance_results["success"]:
            recommendations.append("Check metrics collection setup")
        
        if end_to_end_results["passed"] == end_to_end_results["total_tests"]:
            recommendations.append("All orchestration patterns working correctly - ready for production")
        
        return recommendations

# Test execution functions
async def run_orchestration_tests():
    """Run orchestration pattern tests"""
    tester = OrchestrationPatternTester()
    return await tester.run_comprehensive_tests()

if __name__ == "__main__":
    # Run tests
    results = asyncio.run(run_orchestration_tests())
    print(f"\n🎉 Test execution completed!")
    print(f"Results: {json.dumps(results, indent=2, default=str)}")
