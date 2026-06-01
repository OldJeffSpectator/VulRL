"""
CVE-bench Test Launcher
训练完成后使用 CVE-bench 测试模型性能

用法:
    python test_launcher.py --checkpoint ~/checkpoints/cve_agent/global_step_100
    python test_launcher.py --variants zero_day,one_day
    python test_launcher.py --challenges CVE-2024-2624,CVE-2024-2771
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Optional


class CVEBenchTester:
    """CVE-bench 测试启动器"""

    def __init__(self, checkpoint_dir: str = None):
        self.script_dir = Path(__file__).parent.resolve()
        self.project_root = self.script_dir.parent  # dataset/dataset/
        self.cvebench_dir = self.project_root / "benchmark" / "cve-bench"
        # 支持自定义 checkpoint 目录
        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir).expanduser()
        else:
            self.checkpoint_dir = Path.home() / "checkpoints" / "cve_agent"
        self.results_dir = self.script_dir / "eval_results"

    def check_prerequisites(self, skip_checkpoint_check: bool = False) -> bool:
        """检查前置条件"""
        print("=" * 60)
        print("Checking Prerequisites")
        print("=" * 60)

        checks = []

        # CVE-bench
        if self.cvebench_dir.exists():
            print(f"✓ CVE-bench: {self.cvebench_dir}")
            checks.append(True)
        else:
            print(f"✗ CVE-bench not found at {self.cvebench_dir}")
            print(f"  Please run: git clone https://github.com/uiuc-kang-lab/cve-bench.git {self.cvebench_dir}")
            checks.append(False)

        # Docker
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True)
            if result.returncode == 0:
                print(f"✓ Docker: {result.stdout.decode().strip()}")
                checks.append(True)
            else:
                print("✗ Docker not working")
                checks.append(False)
        except:
            print("✗ Docker not found")
            checks.append(False)

        # Checkpoints (可跳过，当明确指定 checkpoint 路径时)
        if skip_checkpoint_check:
            print(f"○ Checkpoint check skipped (will use specified path)")
            checks.append(True)
        elif self.checkpoint_dir.exists():
            checkpoints = list(self.checkpoint_dir.glob("global_step_*"))
            if checkpoints:
                print(f"✓ Checkpoints: {len(checkpoints)} found in {self.checkpoint_dir}")
                checks.append(True)
            else:
                print(f"✗ No checkpoints found in {self.checkpoint_dir}")
                checks.append(False)
        else:
            print(f"✗ Checkpoint directory not found: {self.checkpoint_dir}")
            checks.append(False)

        # Model provider
        provider_file = self.script_dir / "lora_model_provider.py"
        if provider_file.exists():
            print(f"✓ Model provider: {provider_file}")
            checks.append(True)
        else:
            print(f"✗ Model provider not found: {provider_file}")
            checks.append(False)

        return all(checks)

    def find_latest_checkpoint(self) -> Optional[Path]:
        """找到最新的 checkpoint"""
        if not self.checkpoint_dir.exists():
            return None

        checkpoints = list(self.checkpoint_dir.glob("global_step_*"))
        if not checkpoints:
            return None

        # 按步数排序
        def get_step(p):
            try:
                return int(p.name.split("_")[-1])
            except:
                return 0

        checkpoints.sort(key=get_step, reverse=True)
        return checkpoints[0]

    def setup_cvebench(self):
        """设置 CVE-bench 环境"""
        print("\n" + "=" * 60)
        print("Setting up CVE-bench")
        print("=" * 60)

        if not self.cvebench_dir.exists():
            print("Cloning CVE-bench...")
            subprocess.run(
                ["git", "clone", "https://github.com/uiuc-kang-lab/cve-bench.git", str(self.cvebench_dir)],
                check=True
            )

        # 安装依赖
        print("Installing dependencies...")
        subprocess.run(
            ["uv", "sync", "--dev"],
            cwd=self.cvebench_dir,
            check=True
        )

        # 复制模型提供者到 CVE-bench
        src_provider = self.script_dir / "lora_model_provider.py"
        dst_provider = self.cvebench_dir / "src" / "cvebench" / "lora_model_provider.py"

        if src_provider.exists():
            import shutil
            shutil.copy(src_provider, dst_provider)
            print(f"✓ Copied model provider to {dst_provider}")

        # 创建注册入口
        registry_content = '''"""Model provider registry for Inspect AI"""
from .lora_model_provider import cve_lora_provider
'''
        registry_file = self.cvebench_dir / "src" / "cvebench" / "_registry.py"
        registry_file.write_text(registry_content)
        print(f"✓ Created registry at {registry_file}")

    def run_evaluation(
        self,
        checkpoint: str,
        variants: List[str] = None,
        challenges: List[str] = None,
        max_messages: int = 30,
    ) -> dict:
        """运行评估"""
        print("\n" + "=" * 60)
        print("Running Evaluation")
        print("=" * 60)

        if variants is None:
            variants = ["zero_day", "one_day"]

        # 构建命令
        cmd = [
            "uv", "run", "inspect", "eval",
            "src/cvebench/cvebench.py@cvebench",
            f"--model=cve_lora/model",
            f"-M", f"checkpoint_path={checkpoint}",
            f"-M", f"max_messages={max_messages}",
        ]

        # 添加变体
        if variants:
            cmd.extend(["-T", f"variants={','.join(variants)}"])

        # 添加特定挑战
        if challenges:
            cmd.extend(["-T", f"challenges={','.join(challenges)}"])

        print(f"\nCommand: {' '.join(cmd)}")
        print(f"\nCheckpoint: {checkpoint}")
        print(f"Variants: {variants}")
        if challenges:
            print(f"Challenges: {challenges}")
        print()

        # 创建结果目录
        self.results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = self.results_dir / f"eval_{timestamp}.json"

        # 运行评估
        try:
            result = subprocess.run(
                cmd,
                cwd=self.cvebench_dir,
                capture_output=True,
                text=True,
            )

            print("STDOUT:")
            print(result.stdout)

            if result.stderr:
                print("STDERR:")
                print(result.stderr)

            # 解析结果
            eval_result = {
                "timestamp": timestamp,
                "checkpoint": checkpoint,
                "variants": variants,
                "challenges": challenges,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

            # 保存结果
            with open(result_file, 'w') as f:
                json.dump(eval_result, f, indent=2)
            print(f"\n✓ Results saved to {result_file}")

            return eval_result

        except Exception as e:
            print(f"\n✗ Evaluation failed: {e}")
            return {"error": str(e)}

    def run_single_challenge(self, checkpoint: str, challenge: str, variant: str = "zero_day"):
        """运行单个挑战（用于调试）"""
        print(f"\nRunning single challenge: {challenge} ({variant})")

        # 先启动容器
        print("Starting container...")
        subprocess.run(
            ["./run", "up", challenge],
            cwd=self.cvebench_dir,
            check=True
        )

        try:
            # 运行评估
            result = self.run_evaluation(
                checkpoint=checkpoint,
                variants=[variant],
                challenges=[challenge]
            )
            return result
        finally:
            # 停止容器
            print("\nStopping container...")
            subprocess.run(
                ["./run", "down", challenge],
                cwd=self.cvebench_dir
            )

    def generate_report(self, results: List[dict]) -> str:
        """生成评估报告"""
        report = []
        report.append("=" * 60)
        report.append("CVE-bench Evaluation Report")
        report.append("=" * 60)

        for result in results:
            report.append(f"\nCheckpoint: {result.get('checkpoint', 'N/A')}")
            report.append(f"Variants: {result.get('variants', 'N/A')}")
            report.append(f"Return code: {result.get('returncode', 'N/A')}")

            if "error" in result:
                report.append(f"Error: {result['error']}")

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="CVE-bench Test Launcher")
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to checkpoint directory (default: latest)"
    )
    parser.add_argument(
        "--variants",
        type=str,
        default="zero_day,one_day",
        help="Comma-separated list of variants (default: zero_day,one_day)"
    )
    parser.add_argument(
        "--challenges",
        type=str,
        default=None,
        help="Comma-separated list of specific CVE challenges"
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=30,
        help="Maximum messages per challenge (default: 30)"
    )
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only setup CVE-bench, don't run evaluation"
    )
    parser.add_argument(
        "--skip-check",
        action="store_true",
        help="Skip prerequisite check"
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=str,
        default=None,
        help="Directory containing checkpoints (default: ~/checkpoints/cve_agent)"
    )
    args = parser.parse_args()

    # 确定 checkpoint 目录
    checkpoint_dir = args.checkpoint_dir
    if checkpoint_dir is None and args.checkpoint:
        # 如果指定了具体 checkpoint，从中推断目录
        checkpoint_path = Path(args.checkpoint).expanduser()
        if checkpoint_path.exists():
            checkpoint_dir = str(checkpoint_path.parent)

    tester = CVEBenchTester(checkpoint_dir=checkpoint_dir)

    # 检查前置条件（如果明确指定了 checkpoint 路径，跳过 checkpoint 检查）
    skip_checkpoint_check = args.checkpoint is not None
    if not args.skip_check and not args.setup_only:
        if not tester.check_prerequisites(skip_checkpoint_check=skip_checkpoint_check):
            print("\n✗ Prerequisites not met")
            print("Run with --setup-only to install CVE-bench first")
            return 1

    # 设置 CVE-bench
    if args.setup_only or not tester.cvebench_dir.exists():
        tester.setup_cvebench()
        if args.setup_only:
            print("\n✓ CVE-bench setup complete")
            return 0

    # 确定 checkpoint
    checkpoint = args.checkpoint
    if checkpoint is None:
        checkpoint = tester.find_latest_checkpoint()
        if checkpoint is None:
            print("\n✗ No checkpoint found. Please specify --checkpoint")
            return 1
        print(f"\nUsing latest checkpoint: {checkpoint}")

    # 解析参数
    variants = args.variants.split(",") if args.variants else None
    challenges = args.challenges.split(",") if args.challenges else None

    # 运行评估
    result = tester.run_evaluation(
        checkpoint=str(checkpoint),
        variants=variants,
        challenges=challenges,
        max_messages=args.max_messages
    )

    if result.get("returncode") == 0:
        print("\n✓ Evaluation completed successfully!")
    else:
        print(f"\n✗ Evaluation completed with return code: {result.get('returncode')}")

    return result.get("returncode", 1)


if __name__ == "__main__":
    sys.exit(main())
