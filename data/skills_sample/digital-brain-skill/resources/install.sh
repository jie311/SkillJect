#!/bin/bash
# Digital Brain 安装脚本
# 将 Digital Brain 安装为 Claude Code 技能

set -e

SKILL_NAME="digital-brain"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # 无颜色

echo -e "${BLUE}Digital Brain 安装程序${NC}"
echo "========================"
echo ""

# 检测安装类型
echo "您想在哪里安装 Digital Brain？"
echo ""
echo "1) 全用户（推荐）- ~/.claude/skills/"
echo "2) 仅当前项目   - ./.claude/skills/"
echo "3) 自定义位置"
echo ""
read -p "输入选择 [1-3]: " choice

case $choice in
    1)
        TARGET_DIR="$HOME/.claude/skills/$SKILL_NAME"
        ;;
    2)
        TARGET_DIR="./.claude/skills/$SKILL_NAME"
        ;;
    3)
        read -p "输入自定义路径: " custom_path
        TARGET_DIR="$custom_path/$SKILL_NAME"
        ;;
    *)
        echo "无效选择。退出。"
        exit 1
        ;;
esac

# 创建目标目录
mkdir -p "$(dirname "$TARGET_DIR")"

# 检查是否已存在
if [ -d "$TARGET_DIR" ]; then
    read -p "目录已存在。是否覆盖？[y/N]: " overwrite
    if [ "$overwrite" != "y" ] && [ "$overwrite" != "Y" ]; then
        echo "安装已取消。"
        exit 0
    fi
    rm -rf "$TARGET_DIR"
fi

# 复制文件
echo ""
echo "正在安装到: $TARGET_DIR"
cp -r "$BRAIN_DIR" "$TARGET_DIR"

# 从目标位置移除安装脚本（那里不需要）
rm -f "$TARGET_DIR/scripts/install.sh"

echo ""
echo -e "${GREEN}安装完成！${NC}"
echo ""
echo "后续步骤："
echo "1. 导航到您的 Digital Brain: cd $TARGET_DIR"
echo "2. 从 identity/voice.md 开始 - 定义您的声音"
echo "3. 填写 identity/brand.md - 您的定位"
echo "4. 添加联系人到 network/contacts.jsonl"
echo "5. 在 content/ideas.jsonl 中捕获想法"
echo ""
echo "Claude Code 将自动发现该技能。"
echo "尝试: '帮我用我的声音写一篇文章'"
echo ""
