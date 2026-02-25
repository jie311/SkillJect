#!/bin/bash
# 将 bloblang 函数和方法元数据格式化为类别文件
# 用法: ./format-bloblang.sh
# 自动使用技能资源缓存目录

set -euo pipefail

# 获取脚本目录和技能根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 在技能资源中创建输出目录
OUTPUT_DIR="$SKILL_ROOT/resources/cache/bloblref/$("$SCRIPT_DIR/rpk-version.sh")"
mkdir -p "$OUTPUT_DIR"
echo "$OUTPUT_DIR"

# 处理函数和方法
for CATEGORY in bloblang-functions bloblang-methods; do
    rpk connect list --format jsonschema "$CATEGORY" | python3 "$SCRIPT_DIR/format-bloblang.py" --output-dir "$OUTPUT_DIR"
done
