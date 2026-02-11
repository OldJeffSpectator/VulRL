# Testing VulRL Models Without Inspect AI

## Why Skip Inspect AI?

Inspect AI is rigid and constrained to CVE-bench's format. For flexible testing on **Xbow**, **CVE-bench**, **Vulhub**, or custom tasks, use `test_trained_model.py`.

---

## Understanding test_trained_model.py

### What It Does

**`test_trained_model.py` replicates SkyRL's rollout collection loop WITHOUT policy updates.**

```python
# SkyRL Training = Rollout + Update
for epoch in range(1000):
    trajectories = collect_rollouts()  # ← test_trained_model.py does THIS
    update_policy(trajectories)         # ← test_trained_model.py skips THIS

# test_trained_model.py
trajectory = collect_rollout()  # Same as SkyRL rollout
# No policy update!
return trajectory
```

### Key Insight

```
┌─────────────────────────────────────────────────────────────────┐
│  SkyRL Training                                                  │
├─────────────────────────────────────────────────────────────────┤
│  1. Load trainable policy                                       │
│  2. Create environment (SecurityEnv)                            │
│  3. Reset environment                                           │
│  4. Loop: generate action → step() → collect data              │
│  5. Compute loss                                                │
│  6. Backpropagation                                             │
│  7. Update policy                                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  test_trained_model.py (Testing)                                │
├─────────────────────────────────────────────────────────────────┤
│  1. Load frozen policy (no gradients)                           │
│  2. Create environment (SecurityEnv) ← SAME                     │
│  3. Reset environment ← SAME                                    │
│  4. Loop: generate action → step() → collect data ← SAME       │
│  5. ❌ Skip loss computation                                    │
│  6. ❌ Skip backpropagation                                     │
│  7. ❌ Skip policy update                                       │
│  8. ✅ Return results                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Usage Examples

### 1. Single Task Testing

```bash
cd infra_v3

# Test on Vulhub
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861

# Test on CVE-bench
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type cvebench \
    --task-id CVE-2024-2624

# Test on Xbow
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type xbow \
    --task-id xbow_challenge_1
```

### 2. Batch Testing (Multiple Tasks)

```bash
# Test on multiple CVE-bench tasks
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type cvebench \
    --task-ids "CVE-2024-2624,CVE-2024-2771,CVE-2024-3094"

# Test on multiple Xbow tasks
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type xbow \
    --task-ids "xbow_challenge_1,xbow_challenge_2,xbow_challenge_3"

# Test on multiple Vulhub tasks
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type vulhub \
    --task-ids "jenkins/CVE-2018-1000861,struts2/S2-045"
```

### 3. Batch Testing with Task Files

```bash
# Test on CVE-bench suite
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --tasks-file tasks_cvebench.json

# Test on Xbow suite
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --tasks-file tasks_xbow.json

# Test on Vulhub suite
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --tasks-file tasks_vulhub.json
```

---

## Task File Format

Create JSON files with task configurations:

```json
// tasks_custom.json
[
  {
    "task_type": "cvebench",
    "task_id": "CVE-2024-2624",
    "max_steps": 30,
    "metadata": {
      "description": "WordPress AI Engine SQL injection",
      "secret_file_path": "/etc/secret.txt"
    }
  },
  {
    "task_type": "xbow",
    "task_id": "xbow_challenge_1",
    "max_steps": 30,
    "metadata": {
      "description": "Web exploitation challenge"
    }
  }
]
```

---

## Results Format

### Single Task Output

```json
// test_results.json
{
  "task_id": "CVE-2024-2624",
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
    {
      "step": 2,
      "action": {"action_type": "http_request", "url": "http://target/admin"},
      "observation": "Admin panel...",
      "reward": 10.0,
      "done": false
    }
  ]
}
```

### Batch Testing Output

```json
// test_results.json
{
  "tasks": [
    {
      "task_id": "CVE-2024-2624",
      "steps": 18,
      "total_reward": 45.5,
      "success": true,
      "trajectory": [...]
    },
    {
      "task_id": "CVE-2024-2771",
      "steps": 25,
      "total_reward": 30.0,
      "success": false,
      "trajectory": [...]
    }
  ],
  "summary": {
    "total": 5,
    "success": 3,
    "failed": 2,
    "success_rate": 0.6,
    "avg_steps": 21.4,
    "avg_reward": 38.2
  }
}
```

---

## Advantages Over Inspect AI

| Feature | Inspect AI | test_trained_model.py |
|---------|-----------|----------------------|
| **Frameworks** | CVE-bench only | Xbow, CVE-bench, Vulhub, Custom |
| **Flexibility** | Rigid format | Full control |
| **Adapters** | Limited | ALL your adapters |
| **Rewards** | Fixed scoring | YOUR reward system |
| **Observations** | Fixed format | YOUR format |
| **Customization** | Hard | Easy (Python code) |
| **Debugging** | Black box | Full visibility |

---

## Example Workflow

### Step 1: Test on Different Benchmarks

```bash
# Test on CVE-bench
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --tasks-file tasks_cvebench.json \
    --output results_cvebench.json

# Test on Xbow
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --tasks-file tasks_xbow.json \
    --output results_xbow.json

# Test on Vulhub
python test_trained_model.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --tasks-file tasks_vulhub.json \
    --output results_vulhub.json
```

### Step 2: Analyze Results

```python
#!/usr/bin/env python3
"""Analyze test results across benchmarks."""

import json

# Load results
with open("results_cvebench.json") as f:
    cvebench = json.load(f)

with open("results_xbow.json") as f:
    xbow = json.load(f)

with open("results_vulhub.json") as f:
    vulhub = json.load(f)

# Compare
print("Benchmark Comparison:")
print(f"CVE-bench: {cvebench['summary']['success_rate']:.1%}")
print(f"Xbow: {xbow['summary']['success_rate']:.1%}")
print(f"Vulhub: {vulhub['summary']['success_rate']:.1%}")
```

### Step 3: Debug Failures

```bash
# Find failed tasks
python -c "
import json
with open('results_cvebench.json') as f:
    data = json.load(f)
    failed = [t for t in data['tasks'] if not t['success']]
    for t in failed:
        print(t['task_id'])
"

# Test interactively on failed task
python test_interactive.py \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --task-type cvebench \
    --task-id CVE-2024-2771
```

---

## Customization Examples

### 1. Custom Termination Condition

```python
# Edit test_trained_model.py
def test_episode(self, env_config, max_steps=30):
    # ...
    for step in range(max_steps):
        obs, reward, done, _, info = env.step(action)
        
        # Custom termination: Stop if reward > 50
        if reward > 50:
            done = True
            print("High reward achieved, stopping early!")
        
        if done:
            break
```

### 2. Custom Metrics

```python
# Add custom metrics to results
result = {
    "task_id": task_id,
    "success": done,
    "total_reward": total_reward,
    # Custom metrics
    "unique_commands": len(set(t['action']['command'] for t in trajectory)),
    "http_requests": sum(1 for t in trajectory if t['action']['action_type'] == 'http_request'),
    "bash_commands": sum(1 for t in trajectory if t['action']['action_type'] == 'bash'),
}
```

### 3. Custom Reward Weighting

```python
# Use different reward weights
env_config = {
    "task_type": "cvebench",
    "task_id": "CVE-2024-2624",
    "step_weight": 0.5,      # Emphasize step rewards
    "trajectory_weight": 0.3,
    "visual_weight": 0.2,
}
```

---

## Summary

**`test_trained_model.py` is SkyRL's rollout loop without policy updates.**

✅ **Use it when you need:**
- Flexible testing (not limited to CVE-bench)
- Test on Xbow, CVE-bench, Vulhub, or custom
- Full control over rewards, observations, termination
- Batch testing across multiple benchmarks
- Debugging and analysis

❌ **Don't use Inspect AI if:**
- You want to test on non-CVE-bench tasks
- You need custom reward functions
- You want full control over the testing process
- You need detailed trajectory analysis

**Think of it as**: "SkyRL inference mode" - same environment interaction, no training! 🎯
