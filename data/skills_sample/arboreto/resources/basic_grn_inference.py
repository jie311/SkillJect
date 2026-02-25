#!/usr/bin/env python3
"""
使用Arboreto进行基本基因调控网络推断示例

该脚本演示了使用GRNBoost2从表达数据推断基因调控网络
的标准工作流程。

使用方法:
    python basic_grn_inference.py <表达文件> <输出文件> [--tf-file TF文件] [--seed 随机种子]

参数:
    expression_file: 表达矩阵文件路径（TSV格式，基因为列）
    output_file: 输出网络文件路径（TSV格式）
    --tf-file: 可选的转录因子文件路径（每行一个）
    --seed: 用于可重复性的随机种子（默认：777）
"""

import argparse
import pandas as pd
from arboreto.algo import grnboost2
from arboreto.utils import load_tf_names


def run_grn_inference(expression_file, output_file, tf_file=None, seed=777):
    """
    使用GRNBoost2运行GRN推断。

    参数:
        expression_file: 表达矩阵TSV文件路径
        output_file: 输出网络文件路径
        tf_file: 可选的TF名称文件路径
        seed: 用于可重复性的随机种子
    """
    print(f"正在从 {expression_file} 加载表达数据...")
    expression_data = pd.read_csv(expression_file, sep='\t')

    print(f"表达矩阵形状: {expression_data.shape}")
    print(f"基因数量: {expression_data.shape[1]}")
    print(f"观测值数量: {expression_data.shape[0]}")

    # 如果提供了TF名称则加载
    tf_names = 'all'
    if tf_file:
        print(f"正在从 {tf_file} 加载转录因子...")
        tf_names = load_tf_names(tf_file)
        print(f"转录因子数量: {len(tf_names)}")

    # 运行GRN推断
    print(f"正在使用seed={seed}运行GRNBoost2...")
    network = grnboost2(
        expression_data=expression_data,
        tf_names=tf_names,
        seed=seed,
        verbose=True
    )

    # 保存结果
    print(f"正在将网络保存到 {output_file}...")
    network.to_csv(output_file, sep='\t', index=False, header=False)

    print(f"完成！网络包含 {len(network)} 条调控链接。")
    print(f"\n前10条调控链接:")
    print(network.head(10).to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='使用GRNBoost2推断基因调控网络'
    )
    parser.add_argument(
        'expression_file',
        help='表达矩阵文件路径（TSV格式，基因为列）'
    )
    parser.add_argument(
        'output_file',
        help='输出网络文件路径（TSV格式）'
    )
    parser.add_argument(
        '--tf-file',
        help='转录因子文件路径（每行一个）',
        default=None
    )
    parser.add_argument(
        '--seed',
        help='用于可重复性的随机种子（默认：777）',
        type=int,
        default=777
    )

    args = parser.parse_args()

    run_grn_inference(
        expression_file=args.expression_file,
        output_file=args.output_file,
        tf_file=args.tf_file,
        seed=args.seed
    )
