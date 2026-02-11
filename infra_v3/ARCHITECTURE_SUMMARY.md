# VulRL Architecture Summary

**Combined Infrastructure: infra_v3 + SkyRL + Gymnasium**

---

## 🎯 Core Concept

VulRL is a **Reinforcement Learning framework for training LLM agents** to exploit vulnerabilities. It combines:

1. **infra_v3**: Custom vulnerability environment infrastructure (adapters, rewards, configs)
2. **SkyRL**: RL training framework (policy optimization, rollout collection, distributed training)
3. **Gymnasium**: Standard RL environment interface (reset/step API)

```
┌─────────────────────────────────────────────────────────────────┐
│                         VulRL System                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────┐   ┌──────────────┐   ┌──────────────┐     │
│  │   infra_v3     │   │    SkyRL     │   │  Gymnasium   │     │
│  │  (Env Infra)   │◄──┤  (Training)  │◄──┤  (Interface) │     │
│  └────────────────┘   └──────────────┘   └──────────────┘     │
│         │                     │                   │             │
│         │                     │                   │             │
│    Adapters              Optimization         reset()          │
│    Rewards               Rollouts             step()           │
│    Config                Checkpoints          spaces           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ Three-Layer Architecture

### Layer 1: Environment Infrastructure (infra_v3)

**Purpose**: Provides standardized interfaces to different vulnerability environments

**Key Components**:
- **Adapters**: Translate standard actions to environment-specific operations
- **Rewards**: Compute training signals from environment interactions
- **Config**: Manage environment and training parameters
- **Docker Management**: Handle container lifecycle

**Directories**:
```
infra_v3/src/vulrl/
├── env_manage/           # Environment adapters & orchestration
│   ├── adapters/         # Vulhub, CVE-bench, Xbow
│   ├── docker_manager.py # Shared Docker operations
│   └── env_registry.py   # Adapter factory
├── reward/               # Task-specific reward routing
├── config/               # Configuration management
└── scripts/              # Entry points (rl_launcher, test_launcher)
```

### Layer 2: Training Framework (SkyRL)

**Purpose**: Handles RL training mechanics

**Key Responsibilities**:
- Policy optimization (GRPO, PPO algorithms)
- Rollout collection from environments
- Advantage estimation (RLOO)
- Distributed training with Ray
- Checkpoint management
- LoRA fine-tuning integration

**Integration Point**:
```python
# SkyRL calls VulRL environments via Gymnasium interface
from vulrl.env_manage import SecurityEnv

env = SecurityEnv(config)
obs, info = env.reset()           # Gymnasium standard
obs, reward, done, truncated, info = env.step(action)  # Gymnasium standard
```

### Layer 3: Standard Interface (Gymnasium)

**Purpose**: Provides universal RL environment API

**Key Methods**:
```python
class SecurityEnv(gym.Env):  # Inherits Gymnasium interface
    def reset(self) -> Tuple[Observation, Info]:
        """Start new episode"""
        
    def step(self, action: Action) -> Tuple[Observation, Reward, Done, Truncated, Info]:
        """Execute action, return result"""
        
    @property
    def action_space(self):
        """Define valid actions"""
        
    @property
    def observation_space(self):
        """Define observation format"""
```

**Why Gymnasium?**
- Industry-standard RL interface
- Compatible with all RL libraries (SkyRL, Stable-Baselines3, RLlib)
- Modular: swap training frameworks without changing environments

---

## 🔄 Complete Training Flow

### Step 1: User Launches Training

```bash
python -m vulrl.scripts.rl_launcher \
    --task-type vulhub \
    --task-id jenkins/CVE-2018-1000861 \
    --model-path Qwen/Qwen2.5-3B-Instruct
```

### Step 2: Launcher Prepares Environment

```python
# infra_v3/scripts/rl_launcher.py
RLLauncher.run()
├── check_prerequisites()    # Docker, SkyRL, dependencies
├── prepare_environment()    # Build Docker images, set paths
├── build_configs()          # Training, Env, Reward configs
└── launch_training()        # Execute SkyRL command
```

### Step 3: SkyRL Training Loop

```python
# SkyRL (external framework)
SkyRL.train()
├── Initialize Ray cluster
├── Load SecurityEnv from infra_v3
│   └── SecurityEnv(config)
│       ├── EnvRegistry.create_adapter("vulhub")
│       │   └── VulhubAdapter(config)
│       └── CompositeReward(config)
│
├── Training Loop:
│   ├── Collect rollouts (call env.reset(), env.step())
│   ├── Compute advantages (RLOO)
│   ├── Update policy (GRPO)
│   └── Save checkpoint
│
└── Return trained model
```

### Step 4: Environment Step Execution

```python
# infra_v3/env_manage/security_env.py
SecurityEnv.step(action)
├── 1. Translate action via adapter
│   └── VulhubAdapter.step_backend(action)
│       ├── Execute bash command in Docker
│       ├── Capture output
│       └── Return StandardObservation
│
├── 2. Compute reward
│   └── CompositeReward.compute()
│       ├── RewardRouter → VulhubReward
│       ├── StepReward (immediate)
│       ├── TrajectoryReward (cumulative)
│       └── VisualReward (screenshot)
│
└── 3. Return (obs, reward, done, truncated, info)  # Gymnasium format
```

---

## 🎮 Complete Evaluation Flow

### Step 1: User Launches Evaluation

```bash
python -m vulrl.scripts.test_launcher \
    --checkpoint ~/checkpoints/vulrl_agent/global_step_1000 \
    --variants zero_day,one_day
```

### Step 2: Launcher Prepares CVE-bench

```python
# infra_v3/scripts/test_launcher.py
TestLauncher.run()
├── check_prerequisites()     # Docker, Inspect AI, checkpoints
├── setup_cvebench()          # Clone, install, copy model provider
├── find_latest_checkpoint()  # Auto-detect checkpoint
└── run_evaluation()          # Execute Inspect command
```

### Step 3: Inspect AI Evaluation

```python
# Inspect AI (external framework)
inspect eval cvebench.py --model=cve_lora/model
├── Load LoRAModelProvider from infra_v3
│   └── LoRAModelProvider(checkpoint_path)
│       ├── Load base model (Qwen2.5-3B)
│       ├── Load LoRA weights from checkpoint
│       └── Ready for inference
│
├── For each CVE challenge:
│   ├── Start Docker containers (target + attacker)
│   ├── Generate agent actions
│   │   └── LoRAModelProvider.generate(messages, tools)
│   │       ├── Convert to model format
│   │       ├── Run inference
│   │       └── Extract tool calls
│   ├── Execute actions in environment
│   └── Check success criteria
│
└── Save results to JSON
```

---

## 🧩 Key Components Explained

### 1. Environment Adapters (infra_v3 responsibility)

**Purpose**: Bridge between standard interface and specific environments

```python
class BaseEnvAdapter(ABC):
    @abstractmethod
    def setup(self) -> bool:
        """Start Docker containers, initialize environment"""
    
    @abstractmethod
    def reset_backend(self) -> StandardObservation:
        """Reset to initial state"""
    
    @abstractmethod
    def step_backend(self, action: StandardAction) -> Tuple[StandardObservation, StandardInfo]:
        """Execute action, return result"""
    
    @abstractmethod
    def teardown(self) -> bool:
        """Clean up containers"""
```

**Implementations**:
- **VulhubAdapter**: Manages Vulhub Docker Compose environments
- **CveBenchAdapter**: Manages CVE-bench Docker environments with scaling
- **XbowAdapter**: Manages Xbow benchmark environments

### 2. Reward System (infra_v3 responsibility)

**Architecture**: Universal router → Task-specific implementations

```python
# Universal entry point
RewardRouter.create_reward(config)
├── task_type="vulhub" → VulhubReward
│   └── Detects: shell access, file access, admin access
├── task_type="cvebench" → CveBenchReward
│   └── Tracks: 9 objective types (secret files, DB, admin, etc.)
└── task_type="xbow" → XbowReward
    └── Detects: flags, web compromise
```

**Multi-layer Structure**:
```python
CompositeReward
├── StepReward        # Immediate feedback per action
├── TrajectoryReward  # Cumulative strategy evaluation
└── VisualReward      # Screenshot-based assessment
```

### 3. SecurityEnv (infra_v3 responsibility)

**Purpose**: Main environment class that orchestrates everything

```python
class SecurityEnv(gym.Env):  # Implements Gymnasium interface
    def __init__(self, config):
        # Create adapter based on task_type
        self.adapter = EnvRegistry.create_adapter(config)
        
        # Create reward system
        self.reward = CompositeReward(config)
    
    def reset(self):
        # Gymnasium standard: (observation, info)
        obs = self.adapter.reset_backend()
        return obs, {}
    
    def step(self, action):
        # Gymnasium standard: (obs, reward, terminated, truncated, info)
        obs, info = self.adapter.step_backend(action)
        reward = self.reward.compute(obs, action, history)
        done = self._check_done(obs, info)
        return obs, reward, done, False, info
```

### 4. SkyRL Integration (SkyRL responsibility)

**What SkyRL Provides**:
- Policy network (LoRA-finetuned LLM)
- Rollout collection (parallel environments)
- Advantage estimation (RLOO, GAE)
- Policy optimization (GRPO, PPO)
- Distributed training (Ray)

**What SkyRL Expects from VulRL**:
- Gymnasium-compatible environment
- `reset()` returns `(observation, info)`
- `step(action)` returns `(observation, reward, terminated, truncated, info)`
- Text-based observations and actions

**Configuration Mapping**:
```python
# VulRL configs → SkyRL parameters
TrainingConfig → SkyRL trainer config
├── algorithm="grpo"
├── advantage_estimator="rloo"
├── train_batch_size=4
├── learning_rate=1e-6
└── checkpoint_dir="/path/to/checkpoints"

EnvConfig → Environment initialization
├── task_type="vulhub"
├── task_id="jenkins/CVE-2018-1000861"
└── max_steps=30
```

---

## 📊 Data Flow Diagrams

### Training Data Flow

```
User Command
    │
    ▼
rl_launcher.py (infra_v3)
    │
    ├─► Check prerequisites
    ├─► Build Docker images
    ├─► Prepare configs
    │
    ▼
SkyRL Training Framework
    │
    ├─► Initialize Ray cluster
    ├─► Load SecurityEnv (infra_v3)
    │       │
    │       ├─► Create Adapter (VulhubAdapter)
    │       │       │
    │       │       └─► Start Docker containers
    │       │
    │       └─► Create Reward (CompositeReward)
    │
    └─► Training Loop (1000s of iterations)
            │
            ├─► Rollout Collection
            │       │
            │       ├─► env.reset() → Adapter.reset_backend()
            │       │                    └─► Return initial observation
            │       │
            │       └─► env.step(action)
            │               │
            │               ├─► Adapter.step_backend(action)
            │               │       └─► Execute in Docker, return obs
            │               │
            │               ├─► Reward.compute()
            │               │       └─► Calculate reward signal
            │               │
            │               └─► Return (obs, reward, done, info)
            │
            ├─► Compute Advantages (RLOO)
            ├─► Update Policy (GRPO)
            └─► Save Checkpoint
                    │
                    └─► /checkpoints/global_step_XXX/
```

### Evaluation Data Flow

```
User Command
    │
    ▼
test_launcher.py (infra_v3)
    │
    ├─► Setup CVE-bench
    ├─► Find checkpoint
    ├─► Copy model provider
    │
    ▼
Inspect AI Framework
    │
    ├─► Load LoRAModelProvider (infra_v3)
    │       │
    │       ├─► Load base model (Qwen2.5-3B)
    │       └─► Load LoRA weights from checkpoint
    │
    └─► Evaluation Loop (for each CVE)
            │
            ├─► Start Docker containers
            │
            ├─► Agent Interaction
            │       │
            │       ├─► Generate action
            │       │       └─► LoRAModelProvider.generate()
            │       │               └─► LLM inference
            │       │
            │       ├─► Execute in Docker
            │       └─► Observe result
            │
            ├─► Check Success Criteria
            │       └─► CVE-bench scorer
            │
            └─► Save Results
                    └─► /eval_results/eval_XXX.json
```

---

## 🔗 Integration Points

### 1. infra_v3 → SkyRL

**Interface**: Gymnasium environment

```python
# SkyRL imports and uses SecurityEnv
from vulrl.env_manage import SecurityEnv

env = SecurityEnv(config={
    "task_type": "vulhub",
    "task_id": "jenkins/CVE-2018-1000861"
})

# SkyRL calls standard Gymnasium methods
obs, info = env.reset()
obs, reward, done, truncated, info = env.step(action)
```

**Requirements from SkyRL**:
- Environment must inherit from `gym.Env` or `BaseTextEnv`
- Must implement `reset()` and `step()`
- Observations must be text (strings)
- Actions can be text or tool calls

### 2. infra_v3 → Inspect AI

**Interface**: Model provider

```python
# Inspect AI imports model provider
from vulrl.models import cve_lora_provider

# Inspect AI registers provider
@model_registry.register("cve_lora")
def cve_lora_model():
    return cve_lora_provider(
        checkpoint_path="/checkpoints/global_step_1000"
    )

# Inspect AI calls provider
response = model.generate(
    input=[{"role": "user", "content": "..."}],
    tools=[bash_tool, http_tool],
    config={"temperature": 0.7}
)
```

**Requirements from Inspect AI**:
- Provider must implement `generate()` method
- Must handle tool calling format
- Must return `ModelOutput` with choices

### 3. Adapters → Docker

**Interface**: Docker Python SDK + subprocess

```python
# All adapters use Docker for environments
import docker
import subprocess

# Start containers
subprocess.run(["docker-compose", "up", "-d"])

# Interact with containers
client = docker.from_env()
container = client.containers.get("attacker")
result = container.exec_run(["bash", "-c", "whoami"])
```

---

## 🚀 Parallel Execution

### Training Parallelism (ProcessPoolExecutor)

```python
# Multiple task-ids trained simultaneously
rl_launcher.py --task-ids "vulhub/jenkins,vulhub/struts2,vulhub/weblogic" --max-workers 3

Process 1: vulhub/jenkins      → GPU 0 → checkpoint_dir/jenkins/
Process 2: vulhub/struts2      → GPU 1 → checkpoint_dir/struts2/
Process 3: vulhub/weblogic     → GPU 2 → checkpoint_dir/weblogic/
```

**Benefits**:
- Train multiple CVEs simultaneously
- Full CPU/GPU utilization
- Independent checkpoints per task

### Evaluation Parallelism (ThreadPoolExecutor)

```python
# Multiple challenges evaluated simultaneously
test_launcher.py --challenges "CVE-1,CVE-2,CVE-3" --parallel --max-workers 3

Thread 1: CVE-1 → Start Docker → Evaluate → Stop Docker
Thread 2: CVE-2 → Start Docker → Evaluate → Stop Docker
Thread 3: CVE-3 → Start Docker → Evaluate → Stop Docker
```

**Benefits**:
- Faster evaluation of multiple CVEs
- I/O-bound operations (Docker, inference)
- Aggregated results

---

## 📋 Key Features Summary

### 1. **Modular Architecture**
- Clear separation: infra_v3 (env), SkyRL (training), Gymnasium (interface)
- Each component has defined responsibilities
- Easy to extend or replace components

### 2. **Task-Specific Logic**
- **Adapters**: Different environments (Vulhub, CVE-bench, Xbow)
- **Rewards**: Different objectives per task type
- **Configs**: Flexible parameter management

### 3. **Standard Interfaces**
- **Gymnasium**: Universal RL environment API
- **Inspect AI**: Standard model evaluation
- **Docker**: Containerized vulnerability environments

### 4. **Scalability**
- **Parallel training**: Multiple tasks on multiple GPUs
- **Parallel evaluation**: Multiple challenges simultaneously
- **Distributed training**: Ray-based distributed RL (via SkyRL)

### 5. **Production-Ready**
- **Config-driven**: YAML-based configuration
- **Error handling**: Comprehensive prerequisite checks
- **Logging**: Detailed execution logs
- **Checkpointing**: Automatic model saving/loading

---

## ⚡ SkyRL Parallel Execution

### SkyRL's Built-in Parallelism

**Yes! SkyRL can run multiple environments in parallel using Ray.**

```python
# ============================================
# SkyRL's Parallel Training (Built-in)
# ============================================

# Configuration in your rl_launcher.py
config = {
    "rollouts_per_task": 4,  # Collect 4 trajectories per batch
    "train_batch_size": 16,   # 16 trajectories total
}

# SkyRL internally does:
with Ray.init():
    # Spawn multiple environment workers
    envs = [
        RemoteEnv.remote(SecurityEnv, config)  # Worker 1
        for _ in range(16)  # 16 parallel environments
    ]
    
    # Collect rollouts in parallel
    futures = [env.rollout.remote() for env in envs]
    trajectories = ray.get(futures)  # Wait for all to finish
    
    # Each worker independently runs:
    # - reset()
    # - step() x 30 times
    # - Returns trajectory
```

### Your Environment Must Be Thread-Safe

```python
class SecurityEnv(gym.Env):
    def __init__(self, config):
        # Each parallel worker gets its own instance
        # Make sure Docker container names are unique!
        self.container_name = f"attacker_{config['task_id']}_{os.getpid()}"
        self.adapter = VulhubAdapter(config)
    
    def reset(self):
        # This runs in parallel across workers
        # Each worker has its own containers
        return self.adapter.reset_backend()
    
    def step(self, action):
        # This runs in parallel across workers
        return self.adapter.step_backend(action)
```

### Parallelism Levels

```
┌─────────────────────────────────────────────────────────────────┐
│  Level 1: Multiple Tasks (YOUR rl_launcher.py)                  │
│  ─────────────────────────────────────────────────────────────  │
│  ProcessPoolExecutor: 4 workers                                 │
│  ├─ Worker 1: jenkins/CVE-2018-1000861                          │
│  ├─ Worker 2: struts2/S2-045                                    │
│  ├─ Worker 3: weblogic/CVE-2017-10271                           │
│  └─ Worker 4: drupal/CVE-2018-7600                              │
│                                                                  │
│     Each worker launches SkyRL ↓                                │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Level 2: Multiple Environments (SkyRL Built-in)                │
│  ─────────────────────────────────────────────────────────────  │
│  Ray Cluster: 16 environment workers                            │
│  ├─ Env 1: reset() → step() x30 → trajectory 1                 │
│  ├─ Env 2: reset() → step() x30 → trajectory 2                 │
│  ├─ ...                                                          │
│  └─ Env 16: reset() → step() x30 → trajectory 16               │
│                                                                  │
│     All trajectories collected ↓                                │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  Level 3: Batch Update (SkyRL Built-in)                         │
│  ─────────────────────────────────────────────────────────────  │
│  • Compute advantages from 16 trajectories                      │
│  • Update policy with GRPO                                      │
│  • Save checkpoint                                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎁 When Does SkyRL Need Rewards?

**SkyRL gets rewards through the `step()` return value!**

### The Gymnasium Contract

```python
def step(self, action) -> Tuple[Observation, Reward, Done, Truncated, Info]:
    """
    SkyRL calls this and expects 5 values back:
    
    1. observation: str - What the agent sees next
    2. reward: float - Training signal (THIS IS THE REWARD!)
    3. done: bool - Episode finished?
    4. truncated: bool - Episode cut off early?
    5. info: dict - Extra metadata
    """
    pass
```

### Your Implementation

```python
class SecurityEnv(gym.Env):
    def step(self, action: Dict) -> Tuple[str, float, bool, bool, Dict]:
        """
        SkyRL calls this EVERY step to get the reward.
        """
        # 1. Execute action
        next_obs, step_info = self.adapter.step_backend(action)
        
        # 2. Compute reward (THIS IS WHAT SKYRL NEEDS!)
        reward_result = self.reward.compute(
            observation=self.last_obs,
            action=action,
            next_observation=next_obs,
            step_info=step_info,
            episode_history=self.episode_history
        )
        
        # 3. Check termination
        done = self._check_done(next_obs, step_info)
        
        # 4. Return to SkyRL
        #    SkyRL stores this reward for policy updates
        return (
            next_obs,              # observation
            reward_result.reward,  # ← REWARD HERE! SkyRL needs this
            done,                  # terminated
            False,                 # truncated
            step_info             # info
        )
```

### How SkyRL Uses Rewards

```python
# ============================================
# Inside SkyRL (You don't write this)
# ============================================

# Episode trajectory collection
trajectory = []
obs, info = env.reset()

for t in range(30):  # 30 steps
    action = policy.generate_action(obs)
    
    # SkyRL calls YOUR step() to get reward
    next_obs, reward, done, truncated, info = env.step(action)
    #                  ↑
    #                  └─ SkyRL stores this reward!
    
    trajectory.append({
        "observation": obs,
        "action": action,
        "reward": reward,        # ← Stored for later
        "next_observation": next_obs
    })
    
    obs = next_obs
    if done:
        break

# After collecting multiple trajectories:
# SkyRL uses rewards to compute advantages
advantages = []
for traj in trajectories:
    # RLOO: Leave-one-out baseline
    baseline = mean([t.total_reward for t in other_trajectories])
    advantage = traj.total_reward - baseline
    advantages.append(advantage)

# Update policy using advantages
loss = compute_grpo_loss(trajectories, advantages)
loss.backward()
optimizer.step()
```

### Timeline of Reward Computation

```
Step 1: Agent takes action "whoami"
    │
    ▼
SecurityEnv.step({"action_type": "bash", "command": "whoami"})
    │
    ├─► Adapter executes: "root\n"
    │
    ├─► Reward computes: VulhubReward sees "root" → +5.0
    │
    └─► Returns: ("root\n", 5.0, False, False, {})
            │           │
            │           └─ SkyRL stores reward = 5.0
            │
Step 2: Agent takes action "cat /etc/passwd"
    │
    ▼
SecurityEnv.step({"action_type": "bash", "command": "cat /etc/passwd"})
    │
    ├─► Adapter executes: "root:x:0:0:..."
    │
    ├─► Reward computes: VulhubReward sees /etc/passwd → +10.0
    │
    └─► Returns: ("root:x:0:0:...", 10.0, True, False, {})
            │                        │      │
            │                        │      └─ Episode done
            │                        └─ SkyRL stores reward = 10.0
            │
    Total episode reward: 5.0 + 10.0 = 15.0
    SkyRL uses this to compute advantages and update policy
```

---

## 🔢 What Does a "Step" Refer To?

**A step = ONE single action execution**

### Step Definition

```python
# A STEP is:
# 1. Agent observes current state
# 2. Agent selects ONE action
# 3. Environment executes that ONE action
# 4. Environment returns result

# Example Episode with 3 Steps:

# ============================================
# Step 1
# ============================================
obs = "$ "  # Current observation
action = {"action_type": "bash", "command": "whoami"}  # ONE action
next_obs, reward, done, _, _ = env.step(action)
# Result: next_obs = "root\n", reward = 5.0, done = False

# ============================================
# Step 2
# ============================================
obs = "root\n"  # Current observation (from previous step)
action = {"action_type": "bash", "command": "ls"}  # ONE action
next_obs, reward, done, _, _ = env.step(action)
# Result: next_obs = "file1.txt\nfile2.txt\n", reward = 1.0, done = False

# ============================================
# Step 3
# ============================================
obs = "file1.txt\nfile2.txt\n"  # Current observation
action = {"action_type": "bash", "command": "cat file1.txt"}  # ONE action
next_obs, reward, done, _, _ = env.step(action)
# Result: next_obs = "FLAG{success}", reward = 20.0, done = True

# Episode finished after 3 steps
```

### Episode vs Step

```
┌─────────────────────────────────────────────────────────────────┐
│                         Episode                                  │
│  (One complete attempt from start to finish)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  reset()  → Initial observation: "$ "                           │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────────────────────────────────┐              │
│  │  Step 1                                       │              │
│  │  • Observe: "$ "                              │              │
│  │  • Action: whoami                             │              │
│  │  • Execute: ONE command                       │              │
│  │  • Result: "root\n", reward=5.0               │              │
│  └──────────────────────────────────────────────┘              │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────────────────────────────────┐              │
│  │  Step 2                                       │              │
│  │  • Observe: "root\n"                          │              │
│  │  • Action: ls /                               │              │
│  │  • Execute: ONE command                       │              │
│  │  • Result: "bin\netc\n...", reward=1.0        │              │
│  └──────────────────────────────────────────────┘              │
│     │                                                            │
│     ▼                                                            │
│  ┌──────────────────────────────────────────────┐              │
│  │  Step 3                                       │              │
│  │  • Observe: "bin\netc\n..."                   │              │
│  │  • Action: cat /etc/passwd                    │              │
│  │  • Execute: ONE command                       │              │
│  │  • Result: "root:x:0:...", reward=10.0        │              │
│  └──────────────────────────────────────────────┘              │
│     │                                                            │
│     ▼                                                            │
│  Done! Episode complete after 3 steps                           │
│  Total reward: 5.0 + 1.0 + 10.0 = 16.0                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Step Count Limits

```python
class SecurityEnv(gym.Env):
    def __init__(self, config):
        self.max_steps = config.get("max_steps", 30)  # Max 30 steps per episode
        self.current_step = 0
    
    def reset(self):
        self.current_step = 0  # Reset counter
        return initial_obs, {}
    
    def step(self, action):
        # Execute ONE action
        next_obs = self.adapter.step_backend(action)
        reward = self.reward.compute(...)
        
        self.current_step += 1  # Increment step counter
        
        # Episode ends if:
        # 1. Exploit successful (done=True from reward)
        # 2. Reached max steps (truncated)
        done = reward.done or self.current_step >= self.max_steps
        
        return next_obs, reward.reward, done, False, {}
```

### Configuration

```python
# In your training config
config = {
    "max_turns": 30,  # Max 30 steps per episode
    "epochs": 1000,   # Train for 1000 episodes
}

# Total steps = epochs × steps_per_episode
# = 1000 episodes × 30 steps/episode
# = 30,000 total step() calls
```

---

## 📊 Complete Flow with Steps and Rewards

```python
# ============================================
# SkyRL Training Loop (Built-in)
# ============================================

for episode in range(1000):  # 1000 episodes
    
    # Start new episode
    obs, info = env.reset()
    trajectory = []
    
    for step in range(30):  # Up to 30 steps per episode
        
        # SkyRL generates action
        action = policy.generate_action(obs)
        
        # SkyRL calls YOUR step() - ONE action
        next_obs, reward, done, truncated, info = env.step(action)
        #                  ↑
        #                  └─ Reward for THIS step
        
        # SkyRL stores step data
        trajectory.append({
            "step_number": step,
            "observation": obs,
            "action": action,
            "reward": reward,        # ← Step-level reward
            "next_observation": next_obs,
            "done": done
        })
        
        obs = next_obs
        
        if done:
            break  # Episode finished early
    
    # Episode complete - compute total reward
    total_reward = sum(t["reward"] for t in trajectory)
    
    # After collecting batch of episodes:
    if len(trajectories) >= batch_size:
        # SkyRL uses rewards to update policy
        update_policy(trajectories)


# ============================================
# YOUR SecurityEnv.step() Implementation
# ============================================

def step(self, action: Dict) -> Tuple[str, float, bool, bool, Dict]:
    """
    Called by SkyRL for EACH step (one action).
    
    Args:
        action: ONE action to execute (e.g., {"action_type": "bash", "command": "whoami"})
    
    Returns:
        Tuple of (observation, reward, done, truncated, info)
        - reward: Training signal for THIS step
    """
    
    # Execute ONE action
    next_obs, step_info = self.adapter.step_backend(action)
    
    # Compute reward for THIS step
    reward_result = self.reward.compute(
        observation=self.last_obs,
        action=action,  # ONE action
        next_observation=next_obs,
        step_info=step_info,
        episode_history=self.episode_history
    )
    
    # Check if episode should end
    done = (
        reward_result.done or  # Exploit successful
        self.current_step >= self.max_steps  # Reached limit
    )
    
    # Increment step counter
    self.current_step += 1
    
    # Update history
    self.episode_history.append({
        "step": self.current_step,
        "action": action,
        "observation": next_obs,
        "reward": reward_result.reward
    })
    
    # Return reward to SkyRL
    return next_obs, reward_result.reward, done, False, step_info
```

---

## 🎯 Summary Answers

| Question | Answer |
|----------|--------|
| **Can SkyRL execute in parallel?** | Yes! SkyRL uses Ray to run multiple environments simultaneously (e.g., 16 parallel workers) |
| **When does SkyRL need rewards?** | Every `step()` call - reward is the 2nd element in the return tuple |
| **How does SkyRL get rewards?** | `env.step(action)` returns `(obs, reward, done, trunc, info)` |
| **What is a step?** | ONE single action execution (e.g., one bash command, one HTTP request) |
| **What is an episode?** | Multiple steps from `reset()` to `done=True` (e.g., 30 steps) |
| **How many rewards per episode?** | One reward per step (e.g., 30 rewards for 30 steps) |
| **Who decides the action?** | SkyRL's policy (you don't control this) |
| **Who executes the action?** | Your adapter (`step_backend()`) |
| **Who computes the reward?** | Your reward system (`compute()`) |
| **Who uses the reward?** | SkyRL (for policy updates) |

---

## 🎓 Understanding the Stack

### If you're familiar with...

**Gymnasium**: infra_v3 is just another Gym environment, but specialized for security

**OpenAI Gym**: Same as Gymnasium (Gymnasium is the successor)

**Stable-Baselines3**: SkyRL plays the same role, but optimized for LLMs

**Docker Compose**: Adapters manage Docker environments automatically

**LangChain**: infra_v3 provides the environment, SkyRL does the training

**Inspect AI**: infra_v3 provides the model provider for evaluation

---

## 📝 Summary

| Component | Role | Responsibility |
|-----------|------|----------------|
| **infra_v3** | Environment Infrastructure | Adapters, Rewards, Configs, Docker |
| **SkyRL** | RL Training Framework | Optimization, Rollouts, Checkpoints |
| **Gymnasium** | Standard Interface | `reset()`, `step()`, spaces |
| **Inspect AI** | Evaluation Framework | Model loading, Task execution, Scoring |
| **Docker** | Isolation Layer | Vulnerability environments, Attacker containers |

**Key Insight**: 
- **infra_v3** provides the "what" (vulnerability environments, rewards, configs)
- **SkyRL** provides the "how" (training loop, optimization algorithms)
- **Gymnasium** provides the "interface" (standard RL API)
- Together, they enable **end-to-end RL training of LLM agents for security tasks**

---

## 🎯 Next Steps

To complete the system:
1. ✅ Adapters, rewards, configs created
2. ✅ Entry points (rl_launcher, test_launcher) created
3. ✅ Parallel execution implemented
4. ⚠️ **Need to create**: `SecurityEnv` (main training environment)
5. ⚠️ **Need to implement**: Real reward logic (currently returns 0.0)
6. ⚠️ **Need to test**: End-to-end training with SkyRL
