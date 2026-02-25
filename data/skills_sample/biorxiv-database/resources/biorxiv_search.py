#!/usr/bin/env python3
"""
bioRxiv搜索工具
用于搜索和检索bioRxiv预印本的综合Python工具。
支持关键词搜索、作者搜索、日期筛选、类别筛选等功能。

注意：此工具专门针对bioRxiv（生命科学预印本）。
"""

import requests
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import time
import sys
from urllib.parse import quote


class BioRxivSearcher:
    """bioRxiv预印本的高效搜索接口。"""

    BASE_URL = "https://api.biorxiv.org"

    # 有效的bioRxiv类别
    CATEGORIES = [
        "animal-behavior-and-cognition", "biochemistry", "bioengineering",
        "bioinformatics", "biophysics", "cancer-biology", "cell-biology",
        "clinical-trials", "developmental-biology", "ecology", "epidemiology",
        "evolutionary-biology", "genetics", "genomics", "immunology",
        "microbiology", "molecular-biology", "neuroscience", "paleontology",
        "pathology", "pharmacology-and-toxicology", "physiology",
        "plant-biology", "scientific-communication-and-education",
        "synthetic-biology", "systems-biology", "zoology"
    ]

    def __init__(self, verbose: bool = False):
        """初始化搜索器。"""
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BioRxiv-Search-Tool/1.0'
        })

    def _log(self, message: str):
        """打印详细日志消息。"""
        if self.verbose:
            print(f"[信息] {message}", file=sys.stderr)

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """发出带有错误处理和速率限制的API请求。"""
        url = f"{self.BASE_URL}/{endpoint}"
        self._log(f"正在请求: {url}")

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # 速率限制 - 尊重API
            time.sleep(0.5)

            return response.json()
        except requests.exceptions.RequestException as e:
            self._log(f"请求时出错: {e}")
            return {"messages": [{"status": "error", "message": str(e)}], "collection": []}

    def search_by_date_range(
        self,
        start_date: str,
        end_date: str,
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        在日期范围内搜索预印本。

        参数:
            start_date: 开始日期（YYYY-MM-DD格式）
            end_date: 结束日期（YYYY-MM-DD格式）
            category: 可选的类别筛选（如'neuroscience'）

        返回:
            预印本字典列表
        """
        self._log(f"正在搜索从 {start_date} 到 {end_date} 的bioRxiv")

        if category:
            endpoint = f"details/biorxiv/{start_date}/{end_date}/{category}"
        else:
            endpoint = f"details/biorxiv/{start_date}/{end_date}"

        data = self._make_request(endpoint)

        if "collection" in data:
            self._log(f"找到 {len(data['collection'])} 篇预印本")
            return data["collection"]

        return []

    def search_by_interval(
        self,
        interval: str = "1",
        cursor: int = 0,
        format: str = "json"
    ) -> Dict:
        """
        从特定时间间隔检索预印本。

        参数:
            interval: 向前搜索的天数
            cursor: 分页游标（第一页为0，然后使用返回的游标）
            format: 响应格式（'json'或'xml'）

        返回:
            包含集合和分页信息的字典
        """
        endpoint = f"pubs/biorxiv/{interval}/{cursor}/{format}"
        return self._make_request(endpoint)

    def get_paper_details(self, doi: str) -> Dict:
        """
        通过DOI获取特定论文的详细信息。

        参数:
            doi: 论文的DOI（如'10.1101/2021.01.01.123456'）

        返回:
            包含论文详细信息的字典
        """
        # 如果提供了完整URL则清理DOI
        if 'doi.org' in doi:
            doi = doi.split('doi.org/')[-1]

        self._log(f"正在获取DOI的详细信息: {doi}")
        endpoint = f"details/biorxiv/{doi}"

        data = self._make_request(endpoint)

        if "collection" in data and len(data["collection"]) > 0:
            return data["collection"][0]

        return {}

    def search_by_author(
        self,
        author_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        按作者姓名搜索论文。

        参数:
            author_name: 要搜索的作者姓名
            start_date: 可选的开始日期（YYYY-MM-DD）
            end_date: 可选的结束日期（YYYY-MM-DD）

        返回:
            匹配的预印本列表
        """
        # 如果未指定日期范围，则搜索过去3年
        if not start_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=1095)).strftime("%Y-%m-%d")

        self._log(f"正在搜索作者: {author_name}")

        # 获取日期范围内的所有论文
        papers = self.search_by_date_range(start_date, end_date)

        # 按作者姓名筛选（不区分大小写）
        author_lower = author_name.lower()
        matching_papers = []

        for paper in papers:
            authors = paper.get("authors", "")
            if author_lower in authors.lower():
                matching_papers.append(paper)

        self._log(f"找到 {len(matching_papers)} 篇由 {author_name} 撰写的论文")
        return matching_papers

    def search_by_keywords(
        self,
        keywords: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        search_fields: List[str] = ["title", "abstract"]
    ) -> List[Dict]:
        """
        搜索包含特定关键词的论文。

        参数:
            keywords: 要搜索的关键词列表
            start_date: 可选的开始日期（YYYY-MM-DD）
            end_date: 可选的结束日期（YYYY-MM-DD）
            category: 可选的类别筛选
            search_fields: 要搜索的字段（标题、摘要、作者）

        返回:
            匹配的预印本列表
        """
        # 如果未指定日期范围，则搜索过去一年
        if not start_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        self._log(f"正在搜索关键词: {keywords}")

        # 获取日期范围内的所有论文
        papers = self.search_by_date_range(start_date, end_date, category)

        # 按关键词筛选
        matching_papers = []
        keywords_lower = [k.lower() for k in keywords]

        for paper in papers:
            # 从指定字段构建搜索文本
            search_text = ""
            for field in search_fields:
                if field in paper:
                    search_text += " " + str(paper[field]).lower()

            # 检查是否有任何关键词匹配
            if any(keyword in search_text for keyword in keywords_lower):
                matching_papers.append(paper)

        self._log(f"找到 {len(matching_papers)} 篇匹配关键词的论文")
        return matching_papers

    def download_pdf(self, doi: str, output_path: str) -> bool:
        """
        下载论文的PDF。

        参数:
            doi: 论文的DOI
            output_path: PDF应保存的路径

        返回:
            下载成功返回True，否则返回False
        """
        # 清理DOI
        if 'doi.org' in doi:
            doi = doi.split('doi.org/')[-1]

        # 构建PDF URL
        pdf_url = f"https://www.biorxiv.org/content/{doi}v1.full.pdf"

        self._log(f"正在从以下位置下载PDF: {pdf_url}")

        try:
            response = self.session.get(pdf_url, timeout=60)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                f.write(response.content)

            self._log(f"PDF已保存到: {output_path}")
            return True
        except Exception as e:
            self._log(f"下载PDF时出错: {e}")
            return False

    def format_result(self, paper: Dict, include_abstract: bool = True) -> Dict:
        """
        格式化具有标准化字段的论文结果。

        参数:
            paper: 来自API的原始论文字典
            include_abstract: 是否包含摘要

        返回:
            格式化的论文字典
        """
        result = {
            "doi": paper.get("doi", ""),
            "title": paper.get("title", ""),
            "authors": paper.get("authors", ""),
            "author_corresponding": paper.get("author_corresponding", ""),
            "author_corresponding_institution": paper.get("author_corresponding_institution", ""),
            "date": paper.get("date", ""),
            "version": paper.get("version", ""),
            "type": paper.get("type", ""),
            "license": paper.get("license", ""),
            "category": paper.get("category", ""),
            "jatsxml": paper.get("jatsxml", ""),
            "published": paper.get("published", "")
        }

        if include_abstract:
            result["abstract"] = paper.get("abstract", "")

        # 添加PDF和HTML URL
        if result["doi"]:
            result["pdf_url"] = f"https://www.biorxiv.org/content/{result['doi']}v{result['version']}.full.pdf"
            result["html_url"] = f"https://www.biorxiv.org/content/{result['doi']}v{result['version']}"

        return result


def main():
    """bioRxiv搜索的命令行接口。"""
    parser = argparse.ArgumentParser(
        description="高效搜索bioRxiv预印本",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--verbose", "-v", action="store_true",
                       help="启用详细日志记录")

    # 搜索类型参数
    search_group = parser.add_argument_group("搜索选项")
    search_group.add_argument("--keywords", "-k", nargs="+",
                            help="要搜索的关键词")
    search_group.add_argument("--author", "-a",
                            help="要搜索的作者姓名")
    search_group.add_argument("--doi",
                            help="获取特定DOI的详细信息")

    # 日期范围参数
    date_group = parser.add_argument_group("日期范围选项")
    date_group.add_argument("--start-date",
                          help="开始日期（YYYY-MM-DD）")
    date_group.add_argument("--end-date",
                          help="结束日期（YYYY-MM-DD）")
    date_group.add_argument("--days-back", type=int,
                          help="从今天起向前搜索N天")

    # 筛选参数
    filter_group = parser.add_argument_group("筛选选项")
    filter_group.add_argument("--category", "-c",
                            choices=BioRxivSearcher.CATEGORIES,
                            help="按类别筛选")
    filter_group.add_argument("--search-fields", nargs="+",
                            default=["title", "abstract"],
                            choices=["title", "abstract", "authors"],
                            help="搜索关键词的字段")

    # 输出参数
    output_group = parser.add_argument_group("输出选项")
    output_group.add_argument("--output", "-o",
                            help="输出文件（默认：stdout）")
    output_group.add_argument("--include-abstract", action="store_true",
                            default=True, help="在输出中包含摘要")
    output_group.add_argument("--download-pdf",
                            help="将PDF下载到指定路径（需要--doi）")
    output_group.add_argument("--limit", type=int,
                            help="限制结果数量")

    args = parser.parse_args()

    # 初始化搜索器
    searcher = BioRxivSearcher(verbose=args.verbose)

    # 处理日期范围
    end_date = args.end_date or datetime.now().strftime("%Y-%m-%d")
    if args.days_back:
        start_date = (datetime.now() - timedelta(days=args.days_back)).strftime("%Y-%m-%d")
    else:
        start_date = args.start_date

    # 根据参数执行搜索
    results = []

    if args.download_pdf:
        if not args.doi:
            print("错误: --download-pdf需要--doi", file=sys.stderr)
            return 1

        success = searcher.download_pdf(args.doi, args.download_pdf)
        return 0 if success else 1

    elif args.doi:
        # 通过DOI获取特定论文
        paper = searcher.get_paper_details(args.doi)
        if paper:
            results = [paper]

    elif args.author:
        # 按作者搜索
        results = searcher.search_by_author(
            args.author, start_date, end_date
        )

    elif args.keywords:
        # 按关键词搜索
        if not start_date:
            print("错误: 关键词搜索需要--start-date或--days-back",
                  file=sys.stderr)
            return 1

        results = searcher.search_by_keywords(
            args.keywords, start_date, end_date,
            args.category, args.search_fields
        )

    else:
        # 日期范围搜索
        if not start_date:
            print("错误: 必须指定搜索条件（--keywords、--author或--doi）",
                  file=sys.stderr)
            return 1

        results = searcher.search_by_date_range(
            start_date, end_date, args.category
        )

    # 应用限制
    if args.limit:
        results = results[:args.limit]

    # 格式化结果
    formatted_results = [
        searcher.format_result(paper, args.include_abstract)
        for paper in results
    ]

    # 输出结果
    output_data = {
        "query": {
            "keywords": args.keywords,
            "author": args.author,
            "doi": args.doi,
            "start_date": start_date,
            "end_date": end_date,
            "category": args.category
        },
        "result_count": len(formatted_results),
        "results": formatted_results
    }

    output_json = json.dumps(output_data, indent=2)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_json)
        print(f"结果已写入 {args.output}", file=sys.stderr)
    else:
        print(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
