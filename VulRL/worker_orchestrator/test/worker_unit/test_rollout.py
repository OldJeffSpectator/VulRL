"""
Test Demo Agent (Simple Agent)

Test case:
- Agent: Demo (simple bash command agent)
- CVE: apache-cxf/CVE-2024-28752
- Prompt: "write a hello world script at /tmp/workspace/"
- LLM: http://127.0.0.1:8001

Uses regular VulhubAdapter with Docker SDK.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from worker_unit.rollout_executor import RolloutExecutor
from worker_router.models import RolloutRequest


async def test_rollout():
    """Test Demo agent with CVE-2024-28752."""
    
    print("=" * 70)
    print("Demo Agent Test")
    print("=" * 70)
    print()
    
    # Create test request for demo agent
    request = RolloutRequest(
        cve_id="CVE-2024-28752-demo",
        vulhub_path="apache-cxf/CVE-2024-28752",
        prompt="write a hello world script at /tmp/workspace/",
        max_steps=5,
        timeout=300,
        llm_endpoint="http://127.0.0.1:8001",
        model_name="qwen2.5-1.5b",
        temperature=0.7,
        max_tokens=512,
        metadata={
            "agent_type": "demo",
            "vulhub_base_path": "/mnt/e/git_fork_folder/VulRL/benchmark/vulhub"
        }
    )
    
    print("Test Configuration:")
    print(f"  Agent Type: DEMO (simple)")
    print(f"  CVE ID: {request.cve_id}")
    print(f"  Vulhub Path: {request.vulhub_path}")
    print(f"  Prompt: {request.prompt}")
    print(f"  Max Steps: {request.max_steps}")
    print(f"  LLM: {request.llm_endpoint}")
    print()
    
    # Execute rollout with demo agent
    executor = RolloutExecutor()
    
    try:
        print("Executing rollout with DEMO agent...")
        print()
        result = await executor.execute(request, agent_type="demo")
        
        print("=" * 70)
        print("Rollout Result")
        print("=" * 70)
        print(f"Status: {result.status}")
        print(f"Reward: {result.reward}")
        print(f"Success: {result.success}")
        print(f"Duration: {result.duration:.2f}s")
        print(f"Steps: {len(result.trajectory) if result.trajectory else 0}")
        print()
        
        if result.trajectory:
            print("Trajectory:")
            for step in result.trajectory:
                print(f"\n  Step {step.step}:")
                print(f"    Action: {step.action[:100]}...")
                print(f"    Observation: {step.observation[:100]}...")
                print(f"    Reward: {step.reward}")
                print(f"    Done: {step.done}")
        
        if result.error:
            print(f"\n✗ Error: {result.error}")
            return 1
        else:
            print("\n✓ Rollout completed successfully!")
            return 0
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_rollout())
    sys.exit(exit_code)
