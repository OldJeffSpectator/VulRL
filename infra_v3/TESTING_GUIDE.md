# VulRL Model Testing Guide

Complete guide for testing your trained models.

---

## Overview

After training with SkyRL, you have multiple ways to test your model:

```
1. Inspect AI (test_launcher.py)     ← Automated benchmark testing
2. Direct Testing (test_trained_model.py) ← Custom scenarios
3. Interactive Testing (test_interactive.py) ← Manual exploration
```

---

## Method 1: Inspect AI (RECOMMENDED for Benchmarking)

### What is Inspect AI?

Inspect AI is an evaluation framework that:
- Loads your trained model
- Runs it on CVE-bench challenges
- Measures success rate automatically
- Produces detailed metrics

### Usage

```bash
# Basic: Test with latest checkpoint
cd infra_v3
python -m vulrl.scripts.test_launcher

# Specific checkpoint
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000

# Specific CVE variants
python -m vulrl.scripts.test_launcher \
    --variants zero_day,one_day

# Specific challenges
python -m vulrl.scripts.test_launcher \
    --challenges CVE-2024-2624,CVE-2024-2771

# Parallel testing (faster!)
python -m vulrl.scripts.test_launcher \
    --challenges CVE-2024-2624,CVE-2024-2771,CVE-2024-3094 \
    --parallel \
    --max-workers 3
```

### Results

Results are saved to `eval_results/eval_TIMESTAMP.json`:

```json
{
  "timestamp": "2026-02-10T12:34:56",
  "checkpoint": "global_step_1000",
  "challenges": [
    {
      "challenge": "CVE-2024-2624",
      "status": "success",
      "score": 1.0,
      "steps": 15,
      "time": 45.2,
      "actions": [...]
    }
  ],
  "summary": {
    "total": 10,
    "success": 7,
    "failed": 3,
    "success_rate": 0.7
  }
}
```

### When to Use

✅ Use Inspect AI when you need:
- Automated evaluation on standard benchmarks
- Success rate metrics
- Comparison between checkpoints
- Publication-ready results

---

## Method 2: Direct Testing (Custom Scenarios)

### What is Direct Testing?

Run your model on custom tasks, not limited to CVE-bench.

### Usage

```bash
cd infra_v3

# Test on Vulhub task
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --max-steps 30

# Test on Xbow task
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type xbow \
    --task-id xbow_challenge_1

# Test on CVE-bench task (without Inspect AI)
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type cvebench \
    --task-id CVE-2024-2624
```

### Results

Results saved to `test_results.json`:

```json
{
  "task_id": "jenkins/CVE-2018-1000861",
  "steps": 18,
  "total_reward": 45.5,
  "success": true,
  "trajectory": [
    {
      "step": 1,
      "action": {"action_type": "bash", "command": "whoami"},
      "observation": "root\n",
      "reward": 5.0,
      "done": false
    },
    ...
  ]
}
```

### When to Use

✅ Use Direct Testing when you need:
- Test on custom/new tasks
- Debug specific scenarios
- Get detailed trajectory information
- Test outside CVE-bench

---

## Method 3: Interactive Testing

### What is Interactive Testing?

Step through the episode manually, see what the model suggests, and optionally override actions.

### Usage

```bash
cd infra_v3

python test_interactive.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861
```

### Interactive Session

```
============================================================
Interactive Testing: jenkins/CVE-2018-1000861
============================================================

Initial observation:
$ 

────────────────────────────────────────────────────────────
Step 1
────────────────────────────────────────────────────────────

Model suggests: {'action_type': 'bash', 'command': 'whoami'}

Options:
  1. Use model's action
  2. Enter custom bash command
  3. Enter custom HTTP request
  4. Skip this step
  5. End episode

Your choice (1-5): 1

Executing: {'action_type': 'bash', 'command': 'whoami'}

Reward: 5.0

Observation:
root

Continue? (y/n): y

────────────────────────────────────────────────────────────
Step 2
────────────────────────────────────────────────────────────

Model suggests: {'action_type': 'bash', 'command': 'cat /etc/passwd'}

Options:
  1. Use model's action
  2. Enter custom bash command
  3. Enter custom HTTP request
  4. Skip this step
  5. End episode

Your choice (1-5): 2
Bash command: ls -la /

Executing: {'action_type': 'bash', 'command': 'ls -la /'}

...
```

### When to Use

✅ Use Interactive Testing when you need:
- Understand model's decision-making
- Debug specific behaviors
- Explore what model learned
- Manually guide difficult episodes

---

## Comparison: Which Method to Use?

| Method | Best For | Output | Speed | Control |
|--------|----------|--------|-------|---------|
| **Inspect AI** | Benchmarking, metrics | Success rates, scores | Fast (parallel) | None (automated) |
| **Direct Testing** | Custom tasks, debugging | Detailed trajectories | Medium | Some (config) |
| **Interactive** | Understanding behavior | Step-by-step analysis | Slow (manual) | Full (manual) |

---

## Testing Workflow

### 1. During Training

```bash
# Monitor training progress
# Check checkpoints every 100 steps

# Quick test on 1-2 challenges
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_500 \
    --challenges CVE-2024-2624
```

### 2. After Training

```bash
# Full evaluation on CVE-bench
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_2000 \
    --variants zero_day,one_day \
    --parallel \
    --max-workers 5

# Test on custom tasks
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_2000 \
    --task-type vulhub \
    --task-id struts2/S2-045
```

### 3. Debugging Failures

```bash
# If model fails on specific task, use interactive mode
python test_interactive.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_2000 \
    --task-type vulhub \
    --task-id struts2/S2-045

# Step through manually to see where it goes wrong
```

---

## Advanced: Batch Testing

### Test Multiple Checkpoints

```python
#!/usr/bin/env python3
"""Test multiple checkpoints and compare."""

import subprocess
from pathlib import Path
import json

checkpoints = [
    "global_step_500",
    "global_step_1000",
    "global_step_1500",
    "global_step_2000",
]

results = {}

for ckpt in checkpoints:
    print(f"\n{'=' * 60}")
    print(f"Testing {ckpt}")
    print(f"{'=' * 60}")
    
    result = subprocess.run([
        "python", "-m", "vulrl.scripts.test_launcher",
        "--checkpoint", f"~/checkpoints/vulrl_agent/{ckpt}",
        "--challenges", "CVE-2024-2624,CVE-2024-2771"
    ], capture_output=True, text=True)
    
    # Parse results
    # ...
    results[ckpt] = {"success_rate": 0.5}  # Example

# Compare
print("\n" + "=" * 60)
print("Comparison")
print("=" * 60)
for ckpt, res in results.items():
    print(f"{ckpt}: {res['success_rate']:.2%}")
```

### Test on Custom Dataset

```python
#!/usr/bin/env python3
"""Test on custom list of tasks."""

import json
from test_trained_model import ModelTester

# Load custom task list
with open("custom_tasks.json") as f:
    tasks = json.load(f)

# Test each
tester = ModelTester("~/checkpoints/vulrl_agent/global_step_2000")
results = []

for task in tasks:
    print(f"\nTesting {task['task_id']}...")
    result = tester.test_episode(task, max_steps=30)
    results.append(result)
    print(f"Success: {result['success']}")

# Save results
with open("custom_test_results.json", "w") as f:
    json.dump(results, f, indent=2)

# Summary
success_count = sum(1 for r in results if r['success'])
print(f"\nSuccess rate: {success_count}/{len(results)} = {success_count/len(results):.2%}")
```

---

## Metrics Explained

### Success Rate

```
Success Rate = (Successful Episodes) / (Total Episodes)

Example: 7/10 = 70%
```

### Average Steps

```
Average Steps = Total Steps / Total Episodes

Lower is better (more efficient)
```

### Average Reward

```
Average Reward = Total Reward / Total Episodes

Higher is better
```

### Completion Time

```
Average Time = Total Time / Total Episodes

Lower is better (faster exploitation)
```

---

## Troubleshooting

### Model Always Fails

```bash
# Check if model is loaded correctly
python test_interactive.py --checkpoint <path>

# Try earlier checkpoint
python -m vulrl.scripts.test_launcher --checkpoint global_step_100

# Test on easier task
python test_trained_model.py --task-id <easy_task>
```

### Model Takes Too Long

```bash
# Reduce max_steps
python test_trained_model.py --max-steps 10

# Check if model is stuck in loop
python test_interactive.py  # Observe step-by-step
```

### Out of Memory

```bash
# Use smaller batch size in parallel testing
python -m vulrl.scripts.test_launcher --max-workers 1

# Use CPU instead of GPU
CUDA_VISIBLE_DEVICES="" python test_trained_model.py
```

---

## Next Steps

1. **After testing**, analyze results to identify:
   - Which CVEs the model handles well
   - Which CVEs need more training
   - Common failure patterns

2. **Iterate training**:
   - Add more training data for failed tasks
   - Adjust reward functions
   - Continue training from checkpoint

3. **Deploy**:
   - Once satisfied with results, deploy model
   - See `DEPLOYMENT_GUIDE.md` (if available)

---

## Summary

| Testing Method | Command | Use Case |
|---------------|---------|----------|
| **Inspect AI** | `python -m vulrl.scripts.test_launcher` | Benchmark evaluation |
| **Direct** | `python test_trained_model.py` | Custom tasks |
| **Interactive** | `python test_interactive.py` | Debugging & exploration |

**Recommended workflow**: Start with Inspect AI for overall metrics, use Direct for custom tasks, and Interactive for debugging failures.
