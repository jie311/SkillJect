#!/usr/bin/env python3
"""
biomni 环境配置的交互式设置脚本

此脚本帮助用户设置：
1. 带有必需依赖项的 Conda 环境
2. LLM 提供商的 API 密钥
3. 数据湖目录配置
4. MCP 服务器设置（可选）

用法：
    python setup_environment.py
"""

import os
import sys
import subprocess
from pathlib import Path
from typing import Dict, Optional


def check_conda_installed() -> bool:
    """检查系统是否可使用 conda。"""
    try:
        subprocess.run(
            ['conda', '--version'],
            capture_output=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def setup_conda_environment():
    """引导用户完成 conda 环境设置。"""
    print("\n=== Conda 环境设置 ===")

    if not check_conda_installed():
        print("❌ 未找到 Conda。请安装 Miniconda 或 Anaconda:")
        print("   https://docs.conda.io/en/latest/miniconda.html")
        return False

    print("✓ 已安装 Conda")

    # 检查 biomni_e1 环境是否存在
    result = subprocess.run(
        ['conda', 'env', 'list'],
        capture_output=True,
        text=True
    )

    if 'biomni_e1' in result.stdout:
        print("✓ biomni_e1 环境已存在")
        return True

    print("\n正在创建 biomni_e1 conda 环境...")
    print("这将安装 Python 3.10 和必需的依赖项。")

    response = input("继续？[y/N]: ").strip().lower()
    if response != 'y':
        print("跳过 conda 环境设置")
        return False

    try:
        # 创建 conda 环境
        subprocess.run(
            ['conda', 'create', '-n', 'biomni_e1', 'python=3.10', '-y'],
            check=True
        )

        print("\n✓ Conda 环境创建成功")
        print("\n激活方式: conda activate biomni_e1")
        print("然后安装 biomni: pip install biomni --upgrade")
        return True

    except subprocess.CalledProcessError as e:
        print(f"❌ 创建 conda 环境失败: {e}")
        return False


def setup_api_keys() -> Dict[str, str]:
    """交互式 API 密钥配置。"""
    print("\n=== API 密钥配置 ===")
    print("Biomni 支持多个 LLM 提供商。")
    print("至少配置一个提供商。")

    api_keys = {}

    # Anthropic（推荐）
    print("\n1. Anthropic Claude（推荐）")
    print("   从以下网址获取您的 API 密钥: https://console.anthropic.com/")
    anthropic_key = input("   输入 ANTHROPIC_API_KEY（或按 Enter 跳过）: ").strip()
    if anthropic_key:
        api_keys['ANTHROPIC_API_KEY'] = anthropic_key

    # OpenAI
    print("\n2. OpenAI")
    print("   从以下网址获取您的 API 密钥: https://platform.openai.com/api-keys")
    openai_key = input("   输入 OPENAI_API_KEY（或按 Enter 跳过）: ").strip()
    if openai_key:
        api_keys['OPENAI_API_KEY'] = openai_key

    # Google Gemini
    print("\n3. Google Gemini")
    print("   从以下网址获取您的 API 密钥: https://makersuite.google.com/app/apikey")
    google_key = input("   输入 GOOGLE_API_KEY（或按 Enter 跳过）: ").strip()
    if google_key:
        api_keys['GOOGLE_API_KEY'] = google_key

    # Groq
    print("\n4. Groq")
    print("   从以下网址获取您的 API 密钥: https://console.groq.com/keys")
    groq_key = input("   输入 GROQ_API_KEY（或按 Enter 跳过）: ").strip()
    if groq_key:
        api_keys['GROQ_API_KEY'] = groq_key

    if not api_keys:
        print("\n⚠️  未配置 API 密钥。您至少需要一个才能使用 biomni。")
        return {}

    return api_keys


def save_api_keys(api_keys: Dict[str, str], method: str = 'env_file'):
    """使用指定方法保存 API 密钥。"""
    if method == 'env_file':
        env_file = Path.cwd() / '.env.example'

        # 读取现有的 .env.example（如果存在）
        existing_vars = {}
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, val = line.split('=', 1)
                            existing_vars[key.strip()] = val.strip()

        # 更新为新密钥
        existing_vars.update(api_keys)

        # 写入 .env.example
        with open(env_file, 'w') as f:
            f.write("# Biomni API 密钥\n")
            f.write(f"# 由 setup_environment.py 生成\n\n")
            for key, value in existing_vars.items():
                f.write(f"{key}={value}\n")

        print(f"\n✓ API 密钥已保存至 {env_file}")
        print("  在此目录中运行 biomni 时将自动加载密钥")

    elif method == 'shell_export':
        shell_file = Path.home() / '.bashrc'  # 或 .zshrc（对于 zsh 用户）

        print("\n📋 将以下行添加到您的 shell 配置中:")
        for key, value in api_keys.items():
            print(f"   export {key}=\"{value}\"")

        print(f"\n然后运行: source {shell_file}")


def setup_data_directory() -> Optional[Path]:
    """配置 biomni 数据湖目录。"""
    print("\n=== 数据湖配置 ===")
    print("Biomni 需要约 11GB 空间用于集成生物医学数据库。")

    default_path = Path.cwd() / 'biomni_data'
    print(f"\n默认位置: {default_path}")

    response = input("使用默认位置？[Y/n]: ").strip().lower()

    if response == 'n':
        custom_path = input("输入自定义路径: ").strip()
        data_path = Path(custom_path).expanduser().resolve()
    else:
        data_path = default_path

    # 如果目录不存在则创建
    data_path.mkdir(parents=True, exist_ok=True)

    print(f"\n✓ 数据目录已配置: {data_path}")
    print("  数据将在首次使用时自动下载")

    return data_path


def test_installation(data_path: Path):
    """使用简单查询测试 biomni 安装。"""
    print("\n=== 安装测试 ===")
    print("正在使用简单查询测试 biomni 安装...")

    response = input("运行测试？[Y/n]: ").strip().lower()
    if response == 'n':
        print("跳过测试")
        return

    test_code = f'''
import os
from biomni.agent import A1

# 使用环境变量作为 API 密钥
agent = A1(path='{data_path}', llm='claude-sonnet-4-20250514')

# 简单测试查询
result = agent.go("TP53 基因的主要功能是什么？")
print("测试结果:", result)
'''

    test_file = Path('test_biomni.py')
    with open(test_file, 'w') as f:
        f.write(test_code)

    print(f"\n测试脚本已创建: {test_file}")
    print("正在运行测试...")

    try:
        subprocess.run([sys.executable, str(test_file)], check=True)
        print("\n✓ 测试成功完成！")
        test_file.unlink()  # 清理测试文件
    except subprocess.CalledProcessError:
        print("\n❌ 测试失败。检查您的配置。")
        print(f"   测试脚本已保存为 {test_file} 用于调试")


def generate_example_script(data_path: Path):
    """生成示例用法脚本。"""
    example_code = f'''#!/usr/bin/env python3
"""
Biomni 用法示例脚本

演示基本的 biomni 使用模式。
根据您的研究任务修改此脚本。
"""

from biomni.agent import A1

# 初始化代理
agent = A1(
    path='{data_path}',
    llm='claude-sonnet-4-20250514'  # 或您首选的 LLM
)

# 示例 1：简单基因查询
print("示例 1: 基因功能查询")
result = agent.go("""
BRCA1 基因的主要功能是什么？
包括以下信息:
- 分子功能
- 相关疾病
- 蛋白质相互作用
""")
print(result)
print("-" * 80)

# 示例 2: 数据分析
print("\\n示例 2: GWAS 分析")
result = agent.go("""
解释如何分析 GWAS 摘要统计数据进行:
1. 识别全基因组显著变异
2. 将变异映射到基因
3. 通路富集分析
""")
print(result)

# 保存对话历史
agent.save_conversation_history("example_results.pdf")
print("\\n结果已保存至 example_results.pdf")
'''

    example_file = Path('example_biomni_usage.py')
    with open(example_file, 'w') as f:
        f.write(example_code)

    print(f"\n✓ 示例脚本已创建: {example_file}")


def main():
    """主设置流程。"""
    print("=" * 60)
    print("Biomni 环境设置")
    print("=" * 60)

    # 步骤 1：Conda 环境
    conda_success = setup_conda_environment()

    if conda_success:
        print("\n⚠️  记得激活环境:")
        print("   conda activate biomni_e1")
        print("   pip install biomni --upgrade")

    # 步骤 2：API 密钥
    api_keys = setup_api_keys()

    if api_keys:
        print("\n您希望如何存储 API 密钥？")
        print("1. .env.example 文件（推荐，本地于此目录）")
        print("2. Shell 导出（添加到 .bashrc/.zshrc）")

        choice = input("选择 [1/2]: ").strip()

        if choice == '2':
            save_api_keys(api_keys, method='shell_export')
        else:
            save_api_keys(api_keys, method='env_file')

    # 步骤 3：数据目录
    data_path = setup_data_directory()

    # 步骤 4：生成示例脚本
    if data_path:
        generate_example_script(data_path)

    # 步骤 5：测试安装（可选）
    if api_keys and data_path:
        test_installation(data_path)

    # 摘要
    print("\n" + "=" * 60)
    print("设置完成！")
    print("=" * 60)

    if conda_success:
        print("✓ Conda 环境: biomni_e1")

    if api_keys:
        print(f"✓ 已配置 API 密钥: {', '.join(api_keys.keys())}")

    if data_path:
        print(f"✓ 数据目录: {data_path}")

    print("\n下一步:")
    if conda_success:
        print("1. conda activate biomni_e1")
        print("2. pip install biomni --upgrade")
        print("3. 运行 example_biomni_usage.py 进行测试")
    else:
        print("1. 安装 conda/miniconda")
        print("2. 再次运行此脚本")

    print("\n文档，请参阅:")
    print("  - GitHub: https://github.com/snap-stanford/biomni")
    print("  - 论文: https://www.biorxiv.org/content/10.1101/2025.05.30.656746v1")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n设置被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 设置过程中出错: {e}")
        sys.exit(1)
