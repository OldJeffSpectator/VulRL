# VulRL infra_v3 Entry Points

## ✅ Current Status: ENTRY POINTS CREATED!

The `infra_v3/` structure now has **working entry points**. You can run training and evaluation!

---

## Available Entry Points

### 1. Training Entry Point ✅ CREATED
**Location**: `src/vulrl/scripts/rl_launcher.py`

**Purpose**: Main entry point for RL training

**Usage**:
```bash
# From infra_v3/ directory (or project root)
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --num-episodes 1000 \
    --checkpoint-dir ~/checkpoints/vulrl_agent

# CVE-bench training
python -m vulrl.scripts.rl_launcher \
    --task-type cvebench \
    --task-id CVE-2024-2624 \
    --compose-path benchmark/cve-bench/challenges/CVE-2024-2624/docker-compose.yml

# Custom configuration
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --batch-size 8 \
    --num-episodes 2000 \
    --learning-rate 5e-6
```

**What it does**:
- Parse command-line arguments
- Check prerequisites (SkyRL, Vulhub/CVE-bench, Docker, datasets)
- Prepare environment (Docker images, PYTHONPATH, caching)
- Build configurations (training, environment, reward)
- Construct and execute SkyRL training command
- Save checkpoints at regular intervals

**Based on**: Adapted from `infra/train_launcher.py`

**Key Features**:
- Multi-environment support (Vulhub, CVE-bench, Xbow)
- Centralized Docker image management via `DockerManager`
- Configuration system integration
- GPU placement configuration
- Flexible command-line arguments
- Prerequisite validation

---

### 2. Evaluation Entry Point ✅ CREATED
**Location**: `src/vulrl/scripts/test_launcher.py`

**Purpose**: Main entry point for model evaluation with Inspect AI

**Usage**:
```bash
# From infra_v3/ directory (or project root)

# Evaluate latest checkpoint
python -m vulrl.scripts.test_launcher

# Evaluate specific checkpoint
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_100

# Test specific variants
python -m vulrl.scripts.test_launcher \
    --variants zero_day,one_day

# Test specific challenges
python -m vulrl.scripts.test_launcher \
    --challenges CVE-2024-2624,CVE-2024-2771

# Debug single challenge
python -m vulrl.scripts.test_launcher \
    --single-challenge CVE-2024-2624 \
    --variants zero_day
```

**What it does**:
- Check prerequisites (CVE-bench, Docker, checkpoints, Inspect AI)
- Setup CVE-bench environment
- Install dependencies (via uv or pip)
- Register LoRA model provider with Inspect AI
- Find latest checkpoint (if not specified)
- Build and execute `inspect eval` command
- Save and report evaluation results

**Based on**: Adapted from `infra/test_launcher.py`

**Key Features**:
- Auto-discovers latest checkpoint
- Supports both SkyRL format (`global_step_*`) and VulRL format (`checkpoint_episode_*`)
- CVE-bench dependency management
- Model provider integration from `vulrl.models`
- Results tracking and reporting (JSON format)
- Single challenge debugging mode
- Flexible variant and challenge filtering

---

## Current Module Structure

### ✅ What EXISTS (can be imported/used):

1. **Entry Points** (`scripts/`) ✅
   - `rl_launcher.py` - Training launcher
   - `test_launcher.py` - Evaluation launcher

2. **Environment Management** (`env_manage/`) ✅
   - Adapters for Vulhub, CVE-bench, Xbow
   - Docker management (`DockerManager`)
   - Environment registry (`EnvRegistry`)

3. **Reward System** (`reward/`) ✅
   - Abstract reward interfaces
   - Composite reward orchestrator
   - (Implementations are empty/TODO)

4. **Models** (`models/`) ✅
   - LoRA model provider for Inspect AI
   - Model registry

5. **Configuration** (`config/`) ✅
   - Environment, training, reward configs
   - Command builders

6. **Loop Control** (`loop_control/`) ✅
   - Trainer orchestrator
   - Rollout collector, batch manager
   - Policy updater, checkpoint manager
   - (Implementations are skeleton/TODO)

### ❌ What DOES NOT EXIST:

1. **Entry Point Scripts** (`scripts/`)
   - `rl_launcher.py` ✅ **CREATED**
   - `test_launcher.py` ✅ **CREATED**
   - `data_builder.py` ❌

2. **Utility Functions** (`util/`)
   - Docker utilities
   - LLM utilities
   - Logging, path utilities
   - Prerequisite checker

3. **Environment Facades** (`env_manage/`)
   - `security_env.py` (main training environment) ❌
   - `test_env.py` (evaluation environment) ❌

---

## Entry Point Features

### rl_launcher.py Features:
- ✅ Prerequisite checking (SkyRL, Vulhub, Docker, datasets)
- ✅ Environment preparation (attacker image, PYTHONPATH, UV cache)
- ✅ Configuration building (training, environment, reward configs)
- ✅ SkyRL command construction
- ✅ Multi-environment support (Vulhub, CVE-bench, Xbow)
- ✅ GPU placement configuration
- ✅ Command-line argument parsing
- ✅ Integration with `vulrl.config` module
- ✅ Integration with `DockerManager`

### test_launcher.py Features:
- ✅ Prerequisite checking (CVE-bench, Docker, checkpoints, Inspect AI)
- ✅ CVE-bench setup and dependency installation
- ✅ Model provider registration
- ✅ Automatic latest checkpoint discovery
- ✅ Variant and challenge filtering
- ✅ Results saving and reporting (JSON)
- ✅ Single challenge debugging mode
- ✅ Error handling and logging
- ✅ Integration with `vulrl.models` module
- ✅ Support for both checkpoint formats

---

## Comparison with Old Structure

### Old (`infra/`)
- ✅ `train_launcher.py` - Training entry point
- ✅ `test_launcher.py` - Evaluation entry point
- ✅ `main_training.py` - SkyRL training script
- ✅ `security_env.py` - Environment implementation

### New (`infra_v3/`)
- ✅ `scripts/rl_launcher.py` - **CREATED** ✨
- ✅ `scripts/test_launcher.py` - **CREATED** ✨
- ❌ `env_manage/security_env.py` - NOT CREATED
- ✅ `loop_control/trainer.py` - Skeleton only

**Key Improvements in infra_v3**:
1. **Modular design**: Configuration, environment, and models are separate modules
2. **Centralized Docker management**: No duplication of image building code
3. **Type safety**: Using dataclasses and type hints throughout
4. **Better error handling**: Comprehensive prerequisite checking
5. **Flexible configuration**: Command-line args map to config objects
6. **Cleaner imports**: Uses proper package structure instead of file copying

---

## Next Steps to Make infra_v3 Fully Functional

1. ~~**Create `scripts/rl_launcher.py`**~~ ✅ **COMPLETE**
2. ~~**Create `scripts/test_launcher.py`**~~ ✅ **COMPLETE**

3. **Create `env_manage/security_env.py`** (PRIORITY 1)
   - Adapt from `infra/security_env.py`
   - Use new adapter registry
   - Integrate with reward system

4. **Implement loop_control components** (PRIORITY 2)
   - Fill in TODOs in Trainer
   - Implement rollout collection
   - Implement policy updates

5. **Create utility modules** (PRIORITY 3)
   - LLM utilities
   - Logging utilities
   - Path resolution

6. **Testing** (PRIORITY 4)
   - Unit tests for adapters
   - Integration tests for entry points
   - End-to-end testing

---

## Installation

```bash
# From project root
cd infra_v3

# Install in development mode
pip install -e .

# Or install with training dependencies
pip install -e ".[train]"

# Or install with testing dependencies
pip install -e ".[test]"
```

---

## Running Entry Points

### Training:
```bash
# From project root or infra_v3/
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --num-episodes 1000
```

### Evaluation:
```bash
# From project root or infra_v3/
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_100
```

### Help:
```bash
python -m vulrl.scripts.rl_launcher --help
python -m vulrl.scripts.test_launcher --help
```

---

## Dependencies

**For Training** (`rl_launcher.py`):
- SkyRL (must be installed at `~/SkyRL/skyrl-train`)
- Vulhub (if using Vulhub environments, at `~/vulhub`)
- Docker
- Python packages: `docker`, `requests`, `Pillow`
- Dataset files in `dataset/` directory

**For Evaluation** (`test_launcher.py`):
- CVE-bench (auto-cloned if not present)
- Docker
- Inspect AI: `pip install inspect-ai`
- Python packages: `docker`, `transformers`, `peft`, `torch`
- Trained checkpoints

---

## Troubleshooting

### "SkyRL not found"
Install SkyRL:
```bash
git clone https://github.com/PKU-Alignment/SkyRL.git ~/SkyRL
```

### "Vulhub not found"
Install Vulhub:
```bash
git clone https://github.com/vulhub/vulhub.git ~/vulhub
```

### "Training data not found"
Prepare dataset:
```bash
python data_pre_process_scripts/vulhub_dataset_builder.py
```

### "Inspect AI not found"
Install Inspect AI:
```bash
pip install inspect-ai
```

### "ModuleNotFoundError: No module named 'vulrl'"
Install the package:
```bash
cd infra_v3
pip install -e .
```
