# VulRL Parallel Execution Guide

## Overview

Both training and evaluation entry points now support parallel execution across multiple tasks/challenges. This enables:

1. **Training on multiple CVEs simultaneously** - Train separate models for different vulnerabilities in parallel
2. **Evaluating multiple challenges simultaneously** - Test a model against multiple CVE challenges in parallel

---

## Parallel Training

### Basic Usage

Train on multiple task IDs in parallel:

```bash
# Using comma-separated task IDs
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-ids "jenkins/CVE-2018-1000861,struts2/S2-045,weblogic/CVE-2017-10271" \
    --max-workers 3

# Using a file with task IDs (one per line)
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-ids-file tasks.txt \
    --max-workers 4
```

### Task IDs File Format

Create a `tasks.txt` file:
```
# Vulhub CVE tasks (comments start with #)
jenkins/CVE-2018-1000861
struts2/S2-045
weblogic/CVE-2017-10271
tomcat/CVE-2017-12615

# More tasks...
drupal/CVE-2018-7600
```

### Configuration

```bash
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-ids-file tasks.txt \
    --max-workers 4 \
    --batch-size 4 \
    --num-episodes 1000 \
    --num-gpus 4  # Will be divided among workers
```

### How It Works

1. **Process Pool**: Uses `ProcessPoolExecutor` for true parallel execution
2. **Resource Division**: 
   - GPUs are divided among workers (e.g., 4 GPUs / 4 workers = 1 GPU per worker)
   - Each worker gets 1 internal worker (num_workers=1)
3. **Separate Checkpoints**: Each task saves to its own checkpoint directory
   - Format: `checkpoint_dir/task_id_sanitized/`
   - Example: `~/checkpoints/vulrl_agent/jenkins_CVE-2018-1000861/`
4. **Summary Report**: Saves aggregated results to `parallel_training_summary.json`

### Output Structure

```
~/checkpoints/vulrl_agent/
├── jenkins_CVE-2018-1000861/
│   ├── global_step_100/
│   ├── global_step_200/
│   └── ...
├── struts2_S2-045/
│   ├── global_step_100/
│   └── ...
├── weblogic_CVE-2017-10271/
│   └── ...
└── parallel_training_summary.json
```

### Summary Report Format

```json
{
  "timestamp": "2026-02-10 18:30:00",
  "task_type": "vulhub",
  "max_workers": 4,
  "total_tasks": 4,
  "successful": 3,
  "failed": 1,
  "results": [
    {
      "task_id": "jenkins/CVE-2018-1000861",
      "return_code": 0,
      "elapsed_time": 1234.5,
      "checkpoint_dir": "~/checkpoints/vulrl_agent/jenkins_CVE-2018-1000861"
    },
    ...
  ]
}
```

---

## Parallel Evaluation

### Basic Usage

Evaluate multiple challenges in parallel:

```bash
# Evaluate multiple challenges
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_100 \
    --challenges CVE-2024-2624,CVE-2024-2771,CVE-2024-3094 \
    --parallel \
    --max-workers 3

# With specific variants
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_100 \
    --challenges CVE-2024-2624,CVE-2024-2771 \
    --variants zero_day \
    --parallel \
    --max-workers 2
```

### How It Works

1. **Thread Pool**: Uses `ThreadPoolExecutor` for I/O-bound Docker operations
2. **Docker Isolation**: Each challenge runs in its own Docker containers
3. **Sequential per Challenge**: Each challenge is started, evaluated, and stopped sequentially
4. **Aggregated Results**: All results saved to `eval_parallel_TIMESTAMP.json`

### Output Structure

```
infra_v3/eval_results/
├── eval_parallel_20260210_183000.json
├── eval_20260210_183001.json  # Individual challenge results
├── eval_20260210_183002.json
└── ...
```

### Aggregated Results Format

```json
{
  "timestamp": "20260210_183000",
  "checkpoint": "~/checkpoints/vulrl_agent/global_step_100",
  "mode": "parallel",
  "max_workers": 3,
  "results": [
    {
      "challenge": "CVE-2024-2624",
      "returncode": 0,
      "stdout": "...",
      "stderr": "..."
    },
    {
      "challenge": "CVE-2024-2771",
      "returncode": 0,
      "stdout": "...",
      "stderr": "..."
    },
    ...
  ]
}
```

---

## Performance Considerations

### Training

**Resource Requirements per Worker**:
- 1 GPU (if available)
- ~4-8 GB RAM
- Docker containers (target + attacker)
- Disk space for checkpoints

**Recommended Configurations**:

| GPUs | Workers | Config |
|------|---------|--------|
| 1    | 1       | Sequential training |
| 2    | 2       | `--max-workers 2 --num-gpus 2` |
| 4    | 4       | `--max-workers 4 --num-gpus 4` |
| 8    | 4       | `--max-workers 4 --num-gpus 8` (2 GPUs per worker) |

**Example for 4 GPUs**:
```bash
python -m vulrl.scripts.rl_launcher \
    --task-ids-file tasks.txt \
    --max-workers 4 \
    --num-gpus 4 \
    --batch-size 4
```

### Evaluation

**Resource Requirements per Worker**:
- Docker containers (target + attacker + agent)
- ~2-4 GB RAM per challenge
- Network bandwidth for API calls

**Recommended Configurations**:

| Challenges | Workers | Config |
|------------|---------|--------|
| 1-3        | 1       | Sequential evaluation |
| 4-8        | 2-4     | `--max-workers 2-4` |
| 9+         | 4-8     | `--max-workers 4-8` |

**Example for 10 challenges**:
```bash
python -m vulrl.scripts.test_launcher \
    --challenges CVE-2024-2624,CVE-2024-2771,... \
    --parallel \
    --max-workers 4
```

---

## Error Handling

### Training

- **Individual Task Failure**: Other tasks continue running
- **Summary Report**: Shows which tasks succeeded/failed
- **Exit Code**: Returns 0 if at least one task succeeded

### Evaluation

- **Individual Challenge Failure**: Other challenges continue running
- **Error Logging**: Errors captured in results JSON
- **Exit Code**: Returns 0 if at least one challenge succeeded

---

## Monitoring Progress

### Training

Monitor individual task logs:
```bash
# Each worker prints to stdout
[Worker] Starting task: jenkins/CVE-2018-1000861
[Worker] Completed task: jenkins/CVE-2018-1000861 (elapsed: 1234.5s)
```

Check summary:
```bash
cat ~/checkpoints/vulrl_agent/parallel_training_summary.json | jq '.results[] | {task_id, return_code, elapsed_time}'
```

### Evaluation

Monitor challenge progress:
```bash
# Each worker prints to stdout
[Worker] Starting challenge: CVE-2024-2624
[Worker] Completed challenge: CVE-2024-2624
```

Check aggregated results:
```bash
cat infra_v3/eval_results/eval_parallel_*.json | jq '.results[] | {challenge, returncode}'
```

---

## Advanced Usage

### Mixed Task Types (Not Recommended)

While possible, it's better to run separate parallel sessions for different task types:

```bash
# Separate runs for different types
python -m vulrl.scripts.rl_launcher --task-type vulhub --task-ids-file vulhub_tasks.txt
python -m vulrl.scripts.rl_launcher --task-type cvebench --task-ids-file cvebench_tasks.txt
```

### GPU Affinity

For fine-grained GPU control, use environment variables:

```bash
# Worker 1 on GPU 0
CUDA_VISIBLE_DEVICES=0 python -m vulrl.scripts.rl_launcher --task-id task1 &

# Worker 2 on GPU 1
CUDA_VISIBLE_DEVICES=1 python -m vulrl.scripts.rl_launcher --task-id task2 &
```

### Checkpoint Management

Clean up old checkpoints:
```bash
# Keep only latest 5 checkpoints per task
for task_dir in ~/checkpoints/vulrl_agent/*/; do
    ls -t "$task_dir" | tail -n +6 | xargs -I {} rm -rf "$task_dir/{}"
done
```

---

## Comparison: Sequential vs Parallel

### Training Time

**Sequential** (4 tasks, 1000 episodes each):
- Time: ~4 hours × 4 = 16 hours
- Resource usage: 1 GPU fully utilized

**Parallel** (4 tasks, 1000 episodes each, 4 workers):
- Time: ~4 hours (all run simultaneously)
- Resource usage: 4 GPUs partially utilized
- **Speedup: 4x**

### Evaluation Time

**Sequential** (10 challenges, 30 messages each):
- Time: ~5 minutes × 10 = 50 minutes
- Resource usage: 1 Docker environment at a time

**Parallel** (10 challenges, 30 messages each, 4 workers):
- Time: ~5 minutes × (10/4) = 12.5 minutes
- Resource usage: 4 Docker environments simultaneously
- **Speedup: 4x**

---

## Troubleshooting

### "Too many open files"

Increase file descriptor limit:
```bash
ulimit -n 4096
```

### "Out of memory"

Reduce max workers:
```bash
--max-workers 2  # Instead of 4
```

### "GPU out of memory"

Reduce batch size or workers:
```bash
--batch-size 2 --max-workers 2
```

### Docker conflicts

Ensure unique project names (handled automatically by adapters):
- Each task gets unique container names
- Network isolation via Docker Compose projects

---

## Best Practices

1. **Start Small**: Test with 2 workers before scaling to 4+
2. **Monitor Resources**: Watch GPU/RAM usage with `nvidia-smi` and `htop`
3. **Use Task Files**: Easier to manage than long command lines
4. **Checkpoint Often**: Set reasonable `--checkpoint-interval`
5. **Log Everything**: Redirect output to files for later analysis
6. **Clean Up**: Remove old checkpoints and Docker containers regularly

---

## Examples

### Complete Training Workflow

```bash
# 1. Create task list
cat > vulhub_tasks.txt <<EOF
jenkins/CVE-2018-1000861
struts2/S2-045
weblogic/CVE-2017-10271
drupal/CVE-2018-7600
EOF

# 2. Run parallel training
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-ids-file vulhub_tasks.txt \
    --max-workers 4 \
    --num-episodes 1000 \
    --batch-size 4 \
    --num-gpus 4 \
    --checkpoint-interval 100 \
    > training.log 2>&1 &

# 3. Monitor progress
tail -f training.log

# 4. Check summary
cat ~/checkpoints/vulrl_agent/parallel_training_summary.json
```

### Complete Evaluation Workflow

```bash
# 1. Find latest checkpoint
CHECKPOINT=$(ls -t ~/checkpoints/vulrl_agent/jenkins_CVE-2018-1000861/ | head -1)

# 2. Run parallel evaluation
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/jenkins_CVE-2018-1000861/$CHECKPOINT \
    --challenges CVE-2024-2624,CVE-2024-2771,CVE-2024-3094,CVE-2024-4321 \
    --variants zero_day,one_day \
    --parallel \
    --max-workers 4 \
    > evaluation.log 2>&1

# 3. Check results
cat infra_v3/eval_results/eval_parallel_*.json | jq '.results[] | {challenge, returncode}'
```
