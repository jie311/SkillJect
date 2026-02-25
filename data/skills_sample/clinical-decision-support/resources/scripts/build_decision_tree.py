#!/usr/bin/env python3
"""
构建 LaTeX/TikZ 格式的临床决策树流程图

从简单的文本或 YAML 描述生成临床决策算法的 LaTeX/TikZ 代码。

依赖: pyyaml (可选，用于 YAML 输入)
"""

import argparse
from pathlib import Path
import json


class DecisionNode:
    """表示临床算法中的决策点。"""
    
    def __init__(self, question, yes_path=None, no_path=None, node_id=None):
        self.question = question
        self.yes_path = yes_path
        self.no_path = no_path
        self.node_id = node_id or self._generate_id(question)
    
    def _generate_id(self, text):
        """从文本生成清晰的节点 ID。"""
        return ''.join(c for c in text if c.isalnum())[:15].lower()


class ActionNode:
    """表示临床算法中的行动/结果。"""
    
    def __init__(self, action, urgency='routine', node_id=None):
        self.action = action
        self.urgency = urgency  # 'urgent'（紧急）、'semiurgent'（半紧急）、'routine'（常规）
        self.node_id = node_id or self._generate_id(action)
    
    def _generate_id(self, text):
        return ''.join(c for c in text if c.isalnum())[:15].lower()


def generate_tikz_header():
    """生成带有样式定义的 TikZ 前言。"""
    
    tikz = """\\documentclass[10pt]{article}
\\usepackage[margin=0.5in, landscape]{geometry}
\\usepackage{tikz}
\\usetikzlibrary{shapes,arrows,positioning}
\\usepackage{xcolor}

% 颜色定义
\\definecolor{urgentred}{RGB}{220,20,60}
\\definecolor{actiongreen}{RGB}{0,153,76}
\\definecolor{decisionyellow}{RGB}{255,193,7}
\\definecolor{routineblue}{RGB}{100,181,246}
\\definecolor{headerblue}{RGB}{0,102,204}

% TikZ 样式
\\tikzstyle{startstop} = [rectangle, rounded corners=8pt, minimum width=3cm, minimum height=1cm, 
                          text centered, draw=black, fill=headerblue!20, font=\\small\\bfseries]
\\tikzstyle{decision} = [diamond, minimum width=3cm, minimum height=1.2cm, text centered, 
                        draw=black, fill=decisionyellow!40, font=\\small, aspect=2, inner sep=0pt,
                        text width=3.5cm]
\\tikzstyle{process} = [rectangle, rounded corners=4pt, minimum width=3.5cm, minimum height=0.9cm, 
                       text centered, draw=black, fill=actiongreen!20, font=\\small]
\\tikzstyle{urgent} = [rectangle, rounded corners=4pt, minimum width=3.5cm, minimum height=0.9cm, 
                      text centered, draw=urgentred, line width=1.5pt, fill=urgentred!15, 
                      font=\\small\\bfseries]
\\tikzstyle{routine} = [rectangle, rounded corners=4pt, minimum width=3.5cm, minimum height=0.9cm, 
                       text centered, draw=black, fill=routineblue!20, font=\\small]
\\tikzstyle{arrow} = [thick,->,>=stealth]
\\tikzstyle{urgentarrow} = [ultra thick,->,>=stealth,color=urgentred]

\\begin{document}

\\begin{center}
{\\Large\\bfseries 临床决策算法}\\\\[10pt]
{\\large [标题待指定]}
\\end{center}

\\vspace{10pt}

\\begin{tikzpicture}[node distance=2.2cm and 3.5cm, auto]

"""
    
    return tikz


def generate_tikz_footer():
    """生成 TikZ 结束代码。"""
    
    tikz = """
\\end{tikzpicture}

\\end{document}
"""
    
    return tikz


def simple_algorithm_to_tikz(algorithm_text, output_file='algorithm.tex'):
    """
    将简单的基于文本的算法转换为 TikZ 流程图。
    
    输入格式（简单的问题-行动对）：
    START: 主诉
    Q1: 存在高风险标准？ -> 是: 立即行动 (紧急) | 否: 继续
    Q2: 风险评分 >= 3？ -> 是: 收治 ICU | 否: 门诊管理 (常规)
    END: 最终结果
    
    参数：
        algorithm_text: 包含算法的多行字符串
        output_file: 保存 .tex 文件的路径
    """
    
    tikz_code = generate_tikz_header()
    
    # 解析算法文本
    lines = [line.strip() for line in algorithm_text.strip().split('\n') if line.strip()]
    
    node_defs = []
    arrow_defs = []
    
    previous_node = None
    node_counter = 0
    
    for line in lines:
        if line.startswith('START:'):
            # 起始节点
            text = line.replace('START:', '').strip()
            node_id = 'start'
            node_defs.append(f"\\node [startstop] ({node_id}) {{{text}}};")
            previous_node = node_id
            node_counter += 1
        
        elif line.startswith('END:'):
            # 结束节点
            text = line.replace('END:', '').strip()
            node_id = 'end'
            
            # 相对于前一个节点定位
            if previous_node:
                node_defs.append(f"\\node [startstop, below=of {previous_node}] ({node_id}) {{{text}}};")
                arrow_defs.append(f"\\draw [arrow] ({previous_node}) -- ({node_id});")
        
        elif line.startswith('Q'):
            # 决策节点
            parts = line.split(':', 1)
            if len(parts) < 2:
                continue
            
            question_part = parts[1].split('->')[0].strip()
            node_id = f'q{node_counter}'
            
            # 添加决策节点
            if previous_node:
                node_defs.append(f"\\node [decision, below=of {previous_node}] ({node_id}) {{{question_part}}};")
                arrow_defs.append(f"\\draw [arrow] ({previous_node}) -- ({node_id});")
            else:
                node_defs.append(f"\\node [decision] ({node_id}) {{{question_part}}};")
            
            # 解析是和否分支
            if '->' in line:
                branches = line.split('->')[1].split('|')
                
                for branch in branches:
                    branch = branch.strip()
                    
                    if branch.startswith('YES:'):
                        yes_action = branch.replace('YES:', '').strip()
                        yes_id = f'yes{node_counter}'
                        
                        # 检查紧急程度
                        if '(URGENT)' in yes_action:
                            style = 'urgent'
                            yes_action = yes_action.replace('(URGENT)', '').strip()
                            arrow_style = 'urgentarrow'
                        elif '(ROUTINE)' in yes_action:
                            style = 'routine'
                            yes_action = yes_action.replace('(ROUTINE)', '').strip()
                            arrow_style = 'arrow'
                        else:
                            style = 'process'
                            arrow_style = 'arrow'
                        
                        node_defs.append(f"\\node [{style}, left=of {node_id}] ({yes_id}) {{{yes_action}}};")
                        arrow_defs.append(f"\\draw [{arrow_style}] ({node_id}) -- node[above] {{是}} ({yes_id});")
                    
                    elif branch.startswith('NO:'):
                        no_action = branch.replace('NO:', '').strip()
                        no_id = f'no{node_counter}'
                        
                        # 检查紧急程度
                        if '(URGENT)' in no_action:
                            style = 'urgent'
                            no_action = no_action.replace('(URGENT)', '').strip()
                            arrow_style = 'urgentarrow'
                        elif '(ROUTINE)' in no_action:
                            style = 'routine'
                            no_action = no_action.replace('(ROUTINE)', '').strip()
                            arrow_style = 'arrow'
                        else:
                            style = 'process'
                            arrow_style = 'arrow'
                        
                        node_defs.append(f"\\node [{style}, right=of {node_id}] ({no_id}) {{{no_action}}};")
                        arrow_defs.append(f"\\draw [{arrow_style}] ({node_id}) -- node[above] {{否}} ({no_id});")
            
            previous_node = node_id
            node_counter += 1
    
    # 将所有节点和箭头添加到 TikZ
    tikz_code += '\n'.join(node_defs) + '\n\n'
    tikz_code += '% 箭头\n'
    tikz_code += '\n'.join(arrow_defs) + '\n'
    
    tikz_code += generate_tikz_footer()
    
    # 保存到文件
    with open(output_file, 'w') as f:
        f.write(tikz_code)
    
    print(f"TikZ 流程图已保存至: {output_file}")
    print(f"使用以下命令编译: pdflatex {output_file}")
    
    return tikz_code


def json_to_tikz(json_file, output_file='algorithm.tex'):
    """
    将 JSON 决策树规范转换为 TikZ 流程图。
    
    JSON 格式:
    {
        "title": "算法标题",
        "nodes": {
            "start": {"type": "start", "text": "患者表现"},
            "q1": {"type": "decision", "text": "符合标准？", "yes": "action1", "no": "q2"},
            "action1": {"type": "action", "text": "立即干预", "urgency": "urgent"},
            "q2": {"type": "decision", "text": "评分 >= 3？", "yes": "action2", "no": "action3"},
            "action2": {"type": "action", "text": "收治 ICU"},
            "action3": {"type": "action", "text": "门诊", "urgency": "routine"}
        },
        "start_node": "start"
    }
    """
    
    with open(json_file, 'r') as f:
        spec = json.load(f)
    
    tikz_code = generate_tikz_header()
    
    # 替换标题
    title = spec.get('title', '临床决策算法')
    tikz_code = tikz_code.replace('[标题待指定]', title)
    
    nodes = spec['nodes']
    start_node = spec.get('start_node', 'start')
    
    # 生成节点（简化布局 - 垂直）
    node_defs = []
    arrow_defs = []
    
    # 跟踪定位
    previous_node = None
    level = 0
    
    def add_node(node_id, position_rel=None):
        """递归添加节点。"""
        
        if node_id not in nodes:
            return
        
        node = nodes[node_id]
        node_type = node['type']
        text = node['text']
        
        # 确定 TikZ 样式
        if node_type == 'start' or node_type == 'end':
            style = 'startstop'
        elif node_type == 'decision':
            style = 'decision'
        elif node_type == 'action':
            urgency = node.get('urgency', 'normal')
            if urgency == 'urgent':
                style = 'urgent'
            elif urgency == 'routine':
                style = 'routine'
            else:
                style = 'process'
        else:
            style = 'process'
        
        # 定位节点
        if position_rel:
            node_def = f"\\node [{style}, {position_rel}] ({node_id}) {{{text}}};"
        else:
            node_def = f"\\node [{style}] ({node_id}) {{{text}}};"
        
        node_defs.append(node_def)
        
        # 为决策节点添加箭头
        if node_type == 'decision':
            yes_target = node.get('yes')
            no_target = node.get('no')
            
            if yes_target:
                # 根据目标紧急程度确定箭头样式
                target_node = nodes.get(yes_target, {})
                arrow_style = 'urgentarrow' if target_node.get('urgency') == 'urgent' else 'arrow'
                arrow_defs.append(f"\\draw [{arrow_style}] ({node_id}) -| node[near start, above] {{是}} ({yes_target});")
            
            if no_target:
                target_node = nodes.get(no_target, {})
                arrow_style = 'urgentarrow' if target_node.get('urgency') == 'urgent' else 'arrow'
                arrow_defs.append(f"\\draw [{arrow_style}] ({node_id}) -| node[near start, above] {{否}} ({no_target});")
    
    # 简单布局 - 仅列出节点（复杂树手动定位效果更好）
    for node_id in nodes.keys():
        add_node(node_id)
    
    tikz_code += '\n'.join(node_defs) + '\n\n'
    tikz_code += '% 箭头\n'
    tikz_code += '\n'.join(arrow_defs) + '\n'
    
    tikz_code += generate_tikz_footer()
    
    # 保存
    with open(output_file, 'w') as f:
        f.write(tikz_code)
    
    print(f"TikZ 流程图已保存至: {output_file}")
    return tikz_code


def create_example_json():
    """创建用于测试的示例 JSON 规范。"""
    
    example = {
        "title": "急性胸痛管理算法",
        "nodes": {
            "start": {
                "type": "start",
                "text": "伴有\\n胸痛的患者"
            },
            "q1": {
                "type": "decision",
                "text": "STEMI\\n标准？",
                "yes": "stemi_action",
                "no": "q2"
            },
            "stemi_action": {
                "type": "action",
                "text": "激活导管室\\n阿司匹林、肝素\\n直接 PCI",
                "urgency": "urgent"
            },
            "q2": {
                "type": "decision",
                "text": "高危\\n特征？",
                "yes": "admit",
                "no": "q3"
            },
            "admit": {
                "type": "action",
                "text": "收治 CCU\\n系列肌钙蛋白\\n早期血管造影"
            },
            "q3": {
                "type": "decision",
                "text": "TIMI\\n评分 0-1？",
                "yes": "lowrisk",
                "no": "moderate"
            },
            "lowrisk": {
                "type": "action",
                "text": "观察 6-12 小时\\n负荷试验\\n门诊随访",
                "urgency": "routine"
            },
            "moderate": {
                "type": "action",
                "text": "收治心电监护\\n药物治疗\\n风险分层"
            }
        },
        "start_node": "start"
    }
    
    return example


def main():
    parser = argparse.ArgumentParser(description='构建临床决策树流程图')
    parser.add_argument('-i', '--input', type=str, default=None,
                       help='输入文件（JSON 格式）')
    parser.add_argument('-o', '--output', type=str, default='clinical_algorithm.tex',
                       help='输出 .tex 文件')
    parser.add_argument('--example', action='store_true',
                       help='生成示例算法')
    parser.add_argument('--text', type=str, default=None,
                       help='简单文本算法（参见文档字符串中的格式）')
    
    args = parser.parse_args()
    
    if args.example:
        print("正在生成示例算法...")
        example_spec = create_example_json()
        
        # 保存示例 JSON
        with open('example_algorithm.json', 'w') as f:
            json.dump(example_spec, f, indent=2)
        print("示例 JSON 已保存至: example_algorithm.json")
        
        # 从示例生成 TikZ
        json_to_tikz('example_algorithm.json', args.output)
    
    elif args.text:
        print("正在从文本生成算法...")
        simple_algorithm_to_tikz(args.text, args.output)
    
    elif args.input:
        print(f"正在从 {args.input} 生成算法...")
        if args.input.endswith('.json'):
            json_to_tikz(args.input, args.output)
        else:
            with open(args.input, 'r') as f:
                text = f.read()
            simple_algorithm_to_tikz(text, args.output)
    
    else:
        print("未提供输入。使用 --example 生成示例，--text 用于简单文本，或 -i 用于 JSON 输入。")
        print("\n简单文本格式:")
        print("START: 患者表现")
        print("Q1: 符合标准？ -> 是: 行动 (紧急) | 否: 继续")
        print("Q2: 评分 >= 3？ -> 是: 收治 | 否: 门诊 (常规)")
        print("END: 随访")


if __name__ == '__main__':
    main()


# 示例用法:
# python build_decision_tree.py --example
# python build_decision_tree.py -i algorithm_spec.json -o my_algorithm.tex
#
# 然后编译:
# pdflatex clinical_algorithm.tex
