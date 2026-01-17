"""
Vulhub Dataset Builder v2.0
从 Vulhub 解析数据并生成训练数据集

核心特性：
1. 全面理解 README（文本 + 代码块 + 图片 OCR）
2. 生成完整可执行的 Python PoC 脚本
3. LLM 逻辑验证确保 PoC 正确性
4. 以 PoC 为中心的数据集结构
"""

import os
import re
import json
import yaml
import hashlib
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

import pandas as pd
from openai import OpenAI

# OCR 相关导入（可选依赖）
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: pytesseract or Pillow not installed. OCR will be disabled.")


# ============================================================================
# 数据类定义
# ============================================================================

class VulnerabilityType(str, Enum):
    """漏洞类型枚举"""
    RCE = "remote_code_execution"
    SQLI = "sql_injection"
    SSTI = "server_side_template_injection"
    PATH_TRAVERSAL = "path_traversal"
    DESERIALIZATION = "deserialization"
    FILE_UPLOAD = "file_upload"
    AUTH_BYPASS = "authentication_bypass"
    SSRF = "server_side_request_forgery"
    XXE = "xml_external_entity"
    XSS = "cross_site_scripting"
    FILE_INCLUSION = "file_inclusion"
    COMMAND_INJECTION = "command_injection"
    OTHER = "other"


@dataclass
class CodeBlock:
    """README 中提取的代码块"""
    language: str          # python, bash, shell, curl, http 等
    content: str           # 代码内容
    context: str           # 上下文说明（代码块前后的文字）
    line_number: int = 0   # 在 README 中的位置


@dataclass
class ImageContent:
    """图片 OCR 提取内容"""
    image_path: str        # 图片文件路径
    ocr_text: str          # pytesseract 提取的文字
    description: str       # 图片内容描述
    is_success_indicator: bool = False  # 是否展示成功利用


@dataclass
class ReadmeAnalysis:
    """README 综合分析结果"""
    raw_text: str                       # 原始 README 文本
    vulnerability_type: str             # 漏洞类型
    service_name: str                   # 服务名称
    service_version: str                # 受影响版本
    vulnerability_description: str      # 漏洞描述
    environment_setup: str              # 环境搭建说明
    exploitation_steps: List[Dict]      # 利用步骤
    success_indicators: List[str]       # 成功标志
    code_blocks: List[CodeBlock] = field(default_factory=list)
    images: List[ImageContent] = field(default_factory=list)
    reference_links: List[str] = field(default_factory=list)


@dataclass
class DockerConfig:
    """Docker 配置信息"""
    compose_path: str
    services: Dict[str, Any]
    exposed_ports: List[int]
    primary_port: int
    primary_service: str
    environment_vars: Dict[str, str] = field(default_factory=dict)


@dataclass
class GeneratedPoC:
    """生成的 PoC 脚本"""
    script: str                         # 完整 Python 脚本
    script_hash: str                    # SHA256 哈希
    dependencies: List[str]             # pip 依赖
    execution_cmd: str                  # 执行命令模板
    expected_output: str                # 预期输出描述
    validation_status: str              # validated/needs_review/failed
    validation_score: float             # 0.0-1.0
    validation_notes: str               # 验证说明
    generation_model: str               # 使用的模型
    generation_timestamp: str           # 生成时间


@dataclass
class VulhubEntry:
    """完整的 Vulhub 条目 - 核心数据结构"""
    # 标识信息
    cve_id: str
    vulhub_path: str

    # 内容分析
    readme_analysis: ReadmeAnalysis
    docker_config: DockerConfig

    # 生成的 PoC
    poc_script: Optional[GeneratedPoC] = None

    # 原始 PoC 文件
    original_poc_files: Dict[str, str] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """PoC 验证结果"""
    is_valid: bool
    completeness_score: float           # 完整性评分
    correctness_score: float            # 正确性评分
    issues: List[Dict]                  # 发现的问题
    missing_steps: List[str]            # 缺失的步骤
    recommendation: str                 # accept/revise/regenerate
    overall_assessment: str             # 总体评估


# ============================================================================
# OCR 处理器
# ============================================================================

class OCRProcessor:
    """图片 OCR 处理器"""

    def __init__(self, openai_client: OpenAI = None):
        self.client = openai_client

    def extract_text(self, image_path: Path) -> str:
        """使用 pytesseract 提取图片文字"""
        if not OCR_AVAILABLE:
            return ""

        try:
            image = Image.open(image_path)
            # 转换为 RGB 模式（处理 PNG 透明通道）
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            text = pytesseract.image_to_string(image, lang='eng+chi_sim')
            return text.strip()
        except Exception as e:
            print(f"  Warning: OCR failed for {image_path}: {e}")
            return ""

    def describe_image(self, image_path: Path, ocr_text: str) -> ImageContent:
        """生成图片描述"""
        description = f"Image at {image_path.name}"
        is_success = False

        # 基于 OCR 文本推断
        if ocr_text:
            success_keywords = ['success', 'pwned', 'root', 'admin', 'rce',
                              'command executed', 'shell', 'flag', 'id=0']
            if any(kw in ocr_text.lower() for kw in success_keywords):
                is_success = True
                description = f"Screenshot showing successful exploitation. OCR content: {ocr_text[:200]}"
            else:
                description = f"Screenshot with content: {ocr_text[:200]}"

        return ImageContent(
            image_path=str(image_path),
            ocr_text=ocr_text,
            description=description,
            is_success_indicator=is_success
        )


# ============================================================================
# 内容解析器
# ============================================================================

class ContentParser:
    """README 内容解析器"""

    def __init__(self, ocr_processor: OCRProcessor = None):
        self.ocr = ocr_processor or OCRProcessor()

    def extract_code_blocks(self, markdown: str) -> List[CodeBlock]:
        """从 Markdown 中提取所有代码块"""
        code_blocks = []

        # 匹配带语言标记的代码块：```language\ncode\n```
        pattern = r'```(\w*)\n(.*?)```'

        for match in re.finditer(pattern, markdown, re.DOTALL):
            language = match.group(1) or 'text'
            content = match.group(2).strip()

            # 获取上下文（代码块前 100 个字符）
            start_pos = match.start()
            context_start = max(0, start_pos - 150)
            context = markdown[context_start:start_pos].strip()
            # 只保留最后一行作为上下文
            context_lines = context.split('\n')
            context = context_lines[-1] if context_lines else ""

            code_blocks.append(CodeBlock(
                language=language.lower(),
                content=content,
                context=context,
                line_number=markdown[:start_pos].count('\n') + 1
            ))

        return code_blocks

    def extract_images(self, markdown: str, cve_path: Path) -> List[Path]:
        """从 Markdown 中提取图片路径"""
        images = []
        pattern = r'!\[.*?\]\((.*?)(?:\s+".*?")?\)'

        for match in re.findall(pattern, markdown):
            if match.startswith(('http://', 'https://')):
                continue
            img_path = cve_path / match
            if img_path.exists():
                images.append(img_path)

        return images

    def find_existing_poc_files(self, cve_path: Path) -> Dict[str, str]:
        """查找目录中已有的 PoC 文件"""
        poc_files = {}
        poc_patterns = ['poc.py', 'poc.xml', 'poc.sh', 'exploit.py',
                       'exploit.sh', 'payload.xml', 'poc.txt']

        for pattern in poc_patterns:
            poc_path = cve_path / pattern
            if poc_path.exists():
                try:
                    content = poc_path.read_text(encoding='utf-8')
                    poc_files[pattern] = content
                except Exception:
                    pass

        # 同时查找其他可能的 PoC 文件
        for file_path in cve_path.iterdir():
            if file_path.is_file() and file_path.suffix in ['.py', '.sh', '.xml']:
                name = file_path.name.lower()
                if 'poc' in name or 'exploit' in name or 'payload' in name:
                    if file_path.name not in poc_files:
                        try:
                            poc_files[file_path.name] = file_path.read_text(encoding='utf-8')
                        except Exception:
                            pass

        return poc_files

    def extract_reference_links(self, markdown: str) -> List[str]:
        """提取参考链接"""
        links = []
        # 匹配 Markdown 链接格式
        pattern = r'<(https?://[^>]+)>|\[([^\]]+)\]\((https?://[^)]+)\)'

        for match in re.finditer(pattern, markdown):
            url = match.group(1) or match.group(3)
            if url:
                links.append(url)

        return links

    def parse_readme(self, readme_path: Path, cve_path: Path) -> Tuple[str, List[CodeBlock], List[ImageContent], List[str]]:
        """解析 README 文件"""
        try:
            content = readme_path.read_text(encoding='utf-8')
        except Exception:
            return "", [], [], []

        # 提取代码块
        code_blocks = self.extract_code_blocks(content)

        # 提取并处理图片
        image_paths = self.extract_images(content, cve_path)
        images = []
        for img_path in image_paths:
            ocr_text = self.ocr.extract_text(img_path)
            image_content = self.ocr.describe_image(img_path, ocr_text)
            images.append(image_content)

        # 提取参考链接
        links = self.extract_reference_links(content)

        return content, code_blocks, images, links

    def parse_docker_compose(self, compose_path: Path) -> DockerConfig:
        """解析 docker-compose.yml"""
        try:
            with open(compose_path) as f:
                config = yaml.safe_load(f)

            services = config.get('services', {})
            if not services:
                return DockerConfig(
                    compose_path=str(compose_path),
                    services={},
                    exposed_ports=[80],
                    primary_port=80,
                    primary_service='web'
                )

            # 获取第一个服务作为主服务
            primary_service = list(services.keys())[0]
            service_config = services[primary_service]

            # 解析端口
            ports = []
            port_mappings = service_config.get('ports', [])
            for port in port_mappings:
                port_str = str(port)
                if ':' in port_str:
                    # 格式: "host:container" 或 "host:container/protocol"
                    container_port = port_str.split(':')[-1].split('/')[0]
                    ports.append(int(container_port))
                else:
                    ports.append(int(port_str.split('/')[0]))

            primary_port = ports[0] if ports else 80

            # 获取环境变量
            env_vars = {}
            env_list = service_config.get('environment', [])
            if isinstance(env_list, list):
                for item in env_list:
                    if '=' in str(item):
                        key, value = str(item).split('=', 1)
                        env_vars[key] = value
            elif isinstance(env_list, dict):
                env_vars = env_list

            return DockerConfig(
                compose_path=str(compose_path),
                services=services,
                exposed_ports=ports,
                primary_port=primary_port,
                primary_service=primary_service,
                environment_vars=env_vars
            )

        except Exception as e:
            print(f"  Warning: Failed to parse docker-compose: {e}")
            return DockerConfig(
                compose_path=str(compose_path),
                services={},
                exposed_ports=[80],
                primary_port=80,
                primary_service='web'
            )


# ============================================================================
# PoC 生成器
# ============================================================================

class PoCGenerator:
    """PoC 脚本生成器"""

    README_ANALYSIS_PROMPT = """You are a security expert analyzing a Vulhub CVE documentation.

## Input Materials

### README Content:
{readme_content}

### Code Blocks Extracted from README:
{code_blocks}

### OCR Text from Images:
{ocr_content}

### Existing PoC Files in Directory:
{existing_poc_files}

### Docker Configuration:
- Primary Port: {primary_port}
- Primary Service: {primary_service}

### CVE ID: {cve_id}

## Task
Analyze ALL provided materials and extract comprehensive vulnerability information.

## Output as JSON:
{{
  "vulnerability_type": "string (rce/sqli/ssti/path_traversal/deserialization/file_upload/auth_bypass/ssrf/xxe/xss/file_inclusion/command_injection/other)",
  "service_name": "string (e.g., Apache ActiveMQ, WordPress, nginx)",
  "service_version": "string (e.g., 5.17.3, < 2.4.50)",
  "vulnerability_description": "string (brief description of the vulnerability)",
  "environment_setup": "string (how to set up the environment)",
  "exploitation_steps": [
    {{
      "step_number": 1,
      "description": "string (what to do)",
      "action_type": "string (http_request/socket/command/upload/inject)",
      "technical_details": {{
        "method": "string (GET/POST/PUT/etc, if HTTP)",
        "endpoint": "string (target path)",
        "payload": "string (the actual payload)",
        "headers": {{}},
        "notes": "string (any important notes)"
      }},
      "expected_observation": "string (what you should see)"
    }}
  ],
  "success_indicators": ["string (observable evidence of success)"],
  "required_dependencies": ["string (Python packages needed, e.g., requests, pwntools)"],
  "difficulty": "string (easy/medium/hard)"
}}

Important:
- Be VERY specific about exploitation steps based on the README and existing PoC code
- Extract actual payloads, endpoints, and parameters from the documentation
- If existing PoC files are provided, analyze their logic carefully
- Output ONLY valid JSON, no other text"""

    POC_GENERATION_PROMPT = """You are a security expert writing a Python PoC (Proof of Concept) script.

## Vulnerability Analysis:
{vulnerability_analysis}

## Existing PoC Reference (if available):
{existing_poc}

## README Code Blocks:
{code_blocks}

## Requirements

Generate a COMPLETE, EXECUTABLE Python script that exploits this vulnerability.

### Script Requirements:
1. **Standalone executable** - Can run directly with `python3 poc.py`
2. **Command-line arguments** using argparse:
   - `--host` or `--target`: Target host (required)
   - `--port`: Target port (with sensible default based on vulnerability)
   - Any other necessary parameters
3. **Clear output messages**:
   - `[+]` prefix for successful steps
   - `[-]` prefix for failures
   - `[*]` prefix for informational messages
4. **Error handling** - Catch and handle common errors gracefully
5. **Comments** - Explain key parts of the exploit

### Code Structure Template:
```python
#!/usr/bin/env python3
\"\"\"
{cve_id} PoC - {service_name} {vulnerability_type}
{brief_description}

Usage: python3 poc.py --host TARGET_HOST --port TARGET_PORT
\"\"\"

import argparse
import requests  # or other necessary imports
# ... other imports

def exploit(host: str, port: int, **kwargs) -> bool:
    \"\"\"
    Main exploitation function.

    Args:
        host: Target host IP/hostname
        port: Target port

    Returns:
        True if exploitation successful, False otherwise
    \"\"\"
    target_url = f"http://{{host}}:{{port}}"

    # Step 1: ...
    print(f"[*] Targeting {{target_url}}")

    # Implement exploitation logic here
    # ...

    return True  # or False

def main():
    parser = argparse.ArgumentParser(
        description='{cve_id} PoC',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--host', '-H', required=True, help='Target host')
    parser.add_argument('--port', '-p', type=int, default={default_port}, help='Target port')
    # Add more arguments as needed

    args = parser.parse_args()

    print(f"[*] {cve_id} Exploit")
    print(f"[*] Target: {{args.host}}:{{args.port}}")

    try:
        success = exploit(args.host, args.port)
        if success:
            print("[+] Exploitation successful!")
        else:
            print("[-] Exploitation failed")
    except KeyboardInterrupt:
        print("\\n[-] Interrupted by user")
    except Exception as e:
        print(f"[-] Error: {{e}}")

if __name__ == "__main__":
    main()
```

## Output
Generate ONLY the complete Python script. No explanations before or after.
The script must be syntactically correct and executable.
Start with #!/usr/bin/env python3"""

    POC_VALIDATION_PROMPT = """You are a security expert reviewing a generated PoC script.

## Original README Content:
{readme_content}

## Vulnerability Analysis:
{vulnerability_analysis}

## Generated PoC Script:
```python
{generated_poc}
```

## Validation Criteria

1. **Completeness** (0.0-1.0)
   - Does it implement ALL required exploitation steps?
   - Are all endpoints/payloads correct?
   - Are all required headers/parameters included?

2. **Correctness** (0.0-1.0)
   - Are HTTP methods correct?
   - Are payloads properly formatted?
   - Is URL encoding handled where needed?
   - Are special characters escaped properly?

3. **Executability**
   - Is the script syntactically correct?
   - Are all imports available?
   - Is error handling present?

4. **Logic Flow**
   - Are steps in correct order?
   - Are dependencies between steps handled?
   - Does it check success conditions?

## Output as JSON:
{{
  "is_valid": boolean,
  "completeness_score": float,
  "correctness_score": float,
  "issues": [
    {{
      "severity": "critical/major/minor",
      "description": "string",
      "line_hint": "string (code snippet with issue)",
      "suggested_fix": "string"
    }}
  ],
  "missing_steps": ["string"],
  "overall_assessment": "string (brief summary)",
  "recommendation": "accept/revise/regenerate"
}}"""

    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def analyze_readme(self, entry: VulhubEntry) -> Dict:
        """分析 README 内容，提取结构化信息"""
        # 准备代码块信息
        code_blocks_text = ""
        for i, cb in enumerate(entry.readme_analysis.code_blocks):
            code_blocks_text += f"\n### Code Block {i+1} ({cb.language}):\n"
            code_blocks_text += f"Context: {cb.context}\n"
            code_blocks_text += f"```{cb.language}\n{cb.content}\n```\n"

        # 准备 OCR 内容
        ocr_content = ""
        for img in entry.readme_analysis.images:
            if img.ocr_text:
                ocr_content += f"\n### Image: {Path(img.image_path).name}\n"
                ocr_content += f"OCR Text: {img.ocr_text}\n"
                ocr_content += f"Description: {img.description}\n"

        # 准备现有 PoC 文件
        existing_poc_text = ""
        for filename, content in entry.original_poc_files.items():
            existing_poc_text += f"\n### {filename}:\n```\n{content}\n```\n"

        prompt = self.README_ANALYSIS_PROMPT.format(
            readme_content=entry.readme_analysis.raw_text[:6000],
            code_blocks=code_blocks_text or "No code blocks found",
            ocr_content=ocr_content or "No OCR content available",
            existing_poc_files=existing_poc_text or "No existing PoC files",
            primary_port=entry.docker_config.primary_port,
            primary_service=entry.docker_config.primary_service,
            cve_id=entry.cve_id
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a security expert. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"  Warning: README analysis failed: {e}")
            return {
                "vulnerability_type": "other",
                "service_name": entry.docker_config.primary_service,
                "service_version": "unknown",
                "vulnerability_description": "",
                "environment_setup": "",
                "exploitation_steps": [],
                "success_indicators": [],
                "required_dependencies": ["requests"],
                "difficulty": "medium"
            }

    def generate_poc(self, entry: VulhubEntry, analysis: Dict, feedback: str = None) -> GeneratedPoC:
        """生成 Python PoC 脚本"""
        # 准备现有 PoC 参考
        existing_poc = ""
        if entry.original_poc_files:
            # 优先使用 poc.py
            if 'poc.py' in entry.original_poc_files:
                existing_poc = entry.original_poc_files['poc.py']
            else:
                # 使用第一个找到的 PoC
                existing_poc = list(entry.original_poc_files.values())[0]

        # 准备代码块
        code_blocks_text = ""
        for cb in entry.readme_analysis.code_blocks:
            if cb.language in ['python', 'bash', 'shell', 'sh', 'curl']:
                code_blocks_text += f"\n```{cb.language}\n{cb.content}\n```\n"

        prompt = self.POC_GENERATION_PROMPT.format(
            vulnerability_analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
            existing_poc=existing_poc or "No existing PoC available",
            code_blocks=code_blocks_text or "No relevant code blocks",
            cve_id=entry.cve_id,
            service_name=analysis.get('service_name', 'Unknown'),
            vulnerability_type=analysis.get('vulnerability_type', 'vulnerability'),
            brief_description=analysis.get('vulnerability_description', ''),
            default_port=entry.docker_config.primary_port
        )

        if feedback:
            prompt += f"\n\n## Previous Issues (MUST FIX):\n{feedback}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a security expert writing Python exploit code. Output only the Python script, nothing else."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )

            script = response.choices[0].message.content.strip()

            # 清理脚本（移除可能的 markdown 标记）
            if script.startswith('```python'):
                script = script[9:]
            elif script.startswith('```'):
                script = script[3:]
            if script.endswith('```'):
                script = script[:-3]
            script = script.strip()

            # 确保脚本以 shebang 开头
            if not script.startswith('#!/'):
                script = '#!/usr/bin/env python3\n' + script

            # 计算哈希
            script_hash = hashlib.sha256(script.encode()).hexdigest()[:16]

            return GeneratedPoC(
                script=script,
                script_hash=script_hash,
                dependencies=analysis.get('required_dependencies', ['requests']),
                execution_cmd=f"python3 poc.py --host {{host}} --port {entry.docker_config.primary_port}",
                expected_output=', '.join(analysis.get('success_indicators', [])),
                validation_status="pending",
                validation_score=0.0,
                validation_notes="",
                generation_model=self.model,
                generation_timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            print(f"  Error: PoC generation failed: {e}")
            return GeneratedPoC(
                script="# Generation failed",
                script_hash="",
                dependencies=[],
                execution_cmd="",
                expected_output="",
                validation_status="failed",
                validation_score=0.0,
                validation_notes=str(e),
                generation_model=self.model,
                generation_timestamp=datetime.now().isoformat()
            )


# ============================================================================
# PoC 验证器
# ============================================================================

class PoCValidator:
    """PoC 脚本验证器"""

    MAX_RETRIES = 3
    VALIDATION_THRESHOLD = 0.7

    def __init__(self, api_key: str = None, model: str = "gpt-4o"):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def validate(self, entry: VulhubEntry, analysis: Dict) -> ValidationResult:
        """验证生成的 PoC"""
        if not entry.poc_script or entry.poc_script.script == "# Generation failed":
            return ValidationResult(
                is_valid=False,
                completeness_score=0.0,
                correctness_score=0.0,
                issues=[{"severity": "critical", "description": "No PoC script generated"}],
                missing_steps=[],
                recommendation="regenerate",
                overall_assessment="No valid PoC script to validate"
            )

        prompt = PoCGenerator.POC_VALIDATION_PROMPT.format(
            readme_content=entry.readme_analysis.raw_text[:4000],
            vulnerability_analysis=json.dumps(analysis, indent=2, ensure_ascii=False),
            generated_poc=entry.poc_script.script
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a security expert reviewing exploit code. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            return ValidationResult(
                is_valid=result.get('is_valid', False),
                completeness_score=result.get('completeness_score', 0.0),
                correctness_score=result.get('correctness_score', 0.0),
                issues=result.get('issues', []),
                missing_steps=result.get('missing_steps', []),
                recommendation=result.get('recommendation', 'regenerate'),
                overall_assessment=result.get('overall_assessment', '')
            )

        except Exception as e:
            print(f"  Warning: Validation failed: {e}")
            return ValidationResult(
                is_valid=False,
                completeness_score=0.0,
                correctness_score=0.0,
                issues=[{"severity": "critical", "description": f"Validation error: {e}"}],
                missing_steps=[],
                recommendation="regenerate",
                overall_assessment=f"Validation failed: {e}"
            )

    def build_feedback(self, validation: ValidationResult) -> str:
        """构建反馈信息用于重新生成"""
        feedback_parts = []

        if validation.issues:
            feedback_parts.append("Issues found:")
            for issue in validation.issues:
                feedback_parts.append(f"- [{issue.get('severity', 'unknown')}] {issue.get('description', '')}")
                if issue.get('suggested_fix'):
                    feedback_parts.append(f"  Suggested fix: {issue.get('suggested_fix')}")

        if validation.missing_steps:
            feedback_parts.append("\nMissing steps:")
            for step in validation.missing_steps:
                feedback_parts.append(f"- {step}")

        feedback_parts.append(f"\nOverall: {validation.overall_assessment}")

        return '\n'.join(feedback_parts)


# ============================================================================
# Vulhub 扫描器
# ============================================================================

class VulhubScanner:
    """Vulhub 仓库扫描器"""

    def __init__(self, vulhub_path: str):
        self.vulhub_path = Path(vulhub_path).expanduser()
        if not self.vulhub_path.exists():
            raise ValueError(f"Vulhub path not found: {vulhub_path}")

    def scan_all(self) -> List[Path]:
        """扫描所有有效的 CVE 目录"""
        valid_dirs = []

        for category in self.vulhub_path.iterdir():
            if not category.is_dir() or category.name.startswith('.'):
                continue

            for cve_dir in category.iterdir():
                if not cve_dir.is_dir() or cve_dir.name.startswith('.'):
                    continue

                if self._is_valid_cve_dir(cve_dir):
                    valid_dirs.append(cve_dir)

        return valid_dirs

    def _is_valid_cve_dir(self, cve_dir: Path) -> bool:
        """检查是否为有效的 CVE 目录"""
        # 必须有 README
        has_readme = any((cve_dir / name).exists()
                        for name in ['README.md', 'README.zh-cn.md', 'readme.md'])

        # 必须有 docker-compose
        has_compose = any((cve_dir / name).exists()
                         for name in ['docker-compose.yml', 'docker-compose.yaml'])

        return has_readme and has_compose

    def extract_cve_id(self, cve_path: Path) -> str:
        """从路径提取 CVE ID"""
        match = re.search(r'(CVE-\d{4}-\d+)', str(cve_path), re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return f"{cve_path.parent.name}/{cve_path.name}"

    def find_readme(self, cve_path: Path) -> Optional[Path]:
        """查找 README 文件"""
        for name in ['README.md', 'README.zh-cn.md', 'readme.md']:
            readme = cve_path / name
            if readme.exists():
                return readme
        return None

    def find_compose(self, cve_path: Path) -> Optional[Path]:
        """查找 docker-compose 文件"""
        for name in ['docker-compose.yml', 'docker-compose.yaml']:
            compose = cve_path / name
            if compose.exists():
                return compose
        return None


# ============================================================================
# 数据集构建器
# ============================================================================

class DatasetBuilder:
    """数据集构建器"""

    def __init__(self, output_dir: str, api_key: str = None):
        self.output_dir = Path(output_dir).expanduser()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        api_key = api_key or os.getenv("OPENAI_API_KEY")

        self.ocr_processor = OCRProcessor()
        self.content_parser = ContentParser(self.ocr_processor)
        self.poc_generator = PoCGenerator(api_key)
        self.poc_validator = PoCValidator(api_key)

    def process_cve(self, cve_path: Path, scanner: VulhubScanner) -> Optional[VulhubEntry]:
        """处理单个 CVE"""
        cve_id = scanner.extract_cve_id(cve_path)
        print(f"  Processing: {cve_id}")

        # 查找文件
        readme_path = scanner.find_readme(cve_path)
        compose_path = scanner.find_compose(cve_path)

        if not readme_path or not compose_path:
            print(f"    Skipped: Missing README or docker-compose")
            return None

        # 解析内容
        readme_text, code_blocks, images, links = self.content_parser.parse_readme(
            readme_path, cve_path
        )
        docker_config = self.content_parser.parse_docker_compose(compose_path)
        original_poc_files = self.content_parser.find_existing_poc_files(cve_path)

        # 计算相对路径
        try:
            rel_path = str(cve_path.relative_to(scanner.vulhub_path))
        except ValueError:
            rel_path = str(cve_path)

        # 创建条目
        entry = VulhubEntry(
            cve_id=cve_id,
            vulhub_path=rel_path,
            readme_analysis=ReadmeAnalysis(
                raw_text=readme_text,
                vulnerability_type="",
                service_name="",
                service_version="",
                vulnerability_description="",
                environment_setup="",
                exploitation_steps=[],
                success_indicators=[],
                code_blocks=code_blocks,
                images=images,
                reference_links=links
            ),
            docker_config=docker_config,
            original_poc_files=original_poc_files
        )

        # 分析 README
        print(f"    Analyzing README...")
        analysis = self.poc_generator.analyze_readme(entry)

        # 更新分析结果
        entry.readme_analysis.vulnerability_type = analysis.get('vulnerability_type', 'other')
        entry.readme_analysis.service_name = analysis.get('service_name', '')
        entry.readme_analysis.service_version = analysis.get('service_version', '')
        entry.readme_analysis.vulnerability_description = analysis.get('vulnerability_description', '')
        entry.readme_analysis.environment_setup = analysis.get('environment_setup', '')
        entry.readme_analysis.exploitation_steps = analysis.get('exploitation_steps', [])
        entry.readme_analysis.success_indicators = analysis.get('success_indicators', [])

        print(f"    Type: {entry.readme_analysis.vulnerability_type}")
        print(f"    Service: {entry.readme_analysis.service_name}")

        # 生成 PoC（带验证循环）
        print(f"    Generating PoC...")
        feedback = None

        for attempt in range(PoCValidator.MAX_RETRIES):
            entry.poc_script = self.poc_generator.generate_poc(entry, analysis, feedback)

            if entry.poc_script.validation_status == "failed":
                print(f"    PoC generation failed")
                break

            # 验证
            print(f"    Validating (attempt {attempt + 1}/{PoCValidator.MAX_RETRIES})...")
            validation = self.poc_validator.validate(entry, analysis)

            avg_score = (validation.completeness_score + validation.correctness_score) / 2
            entry.poc_script.validation_score = avg_score

            if validation.is_valid and avg_score >= PoCValidator.VALIDATION_THRESHOLD:
                entry.poc_script.validation_status = "validated"
                entry.poc_script.validation_notes = validation.overall_assessment
                print(f"    Validated! Score: {avg_score:.2f}")
                break

            if validation.recommendation == "accept":
                entry.poc_script.validation_status = "validated"
                entry.poc_script.validation_notes = validation.overall_assessment
                print(f"    Accepted with score: {avg_score:.2f}")
                break

            # 需要重新生成
            feedback = self.poc_validator.build_feedback(validation)
            print(f"    Score: {avg_score:.2f}, retrying...")

        else:
            # 达到最大重试次数
            entry.poc_script.validation_status = "needs_review"
            entry.poc_script.validation_notes = f"Failed after {PoCValidator.MAX_RETRIES} attempts"
            print(f"    Marked for review")

        return entry

    def build(self, scanner: VulhubScanner, limit: int = None) -> Path:
        """构建数据集"""
        cve_dirs = scanner.scan_all()
        print(f"Found {len(cve_dirs)} valid CVE directories")

        if limit:
            cve_dirs = cve_dirs[:limit]
            print(f"Processing first {limit} CVEs")

        entries = []
        failed = []

        for i, cve_path in enumerate(cve_dirs):
            print(f"\n[{i+1}/{len(cve_dirs)}]", end="")

            try:
                entry = self.process_cve(cve_path, scanner)
                if entry:
                    entries.append(entry)
            except Exception as e:
                print(f"    Error: {e}")
                failed.append((cve_path, str(e)))

        print(f"\n{'='*60}")
        print(f"Processed: {len(entries)} successful, {len(failed)} failed")

        # 转换为 DataFrame
        records = []
        for entry in entries:
            record = {
                # 标识信息
                "cve_id": entry.cve_id,
                "vulhub_path": entry.vulhub_path,

                # 漏洞元数据
                "vulnerability_type": entry.readme_analysis.vulnerability_type,
                "service_name": entry.readme_analysis.service_name,
                "service_version": entry.readme_analysis.service_version,
                "vulnerability_description": entry.readme_analysis.vulnerability_description,

                # 环境配置
                "primary_port": entry.docker_config.primary_port,
                "exposed_ports": json.dumps(entry.docker_config.exposed_ports),
                "primary_service": entry.docker_config.primary_service,

                # PoC 脚本（核心字段）
                "poc_script": entry.poc_script.script if entry.poc_script else "",
                "poc_dependencies": json.dumps(entry.poc_script.dependencies if entry.poc_script else []),
                "poc_execution_cmd": entry.poc_script.execution_cmd if entry.poc_script else "",

                # 利用步骤和成功标志
                "exploitation_steps": json.dumps(entry.readme_analysis.exploitation_steps, ensure_ascii=False),
                "success_indicators": json.dumps(entry.readme_analysis.success_indicators, ensure_ascii=False),

                # README 原始内容
                "readme_content": entry.readme_analysis.raw_text,

                # 代码块
                "code_blocks": json.dumps([asdict(cb) for cb in entry.readme_analysis.code_blocks], ensure_ascii=False),

                # 图片 OCR 内容
                "image_ocr_content": json.dumps([asdict(img) for img in entry.readme_analysis.images], ensure_ascii=False),

                # 原有 PoC 文件
                "original_poc_files": json.dumps(entry.original_poc_files, ensure_ascii=False),

                # 参考链接
                "reference_links": json.dumps(entry.readme_analysis.reference_links),

                # 验证元数据
                "validation_status": entry.poc_script.validation_status if entry.poc_script else "failed",
                "validation_score": entry.poc_script.validation_score if entry.poc_script else 0.0,
                "validation_notes": entry.poc_script.validation_notes if entry.poc_script else "",

                # 生成元数据
                "generation_model": entry.poc_script.generation_model if entry.poc_script else "",
                "generation_timestamp": entry.poc_script.generation_timestamp if entry.poc_script else "",
            }
            records.append(record)

        # 保存
        output_path = self.output_dir / "train.parquet"
        df = pd.DataFrame(records)
        df.to_parquet(output_path, index=False)
        print(f"\nDataset saved to: {output_path}")
        print(f"Total samples: {len(records)}")

        # 保存失败记录
        if failed:
            error_path = self.output_dir / "errors.json"
            with open(error_path, 'w') as f:
                json.dump([{"path": str(p), "error": e} for p, e in failed], f, indent=2)
            print(f"Error log saved to: {error_path}")

        # 统计信息
        if records:
            validated = sum(1 for r in records if r['validation_status'] == 'validated')
            needs_review = sum(1 for r in records if r['validation_status'] == 'needs_review')
            failed_count = sum(1 for r in records if r['validation_status'] == 'failed')
            print(f"\nValidation stats:")
            print(f"  Validated: {validated}")
            print(f"  Needs review: {needs_review}")
            print(f"  Failed: {failed_count}")

        return output_path


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Vulhub Dataset Builder v2.0 - Generate PoC scripts from Vulhub CVEs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all CVEs
  python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ~/data/cve_vulhub

  # Process first 10 CVEs (for testing)
  python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ~/data/cve_vulhub --limit 10

  # Use a specific model
  python vulhub_dataset_builder.py --vulhub_path ~/vulhub --output_dir ~/data/cve_vulhub --model gpt-4o-mini
"""
    )
    parser.add_argument("--vulhub_path", type=str, default="~/vulhub",
                        help="Path to Vulhub repository (default: ~/vulhub)")
    parser.add_argument("--output_dir", type=str, default="~/data/cve_vulhub",
                        help="Output directory for dataset (default: ~/data/cve_vulhub)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of CVEs to process (for testing)")
    parser.add_argument("--model", type=str, default="gpt-4o",
                        help="OpenAI model to use (default: gpt-4o)")
    parser.add_argument("--api_key", type=str, default=None,
                        help="OpenAI API key (default: from OPENAI_API_KEY env)")

    args = parser.parse_args()

    print("=" * 60)
    print("Vulhub Dataset Builder v2.0")
    print("=" * 60)
    print(f"Vulhub path: {args.vulhub_path}")
    print(f"Output dir: {args.output_dir}")
    print(f"Model: {args.model}")
    print(f"OCR available: {OCR_AVAILABLE}")
    if args.limit:
        print(f"Limit: {args.limit}")
    print("=" * 60)

    # 检查 API key
    api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key not found. Set OPENAI_API_KEY environment variable or use --api_key")
        return 1

    try:
        # 初始化
        scanner = VulhubScanner(args.vulhub_path)
        builder = DatasetBuilder(args.output_dir, api_key)

        # 更新模型设置
        builder.poc_generator.model = args.model
        builder.poc_validator.model = args.model

        # 构建数据集
        output_path = builder.build(scanner, limit=args.limit)

        print("\n" + "=" * 60)
        print("Dataset built successfully!")
        print(f"Output: {output_path}")
        print("=" * 60)

        return 0

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
