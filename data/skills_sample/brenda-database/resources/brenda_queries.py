"""
BRENDA 数据库查询工具

此模块提供使用 SOAP API 从 BRENDA 数据库查询和分析
酶数据的高级函数。

主要功能：
- 解析 BRENDA 响应数据条目
- 按底物/产物搜索酶
- 比较不同生物体的酶属性
- 检索动力学参数和环境条件
- 分析底物特异性和抑制
- 支持酶工程和通路设计
- 以多种格式导出数据

安装：
    uv pip install zeep requests pandas

用法：
    from scripts.brenda_queries import search_enzymes_by_substrate, compare_across_organisms

    enzymes = search_enzymes_by_substrate("glucose", limit=20)
    comparison = compare_across_organisms("1.1.1.1", ["E. coli", "S. cerevisiae"])
"""

import re
import time
import json
import csv
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

try:
    from zeep import Client, Settings
    from zeep.exceptions import Fault, TransportError
    ZEEP_AVAILABLE = True
except ImportError:
    print("警告: 未安装 zeep。使用以下命令安装: uv pip install zeep")
    ZEEP_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("警告: 未安装 requests。使用以下命令安装: uv pip install requests")
    REQUESTS_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    print("警告: 未安装 pandas。使用以下命令安装: uv pip install pandas")
    PANDAS_AVAILABLE = False

# 从项目根目录导入 brenda_client
import sys
sys.path.append(str(Path(__file__).parent.parent.parent.parent))

try:
    from brenda_client import get_km_values, get_reactions, call_brenda
    BRENDA_CLIENT_AVAILABLE = True
except ImportError:
    print("警告: brenda_client 不可用")
    BRENDA_CLIENT_AVAILABLE = False


def validate_dependencies():
    """验证已安装必需的依赖项。"""
    missing = []
    if not ZEEP_AVAILABLE:
        missing.append("zeep")
    if not REQUESTS_AVAILABLE:
        missing.append("requests")
    if not PANDAS_AVAILABLE:
        missing.append("pandas")
    if missing:
        raise ImportError(f"缺少必需的依赖项: {', '.join(missing)}")


def parse_km_entry(entry: str) -> Dict[str, Any]:
    """
    解析 BRENDA Km 值条目。
    
    参数：
        entry：来自 BRENDA 的原始 Km 条目字符串
    
    返回：
        包含解析字段的字典
    """
    result = {}
    
    # 解析数值
    value_match = re.search(r'([\d.]+)\s*(mM|µM|uM|nM)?', entry)
    if value_match:
        result['km_value_numeric'] = float(value_match.group(1))
        unit = value_match.group(2)
        if unit:
            if unit in ['µM', 'uM']:
                result['km_value_numeric'] /= 1000  # 转换为 mM
            elif unit == 'nM':
                result['km_value_numeric'] /= 1000000  # 转换为 mM
    
    # 解析生物体
    organism_match = re.search(r'(\w+\s+\w+|\w+)\s*#\d+', entry)
    if organism_match:
        result['organism'] = organism_match.group(1)
    
    # 解析底物
    substrate_match = re.search(r'substrate[:\s]+([^,;\n]+)', entry, re.IGNORECASE)
    if substrate_match:
        result['substrate'] = substrate_match.group(1).strip()
    
    # 解析 pH
    ph_match = re.search(r'pH[:\s]+([\d.]+)', entry, re.IGNORECASE)
    if ph_match:
        result['ph'] = float(ph_match.group(1))
    
    # 解析温度
    temp_match = re.search(r'(\d+\.?\d*)\s*°?[Cc]', entry)
    if temp_match:
        result['temperature'] = float(temp_match.group(1))
    
    # 解析注释
    comment_match = re.search(r'comment[:\s]+([^\n]+)', entry, re.IGNORECASE)
    if comment_match:
        result['comment'] = comment_match.group(1).strip()
    
    return result


def parse_reaction_entry(entry: str) -> Dict[str, Any]:
    """
    解析 BRENDA 反应条目。
    
    参数：
        entry：来自 BRENDA 的原始反应条目字符串
    
    返回：
        包含解析字段的字典
    """
    result = {}
    
    # 解析反应方程式
    equation_match = re.search(r'([^\n]+)', entry)
    if equation_match:
        result['equation'] = equation_match.group(1).strip()
    
    # 解析生物体
    organism_match = re.search(r'(\w+\s+\w+|\w+)\s*#\d+', entry)
    if organism_match:
        result['organism'] = organism_match.group(1)
    
    # 解析反应方向
    if '<=>' in entry or '⇌' in entry:
        result['reversible'] = True
    elif '=>' in entry or '→' in entry:
        result['reversible'] = False
    
    return result


def search_enzymes_by_substrate(substrate: str, limit: int = 50,
                                 ec_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    按底物搜索酶。
    
    参数：
        substrate：底物名称（例如，"glucose"）
        limit：返回的最大结果数
        ec_filter：可选的 EC 编号过滤器（例如，"1.1.1"）
    
    返回：
        酶条目列表
    """
    validate_dependencies()
    
    if not BRENDA_CLIENT_AVAILABLE:
        raise ImportError("BRENDA 客户端不可用")
    
    results = []
    
    try:
        # 获取按底物检索的 Km 值
        km_entries = get_km_values(ec_filter) if ec_filter else []
        
        for entry in km_entries[:limit]:
            parsed = parse_km_entry(entry)
            if substrate.lower() in parsed.get('substrate', '').lower():
                results.append(parsed)
    
    except Exception as e:
        print(f"按底物搜索时出错: {e}")
    
    return results


def search_enzymes_by_product(product: str, limit: int = 50,
                               ec_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    按产物搜索酶。
    
    参数：
        product：产物名称（例如，"lactate"）
        limit：返回的最大结果数
        ec_filter：可选的 EC 编号过滤器
    
    返回：
        酶条目列表
    """
    validate_dependencies()
    
    if not BRENDA_CLIENT_AVAILABLE:
        raise ImportError("BRENDA 客户端不可用")
    
    results = []
    
    try:
        # 获取反应数据
        reaction_entries = get_reactions(ec_filter) if ec_filter else []
        
        for entry in reaction_entries[:limit]:
            parsed = parse_reaction_entry(entry)
            if product.lower() in parsed.get('equation', '').lower():
                results.append(parsed)
    
    except Exception as e:
        print(f"按产物搜索时出错: {e}")
    
    return results


def compare_across_organisms(ec_number: str, organisms: List[str]) -> List[Dict[str, Any]]:
    """
    比较不同生物体的酶属性。
    
    参数：
        ec_number：EC 编号（例如，"1.1.1.1"）
        organisms：生物体名称列表
    
    返回：
        包含每个生物体比较数据的字典列表
    """
    validate_dependencies()
    
    if not BRENDA_CLIENT_AVAILABLE:
        raise ImportError("BRENDA 客户端不可用")
    
    comparison_results = []
    
    try:
        km_entries = get_km_values(ec_number)
        
        for organism in organisms:
            organism_data = {
                'organism': organism,
                'ec_number': ec_number,
                'data_points': 0,
                'average_km': None,
                'km_values': [],
                'optimal_ph': None,
                'optimal_temperature': None
            }
            
            # 解析该生物体的条目
            for entry in km_entries:
                parsed = parse_km_entry(entry)
                if organism.lower() in parsed.get('organism', '').lower():
                    organism_data['data_points'] += 1
                    if 'km_value_numeric' in parsed:
                        organism_data['km_values'].append(parsed['km_value_numeric'])
                    if 'ph' in parsed:
                        organism_data['optimal_ph'] = parsed['ph']
                    if 'temperature' in parsed:
                        organism_data['optimal_temperature'] = parsed['temperature']
            
            # 计算平均 Km
            if organism_data['km_values']:
                organism_data['average_km'] = sum(organism_data['km_values']) / len(organism_data['km_values'])
            
            comparison_results.append(organism_data)
    
    except Exception as e:
        print(f"跨生物体比较时出错: {e}")
    
    return comparison_results


def get_environmental_parameters(ec_number: str, organism: Optional[str] = None) -> Dict[str, Any]:
    """
    检索酶的环境参数（pH、温度等）。
    
    参数：
        ec_number：EC 编号
        organism：可选的生物体过滤器
    
    返回：
        包含环境参数的字典
    """
    validate_dependencies()
    
    if not BRENDA_CLIENT_AVAILABLE:
        raise ImportError("BRENDA 客户端不可用")
    
    result = {
        'ec_number': ec_number,
        'organism': organism,
        'ph_range': None,
        'optimal_ph': None,
        'temperature_range': None,
        'optimal_temperature': None,
        'stability_info': []
    }
    
    try:
        km_entries = get_km_values(ec_number)
        
        ph_values = []
        temperatures = []
        
        for entry in km_entries:
            parsed = parse_km_entry(entry)
            
            if organism and organism.lower() not in parsed.get('organism', '').lower():
                continue
            
            if 'ph' in parsed:
                ph_values.append(parsed['ph'])
            if 'temperature' in parsed:
                temperatures.append(parsed['temperature'])
        
        if ph_values:
            result['ph_range'] = (min(ph_values), max(ph_values))
            result['optimal_ph'] = sum(ph_values) / len(ph_values)
        
        if temperatures:
            result['temperature_range'] = (min(temperatures), max(temperatures))
            result['optimal_temperature'] = sum(temperatures) / len(temperatures)
    
    except Exception as e:
        print(f"获取环境参数时出错: {e}")
    
    return result


def get_substrate_specificity(ec_number: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    分析酶的底物特异性。
    
    参数：
        ec_number：EC 编号
        limit：要分析的底物数量
    
    返回：
        包含底物特异性数据的字典列表
    """
    validate_dependencies()
    
    if not BRENDA_CLIENT_AVAILABLE:
        raise ImportError("BRENDA 客户端不可用")
    
    substrate_data = {}
    
    try:
        km_entries = get_km_values(ec_number)
        
        for entry in km_entries:
            parsed = parse_km_entry(entry)
            substrate = parsed.get('substrate', 'Unknown')
            
            if substrate not in substrate_data:
                substrate_data[substrate] = {
                    'name': substrate,
                    'km_values': [],
                    'data_points': 0
                }
            
            substrate_data[substrate]['data_points'] += 1
            if 'km_value_numeric' in parsed:
                substrate_data[substrate]['km_values'].append(parsed['km_value_numeric'])
        
        # 计算统计量
        results = []
        for name, data in substrate_data.items():
            if data['km_values']:
                result = {
                    'name': name,
                    'km': sum(data['km_values']) / len(data['km_values']),
                    'km_min': min(data['km_values']),
                    'km_max': max(data['km_values']),
                    'data_points': data['data_points']
                }
                results.append(result)
        
        # 按数据点排序
        results.sort(key=lambda x: x['data_points'], reverse=True)
        
    except Exception as e:
        print(f"获取底物特异性时出错: {e}")
    
    return results[:limit]


def get_cofactor_requirements(ec_number: str) -> List[str]:
    """
    检索酶的辅因子需求。
    
    参数：
        ec_number：EC 编号
    
    返回：
        辅因子名称列表
    """
    # 这是简化的实现
    # 实际实现需要从 BRENDA 解析反应数据
    cofactors = []
    
    try:
        reactions = get_reactions(ec_number)
        for reaction in reactions:
            # 检查常见辅因子
            common_cofactors = ['NAD+', 'NADH', 'NADP+', 'NADPH', 'ATP', 'ADP', 'FAD', 'FMN']
            for cofactor in common_cofactors:
                if cofactor in reaction:
                    if cofactor not in cofactors:
                        cofactors.append(cofactor)
    except:
        pass
    
    return cofactors


def get_modeling_parameters(ec_number: str, substrate: Optional[str] = None) -> Dict[str, Any]:
    """
    获取用于 Michaelis-Menten 建模的参数。
    
    参数：
        ec_number：EC 编号
        substrate：可选的底物过滤器
    
    返回：
        包含建模参数的字典
    """
    validate_dependencies()
    
    result = {
        'ec_number': ec_number,
        'substrate': substrate,
        'km': None,
        'kcat': None,
        'vmax': None,
        'enzyme_conc': None
    }
    
    try:
        km_entries = get_km_values(ec_number)
        
        km_values = []
        for entry in km_entries:
            parsed = parse_km_entry(entry)
            if substrate is None or substrate.lower() in parsed.get('substrate', '').lower():
                if 'km_value_numeric' in parsed:
                    km_values.append(parsed['km_value_numeric'])
        
        if km_values:
            result['km'] = sum(km_values) / len(km_values)
    
    except Exception as e:
        print(f"获取建模参数时出错: {e}")
    
    return result


def find_thermophilic_homologs(ec_number: str, min_temp: float = 50.0) -> List[Dict[str, Any]]:
    """
    查找耐热同源酶。
    
    参数：
        ec_number：EC 编号
        min_temp：最低温度阈值
    
    返回：
        耐热同源酶列表
    """
    validate_dependencies()
    
    thermophilic = []
    
    try:
        km_entries = get_km_values(ec_number)
        
        for entry in km_entries:
            parsed = parse_km_entry(entry)
            if 'temperature' in parsed and parsed['temperature'] >= min_temp:
                thermophilic.append(parsed)
    
    except Exception as e:
        print(f"查找耐热同源酶时出错: {e}")
    
    return thermophilic


def find_ph_stable_variants(ec_number: str, ph_range: Tuple[float, float] = (4.0, 9.0)) -> List[Dict[str, Any]]:
    """
    查找 pH 稳定的酶变体。
    
    参数：
        ec_number：EC 编号
        ph_range：可接受的 pH 范围
    
    返回：
        pH 稳定变体列表
    """
    validate_dependencies()
    
    stable_variants = []
    
    try:
        km_entries = get_km_values(ec_number)
        
        for entry in km_entries:
            parsed = parse_km_entry(entry)
            if 'ph' in parsed:
                ph = parsed['ph']
                if ph_range[0] <= ph <= ph_range[1]:
                    stable_variants.append(parsed)
    
    except Exception as e:
        print(f"查找 pH 稳定变体时出错: {e}")
    
    return stable_variants


def search_by_pattern(pattern: str, search_type: str = 'substrate', limit: int = 100) -> List[Dict[str, Any]]:
    """
    使用模式匹配搜索酶条目。
    
    参数：
        pattern：搜索模式（支持正则表达式）
        search_type：搜索类型（'substrate'、'product'、'organism'）
        limit：最大结果数
    
    返回：
        匹配的酶条目列表
    """
    validate_dependencies()
    
    results = []
    regex = re.compile(pattern, re.IGNORECASE)
    
    try:
        if search_type == 'substrate':
            entries = get_km_values('')
        else:
            entries = get_reactions('')
        
        for entry in entries[:limit]:
            if regex.search(entry):
                if search_type == 'substrate':
                    parsed = parse_km_entry(entry)
                else:
                    parsed = parse_reaction_entry(entry)
                results.append(parsed)
    
    except Exception as e:
        print(f"模式搜索时出错: {e}")
    
    return results


def export_to_csv(data: List[Dict[str, Any]], output_file: str):
    """
    将数据导出为 CSV 文件。
    
    参数：
        data：要导出的字典列表
        output_file：输出文件路径
    """
    validate_dependencies()
    
    if not PANDAS_AVAILABLE:
        print("需要 pandas 才能导出 CSV")
        return
    
    try:
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        print(f"数据已导出至: {output_file}")
    except Exception as e:
        print(f"导出 CSV 时出错: {e}")


def export_to_json(data: List[Dict[str, Any]], output_file: str):
    """
    将数据导出为 JSON 文件。
    
    参数：
        data：要导出的字典列表
        output_file：输出文件路径
    """
    try:
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"数据已导出至: {output_file}")
    except Exception as e:
        print(f"导出 JSON 时出错: {e}")


# 便捷函数别名
def get_km(ec_number: str) -> List[Dict[str, Any]]:
    """获取 Km 值的便捷函数。"""
    entries = get_km_values(ec_number)
    return [parse_km_entry(e) for e in entries]


def get_reactions_list(ec_number: str) -> List[Dict[str, Any]]:
    """获取反应列表的便捷函数。"""
    entries = get_reactions(ec_number)
    return [parse_reaction_entry(e) for e in entries]


if __name__ == "__main__":
    # 示例用法
    print("BRENDA 查询示例")
    print("=" * 40)
    
    try:
        # 按底物搜索
        print("\n1. 按底物 'glucose' 搜索酶")
        enzymes = search_enzymes_by_substrate("glucose", limit=5)
        for enzyme in enzymes[:3]:
            print(f"  - {enzyme.get('organism', 'Unknown')}: Km = {enzyme.get('km_value_numeric', 'N/A')}")
        
        # 比较生物体
        print("\n2. 比较不同生物体的 EC 1.1.1.1")
        comparison = compare_across_organisms("1.1.1.1", ["Escherichia coli", "Saccharomyces cerevisiae"])
        for comp in comparison:
            print(f"  - {comp['organism']}: 平均 Km = {comp.get('average_km', 'N/A')}")
        
        # 获取环境参数
        print("\n3. EC 1.1.1.1 的环境参数")
        env = get_environmental_parameters("1.1.1.1")
        print(f"  - pH 范围: {env.get('ph_range')}")
        print(f"  - 温度范围: {env.get('temperature_range')}")
        
    except Exception as e:
        print(f"示例失败: {e}")
