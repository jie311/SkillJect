#!/bin/bash
# 获取 rpk connect 版本号
# 用法: ./rpk-version.sh
# 输出: 版本号（例如 "4.72.0"）

set -euo pipefail

rpk connect --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1
