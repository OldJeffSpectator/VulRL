# VulRL - Unified Security RL Training Framework

A modular, extensible framework for training reinforcement learning agents on security vulnerability exploitation tasks.

## Features

- **Unified Environment Interface**: Support for Vulhub, CVE-bench, and Xbow
- **Modular Architecture**: Clean separation of concerns (env, reward, training)
- **Composite Reward System**: 3-layer reward (intermediate, trajectory, visual)
- **Docker-based Isolation**: Safe execution in containerized environments
- **Extensible**: Easy to add new data sources and reward functions

## Installation

```bash
# Development install (recommended)
cd infra_v3
pip install -e .

# With training dependencies
pip install -e ".[train]"

# With testing dependencies
pip install -e ".[test]"
```

## Quick Start

### Training
```bash
python scripts/rl_launcher.py
```

### Testing
```bash
python scripts/test_launcher.py --checkpoint ~/checkpoints/cve_agent/global_step_100
```

## Structure

```
infra_v3/
├── src/vulrl/          # Main package
│   ├── env/            # Environment management
│   ├── reward/         # Reward functions
│   ├── models/         # Model providers
│   ├── config/         # Configuration
│   └── util/           # Utilities
├── scripts/            # Entry points
├── tests/              # Unit tests
└── docs/               # Documentation
```

## Documentation

See [docs/](docs/) for detailed documentation.
