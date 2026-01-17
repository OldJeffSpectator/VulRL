# CVE Exploit RL Training System

基于 SkyRL 框架和 LoRA 微调的漏洞利用强化学习训练系统。该系统使用 Vulhub 漏洞环境作为训练场景，通过 LLM-as-Judge（GPT-4o）进行视觉评估，训练模型学习自动化漏洞利用。

## 目录结构

```
dataset/
├── README.md                    # 本文档
├── vulhub_dataset_builder.py    # 数据集构建器
├── cve_exploit_env.py           # RL 环境定义
├── main_training.py             # SkyRL 训练入口点
├── train_launcher.py            # 训练启动器（主要配置文件）
├── test_launcher.py             # CVE-bench 测试启动器
├── lora_model_provider.py       # Inspect AI 模型提供者
├── _registry.py                 # 模型注册入口
├── pyproject.toml               # 项目配置
├── cve_vulhub/                  # 生成的训练数据
│   └── train.parquet            # 训练数据集
└── eval_results/                # 测试结果目录
```

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Training Pipeline                       │
├─────────────────────────────────────────────────────────────┤
│  train_launcher.py  →  main_training.py  →  SkyRL Framework │
│         ↓                    ↓                    ↓          │
│   配置参数生成           Ray 初始化          GRPO 训练循环    │
│         ↓                    ↓                    ↓          │
│   启动训练命令           环境注册            LoRA 微调        │
├─────────────────────────────────────────────────────────────┤
│                      Environment                             │
├─────────────────────────────────────────────────────────────┤
│  cve_exploit_env.py                                          │
│  ├── CVEExploitEnv      # 主环境类                           │
│  ├── LLM1Judge          # GPT-4o 视觉判断器                  │
│  └── ScreenshotGenerator # 证据截图生成                      │
├─────────────────────────────────────────────────────────────┤
│                      Docker Environment                      │
├─────────────────────────────────────────────────────────────┤
│  Vulhub Container ←→ Attacker Container                      │
│  (目标漏洞环境)         (执行攻击命令)                        │
└─────────────────────────────────────────────────────────────┘
```

## 前置要求

### 1. 系统要求
- Linux 服务器（推荐 Ubuntu 20.04+）
- NVIDIA GPU（至少 48GB 显存，推荐 96GB）
- Docker 和 Docker Compose
- Python 3.10+

### 2. 软件依赖

```bash
# 安装 uv（Python 包管理器）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆 SkyRL
cd ~
git clone https://github.com/NovaSkyAI/SkyRL.git

# 克隆 Vulhub
git clone https://github.com/vulhub/vulhub.git

# 安装 Tesseract OCR（用于图片文字提取）
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# 安装 Python OCR 依赖
pip install pytesseract Pillow
```

### 3. 环境变量

```bash
# OpenAI API Key（用于 LLM-as-Judge）也可以换成其他的api(修改对应的依赖和代码使用就行）
export OPENAI_API_KEY="your-openai-api-key"
```

## 快速开始

### Step 1: 构建数据集

数据集构建器 v2.0 会自动：
1. 解析 README 文件（提取代码块、图片）
2. 使用 OCR 提取图片中的文字
3. 使用 GPT-4o 分析漏洞信息
4. **生成完整可执行的 Python PoC 脚本**
5. 使用 LLM 验证 PoC 正确性（最多 3 次重试）

```bash
# 处理所有 CVE（需要 OpenAI API Key）
python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ./cve_vulhub

# 测试模式：只处理前 10 个 CVE
python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ./cve_vulhub --limit 10

# 使用更便宜的模型
python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ./cve_vulhub --model gpt-4o-mini
```

**参数说明：**
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--vulhub_path` | `~/vulhub` | Vulhub 仓库路径 |
| `--output_dir` | `~/data/cve_vulhub` | 输出数据集路径 |
| `--limit` | `None` | 限制处理的 CVE 数量（用于测试） |
| `--model` | `gpt-4o` | 使用的 OpenAI 模型 |
| `--api_key` | `$OPENAI_API_KEY` | OpenAI API Key |

### Step 2: 启动训练（目前用的是我的WANDB的key)

```bash
export WANDB_API_KEY="0182a73971e45b6b05b10d7a8c3e77ea26a9a596"
python train_launcher.py
```

训练启动器会自动：
1. 检查前置条件（SkyRL、Vulhub、Docker、数据集）
2. 构建 attacker Docker 镜像
3. 复制必要文件到 SkyRL 目录
4. 启动训练

## 配置参数详解

### 训练配置 (`train_launcher.py`)

所有训练参数都在 `train_launcher.py` 的 `build_config()` 和 `build_command()` 方法中定义。

#### 基础配置 (`build_config` 方法，第 143-162 行)

```python
def build_config(self) -> dict:
    return {
        "model_path": "Qwen/Qwen2.5-3B-Instruct",  # 基础模型
        "train_data": str(self.data_dir / "train.parquet"),  # 训练数据
        "algorithm": "grpo",           # 算法：GRPO
        "advantage_estimator": "rloo", # 优势估计：RLOO
        "train_batch_size": 4,         # 批次大小
        "rollouts_per_task": 4,        # 每个任务的 rollout 数
        "learning_rate": 1e-6,         # 学习率
        "epochs": 20,                  # 训练轮数
        "checkpoint_dir": str(self.checkpoint_dir),  # checkpoint 保存路径
    }
```

#### 详细参数配置 (`build_command` 方法，第 164-234 行)

| 类别 | 参数 | 默认值 | 说明 | 代码位置 |
|------|------|--------|------|----------|
| **数据** | `data.train_data` | `./cve_vulhub/train.parquet` | 训练数据路径 | 第 176 行 |
| | `data.val_data` | `null` | 验证数据（已禁用） | 第 177 行 |
| **算法** | `trainer.algorithm.name` | `grpo` | 算法名称 | 第 180 行 |
| | `trainer.algorithm.advantage_estimator` | `rloo` | 优势估计方法 | 第 181 行 |
| | `trainer.algorithm.kl_coef` | `0.0` | KL 散度系数 | 第 182 行 |
| | `trainer.algorithm.entropy_coef` | `0.0` | 熵系数 | 第 183 行 |
| | `trainer.algorithm.normalize_advantage` | `False` | 是否归一化优势 | 第 184 行 |
| **批次** | `trainer.train_batch_size` | `4` | 训练批次大小 | 第 187 行 |
| | `trainer.policy_mini_batch_size` | `4` | 策略更新小批次 | 第 188 行 |
| | `trainer.rollout_batch_size` | `4` | rollout 批次大小 | 第 189 行 |
| | `trainer.rollouts_per_task` | `4` | 每任务 rollout 数 | 第 190 行 |
| **训练** | `trainer.learning_rate` | `1e-6` | 学习率 | 第 191 行 |
| | `trainer.epochs` | `20` | 训练轮数 | 第 192 行 |
| | `trainer.eval_interval` | `-1` | 评估间隔（-1 禁用） | 第 193 行 |
| | `trainer.save_interval` | `10` | checkpoint 保存间隔 | 第 197 行 |
| **模型** | `trainer.policy.model.path` | `Qwen/Qwen2.5-3B-Instruct` | 基础模型路径 | 第 200 行 |
| **LoRA** | `trainer.policy.model.lora.rank` | `16` | LoRA 秩 | 第 203 行 |
| | `trainer.policy.model.lora.alpha` | `32` | LoRA alpha | 第 204 行 |
| | `trainer.policy.model.lora.dropout` | `0.05` | LoRA dropout | 第 205 行 |
| | `trainer.policy.model.lora.target_modules` | `all-linear` | 目标模块 | 第 206 行 |
| **GPU** | `trainer.placement.colocate_all` | `true` | 所有组件共置 | 第 209 行 |
| | `trainer.placement.policy_num_gpus_per_node` | `1` | 策略 GPU 数 | 第 211 行 |
| | `generator.gpu_memory_utilization` | `0.5` | GPU 内存利用率 | 第 223 行 |
| | `generator.engine_init_kwargs.max_model_len` | `4096` | 最大模型长度 | 第 224 行 |
| **其他** | `dispatcher.strategy` | `async_pipeline` | 调度策略 | 第 227 行 |
| | `logging.backend` | `local` | 日志后端 | 第 230 行 |

### 环境配置 (`cve_exploit_env.py`)

#### EnvConfig 类（第 40-63 行）

| 参数 | 类型 | 说明 |
|------|------|------|
| `cve_id` | `str` | CVE 编号 |
| `vulhub_path` | `str` | Vulhub 相对路径 |
| `service_port` | `int` | 服务端口 |
| `ground_truth_images` | `List[str]` | Ground Truth 图片路径 |
| `max_steps` | `int` | 最大步数（默认 30） |
| `timeout` | `int` | 命令超时（默认 30 秒） |

#### LLM1Judge 配置（第 103-114 行）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `api_key` | `$OPENAI_API_KEY` | OpenAI API Key |
| `model` | `gpt-4o` | 评估模型 |
| `api_endpoint` | `https://api.openai.com/v1/chat/completions` | API 端点 |
| `cache_dir` | `/tmp/llm1_cache` | 缓存目录 |

### Ray 配置 (`main_training.py`)

| 参数 | 默认值 | 说明 | 代码位置 |
|------|--------|------|----------|
| `num_gpus` | `1` | GPU 数量 | 第 51 行 |
| `_temp_dir` | `~/ray_tmp` | Ray 临时目录 | 第 53 行 |
| `CUDA_VISIBLE_DEVICES` | `0` | 可见 GPU | 第 20 行 |

## 路径配置

### 默认路径 (`train_launcher.py` 第 20-26 行)

| 路径 | 默认值 | 说明 |
|------|--------|------|
| `skyrl_dir` | `~/SkyRL/skyrl-train` | SkyRL 安装目录 |
| `data_dir` | `./cve_vulhub` | 训练数据目录 |
| `checkpoint_dir` | `~/checkpoints/cve_agent` | Checkpoint 保存目录 |
| `vulhub_dir` | `~/vulhub` | Vulhub 仓库目录 |

## 可用工具

环境提供两个工具供 Agent 使用：

### 1. bash
在攻击者容器内执行任意 bash 命令。

```json
{
  "tool": "bash",
  "arguments": {
    "command": "nmap -p 1-1000 target"
  }
}
```

### 2. http_request
发送 HTTP 请求。

```json
{
  "tool": "http_request",
  "arguments": {
    "method": "POST",
    "url": "http://target/api",
    "headers": {"Content-Type": "application/json"},
    "json": {"key": "value"}
  }
}
```

## 奖励机制

- **二值奖励**：成功 = 1.0，失败 = 0.0
- **单次判断**：仅在 episode 结束时调用 LLM1 判断
- **视觉比较**：将 Agent 的操作截图与 Ground Truth 图片对比

## 常见问题

### 1. 磁盘空间不足

```
OSError: [Errno 28] No space left on device
```

**解决方案**：清理 Ray 临时目录
```bash
ray stop
rm -rf ~/ray_tmp
rm -rf /tmp/ray*
```

### 2. GPU 内存不足

**解决方案**：调整 `gpu_memory_utilization`
```python
# train_launcher.py 第 223 行
"++generator.gpu_memory_utilization=0.3",  # 降低到 30%
```

### 3. Checkpoint 加载失败

如果修改了 LoRA 配置后无法加载旧 checkpoint：
```bash
rm -rf ~/checkpoints/cve_agent
```

### 4. Docker Compose 版本问题

系统会自动检测 `docker compose` 或 `docker-compose` 命令。

## 监控训练

训练过程会自动上传到 Weights & Biases：
- 项目：`skyrl`
- 查看地址：https://wandb.ai/your-username/skyrl

## 自定义训练

### 修改基础模型

```python
# train_launcher.py build_config() 方法
"model_path": "Qwen/Qwen2.5-7B-Instruct",  # 使用更大的模型
```

### 调整 LoRA 参数

```python
# train_launcher.py build_command() 方法
"++trainer.policy.model.lora.rank=32",     # 增加 LoRA 秩
"++trainer.policy.model.lora.alpha=64",    # 相应增加 alpha
```

### 增加训练步数

```python
# train_launcher.py build_config() 方法
"epochs": 50,  # 增加到 50 轮
```

### 使用不同的 LLM 判断器

```python
# cve_exploit_env.py LLM1Judge.__init__()
self.model = "gpt-4o-mini"  # 使用更便宜的模型
```

## 文件说明

### vulhub_dataset_builder.py (v2.0)

从 Vulhub 仓库解析 CVE 信息，**生成可执行的 Python PoC 脚本**，并输出训练数据集。

**核心特性**：
1. 全面理解 README（文本 + 代码块 + 图片 OCR）
2. 生成完整可执行的 Python PoC 脚本
3. LLM 逻辑验证确保 PoC 正确性（最多 3 次重试）
4. 以 PoC 为中心的数据集结构

**处理流程**：
```
VulhubScanner → ContentParser → PoCGenerator → PoCValidator → DatasetWriter
     ↓              ↓               ↓              ↓
  扫描CVE目录    解析README      生成Python脚本   LLM验证
                提取代码块                      (最多3次重试)
                OCR处理图片
```

**主要类**：
| 类名 | 功能 |
|------|------|
| `VulhubScanner` | 扫描 Vulhub 仓库中的有效 CVE 目录 |
| `ContentParser` | 解析 README（代码块、图片、链接） |
| `OCRProcessor` | 使用 pytesseract 提取图片文字 |
| `PoCGenerator` | 使用 GPT-4o 生成 Python PoC 脚本 |
| `PoCValidator` | 使用 LLM 验证 PoC 正确性 |
| `DatasetBuilder` | 编排整个流程，输出 parquet 数据集 |

**数据类**：
| 类名 | 功能 |
|------|------|
| `CodeBlock` | README 中的代码块（语言、内容、上下文） |
| `ImageContent` | 图片 OCR 内容和描述 |
| `ReadmeAnalysis` | README 综合分析结果 |
| `GeneratedPoC` | 生成的 PoC 脚本及元数据 |
| `VulhubEntry` | 完整的 Vulhub 条目（核心数据结构） |

**输出格式（train.parquet，共 24 个字段）**：
| 字段 | 类型 | 说明 |
|------|------|------|
| `cve_id` | str | CVE 编号 |
| `vulhub_path` | str | Vulhub 相对路径 |
| `vulnerability_type` | str | 漏洞类型（rce/sqli/ssti 等） |
| `service_name` | str | 服务名称 |
| `service_version` | str | 受影响版本 |
| `vulnerability_description` | str | 漏洞描述 |
| `primary_port` | int | 主要攻击端口 |
| `exposed_ports` | str | JSON 暴露端口列表 |
| `primary_service` | str | 主要服务名称 |
| **`poc_script`** | str | **生成的完整 Python PoC（核心字段）** |
| `poc_dependencies` | str | JSON 依赖列表 |
| `poc_execution_cmd` | str | PoC 执行命令 |
| `exploitation_steps` | str | JSON 利用步骤 |
| `success_indicators` | str | JSON 成功标志 |
| `readme_content` | str | README 原文 |
| `code_blocks` | str | JSON 代码块列表 |
| `image_ocr_content` | str | JSON OCR 结果 |
| `original_poc_files` | str | JSON 原有 PoC 文件 |
| `reference_links` | str | JSON 参考链接列表 |
| `validation_status` | str | validated/needs_review/failed |
| `validation_score` | float | 验证分数 (0.0-1.0) |
| `validation_notes` | str | 验证说明 |
| `generation_model` | str | 使用的 LLM 模型 |
| `generation_timestamp` | str | 生成时间 (ISO 格式) |

### cve_exploit_env.py

RL 环境实现，继承 SkyRL 的 `BaseTextEnv`。

**主要类**：
- `CVEExploitEnv`：主环境类
- `LLM1Judge`：LLM 视觉判断器
- `ScreenshotGenerator`：截图生成器
- `EnvConfig`：环境配置

### main_training.py

SkyRL 训练入口点。

**功能**：
- 设置环境变量
- 初始化 Ray
- 注册 CVE 环境
- 启动训练循环

### train_launcher.py

训练启动器，负责配置管理和命令构建。

**主要方法**：
- `check_prerequisites()`：检查前置条件
- `prepare_environment()`：准备环境
- `build_config()`：构建配置
- `build_command()`：构建命令行参数
- `launch()`：启动训练

---

# CVE-bench 测试

训练完成后，使用 CVE-bench 测试集评估模型的漏洞利用能力。

## CVE-bench 简介

CVE-bench 是一个评估 AI Agent 识别和利用真实世界 Web 应用漏洞能力的基准测试集，包含 40+ 个关键严重性的 CVE 挑战。

**测试变体**：
- **zero_day**：不提供漏洞详情，只告知目标地址，测试模型的漏洞发现能力
- **one_day**：提供漏洞的详细描述，测试模型的漏洞利用能力

**攻击类型**：
1. 拒绝服务攻击 (DoS)
2. 文件系统访问
3. 文件创建
4. 数据库修改
5. 数据库访问
6. 管理员账户攻陷
7. 用户权限提升
8. 出站服务利用

## 测试前置要求

### 1. 安装 CVE-bench

```bash
# 在 SecurityRL 同级目录克隆 CVE-bench
cd ~/PycharmProjects/SecurityRL
git clone https://github.com/uiuc-kang-lab/cve-bench.git
cd cve-bench
uv sync --dev
```

### 2. 确保训练完成

训练完成后，checkpoint 会保存在 `~/checkpoints/cve_agent/global_step_XXX` 目录。

## 运行测试

### 快速开始

```bash
cd dataset/dataset

# 使用最新 checkpoint 运行所有变体测试
python test_launcher.py

# 指定 checkpoint
python test_launcher.py --checkpoint ~/checkpoints/cve_agent/global_step_100

# 只运行 zero_day 变体
python test_launcher.py --variants zero_day

# 只运行 one_day 变体
python test_launcher.py --variants one_day

# 运行特定 CVE 挑战
python test_launcher.py --challenges CVE-2024-2624,CVE-2024-2771
```

### 完整参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--checkpoint` | 最新 checkpoint | Checkpoint 目录路径 |
| `--variants` | `zero_day,one_day` | 测试变体（逗号分隔） |
| `--challenges` | 全部 | 特定 CVE 挑战（逗号分隔） |
| `--max-messages` | `30` | 每个挑战的最大消息数 |
| `--setup-only` | - | 只安装 CVE-bench，不运行测试 |
| `--skip-check` | - | 跳过前置条件检查 |

### 首次运行

首次运行时，测试启动器会自动：
1. 检查 CVE-bench 是否已安装
2. 安装依赖（`uv sync --dev`）
3. 复制模型提供者到 CVE-bench
4. 创建模型注册入口

```bash
# 首次运行建议先 setup
python test_launcher.py --setup-only

# 然后运行测试
python test_launcher.py
```

## 测试结果

测试结果保存在 `eval_results/` 目录：

```
eval_results/
└── eval_YYYYMMDD_HHMMSS.json
```

**结果格式**：
```json
{
  "timestamp": "20241223_120000",
  "checkpoint": "/home/user/checkpoints/cve_agent/global_step_100",
  "variants": ["zero_day", "one_day"],
  "challenges": null,
  "returncode": 0,
  "stdout": "...",
  "stderr": "..."
}
```

## 评估指标

| 指标 | 说明 |
|------|------|
| Success Rate | 成功利用的 CVE 数量 / 总 CVE 数量 |
| Zero-day Rate | 在 zero_day 变体中的成功率 |
| One-day Rate | 在 one_day 变体中的成功率 |
| Attack Category | 按攻击类型分类的成功率 |

## 模型提供者

`lora_model_provider.py` 实现了 Inspect AI 的 `ModelAPI` 接口，将训练好的 LoRA 模型注册为 Inspect 兼容的模型提供者。

**使用方式**：
```bash
# 在 Inspect 中使用
inspect eval task.py --model=cve_lora/model -M checkpoint_path=/path/to/checkpoint
```

**参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `checkpoint_path` | - | LoRA checkpoint 路径 |
| `base_model` | `Qwen/Qwen2.5-3B-Instruct` | 基础模型 |
| `device` | `auto` | 设备 |
| `torch_dtype` | `bfloat16` | 数据类型 |
| `max_new_tokens` | `2048` | 最大生成 token 数 |

## 常见问题

### 1. CVE-bench 容器启动失败

```bash
# 手动检查容器健康状态
cd ../cve-bench
./run test-health CVE-2024-2624

# 手动启动/停止容器
./run up CVE-2024-2624
./run down CVE-2024-2624
```

### 2. 模型加载失败

确保 checkpoint 目录结构正确：
```
global_step_XXX/
├── policy/
│   ├── adapter_config.json
│   └── adapter_model.safetensors
└── trainer_state.json
```

### 3. GPU 内存不足

测试时模型会完整加载到 GPU，确保有足够显存（约 10-15GB for 3B 模型）。

## 目录结构

```
SecurityRL/
├── dataset/
│   └── dataset/
│       ├── train_launcher.py      # 训练启动器
│       ├── test_launcher.py       # 测试启动器
│       ├── lora_model_provider.py # Inspect 模型提供者
│       └── eval_results/          # 测试结果
└── cve-bench/                     # CVE-bench 仓库（同级目录）
    ├── run
    └── src/
        ├── cvebench/
        └── critical/
            └── challenges/
```

## 许可证

MIT License
