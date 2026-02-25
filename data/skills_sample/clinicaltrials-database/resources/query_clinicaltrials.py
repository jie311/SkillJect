#!/usr/bin/env python3
"""
ClinicalTrials.gov API查询助手

用于查询ClinicalTrials.gov API v2的综合Python脚本。
提供常见查询模式的便捷函数，包括按疾病、干预措施、
位置、赞助商搜索以及检索特定试验。

API文档: https://clinicaltrials.gov/data-api/api
速率限制: 每个IP地址每分钟约50个请求
"""

import requests
import json
from typing import Dict, List, Optional, Union
from urllib.parse import urlencode


BASE_URL = "https://clinicaltrials.gov/api/v2"


def search_studies(
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    location: Optional[str] = None,
    sponsor: Optional[str] = None,
    status: Optional[Union[str, List[str]]] = None,
    nct_ids: Optional[List[str]] = None,
    sort: str = "LastUpdatePostDate:desc",
    page_size: int = 10,
    page_token: Optional[str] = None,
    format: str = "json"
) -> Dict:
    """
    使用各种筛选器搜索临床试验。

    参数:
        condition: 疾病或状况（如"lung cancer"、"diabetes"）
        intervention: 治疗或干预措施（如"Pembrolizumab"、"exercise"）
        location: 地理位置（如"New York"、"California"）
        sponsor: 赞助商或合作者名称（如"National Cancer Institute"）
        status: 研究状态（可以是字符串或列表）。有效值：
                RECRUITING（招募中）、NOT_YET_RECRUITING（尚未招募）、
                ENROLLING_BY_INVITATION（仅通过邀请招募）、
                ACTIVE_NOT_RECRUITING（活跃但未招募）、SUSPENDED（暂停）、
                TERMINATED（终止）、COMPLETED（已完成）、WITHDRAWN（已撤回）
        nct_ids: 要筛选的NCT ID列表
        sort: 排序方式（如"LastUpdatePostDate:desc"、"EnrollmentCount:desc"）
        page_size: 每页结果数（默认：10，最大：1000）
        page_token: 分页令牌（从上一次查询返回）
        format: 响应格式（"json"或"csv"）

    返回:
        包含研究和元数据的搜索结果字典
    """
    params = {}

    # 构建查询参数
    if condition:
        params['query.cond'] = condition
    if intervention:
        params['query.intr'] = intervention
    if location:
        params['query.locn'] = location
    if sponsor:
        params['query.spons'] = sponsor

    # 处理状态筛选（可以是列表或字符串）
    if status:
        if isinstance(status, list):
            params['filter.overallStatus'] = ','.join(status)
        else:
            params['filter.overallStatus'] = status

    # 处理NCT ID筛选
    if nct_ids:
        params['filter.ids'] = ','.join(nct_ids)

    # 添加分页和排序
    params['sort'] = sort
    params['pageSize'] = page_size
    if page_token:
        params['pageToken'] = page_token

    # 设置格式
    params['format'] = format

    url = f"{BASE_URL}/studies"
    response = requests.get(url, params=params)
    response.raise_for_status()

    if format == "json":
        return response.json()
    else:
        return response.text


def get_study_details(nct_id: str, format: str = "json") -> Dict:
    """
    检索特定临床试验的详细信息。

    参数:
        nct_id: 试验的NCT ID（如"NCT04852770"）
        format: 响应格式（"json"或"csv"）

    返回:
        包含综合研究信息的字典
    """
    params = {'format': format}
    url = f"{BASE_URL}/studies/{nct_id}"

    response = requests.get(url, params=params)
    response.raise_for_status()

    if format == "json":
        return response.json()
    else:
        return response.text


def search_with_all_results(
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    location: Optional[str] = None,
    sponsor: Optional[str] = None,
    status: Optional[Union[str, List[str]]] = None,
    max_results: Optional[int] = None
) -> List[Dict]:
    """
    搜索临床试验并自动分页遍历所有结果。

    参数:
        condition: 要搜索的疾病或状况
        intervention: 要搜索的治疗或干预措施
        location: 要搜索的地理位置
        sponsor: 赞助商或合作者名称
        status: 要筛选的研究状态
        max_results: 要检索的最大结果数（None表示全部）

    返回:
        所有匹配的研究列表
    """
    all_studies = []
    page_token = None

    while True:
        result = search_studies(
            condition=condition,
            intervention=intervention,
            location=location,
            sponsor=sponsor,
            status=status,
            page_size=1000,  # 使用最大页面大小以提高效率
            page_token=page_token
        )

        studies = result.get('studies', [])
        all_studies.extend(studies)

        # 检查是否已达到最大值或没有更多结果
        if max_results and len(all_studies) >= max_results:
            return all_studies[:max_results]

        # 检查下一页
        page_token = result.get('nextPageToken')
        if not page_token:
            break

    return all_studies


def extract_study_summary(study: Dict) -> Dict:
    """
    从研究中提取关键信息以快速概览。

    参数:
        study: 来自API响应的研究字典

    返回:
        包含基本研究信息的字典
    """
    protocol = study.get('protocolSection', {})
    identification = protocol.get('identificationModule', {})
    status_module = protocol.get('statusModule', {})
    description = protocol.get('descriptionModule', {})

    return {
        'nct_id': identification.get('nctId'),
        'title': identification.get('officialTitle') or identification.get('briefTitle'),
        'status': status_module.get('overallStatus'),
        'phase': protocol.get('designModule', {}).get('phases', []),
        'enrollment': protocol.get('designModule', {}).get('enrollmentInfo', {}).get('count'),
        'brief_summary': description.get('briefSummary'),
        'last_update': status_module.get('lastUpdatePostDateStruct', {}).get('date')
    }


# 使用示例
if __name__ == "__main__":
    # 示例 1: 搜索招募中的肺癌试验
    print("示例 1: 正在搜索招募中的肺癌试验...")
    results = search_studies(
        condition="lung cancer",
        status="RECRUITING",
        page_size=5
    )
    print(f"找到 {results.get('totalCount', 0)} 个试验总数")
    print(f"显示前 {len(results.get('studies', []))} 个试验\n")

    # 示例 2: 获取特定试验的详细信息
    if results.get('studies'):
        first_study = results['studies'][0]
        nct_id = first_study['protocolSection']['identificationModule']['nctId']
        print(f"示例 2: 正在获取 {nct_id} 的详细信息...")
        details = get_study_details(nct_id)
        summary = extract_study_summary(details)
        print(json.dumps(summary, indent=2))
