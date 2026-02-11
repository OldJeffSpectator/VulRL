#!/usr/bin/env python3
"""
Test a trained model directly with SecurityEnv.

Usage:
    python test_trained_model.py \
        --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
        --task-type vulhub \
        --task-id jenkins/CVE-2018-1000861
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vulrl.env_manage import SecurityEnv
from vulrl.config import EnvConfig
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


class ModelTester:
    """Test trained model with SecurityEnv."""
    
    def __init__(self, checkpoint_path: str, base_model: str = "Qwen/Qwen2.5-3B-Instruct"):
        """
        Load trained model.
        
        Args:
            checkpoint_path: Path to trained checkpoint
            base_model: Base model name
        """
        print(f"Loading model from {checkpoint_path}...")
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        
        # Load base model
        self.model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        
        # Load LoRA weights
        self.model = PeftModel.from_pretrained(
            self.model,
            checkpoint_path
        )
        
        self.model.eval()
        print("✓ Model loaded!")
    
    def generate_action(self, observation: str, max_length: int = 256) -> dict:
        """
        Generate action from observation.
        
        Args:
            observation: Current observation
            max_length: Max tokens to generate
            
        Returns:
            Action dictionary
        """
        # Format prompt (adjust based on your training prompt format)
        prompt = f"""You are a security researcher testing a vulnerable system.

Current observation:
{observation}

What action do you take? Respond with a bash command or HTTP request.
Action:"""
        
        # Tokenize
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=max_length,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        # Decode
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract action from response (simple parsing)
        action_text = response.split("Action:")[-1].strip()
        
        # Parse into action format
        # This is simplified - you may need more sophisticated parsing
        if action_text.startswith("curl") or action_text.startswith("http"):
            return {
                "action_type": "http_request",
                "method": "GET",
                "url": action_text.split()[-1]
            }
        else:
            return {
                "action_type": "bash",
                "command": action_text
            }
    
    def test_episode(self, env_config: dict, max_steps: int = 30, verbose: bool = True):
        """
        Run one episode and return results.
        
        This replicates SkyRL's rollout collection loop WITHOUT policy updates.
        
        Args:
            env_config: Environment configuration
            max_steps: Maximum steps per episode
            verbose: Print detailed output
            
        Returns:
            Episode results
        """
        # Create environment (same as SkyRL)
        env = SecurityEnv(env_config)
        
        # Reset (same as SkyRL)
        obs, info = env.reset()
        
        if verbose:
            print(f"\n{'=' * 60}")
            print(f"Starting episode: {env_config['task_id']}")
            print(f"{'=' * 60}")
            print(f"Initial observation:\n{obs}\n")
        
        trajectory = []
        total_reward = 0.0
        
        for step in range(max_steps):
            if verbose:
                print(f"\n--- Step {step + 1}/{max_steps} ---")
            
            # Generate action (same as SkyRL rollout)
            action = self.generate_action(obs)
            if verbose:
                print(f"Action: {action}")
            
            # Execute (same as SkyRL rollout)
            next_obs, reward, done, truncated, info = env.step(action)
            if verbose:
                print(f"Reward: {reward}")
                print(f"Observation:\n{next_obs[:500]}...")  # Show first 500 chars
            
            # Store
            trajectory.append({
                "step": step + 1,
                "action": action,
                "observation": next_obs,
                "reward": reward,
                "done": done
            })
            
            total_reward += reward
            obs = next_obs
            
            if done:
                if verbose:
                    print(f"\n✓ Episode completed at step {step + 1}")
                break
        
        env.close()
        
        if verbose:
            print(f"\n{'=' * 60}")
            print(f"Episode Summary")
            print(f"{'=' * 60}")
            print(f"Total steps: {len(trajectory)}")
            print(f"Total reward: {total_reward:.2f}")
            print(f"Success: {'Yes' if done else 'No'}")
        
        return {
            "task_id": env_config["task_id"],
            "steps": len(trajectory),
            "total_reward": total_reward,
            "success": done,
            "trajectory": trajectory
        }


def batch_test(tester: ModelTester, tasks: list, max_steps: int = 30):
    """
    Test model on multiple tasks (replicates SkyRL's batch rollout).
    
    Args:
        tester: ModelTester instance
        tasks: List of task configs
        max_steps: Max steps per episode
        
    Returns:
        Batch results
    """
    print(f"\n{'=' * 60}")
    print(f"Batch Testing: {len(tasks)} tasks")
    print(f"{'=' * 60}")
    
    results = []
    success_count = 0
    total_steps = 0
    total_reward = 0.0
    
    for i, task_config in enumerate(tasks):
        print(f"\n[{i+1}/{len(tasks)}] Testing {task_config['task_id']}...")
        
        try:
            result = tester.test_episode(task_config, max_steps, verbose=False)
            results.append(result)
            
            if result['success']:
                success_count += 1
                print(f"  ✓ Success (steps: {result['steps']}, reward: {result['total_reward']:.2f})")
            else:
                print(f"  ✗ Failed (steps: {result['steps']}, reward: {result['total_reward']:.2f})")
            
            total_steps += result['steps']
            total_reward += result['total_reward']
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            results.append({
                "task_id": task_config['task_id'],
                "error": str(e),
                "success": False
            })
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"Batch Summary")
    print(f"{'=' * 60}")
    print(f"Total tasks: {len(tasks)}")
    print(f"Success: {success_count}/{len(tasks)} ({success_count/len(tasks)*100:.1f}%)")
    print(f"Average steps: {total_steps/len(tasks):.1f}")
    print(f"Average reward: {total_reward/len(tasks):.2f}")
    
    return {
        "tasks": results,
        "summary": {
            "total": len(tasks),
            "success": success_count,
            "failed": len(tasks) - success_count,
            "success_rate": success_count / len(tasks),
            "avg_steps": total_steps / len(tasks),
            "avg_reward": total_reward / len(tasks)
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Test trained VulRL model (SkyRL rollout without updates)")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to checkpoint")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-3B-Instruct", help="Base model")
    
    # Single task testing
    parser.add_argument("--task-type", type=str, default=None, help="Task type")
    parser.add_argument("--task-id", type=str, default=None, help="Task ID")
    
    # Batch testing
    parser.add_argument("--tasks-file", type=str, default=None, help="JSON file with list of tasks")
    parser.add_argument("--task-ids", type=str, default=None, help="Comma-separated task IDs")
    
    # Options
    parser.add_argument("--max-steps", type=int, default=30, help="Max steps per episode")
    parser.add_argument("--output", type=str, default="test_results.json", help="Output file")
    
    args = parser.parse_args()
    
    # Load model
    tester = ModelTester(args.checkpoint, args.base_model)
    
    # Determine test mode
    if args.tasks_file:
        # Batch mode: Load tasks from file
        import json
        with open(args.tasks_file) as f:
            tasks = json.load(f)
        results = batch_test(tester, tasks, args.max_steps)
        
    elif args.task_ids:
        # Batch mode: Multiple task IDs
        task_type = args.task_type or "vulhub"
        task_ids = args.task_ids.split(',')
        tasks = [
            {"task_type": task_type, "task_id": tid.strip(), "max_steps": args.max_steps}
            for tid in task_ids
        ]
        results = batch_test(tester, tasks, args.max_steps)
        
    else:
        # Single task mode
        if not args.task_type or not args.task_id:
            print("Error: Must specify --task-type and --task-id, or --tasks-file, or --task-ids")
            return 1
        
        env_config = {
            "task_type": args.task_type,
            "task_id": args.task_id,
            "max_steps": args.max_steps,
        }
        
        results = tester.test_episode(env_config, args.max_steps)
    
    # Save results
    import json
    result_file = Path(args.output)
    with open(result_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to: {result_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
