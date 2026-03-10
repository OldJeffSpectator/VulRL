"""Worker Unit main entry point."""

import argparse
import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from worker_router.redis_client import RedisClient
from worker_router.config import Config
from worker_unit.llm_client import LLMClient
from worker_unit.docker_manager import DockerManager
from worker_unit.reward_calculator import RewardCalculator


class WorkerUnit:
    """Worker unit that executes rollouts."""
    
    def __init__(self, worker_id: str, redis_client: RedisClient):
        """Initialize worker unit.
        
        Args:
            worker_id: Worker ID
            redis_client: Redis client
        """
        self.worker_id = worker_id
        self.redis_client = redis_client
        self.docker_manager = DockerManager()
        self.reward_calculator = RewardCalculator()
        self.running = True
    
    async def run(self):
        """Main worker loop: poll Redis queue and execute tasks."""
        print(f"[Worker {self.worker_id}] Started")
        
        while self.running:
            # Poll queue for task
            task_id = self.redis_client.pop_task(self.worker_id, timeout=5)
            
            if not task_id:
                continue
            
            print(f"[Worker {self.worker_id}] Received task: {task_id}")
            
            # Update worker status
            self.redis_client.set_worker_status(self.worker_id, "busy")
            
            # Get task details
            task_meta = self.redis_client.get_task_metadata(task_id)
            request = task_meta.get("request")
            
            # Execute rollout
            await self.execute_rollout(task_id, request)
            
            # Update worker status
            self.redis_client.set_worker_status(self.worker_id, "idle")
            
            # Increment tasks completed
            worker_status = self.redis_client.get_worker_status(self.worker_id)
            completed = worker_status.get("tasks_completed", 0) + 1
            self.redis_client.set_worker_metadata(self.worker_id, {
                "tasks_completed": completed,
                "current_task": None,
            })
            
            print(f"[Worker {self.worker_id}] Task {task_id} completed")
    
    async def execute_rollout(self, task_id: str, request: dict):
        """Execute a single rollout.
        
        Args:
            task_id: Task ID
            request: Rollout request dict
        """
        # Extract request parameters
        cve_id = request["cve_id"]
        vulhub_path = request["vulhub_path"]
        prompt = request["prompt"]
        max_steps = request.get("max_steps", 20)
        llm_endpoint = request["llm_endpoint"]
        model_name = request["model_name"]
        temperature = request.get("temperature", 0.7)
        max_tokens = request.get("max_tokens", 512)
        
        # Initialize LLM client
        llm_client = LLMClient(llm_endpoint, model_name)
        
        # Setup Docker environment
        docker_context = await self.docker_manager.setup_environment(vulhub_path, cve_id)
        
        # Initialize conversation
        messages = [
            {"role": "system", "content": "You are a penetration testing agent. Provide concrete bash commands."},
            {"role": "user", "content": prompt},
        ]
        
        # Execute exploitation loop
        trajectory = []
        total_reward = 0.0
        success = False
        
        for step in range(max_steps):
            # Query LLM for action
            action = await llm_client.query(messages, max_tokens, temperature)
            
            # Execute action
            observation = await self.docker_manager.execute_action(action, docker_context)
            
            # Compute reward
            reward, done = self.reward_calculator.compute_reward(observation, action, step)
            total_reward += reward
            
            # Store step
            trajectory.append({
                "step": step,
                "action": action,
                "observation": observation,
                "reward": reward,
                "done": done,
                "metadata": {},
            })
            
            # Update conversation
            messages.append({"role": "assistant", "content": action})
            messages.append({"role": "user", "content": observation})
            
            # Check if done
            if done:
                success = reward > 0.5
                break
        
        # Cleanup Docker
        await self.docker_manager.cleanup_environment(docker_context)
        
        # Store result
        result = {
            "reward": total_reward,
            "trajectory": trajectory,
            "success": success,
            "metadata": {
                "cve_id": cve_id,
                "total_steps": len(trajectory),
            },
        }
        
        self.redis_client.store_result(task_id, result, ttl=3600)
        
        # Update task status
        self.redis_client.set_task_metadata(task_id, {
            "status": "completed",
            "completed_at": time.time(),
        })
    
    def shutdown(self):
        """Shutdown worker."""
        self.running = False
        print(f"[Worker {self.worker_id}] Shutting down")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Worker Unit")
    parser.add_argument("--worker-id", required=True, help="Worker ID")
    args = parser.parse_args()
    
    # Load config
    config = Config("config.yaml")
    
    # Initialize Redis client
    redis_config = config.redis
    redis_client = RedisClient(
        host=redis_config.get("host", "localhost"),
        port=redis_config.get("port", 6379),
        db=redis_config.get("db", 0),
        password=redis_config.get("password"),
    )
    
    # Create worker
    worker = WorkerUnit(args.worker_id, redis_client)
    
    # Run worker
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
