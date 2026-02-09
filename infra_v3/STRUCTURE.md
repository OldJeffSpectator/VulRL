# infra_v3 File Structure Status

## ✅ Created Files

### Core Package Structure
- [x] `pyproject.toml` - Package configuration
- [x] `README.md` - Project documentation
- [x] `src/vulrl/__init__.py` - Main package init

### Environment Module (`src/vulrl/env/`)
- [x] `__init__.py` - Environment module init
- [x] `base/__init__.py` - Base classes init
- [x] `base/env_types.py` - Standard data types
- [x] `base/env_adapter.py` - Base adapter interface
- [x] `docker_manager.py` - Docker operations
- [x] `adapters/__init__.py` - Adapters module init

### Adapters (Partially Complete)
- [x] `adapters/cvebench_adapter.py` - CVE-bench adapter (from infra_v2)
- [ ] `adapters/vulhub_adapter.py` - **TODO: Copy from infra/**
- [ ] `adapters/xbow_adapter.py` - **TODO: Copy from infra/**

### Environment Orchestration
- [ ] `security_env.py` - **TODO: Main training environment**
- [ ] `test_env.py` - **TODO: Testing environment**
- [ ] `env_registry.py` - **TODO: Adapter registry**

## 📋 TODO: Remaining Files

### Reward Module (`src/vulrl/reward/`)
```
reward/
├── __init__.py
├── base/
│   ├── __init__.py
│   └── reward_function.py
├── intermediate/
│   ├── __init__.py
│   └── step_judge.py
├── trajectory/
│   ├── __init__.py
│   └── trajectory_judge.py
├── visual/
│   ├── __init__.py
│   ├── llm1_judge.py
│   └── screenshot_generator.py
└── composite/
    ├── __init__.py
    └── reward_orchestrator.py
```

### Models Module (`src/vulrl/models/`)
```
models/
├── __init__.py
├── lora_model.py
├── model_provider.py (from infra/lora_model_provider.py)
└── _registry.py (from infra/_registry.py)
```

### Config Module (`src/vulrl/config/`)
```
config/
├── __init__.py
├── env_config.py (EnvConfigParser)
├── training_config.py
├── reward_config.py
└── command_builder.py
```

### Utilities Module (`src/vulrl/util/`)
```
util/
├── __init__.py
├── docker_utils.py
├── llm_utils.py
├── logging_utils.py
├── path_utils.py
├── prerequisite_checker.py
└── environment_setup.py
```

### Loop Control Module (`src/vulrl/loop_control/`)
```
loop_control/
├── __init__.py
├── trainer.py (from infra/main_training.py)
├── rollout_collector.py
├── batch_manager.py
├── policy_updater.py
└── checkpoint_manager.py
```

### Scripts (`scripts/`)
```
scripts/
├── rl_launcher.py (refactored from infra/train_launcher.py)
└── test_launcher.py (from infra/test_launcher.py)
```

### Tests (`tests/`)
```
tests/
├── __init__.py
├── test_adapters.py (from infra/test_unified_env.py)
├── test_rewards.py
├── test_training.py
└── test_integration.py
```

### Documentation (`docs/`)
```
docs/
├── UNIFIED_ENV_GUIDE.md (from infra/)
├── API_REFERENCE.md
└── EXAMPLES.md
```

## 🎯 Priority Order

1. **HIGH PRIORITY** (Core functionality):
   - [ ] Complete adapters (vulhub, xbow)
   - [ ] security_env.py
   - [ ] env_registry.py
   - [ ] Reward module (all files)
   - [ ] Models module (model_provider.py)

2. **MEDIUM PRIORITY** (Training):
   - [ ] loop_control/trainer.py
   - [ ] config/training_config.py
   - [ ] scripts/rl_launcher.py

3. **LOW PRIORITY** (Testing & Utilities):
   - [ ] test_env.py
   - [ ] scripts/test_launcher.py
   - [ ] util/* (helpers)
   - [ ] tests/*
   - [ ] docs/*

## 📝 Notes

- CVE-bench adapter is complete and uses infra_v2 version
- Docker manager consolidates image building logic
- All adapters will use shared DockerManager
- Package is installable with `pip install -e .`
