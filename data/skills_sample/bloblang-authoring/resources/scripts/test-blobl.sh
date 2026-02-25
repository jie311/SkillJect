#!/bin/bash
# 使用输入数据测试 Bloblang 脚本
# 用法: ./test-blobl.sh <目录>
#
# 目录中需要的文件：
#   - data.json: 输入 JSON 数据（每行一条消息）
#   - script.blobl: Bloblang 转换脚本

set -euo pipefail

DIR="${1:?错误: 需要目录参数}"

# 验证目录和文件是否存在
if [[ ! -d "$DIR" ]]; then
    echo "错误: 目录 '$DIR' 不存在" >&2
    exit 1
fi
if [[ ! -f "$DIR/data.json" ]]; then
    echo "错误: 未找到 $DIR/data.json" >&2
    exit 1
fi
if [[ ! -f "$DIR/script.blobl" ]]; then
    echo "错误: 未找到 $DIR/script.blobl" >&2
    exit 1
fi

# 使用 jq 压缩 JSON 并通过管道传给 rpk connect blobl
jq -c < "$DIR/data.json" | rpk connect blobl --pretty -f "$DIR/script.blobl"
