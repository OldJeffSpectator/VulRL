# Vulhub Dataset Builder v2.0

从 Vulhub 仓库解析 CVE 信息，**自动生成可执行的 Python PoC 脚本**，并输出训练数据集。

## 核心特性

1. **全面理解 README** - 解析文本、代码块、图片（OCR）
2. **生成 Python PoC** - 完整可执行的漏洞利用脚本
3. **LLM 验证** - 自动检查 PoC 正确性（最多 3 次重试）
4. **以 PoC 为中心** - 全新的数据集结构设计

## 快速开始

### 前置条件

```bash
# 1. 安装 Tesseract OCR
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# 2. 安装 Python 依赖
pip install pytesseract Pillow pandas openai pyyaml

# 3. 设置 OpenAI API Key
export OPENAI_API_KEY="your-api-key"

# 4. 克隆 Vulhub
git clone https://github.com/vulhub/vulhub.git ~/vulhub
```

### 运行

```bash
# 处理所有 CVE
python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ~/data/cve_vulhub

# 测试模式：只处理前 10 个 CVE
python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ~/data/cve_vulhub --limit 10

# 使用更便宜的模型
python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ~/data/cve_vulhub --model gpt-4o-mini
```

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--vulhub_path` | `~/vulhub` | Vulhub 仓库路径 |
| `--output_dir` | `~/data/cve_vulhub` | 输出数据集路径 |
| `--limit` | `None` | 限制处理的 CVE 数量（用于测试） |
| `--model` | `gpt-4o` | 使用的 OpenAI 模型 |
| `--api_key` | `$OPENAI_API_KEY` | OpenAI API Key |

## 处理流程

```
┌─────────────┐    ┌───────────────┐    ┌─────────────────┐
│ VulhubScanner │───>│ ContentParser │───>│   PoCGenerator  │
│             │    │               │    │                 │
│ - 扫描 CVE  │    │ - README 文本 │    │ - 分析漏洞信息  │
│ - 验证结构  │    │ - 代码块提取  │    │ - 生成 Python   │
│             │    │ - OCR 图片    │    │   PoC 脚本      │
└─────────────┘    └───────────────┘    └────────┬────────┘
                                                  │
┌─────────────┐    ┌───────────────┐              │
│ DatasetWriter │<───│ PoCValidator │<─────────────┘
│             │    │               │
│ - 输出      │    │ - LLM 验证    │
│   parquet   │    │ - 最多 3 次   │
│ - 统计信息  │    │   重试        │
└─────────────┘    └───────────────┘
```

## 输出格式

### train.parquet 字段

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

### 验证状态

| 状态 | 说明 |
|------|------|
| `validated` | PoC 通过验证，可直接使用 |
| `needs_review` | 验证未通过，需人工检查 |
| `failed` | 生成失败 |

## 主要类

### 处理组件

| 类名 | 功能 |
|------|------|
| `VulhubScanner` | 扫描 Vulhub 仓库中的有效 CVE 目录 |
| `ContentParser` | 解析 README（代码块、图片、链接） |
| `OCRProcessor` | 使用 pytesseract 提取图片文字 |
| `PoCGenerator` | 使用 GPT-4o 生成 Python PoC 脚本 |
| `PoCValidator` | 使用 LLM 验证 PoC 正确性 |
| `DatasetBuilder` | 编排整个流程，输出 parquet 数据集 |

### 数据类

| 类名 | 功能 |
|------|------|
| `CodeBlock` | README 中的代码块（语言、内容、上下文） |
| `ImageContent` | 图片 OCR 内容和描述 |
| `ReadmeAnalysis` | README 综合分析结果 |
| `DockerConfig` | Docker 配置信息 |
| `GeneratedPoC` | 生成的 PoC 脚本及元数据 |
| `VulhubEntry` | 完整的 Vulhub 条目（核心数据结构） |
| `ValidationResult` | PoC 验证结果 |

## 生成的 PoC 示例

```python
#!/usr/bin/env python3
"""
CVE-2016-3088 PoC - Apache ActiveMQ file_upload
The Fileserver application in Apache ActiveMQ allows arbitrary file write...

Usage: python3 poc.py --host TARGET_HOST --port TARGET_PORT
"""

import argparse
import requests

def exploit(host: str, port: int) -> bool:
    """Main exploitation function."""
    target_url = f"http://{host}:{port}"

    # Step 1: Upload webshell
    print(f"[*] Uploading webshell to {target_url}")
    # ... exploitation logic ...

    return True

def main():
    parser = argparse.ArgumentParser(description='CVE-2016-3088 PoC')
    parser.add_argument('--host', '-H', required=True, help='Target host')
    parser.add_argument('--port', '-p', type=int, default=8161, help='Target port')
    args = parser.parse_args()

    success = exploit(args.host, args.port)
    if success:
        print("[+] Exploitation successful!")
    else:
        print("[-] Exploitation failed")

if __name__ == "__main__":
    main()
```

## 常见问题

### 1. OCR 不工作

确保安装了 Tesseract：
```bash
# macOS
brew install tesseract

# Ubuntu
sudo apt-get install tesseract-ocr
```

### 2. API 调用失败

检查 OpenAI API Key 是否正确设置：
```bash
echo $OPENAI_API_KEY
```

### 3. 验证分数低

PoC 验证分数低于 0.7 会被标记为 `needs_review`。可以：
- 检查原始 README 内容
- 手动修改生成的 PoC
- 使用更强的模型（gpt-4o）

### 4. 内存不足

处理大量 CVE 时可能内存不足，使用 `--limit` 参数分批处理：
```bash
python vulhub_dataset_builder.py --limit 50
```

## 依赖

- Python 3.10+
- pandas
- openai
- pyyaml
- pytesseract (可选，用于 OCR)
- Pillow (可选，用于图片处理)

## 许可证

MIT License
