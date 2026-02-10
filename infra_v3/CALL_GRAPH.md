# VulRL infra_v3 Call Graph

## Entry Point: `rl_launcher.py` (Training)

```
rl_launcher.py::main()
├── parse_args()
│   └── argparse.ArgumentParser
│
├── RLLauncher.__init__(args)
│   ├── Path resolution (project_root, skyrl_dir, vulhub_dir, etc.)
│   └── Initialize config placeholders
│
├── RLLauncher.run()
│   │
│   ├── check_prerequisites()
│   │   ├── Check SkyRL directory exists
│   │   ├── Check Vulhub directory exists (if task_type == "vulhub")
│   │   ├── subprocess.run(["docker", "--version"])
│   │   ├── Check training data file exists
│   │   └── Check Python dependencies (import docker)
│   │
│   ├── prepare_environment()
│   │   ├── checkpoint_dir.mkdir()
│   │   ├── DockerManager.ensure_attacker_image()  ← env_manage/docker_manager.py
│   │   │   ├── docker.from_env()
│   │   │   ├── client.images.get()
│   │   │   └── [if not exists] client.images.build()
│   │   ├── Set environment variables (PYTHONPATH, RAY_*, UV_CACHE_DIR)
│   │   └── Print setup confirmation
│   │
│   ├── [if --task-ids or --task-ids-file] run_parallel_training()  ✨ NEW
│   │   ├── Load task IDs from file or command line
│   │   ├── Create task-specific configurations
│   │   │   └── For each task_id:
│   │   │       ├── Unique checkpoint_dir
│   │   │       └── Divided GPU allocation
│   │   ├── ProcessPoolExecutor(max_workers)
│   │   │   └── For each task in parallel:
│   │   │       ├── run_single_task(config)
│   │   │       │   ├── Create task-specific RLLauncher
│   │   │       │   ├── build_configs()
│   │   │       │   └── launch_training()
│   │   │       └── Return result dict
│   │   ├── Collect results from all workers
│   │   ├── Generate summary report
│   │   └── Save parallel_training_summary.json
│   │
│   ├── [else] build_configs()  ← Single task mode
│   │   ├── create_training_config()  ← config/training_config.py
│   │   │   └── TrainingConfig().__init__()
│   │   │       └── validate()
│   │   ├── create_env_config()  ← config/env_config.py
│   │   │   └── EnvConfig().__init__()
│   │   │       └── validate()
│   │   └── RewardConfig()  ← config/reward_config.py
│   │       └── validate()
│   │
│   └── [else] launch_training()  ← Single task mode
│       ├── build_skyrl_command()
│       │   └── Construct command list with SkyRL parameters
│       ├── os.chdir(skyrl_dir)
│       └── subprocess.run(command)
│           └── [Executes SkyRL training]
│               └── SkyRL will call cve_exploit_env.py (from infra/)
│                   └── [NOT YET PORTED TO infra_v3]
│
└── sys.exit(return_code)
```

---

## Entry Point: `test_launcher.py` (Evaluation)

```
test_launcher.py::main()
├── parse_args()
│   └── argparse.ArgumentParser
│
├── TestLauncher.__init__(args)
│   ├── Path resolution (project_root, cvebench_dir, checkpoint_dir, etc.)
│   └── Initialize paths
│
├── TestLauncher.run()
│   │
│   ├── check_prerequisites(skip_checkpoint_check)
│   │   ├── Check CVE-bench directory exists
│   │   ├── subprocess.run(["docker", "--version"])
│   │   ├── Check checkpoint directory exists
│   │   ├── Check model provider file exists
│   │   └── subprocess.run(["inspect", "--version"])
│   │
│   ├── setup_cvebench()
│   │   ├── [if not exists] git clone CVE-bench
│   │   ├── subprocess.run(["uv", "sync", "--dev"])
│   │   ├── shutil.copy(model_provider.py -> cvebench/)
│   │   └── Create _registry.py in CVE-bench
│   │
│   ├── find_latest_checkpoint()
│   │   ├── checkpoint_dir.glob("global_step_*")
│   │   ├── checkpoint_dir.glob("checkpoint_episode_*")
│   │   └── Sort by step number, return latest
│   │
│   ├── [if single_challenge mode] run_single_challenge()
│   │   ├── subprocess.run(["./run", "up", challenge])  # Start container
│   │   ├── run_evaluation(challenge)
│   │   └── subprocess.run(["./run", "down", challenge])  # Stop container
│   │
│   ├── [elif parallel mode] run_parallel_evaluations()  ✨ NEW
│   │   ├── ThreadPoolExecutor(max_workers)
│   │   │   └── For each challenge in parallel:
│   │   │       ├── run_single_eval(challenge)
│   │   │       │   ├── Print worker status
│   │   │       │   ├── run_single_challenge(challenge)
│   │   │       │   └── Return result dict
│   │   │       └── Collect result
│   │   ├── Generate summary report
│   │   │   ├── Count successful/failed
│   │   │   └── Print statistics
│   │   └── Save eval_parallel_TIMESTAMP.json
│   │
│   └── [else] run_evaluation()  ← Sequential mode
│       ├── Build inspect eval command
│       │   └── ["inspect", "eval", "cvebench.py", "--model=cve_lora", ...]
│       ├── subprocess.run(command, cwd=cvebench_dir)
│       │   └── Inspect AI executes
│       │       └── Calls cve_lora_provider()  ← models/model_provider.py
│       │           └── LoRAModelProvider.__init__()
│       │               ├── AutoTokenizer.from_pretrained(base_model)
│       │               ├── AutoModelForCausalLM.from_pretrained(base_model)
│       │               └── PeftModel.from_pretrained(model, checkpoint_path)
│       │
│       ├── Parse results
│       └── Save to eval_results/eval_TIMESTAMP.json
│
└── sys.exit(return_code)
```

---

## Detailed Module Call Graph

### Environment Management (`env_manage/`)

```
EnvRegistry.create_adapter(config)  ← env_manage/env_registry.py
├── Get adapter class from ADAPTERS dict
├── Prepare adapter_config dict
├── adapter_class(adapter_config)
│   └── [One of: VulhubAdapter, CveBenchAdapter, XbowAdapter]
│       └── BaseEnvAdapter.__init__(config)  ← env_manage/base/env_adapter.py
│
└── adapter.setup()
    │
    ├── [VulhubAdapter.setup()]  ← env_manage/adapters/vulhub_adapter.py
    │   ├── subprocess.run(docker-compose up)
    │   ├── _discover_containers()
    │   │   └── docker.from_env().containers.get()
    │   └── DockerManager.create_attacker_container()
    │       └── DockerManager.ensure_attacker_image()
    │
    ├── [CveBenchAdapter.setup()]  ← env_manage/adapters/cvebench_adapter.py
    │   ├── _build_cvebench_env()
    │   ├── subprocess.run(docker-compose up --scale agent=0)
    │   ├── _discover_containers_from_compose()
    │   │   └── docker.from_env().containers.get()
    │   └── DockerManager.create_attacker_container()
    │       └── DockerManager.ensure_attacker_image()
    │
    └── [XbowAdapter.setup()]  ← env_manage/adapters/xbow_adapter.py
        ├── subprocess.run(docker-compose up)
        ├── _discover_containers()
        │   └── docker.from_env().containers.get()
        └── DockerManager.create_attacker_container()
            └── DockerManager.ensure_attacker_image()
```

### Docker Management

```
DockerManager.ensure_attacker_image()  ← env_manage/docker_manager.py
├── docker.from_env()
├── client.images.get(image_name)
│   └── [if ImageNotFound]
│       ├── tempfile.TemporaryDirectory()
│       ├── Write ATTACKER_DOCKERFILE
│       └── client.images.build()
└── Return True/False

DockerManager.create_attacker_container()
├── ensure_attacker_image()
├── docker.from_env()
├── [Remove existing container if exists]
│   └── client.containers.get(name).remove(force=True)
└── client.containers.run()
    └── Wait for container to be running
```

### Reward System

```
CompositeReward.compute()  ← reward/composite_reward.py
├── StepReward.compute()  ← reward/step_reward.py
│   └── [TODO: LLM-based step evaluation]
├── TrajectoryReward.compute()  ← reward/trajectory_reward.py
│   └── [TODO: LLM-based trajectory evaluation]
└── VisualReward.compute()  ← reward/visual_reward.py
    └── [TODO: Screenshot capture + vision LLM]
```

### Model Provider

```
cve_lora_provider()  ← models/model_registry.py
└── LoRAModelProvider(model_name, base_model, checkpoint_path)  ← models/model_provider.py
    ├── AutoTokenizer.from_pretrained(base_model)
    ├── AutoModelForCausalLM.from_pretrained(base_model)
    └── PeftModel.from_pretrained(model, checkpoint_path)

LoRAModelProvider.generate(input, tools, tool_choice, config)
├── convert_messages_to_qwen_format(input)
├── convert_tools_to_qwen_format(tools)
├── tokenizer.apply_chat_template()
├── model.generate()
├── tokenizer.decode()
├── _extract_tool_calls()
└── Return ModelOutput
```

### Configuration System

```
create_training_config()  ← config/training_config.py
└── TrainingConfig().__init__()
    └── validate()

create_env_config()  ← config/env_config.py
└── EnvConfig().__init__()
    └── validate()

create_reward_config()  ← config/reward_config.py
└── RewardConfig().__init__()
    └── validate()
```

---

## Loop Control (Skeleton - Not Yet Implemented)

```
Trainer.train()  ← loop_control/trainer.py
├── RolloutCollector.collect()  ← loop_control/rollout_collector.py
│   └── [TODO: Parallel environment execution]
├── BatchManager.create_batches(rollouts)  ← loop_control/batch_manager.py
│   └── [TODO: Batch assembly and preprocessing]
├── PolicyUpdater.update(batches)  ← loop_control/policy_updater.py
│   └── [TODO: Policy optimization (GRPO/PPO)]
└── CheckpointManager.save(episode, metrics)  ← loop_control/checkpoint_manager.py
    └── [Saves checkpoint to disk]
```

---

## Missing Components (Not Yet Created)

### 1. SecurityEnv (Main Training Environment)
```
SecurityEnv.__init__()  ← env_manage/security_env.py [NOT CREATED]
├── EnvRegistry.create_adapter(config)
└── CompositeReward(reward_config)

SecurityEnv.reset()
├── adapter.reset_backend()
└── Return initial observation

SecurityEnv.step(action)
├── adapter.step_backend(action)
├── reward.compute(obs, action, next_obs, info, history)
└── Return (observation, reward, done, info)
```

### 2. TestEnv (Evaluation Environment)
```
TestEnv.__init__()  ← env_manage/test_env.py [NOT CREATED]
├── EnvRegistry.create_adapter(config)
└── [Simpler than SecurityEnv, no reward computation]

TestEnv.reset()
├── adapter.reset_backend()
└── Return initial observation

TestEnv.step(action)
├── adapter.step_backend(action)
└── Return (observation, 0.0, done, info)
```

---

## Data Flow Summary

### Training Flow:
```
rl_launcher.py
  → SkyRL main_training.py (not in infra_v3)
    → SecurityEnv (NOT YET CREATED)
      → EnvRegistry → Adapter (Vulhub/CVEBench/Xbow)
        → Docker containers
      → CompositeReward
        → StepReward/TrajectoryReward/VisualReward
  → Checkpoints saved
```

### Evaluation Flow:
```
test_launcher.py
  → Inspect AI
    → LoRAModelProvider
      → Load base model + LoRA weights
      → Generate responses
    → CVE-bench tasks
      → Docker containers
      → Scoring functions
  → Results saved to JSON
```

---

## Critical Dependencies

1. **rl_launcher.py** depends on:
   - SkyRL (external, not in infra_v3)
   - `SecurityEnv` (NOT YET CREATED)
   - `DockerManager` ✅
   - Config classes ✅
   - Adapters ✅

2. **test_launcher.py** depends on:
   - Inspect AI (external)
   - CVE-bench (external, auto-cloned)
   - `LoRAModelProvider` ✅
   - Checkpoints (from training)

3. **Both** depend on:
   - Docker
   - Environment adapters ✅
   - Docker manager ✅

---

## Execution Order

### For Training:
1. User runs `rl_launcher.py`
2. Prerequisites checked
3. Environment prepared (Docker image, directories)
4. Configs built
5. SkyRL command constructed
6. SkyRL executed → calls `SecurityEnv` → calls adapters → training loop

### For Evaluation:
1. User runs `test_launcher.py`
2. Prerequisites checked
3. CVE-bench setup
4. Checkpoint discovered
5. Inspect command constructed
6. Inspect executed → calls `LoRAModelProvider` → loads model → evaluates → scores

---

## Parallel Execution Flow ✨ NEW

### Parallel Training Flow:
```
rl_launcher.py --task-ids-file tasks.txt --max-workers 4
  → Load task IDs from file
  → Create ProcessPoolExecutor(4 workers)
    → Worker 1: Train on jenkins/CVE-2018-1000861
    │   → Separate checkpoint dir
    │   → 1 GPU allocated
    │   → Independent SkyRL process
    │
    → Worker 2: Train on struts2/S2-045
    │   → Separate checkpoint dir
    │   → 1 GPU allocated
    │   → Independent SkyRL process
    │
    → Worker 3: Train on weblogic/CVE-2017-10271
    │   → Separate checkpoint dir
    │   → 1 GPU allocated
    │   → Independent SkyRL process
    │
    → Worker 4: Train on drupal/CVE-2018-7600
        → Separate checkpoint dir
        → 1 GPU allocated
        → Independent SkyRL process
  → Collect all results
  → Save parallel_training_summary.json
```

### Parallel Evaluation Flow:
```
test_launcher.py --challenges CVE-1,CVE-2,CVE-3 --parallel --max-workers 3
  → Create ThreadPoolExecutor(3 workers)
    → Worker 1: Evaluate CVE-1
    │   → Start Docker containers
    │   → Run Inspect AI evaluation
    │   → Stop Docker containers
    │   → Return result
    │
    → Worker 2: Evaluate CVE-2
    │   → Start Docker containers
    │   → Run Inspect AI evaluation
    │   → Stop Docker containers
    │   → Return result
    │
    → Worker 3: Evaluate CVE-3
        → Start Docker containers
        → Run Inspect AI evaluation
        → Stop Docker containers
        → Return result
  → Collect all results
  → Save eval_parallel_TIMESTAMP.json
```

---

## Next Implementation Priority

To make training work end-to-end:
1. **Create `SecurityEnv`** (adapts `infra/security_env.py`)
2. **Implement reward functions** (step, trajectory, visual)
3. **Test with single environment**
4. ~~**Add parallel execution**~~ ✅ **COMPLETE** (multiple task-ids)
