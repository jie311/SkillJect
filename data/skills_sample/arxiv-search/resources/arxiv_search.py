#!/usr/bin/env python3
"""arXiv搜索。

在arXiv预印本库中搜索研究论文。
"""

import argparse


def query_arxiv(query: str, max_papers: int = 10) -> str:
    """根据提供的搜索查询在arXiv中查询论文。

    参数
    ----------
    query : str
        搜索查询字符串。
    max_papers : int
        要检索的最大论文数（默认：10）。

    返回:
        格式化的搜索结果或错误消息。
    """
    try:
        import arxiv
    except ImportError:
        return "错误: 未安装arxiv包。使用以下命令安装: pip install arxiv"

    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query, max_results=max_papers, sort_by=arxiv.SortCriterion.Relevance
        )
        results = "\n\n".join(
            [f"标题: {paper.title}\n摘要: {paper.summary}" for paper in client.results(search)]
        )
        return results if results else "在arXiv上未找到论文。"
    except Exception as e:
        return f"查询arXiv时出错: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(description="在arXiv中搜索研究论文")
    parser.add_argument("query", type=str, help="搜索查询字符串")
    parser.add_argument(
        "--max-papers",
        type=int,
        default=10,
        help="要检索的最大论文数（默认：10）",
    )

    args = parser.parse_args()

    query_arxiv(args.query, max_papers=args.max_papers)


if __name__ == "__main__":
    main()
