# VulRL infra_v3 Quick Start Guide

## ✅ Entry Points Are Ready!

Your `infra_v3/` now has working entry points for training and evaluation.

---

## Prerequisites

Before running, ensure you have:

1. **SkyRL** installed at `~/SkyRL/skyrl-train`
   ```bash
   git clone https://github.com/PKU-Alignment/SkyRL.git ~/SkyRL
   ```

2. **Vulhub** (for Vulhub environments) at `~/vulhub`
   ```bash
   git clone https://github.com/vulhub/vulhub.git ~/vulhub
   ```

3. **Docker** running
   ```bash
   docker --version
   ```

4. **Training data** in `dataset/cve_vulhub/train.parquet`
   ```bash
   python data_pre_process_scripts/vulhub_dataset_builder.py
   ```

5. **Python dependencies**
   ```bash
   cd infra_v3
   pip install -e ".[train,test]"
   ```

---

## Quick Start: Training

```bash
# Basic training on Vulhub
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --num-episodes 1000

# With custom parameters
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --batch-size 8 \
    --num-episodes 2000 \
    --learning-rate 5e-6 \
    --checkpoint-dir ./my_checkpoints

# See all options
python -m vulrl.scripts.rl_launcher --help
```

---

## Quick Start: Evaluation

```bash
# Evaluate latest checkpoint
python -m vulrl.scripts.test_launcher

# Evaluate specific checkpoint
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_100

# Test specific CVEs
python -m vulrl.scripts.test_launcher \
    --challenges CVE-2024-2624,CVE-2024-2771 \
    --variants zero_day

# Debug single challenge
python -m vulrl.scripts.test_launcher \
    --single-challenge CVE-2024-2624

# See all options
python -m vulrl.scripts.test_launcher --help
```

---

## File Locations

### Entry Points (✅ Ready to use)
- **Training**: `infra_v3/src/vulrl/scripts/rl_launcher.py`
- **Evaluation**: `infra_v3/src/vulrl/scripts/test_launcher.py`

### Supporting Modules (✅ Created)
- **Env Adapters**: `infra_v3/src/vulrl/env_manage/adapters/`
- **Docker Manager**: `infra_v3/src/vulrl/env_manage/docker_manager.py`
- **Model Provider**: `infra_v3/src/vulrl/models/model_provider.py`
- **Config System**: `infra_v3/src/vulrl/config/`
- **Reward System**: `infra_v3/src/vulrl/reward/` (abstract only)

### Checkpoints
- Default location: `~/checkpoints/vulrl_agent/`
- SkyRL format: `global_step_*`
- VulRL format: `checkpoint_episode_*`

### Results
- Evaluation results: `infra_v3/eval_results/eval_TIMESTAMP.json`

---

## Common Workflows

### 1. Train on Vulhub CVE
```bash
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --num-episodes 1000
```

### 2. Train on CVE-bench
```bash
python -m vulrl.scripts.rl_launcher \
    --task-type cvebench \
    --task-id CVE-2024-2624 \
    --compose-path benchmark/cve-bench/challenges/CVE-2024-2624/docker-compose.yml \
    --eval-config-path benchmark/cve-bench/challenges/CVE-2024-2624/eval.yml
```

### 3. Evaluate Latest Model
```bash
python -m vulrl.scripts.test_launcher
```

### 4. Evaluate Specific Checkpoint
```bash
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_500
```

### 5. Debug Single CVE Challenge
```bash
python -m vulrl.scripts.test_launcher \
    --single-challenge CVE-2024-2624 \
    --variants zero_day
```

---

## Key Differences from Old `infra/`

| Feature | Old (`infra/`) | New (`infra_v3/`) |
|---------|---------------|-------------------|
| Entry point | `train_launcher.py` | `vulrl.scripts.rl_launcher` |
| Evaluation | `test_launcher.py` | `vulrl.scripts.test_launcher` |
| Docker management | Duplicated in multiple files | Centralized in `DockerManager` |
| Configuration | Hardcoded in launcher | Separate `config/` module |
| Imports | File copying workaround | Proper Python package |
| Type safety | Limited | Dataclasses + type hints |

---

## Next Development Steps

While entry points are ready, some components still need implementation:

1. **Environment Facade** (`env_manage/security_env.py`)
   - Adapt from `infra/security_env.py`
   - Will be used by SkyRL main_training.py

2. **Reward Implementation** (`reward/`)
   - Currently abstract/empty
   - Need to implement step, trajectory, visual rewards

3. **Loop Control** (`loop_control/`)
   - Currently skeleton
   - Need to implement rollout collection, policy updates

4. **Utility Modules** (`util/`)
   - LLM utilities
   - Logging configuration
   - Path resolution

---

## Troubleshooting

### ModuleNotFoundError: No module named 'vulrl'
```bash
cd infra_v3
pip install -e .
```

### SkyRL not found
```bash
git clone https://github.com/PKU-Alignment/SkyRL.git ~/SkyRL
```

### Docker permission denied
```bash
sudo usermod -aG docker $USER
# Then logout and login
```

### Training data not found
```bash
python data_pre_process_scripts/vulhub_dataset_builder.py
```

---

## Documentation

- **Complete entry point docs**: `infra_v3/ENTRY_POINTS.md`
- **Progress tracking**: `infra_v3/PROGRESS.md`
- **Architecture**: `infra_v3/STRUCTURE.md`
- **Package setup**: `infra_v3/pyproject.toml`

---

## Support

For issues or questions:
1. Check `ENTRY_POINTS.md` for detailed usage
2. Check `PROGRESS.md` for implementation status
3. Run with `--help` to see all options
4. Check prerequisite checks in the launcher output
