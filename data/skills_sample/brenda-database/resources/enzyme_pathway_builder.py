"""
用于逆向合成分析的酶通路构建器

此模块提供使用 BRENDA 数据库信息构建酶通路和
逆向合成树的工具。

主要功能：
- 查找目标产物的酶通路
- 从产物构建逆向合成树
- 建议酶替换和替代方案
- 计算通路可行性和热力学
- 优化通路条件（pH、温度、辅因子）
- 生成详细的通路报告
- 支持代谢工程和合成生物学

安装：
    uv pip install networkx matplotlib pandas

用法：
    from scripts.enzyme_pathway_builder import find_pathway_for_product, build_retrosynthetic_tree

    pathway = find_pathway_for_product("lactate", max_steps=3)
    tree = build_retrosynthetic_tree("lactate", depth=2)
"""

import re
import json
import time
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    print("警告: 未安装 networkx。使用以下命令安装: uv pip install networkx")
    NETWORKX_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    print("警告: 未安装 pandas。使用以下命令安装: uv pip install pandas")
    PANDAS_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    print("警告: 未安装 matplotlib。使用以下命令安装: uv pip install matplotlib")
    MATPLOTLIB_AVAILABLE = False

try:
    from brenda_queries import (
        search_enzymes_by_product, search_enzymes_by_substrate,
        get_environmental_parameters, compare_across_organisms,
        get_substrate_specificity, get_cofactor_requirements,
        find_thermophilic_homologs, find_ph_stable_variants
    )
    BRENDA_QUERIES_AVAILABLE = True
except ImportError:
    print("警告: brenda_queries 不可用")
    BRENDA_QUERIES_AVAILABLE = False


def validate_dependencies():
    """验证已安装必需的依赖项。"""
    missing = []
    if not NETWORKX_AVAILABLE:
        missing.append("networkx")
    if not PANDAS_AVAILABLE:
        missing.append("pandas")
    if not MATPLOTLIB_AVAILABLE:
        missing.append("matplotlib")
    if not BRENDA_QUERIES_AVAILABLE:
        missing.append("brenda_queries")
    if missing:
        raise ImportError(f"缺少必需的依赖项: {', '.join(missing)}")


class PathwayNode:
    """表示通路中的化合物节点。"""
    
    def __init__(self, name: str, node_type: str = "intermediate"):
        """
        初始化通路节点。
        
        参数：
            name：化合物名称
            node_type：节点类型（'product'、'intermediate'、'starting_material'）
        """
        self.name = name
        self.node_type = node_type
        self.enzymes = []
        self.reactions = []
    
    def add_enzyme(self, ec_number: str, organism: str = None):
        """添加能够转化此化合物的酶。"""
        enzyme_info = {"ec_number": ec_number}
        if organism:
            enzyme_info["organism"] = organism
        self.enzymes.append(enzyme_info)
    
    def to_dict(self) -> Dict:
        """转换为字典表示。"""
        return {
            "name": self.name,
            "type": self.node_type,
            "enzymes": self.enzymes,
            "reactions": self.reactions
        }


class EnzymaticReaction:
    """表示酶促反应。"""
    
    def __init__(self, ec_number: str, substrates: List[str], products: List[str],
                 organism: str = None):
        """
        初始化酶促反应。
        
        参数：
            ec_number：EC 编号
            substrates：底物列表
            products：产物列表
            organism：生物体
        """
        self.ec_number = ec_number
        self.substrates = substrates
        self.products = products
        self.organism = organism
        self.yield_estimate = None
        self.conditions = {}
    
    def get_equation(self) -> str:
        """获取反应方程式。"""
        left = " + ".join(self.substrates)
        right = " + ".join(self.products)
        return f"{left} -> {right}"
    
    def to_dict(self) -> Dict:
        """转换为字典表示。"""
        return {
            "ec_number": self.ec_number,
            "equation": self.get_equation(),
            "substrates": self.substrates,
            "products": self.products,
            "organism": self.organism,
            "yield": self.yield_estimate,
            "conditions": self.conditions
        }


def find_pathway_for_product(target_product: str, max_steps: int = 3,
                            preferred_organisms: List[str] = None) -> Dict[str, Any]:
    """
    查找目标产物的酶通路。
    
    参数：
        target_product：目标产物名称
        max_steps：最大反应步数
        preferred_organisms：首选的生物体列表
    
    返回：
        包含通路信息的字典
    """
    validate_dependencies()
    
    pathway = {
        "target": target_product,
        "steps": [],
        "intermediates": [],
        "starting_materials": [],
        "enzymes": set(),
        "graph": None
    }
    
    if preferred_organisms is None:
        preferred_organisms = ["大肠杆菌", "酿酒酵母", "智人"]
    
    try:
        # 创建有向图表示通路
        G = nx.DiGraph()
        G.add_node(target_product, type="product")
        
        current_compounds = [target_product]
        
        for step in range(max_steps):
            next_compounds = []
            
            for compound in current_compounds:
                # 查找可生成此化合物的酶
                enzymes = search_enzymes_by_product(compound, limit=50)
                
                for enzyme in enzymes:
                    ec_number = enzyme.get("ec_number")
                    organism = enzyme.get("organism", "")
                    
                    # 按生物体过滤
                    if preferred_organisms:
                        if not any(pref.lower() in organism.lower() for pref in preferred_organisms):
                            continue
                    
                    # 解析反应以获取底物
                    equation = enzyme.get("equation", "")
                    substrates = extract_substrates_from_equation(equation, compound)
                    
                    if substrates:
                        reaction = EnzymaticReaction(
                            ec_number=ec_number,
                            substrates=substrates,
                            products=[compound],
                            organism=organism
                        )
                        
                        # 添加到图中
                        for sub in substrates:
                            G.add_node(sub, type="intermediate")
                            G.add_edge(sub, compound, ec_number=ec_number)
                            if sub not in next_compounds and sub not in pathway["intermediates"]:
                                next_compounds.append(sub)
                        
                        pathway["steps"].append({
                            "step": step + 1,
                            "reaction": reaction.to_dict(),
                            "product": compound
                        })
                        pathway["enzymes"].add(ec_number)
            
            if next_compounds:
                pathway["intermediates"].extend(next_compounds)
            current_compounds = next_compounds
            
            if not current_compounds:
                break
        
        # 最后的化合物是起始原料
        pathway["starting_materials"] = current_compounds
        for sm in current_compounds:
            if sm in G:
                G.nodes[sm]["type"] = "starting_material"
        
        pathway["enzymes"] = list(pathway["enzymes"])
        pathway["graph"] = G
        
    except Exception as e:
        print(f"查找通路时出错: {e}")
    
    return pathway


def build_retrosynthetic_tree(target_molecule: str, depth: int = 2,
                              branching_factor: int = 3) -> nx.DiGraph:
    """
    从目标分子构建逆向合成树。
    
    参数：
        target_molecule：目标分子名称
        depth：树的深度（反应步数）
        branching_factor：每个节点保留的前体数量
    
    返回：
        NetworkX 有向图
    """
    validate_dependencies()
    
    tree = nx.DiGraph()
    tree.add_node(target_molecule, layer=0, type="target")
    
    current_layer = [target_molecule]
    
    for layer in range(1, depth + 1):
        next_layer = []
        
        for molecule in current_layer:
            # 查找可生成此分子的酶
            enzymes = search_enzymes_by_product(molecule, limit=100)
            
            # 收集前体
            precursors = {}
            for enzyme in enzymes:
                equation = enzyme.get("equation", "")
                molecule_precursors = extract_substrates_from_equation(equation, molecule)
                
                for precursor in molecule_precursors:
                    if precursor not in precursors:
                        precursors[precursor] = []
                    ec_number = enzyme.get("ec_number", "Unknown")
                    organism = enzyme.get("organism", "Unknown")
                    precursors[precursor].append({
                        "ec_number": ec_number,
                        "organism": organism
                    })
            
            # 限制分支因子
            top_precursors = list(precursors.keys())[:branching_factor]
            
            for precursor in top_precursors:
                tree.add_node(precursor, layer=layer, type="precursor")
                
                # 添加带酶信息的边
                enzymes_list = precursors[precursor]
                for enzyme_info in enzymes_list:
                    tree.add_edge(
                        precursor,
                        molecule,
                        ec_number=enzyme_info["ec_number"],
                        organism=enzyme_info["organism"]
                    )
                
                if precursor not in next_layer:
                    next_layer.append(precursor)
        
        current_layer = next_layer
    
    return tree


def extract_substrates_from_equation(equation: str, product: str) -> List[str]:
    """
    从反应方程式中提取底物。
    
    参数：
        equation：反应方程式字符串
        product：产物名称
    
    返回：
        底物列表
    """
    # 简化实现：假设方程式格式为 "A + B -> C + D"
    if "->" in equation:
        left, right = equation.split("->")
    elif "=>" in equation:
        left, right = equation.split("=>")
    else:
        return []
    
    # 检查产物是否在右侧
    if product.lower() not in right.lower():
        return []
    
    # 从左侧提取底物
    substrates = [s.strip() for s in left.split("+")]
    
    return substrates


def suggest_enzyme_replacements(ec_number: str, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根据特定标准建议酶替换。
    
    参数：
        ec_number：要替换的 EC 编号
        criteria：替换标准（温度稳定性、pH 范围等）
    
    返回：
        替代酶列表
    """
    validate_dependencies()
    
    alternatives = []
    
    try:
        # 获取跨生物体的比较数据
        all_organisms = ["大肠杆菌", "酿酒酵母", "枯草芽孢杆菌", "智人", "小家鼠"]
        comparison = compare_across_organisms(ec_number, all_organisms)
        
        for org_data in comparison:
            if org_data.get("data_points", 0) == 0:
                continue
            
            organism = org_data["organism"]
            score = 0
            reasons = []
            
            # 检查温度标准
            if "min_temperature" in criteria:
                opt_temp = org_data.get("optimal_temperature", 0)
                if opt_temp and opt_temp >= criteria["min_temperature"]:
                    score += 10
                    reasons.append(f"温度耐受性: {opt_temp}°C")
            
            # 检查 pH 标准
            if "ph_range" in criteria:
                opt_ph = org_data.get("optimal_ph", 0)
                ph_min, ph_max = criteria["ph_range"]
                if opt_ph and ph_min <= opt_ph <= ph_max:
                    score += 10
                    reasons.append(f"pH 兼容性: {opt_ph}")
            
            # 检查数据可用性
            data_points = org_data.get("data_points", 0)
            if data_points >= 5:
                score += 5
                reasons.append(f"充分表征（{data_points} 个数据点）")
            
            if score > 0:
                alternatives.append({
                    "organism": organism,
                    "ec_number": ec_number,
                    "score": score,
                    "reasons": reasons,
                    "average_km": org_data.get("average_km"),
                    "optimal_temperature": org_data.get("optimal_temperature"),
                    "optimal_ph": org_data.get("optimal_ph")
                })
        
        # 按分数排序
        alternatives.sort(key=lambda x: x["score"], reverse=True)
        
    except Exception as e:
        print(f"建议酶替换时出错: {e}")
    
    return alternatives


def calculate_pathway_feasibility(pathway: Dict[str, Any]) -> Dict[str, Any]:
    """
    计算酶通路的可行性评分。
    
    参数：
        pathway：通路字典
    
    返回：
        可行性分析字典
    """
    feasibility = {
        "overall_score": 0,
        "factors": {},
        "recommendations": []
    }
    
    try:
        # 因子 1：通路完整性
        steps = len(pathway.get("steps", []))
        if steps > 0:
            completeness_score = min(100, steps * 20)
            feasibility["factors"]["completeness"] = {
                "score": completeness_score,
                "description": f"识别出 {steps} 个反应步骤"
            }
        else:
            feasibility["factors"]["completeness"] = {
                "score": 0,
                "description": "未识别出反应步骤"
            }
        
        # 因子 2：酶可用性
        enzymes = pathway.get("enzymes", [])
        if enzymes:
            enzyme_score = min(100, len(enzymes) * 10)
            feasibility["factors"]["enzyme_availability"] = {
                "score": enzyme_score,
                "description": f"识别出 {len(enzymes)} 个唯一酶"
            }
        else:
            feasibility["factors"]["enzyme_availability"] = {
                "score": 0,
                "description": "未识别出酶"
            }
        
        # 因子 3：起始材料复杂度
        starting_materials = pathway.get("starting_materials", [])
        if starting_materials:
            # 简单启发式：较少的起始材料 = 更简单
            complexity_score = max(0, 100 - len(starting_materials) * 10)
            feasibility["factors"]["complexity"] = {
                "score": complexity_score,
                "description": f"需要 {len(starting_materials)} 种起始材料"
            }
        
        # 计算总体评分
        if feasibility["factors"]:
            overall = sum(f["score"] for f in feasibility["factors"].values()) / len(feasibility["factors"])
            feasibility["overall_score"] = round(overall, 1)
        
        # 生成建议
        if feasibility["overall_score"] < 50:
            feasibility["recommendations"].append("通路可行性低。考虑替代路线。")
        elif feasibility["overall_score"] < 75:
            feasibility["recommendations"].append("通路中等可行。建议进行实验验证。")
        else:
            feasibility["recommendations"].append("通路高度可行。考虑扩大规模。")
    
    except Exception as e:
        print(f"计算通路可行性时出错: {e}")
    
    return feasibility


def optimize_pathway_conditions(pathway: Dict[str, Any],
                                 target_ph: float = None,
                                 target_temp: float = None) -> Dict[str, Any]:
    """
    优化通路的反应条件。
    
    参数：
        pathway：通路字典
        target_ph：目标 pH（如果为 None，则自动选择）
        target_temp：目标温度（如果为 None，则自动选择）
    
    返回：
        优化条件字典
    """
    optimization = {
        "ph": target_ph,
        "temperature": target_temp,
        "enzyme_adjustments": {},
        "compromises": []
    }
    
    try:
        enzymes = pathway.get("enzymes", [])
        
        if not enzymes:
            return optimization
        
        # 收集所有酶的环境参数
        all_ph_values = []
        all_temp_values = []
        
        for ec in enzymes:
            env = get_environmental_parameters(ec)
            if env.get("optimal_ph"):
                all_ph_values.append(env["optimal_ph"])
            if env.get("optimal_temperature"):
                all_temp_values.append(env["optimal_temperature"])
        
        # 计算折衷条件
        if all_ph_values and not target_ph:
            optimization["ph"] = sum(all_ph_values) / len(all_ph_values)
        
        if all_temp_values and not target_temp:
            optimization["temperature"] = sum(all_temp_values) / len(all_temp_values)
        
        # 识别需要调整的酶
        for ec in enzymes:
            env = get_environmental_parameters(ec)
            adjustments = []
            
            if optimization["ph"] and env.get("optimal_ph"):
                ph_diff = abs(env["optimal_ph"] - optimization["ph"])
                if ph_diff > 1.0:
                    adjustments.append(f"pH 偏离最佳值 {ph_diff:.1f}")
            
            if optimization["temperature"] and env.get("optimal_temperature"):
                temp_diff = abs(env["optimal_temperature"] - optimization["temperature"])
                if temp_diff > 5.0:
                    adjustments.append(f"温度偏离最佳值 {temp_diff:.1f}°C")
            
            if adjustments:
                optimization["enzyme_adjustments"][ec] = adjustments
        
        # 添加折衷说明
        if optimization["enzyme_adjustments"]:
            optimization["compromises"].append(
                f"选择的条件是 {len(enzymes)} 个酶之间的折衷"
            )
    
    except Exception as e:
        print(f"优化通路条件时出错: {e}")
    
    return optimization


def generate_pathway_report(pathway: Dict[str, Any],
                            feasibility: Dict[str, Any] = None,
                            optimization: Dict[str, Any] = None) -> str:
    """
    生成详细的通路报告。
    
    参数：
        pathway：通路字典
        feasibility：可行性分析
        optimization：条件优化
    
    返回：
        格式化的报告字符串
    """
    report = []
    report.append("=" * 70)
    report.append("酶通路分析报告")
    report.append("=" * 70)
    report.append("")
    
    # 目标产物
    report.append(f"目标产物: {pathway.get('target', 'Unknown')}")
    report.append("")
    
    # 反应步骤
    report.append("反应步骤:")
    report.append("-" * 70)
    for step in pathway.get("steps", []):
        report.append(f"步骤 {step['step']}: {step['reaction']['equation']}")
        report.append(f"  EC: {step['reaction']['ec_number']}")
        report.append(f"  生物体: {step['reaction'].get('organism', 'Unknown')}")
        report.append("")
    
    # 起始材料
    starting_materials = pathway.get("starting_materials", [])
    if starting_materials:
        report.append("所需起始材料:")
        for sm in starting_materials:
            report.append(f"  - {sm}")
        report.append("")
    
    # 涉及的酶
    enzymes = pathway.get("enzymes", [])
    if enzymes:
        report.append(f"涉及的酶 ({len(enzymes)} 个唯一酶):")
        for ec in enzymes:
            report.append(f"  - {ec}")
        report.append("")
    
    # 可行性分析
    if feasibility:
        report.append("可行性分析:")
        report.append("-" * 70)
        report.append(f"总体评分: {feasibility['overall_score']}/100")
        for factor, data in feasibility["factors"].items():
            report.append(f"  {factor}: {data['score']}/100 - {data['description']}")
        for rec in feasibility.get("recommendations", []):
            report.append(f"  建议: {rec}")
        report.append("")
    
    # 条件优化
    if optimization:
        report.append("条件优化:")
        report.append("-" * 70)
        if optimization.get("ph"):
            report.append(f"  推荐 pH: {optimization['ph']:.1f}")
        if optimization.get("temperature"):
            report.append(f"  推荐温度: {optimization['temperature']:.1f}°C")
        for ec, adjustments in optimization.get("enzyme_adjustments", {}).items():
            report.append(f"  {ec}: {', '.join(adjustments)}")
        report.append("")
    
    report.append("=" * 70)
    
    return "\n".join(report)


def visualize_pathway(pathway: Dict[str, Any], output_file: str = None):
    """
    可视化酶通路。
    
    参数：
        pathway：通路字典
        output_file：输出文件路径（可选）
    """
    validate_dependencies()
    
    if not MATPLOTLIB_AVAILABLE:
        print("可视化需要 matplotlib")
        return
    
    try:
        G = pathway.get("graph")
        if not G or not isinstance(G, nx.DiGraph):
            print("通路中没有有效的图数据")
            return
        
        plt.figure(figsize=(12, 8))
        
        # 使用层次布局
        pos = nx.spring_layout(G, k=2, iterations=50)
        
        # 按节点类型着色
        node_colors = []
        for node in G.nodes():
            node_type = G.nodes[node].get("type", "intermediate")
            if node_type == "product":
                node_colors.append("green")
            elif node_type == "starting_material":
                node_colors.append("blue")
            else:
                node_colors.append("lightgray")
        
        # 绘制图
        nx.draw(G, pos, with_labels=True, node_color=node_colors,
                node_size=2000, font_size=8, font_weight="bold",
                arrowsize=20, edge_color="gray")
        
        plt.title(f"酶通路: {pathway.get('target', 'Unknown')}")
        plt.axis("off")
        
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")
            print(f"通路图已保存至: {output_file}")
        else:
            plt.show()
        
        plt.close()
        
    except Exception as e:
        print(f"可视化通路时出错: {e}")


def export_pathway_json(pathway: Dict[str, Any], output_file: str):
    """
    将通路导出为 JSON 文件。
    
    参数：
        pathway：通路字典
        output_file：输出文件路径
    """
    try:
        # 将集合转换为列表以便 JSON 序列化
        export_data = pathway.copy()
        if "graph" in export_data:
            # 将 NetworkX 图转换为可序列化的格式
            G = export_data["graph"]
            export_data["graph"] = {
                "nodes": list(G.nodes()),
                "edges": list(G.edges(data=True))
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"通路已导出至: {output_file}")
        
    except Exception as e:
        print(f"导出通路 JSON 时出错: {e}")


# 示例用法
if __name__ == "__main__":
    print("酶通路构建器示例")
    print("=" * 50)
    
    try:
        # 查找通路
        print("\n1. 查找乳酸的通路")
        pathway = find_pathway_for_product("lactate", max_steps=2)
        
        # 可行性分析
        print("\n2. 分析可行性")
        feasibility = calculate_pathway_feasibility(pathway)
        print(f"总体可行性评分: {feasibility['overall_score']}/100")
        
        # 条件优化
        print("\n3. 优化条件")
        optimization = optimize_pathway_conditions(pathway)
        print(f"推荐 pH: {optimization.get('ph')}")
        print(f"推荐温度: {optimization.get('temperature')}°C")
        
        # 生成报告
        print("\n4. 生成报告")
        report = generate_pathway_report(pathway, feasibility, optimization)
        print(report)
        
        # 可视化（如果有 matplotlib）
        if MATPLOTLIB_AVAILABLE:
            print("\n5. 可视化通路")
            visualize_pathway(pathway, "pathway_visualization.png")
        
        # 导出
        print("\n6. 导出 JSON")
        export_pathway_json(pathway, "enzyme_pathway.json")
        
    except Exception as e:
        print(f"示例失败: {e}")
