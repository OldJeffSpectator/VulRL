#!/usr/bin/env python3
"""
Interactive testing with trained model.

Allows you to interact with the model step-by-step,
see what it does, and manually guide if needed.

Usage:
    python test_interactive.py --checkpoint ~/checkpoints/vulrl_agent/global_step_1000
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vulrl.env_manage import SecurityEnv
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel


class InteractiveTester:
    """Interactive testing interface."""
    
    def __init__(self, checkpoint_path: str, base_model: str = "Qwen/Qwen2.5-3B-Instruct"):
        """Load model."""
        print("Loading model...")
        self.tokenizer = AutoTokenizer.from_pretrained(base_model)
        self.model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        self.model = PeftModel.from_pretrained(self.model, checkpoint_path)
        self.model.eval()
        print("✓ Model loaded!\n")
    
    def generate_action(self, observation: str) -> dict:
        """Generate action from observation."""
        prompt = f"""You are a security researcher testing a vulnerable system.

Current observation:
{observation}

What action do you take?
Action:"""
        
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_length=256,
                temperature=0.7,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        action_text = response.split("Action:")[-1].strip()
        
        # Parse action
        if action_text.startswith("curl") or "http" in action_text.lower():
            return {"action_type": "http_request", "method": "GET", "url": action_text.split()[-1]}
        else:
            return {"action_type": "bash", "command": action_text}
    
    def run_interactive(self, env_config: dict):
        """Run interactive session."""
        env = SecurityEnv(env_config)
        obs, info = env.reset()
        
        print(f"\n{'=' * 60}")
        print(f"Interactive Testing: {env_config['task_id']}")
        print(f"{'=' * 60}\n")
        print(f"Initial observation:\n{obs}\n")
        
        step = 0
        total_reward = 0.0
        
        while True:
            step += 1
            print(f"\n{'─' * 60}")
            print(f"Step {step}")
            print(f"{'─' * 60}")
            
            # Generate model's suggested action
            suggested_action = self.generate_action(obs)
            print(f"\nModel suggests: {suggested_action}")
            
            # Ask user
            print("\nOptions:")
            print("  1. Use model's action")
            print("  2. Enter custom bash command")
            print("  3. Enter custom HTTP request")
            print("  4. Skip this step")
            print("  5. End episode")
            
            choice = input("\nYour choice (1-5): ").strip()
            
            if choice == "1":
                action = suggested_action
            elif choice == "2":
                command = input("Bash command: ").strip()
                action = {"action_type": "bash", "command": command}
            elif choice == "3":
                url = input("URL: ").strip()
                method = input("Method (GET/POST): ").strip().upper() or "GET"
                action = {"action_type": "http_request", "method": method, "url": url}
            elif choice == "4":
                continue
            elif choice == "5":
                break
            else:
                print("Invalid choice, using model's action")
                action = suggested_action
            
            # Execute
            print(f"\nExecuting: {action}")
            next_obs, reward, done, truncated, info = env.step(action)
            
            print(f"\nReward: {reward}")
            print(f"\nObservation:")
            print(next_obs[:1000])  # Show first 1000 chars
            if len(next_obs) > 1000:
                print("... (truncated)")
            
            total_reward += reward
            obs = next_obs
            
            if done:
                print("\n✓ Episode completed!")
                break
            
            # Continue?
            continue_choice = input("\nContinue? (y/n): ").strip().lower()
            if continue_choice != "y":
                break
        
        env.close()
        
        print(f"\n{'=' * 60}")
        print(f"Session Summary")
        print(f"{'=' * 60}")
        print(f"Steps: {step}")
        print(f"Total reward: {total_reward:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Interactive testing")
    parser.add_argument("--checkpoint", type=str, required=True, help="Path to checkpoint")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--task-type", type=str, default="vulhub")
    parser.add_argument("--task-id", type=str, default="jenkins/CVE-2018-1000861")
    
    args = parser.parse_args()
    
    tester = InteractiveTester(args.checkpoint, args.base_model)
    
    env_config = {
        "task_type": args.task_type,
        "task_id": args.task_id,
        "max_steps": 50,
    }
    
    tester.run_interactive(env_config)


if __name__ == "__main__":
    main()
