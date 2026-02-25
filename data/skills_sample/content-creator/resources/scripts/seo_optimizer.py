#!/usr/bin/env python3
"""
SEO内容优化器 - 分析和优化内容的SEO
"""

import re
from typing import Dict, List, Set
import json

class SEOOptimizer:
    def __init__(self):
        # 要过滤的常用停用词
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'can', 'shall'
        }
        
        # SEO最佳实践
        self.best_practices = {
            'title_length': (50, 60),
            'meta_description_length': (150, 160),
            'url_length': (50, 60),
            'paragraph_length': (40, 150),
            'heading_keyword_placement': True,
            'keyword_density': (0.01, 0.03)  # 1-3%
        }
    
    def analyze(self, content: str, target_keyword: str = None, 
                secondary_keywords: List[str] = None) -> Dict:
        """分析内容的SEO优化情况"""
        
        analysis = {
            'content_length': len(content.split()),
            'keyword_analysis': {},
            'structure_analysis': self._analyze_structure(content),
            'readability': self._analyze_readability(content),
            'meta_suggestions': {},
            'optimization_score': 0,
            'recommendations': []
        }
        
        # 关键词分析
        if target_keyword:
            analysis['keyword_analysis'] = self._analyze_keywords(
                content, target_keyword, secondary_keywords or []
            )
        
        # 生成元标签建议
        analysis['meta_suggestions'] = self._generate_meta_suggestions(
            content, target_keyword
        )
        
        # 计算优化得分
        analysis['optimization_score'] = self._calculate_seo_score(analysis)
        
        # 生成建议
        analysis['recommendations'] = self._generate_recommendations(analysis)
        
        return analysis
    
    def _analyze_keywords(self, content: str, primary: str, 
                         secondary: List[str]) -> Dict:
        """分析关键词使用情况和密度"""
        content_lower = content.lower()
        word_count = len(content.split())
        
        results = {
            'primary_keyword': {
                'keyword': primary,
                'count': content_lower.count(primary.lower()),
                'density': 0,
                'in_title': False,
                'in_headings': False,
                'in_first_paragraph': False
            },
            'secondary_keywords': [],
            'lsi_keywords': []
        }
        
        # 计算主要关键词指标
        if word_count > 0:
            results['primary_keyword']['density'] = (
                results['primary_keyword']['count'] / word_count
            )
        
        # 检查关键词位置
        first_para = content.split('\n\n')[0] if '\n\n' in content else content[:200]
        results['primary_keyword']['in_first_paragraph'] = (
            primary.lower() in first_para.lower()
        )
        
        # 分析次要关键词
        for keyword in secondary:
            count = content_lower.count(keyword.lower())
            results['secondary_keywords'].append({
                'keyword': keyword,
                'count': count,
                'density': count / word_count if word_count > 0 else 0
            })
        
        # 提取潜在的LSI关键词
        results['lsi_keywords'] = self._extract_lsi_keywords(content, primary)
        
        return results
    
    def _analyze_structure(self, content: str) -> Dict:
        """分析内容的SEO结构"""
        lines = content.split('\n')
        
        structure = {
            'headings': {'h1': 0, 'h2': 0, 'h3': 0, 'total': 0},
            'paragraphs': 0,
            'lists': 0,
            'images': 0,
            'links': {'internal': 0, 'external': 0},
            'avg_paragraph_length': 0
        }
        
        paragraphs = []
        current_para = []
        
        for line in lines:
            # 统计标题
            if line.startswith('# '):
                structure['headings']['h1'] += 1
                structure['headings']['total'] += 1
            elif line.startswith('## '):
                structure['headings']['h2'] += 1
                structure['headings']['total'] += 1
            elif line.startswith('### '):
                structure['headings']['h3'] += 1
                structure['headings']['total'] += 1
            
            # 统计列表
            if line.strip().startswith(('- ', '* ', '1. ')):
                structure['lists'] += 1
            
            # 统计链接
            internal_links = len(re.findall(r'\[.*?\]\(/.*?\)', line))
            external_links = len(re.findall(r'\[.*?\]\(https?://.*?\)', line))
            structure['links']['internal'] += internal_links
            structure['links']['external'] += external_links
            
            # 跟踪段落
            if line.strip() and not line.startswith('#'):
                current_para.append(line)
            elif current_para:
                paragraphs.append(' '.join(current_para))
                current_para = []
        
        if current_para:
            paragraphs.append(' '.join(current_para))
        
        structure['paragraphs'] = len(paragraphs)
        
        if paragraphs:
            avg_length = sum(len(p.split()) for p in paragraphs) / len(paragraphs)
            structure['avg_paragraph_length'] = round(avg_length, 1)
        
        return structure
    
    def _analyze_readability(self, content: str) -> Dict:
        """分析内容可读性"""
        sentences = re.split(r'[.!?]+', content)
        words = content.split()
        
        if not sentences or not words:
            return {'score': 0, 'level': '未知'}
        
        avg_sentence_length = len(words) / len(sentences)
        
        # 简单可读性评分
        if avg_sentence_length < 15:
            level = '简单'
            score = 90
        elif avg_sentence_length < 20:
            level = '中等'
            score = 70
        elif avg_sentence_length < 25:
            level = '困难'
            score = 50
        else:
            level = '非常困难'
            score = 30
        
        return {
            'score': score,
            'level': level,
            'avg_sentence_length': round(avg_sentence_length, 1)
        }
    
    def _extract_lsi_keywords(self, content: str, primary_keyword: str) -> List[str]:
        """提取潜在的LSI（语义相关）关键词"""
        words = re.findall(r'\b[a-z]+\b', content.lower())
        word_freq = {}
        
        # 统计词频
        for word in words:
            if word not in self.stop_words and len(word) > 3:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 按频率排序并返回最相关的词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        
        # 过滤掉主要关键词并返回前10个
        lsi_keywords = []
        for word, count in sorted_words:
            if word != primary_keyword.lower() and count > 1:
                lsi_keywords.append(word)
            if len(lsi_keywords) >= 10:
                break
        
        return lsi_keywords
    
    def _generate_meta_suggestions(self, content: str, keyword: str = None) -> Dict:
        """生成SEO元标签建议"""
        # 提取第一句作为描述基础
        sentences = re.split(r'[.!?]+', content)
        first_sentence = sentences[0] if sentences else content[:160]
        
        suggestions = {
            'title': '',
            'meta_description': '',
            'url_slug': '',
            'og_title': '',
            'og_description': ''
        }
        
        if keyword:
            # 标题建议
            suggestions['title'] = f"{keyword.title()} - 完全指南"
            if len(suggestions['title']) > 60:
                suggestions['title'] = keyword.title()[:57] + "..."
            
            # 元描述
            desc_base = f"了解关于{keyword}的一切。{first_sentence}"
            if len(desc_base) > 160:
                desc_base = desc_base[:157] + "..."
            suggestions['meta_description'] = desc_base
            
            # URL slug
            suggestions['url_slug'] = re.sub(r'[^a-z0-9-]+', '-', 
                                            keyword.lower()).strip('-')
            
            # Open Graph标签
            suggestions['og_title'] = suggestions['title']
            suggestions['og_description'] = suggestions['meta_description']
        
        return suggestions
    
    def _calculate_seo_score(self, analysis: Dict) -> int:
        """计算整体SEO优化得分"""
        score = 0
        max_score = 100
        
        # 内容长度评分（20分）
        if 300 <= analysis['content_length'] <= 2500:
            score += 20
        elif 200 <= analysis['content_length'] < 300:
            score += 10
        elif analysis['content_length'] > 2500:
            score += 15
        
        # 关键词优化（30分）
        if analysis['keyword_analysis']:
            kw_data = analysis['keyword_analysis']['primary_keyword']
            
            # 密度评分
            if 0.01 <= kw_data['density'] <= 0.03:
                score += 15
            elif 0.005 <= kw_data['density'] < 0.01:
                score += 8
            
            # 位置评分
            if kw_data['in_first_paragraph']:
                score += 10
            if kw_data.get('in_headings'):
                score += 5
        
        # 结构评分（25分）
        struct = analysis['structure_analysis']
        if struct['headings']['total'] > 0:
            score += 10
        if struct['paragraphs'] >= 3:
            score += 10
        if struct['links']['internal'] > 0 or struct['links']['external'] > 0:
            score += 5
        
        # 可读性评分（25分）
        readability_score = analysis['readability']['score']
        score += int(readability_score * 0.25)
        
        return min(score, max_score)
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """生成SEO改进建议"""
        recommendations = []
        
        # 内容长度建议
        if analysis['content_length'] < 300:
            recommendations.append(
                f"将内容长度增加到至少300字（当前为{analysis['content_length']}字）"
            )
        elif analysis['content_length'] > 3000:
            recommendations.append(
                "考虑将长内容拆分为多个页面或添加目录"
            )
        
        # 关键词建议
        if analysis['keyword_analysis']:
            kw_data = analysis['keyword_analysis']['primary_keyword']
            
            if kw_data['density'] < 0.01:
                recommendations.append(
                    f"增加'{kw_data['keyword']}'的关键词密度（当前为{kw_data['density']:.2%}）"
                )
            elif kw_data['density'] > 0.03:
                recommendations.append(
                    f"减少关键词密度以避免过度优化（当前为{kw_data['density']:.2%}）"
                )
            
            if not kw_data['in_first_paragraph']:
                recommendations.append(
                    "在第一段中包含主要关键词"
                )
        
        # 结构建议
        struct = analysis['structure_analysis']
        if struct['headings']['total'] == 0:
            recommendations.append("添加标题（H1、H2、H3）以改善内容结构")
        if struct['links']['internal'] == 0:
            recommendations.append("添加指向相关内容的内部链接")
        if struct['avg_paragraph_length'] > 150:
            recommendations.append("拆分长段落以提高可读性")
        
        # 可读性建议
        if analysis['readability']['avg_sentence_length'] > 20:
            recommendations.append("简化句子以提高可读性")
        
        return recommendations

def optimize_content(content: str, keyword: str = None, 
                     secondary_keywords: List[str] = None) -> str:
    """优化内容的主函数"""
    optimizer = SEOOptimizer()
    
    # 如果提供了次要关键词，从逗号分隔的字符串中解析
    if secondary_keywords and isinstance(secondary_keywords, str):
        secondary_keywords = [kw.strip() for kw in secondary_keywords.split(',')]
    
    results = optimizer.analyze(content, keyword, secondary_keywords)
    
    # 格式化输出
    output = [
        "=== SEO内容分析 ===",
        f"整体SEO得分: {results['optimization_score']}/100",
        f"内容长度: {results['content_length']} 字",
        f"",
        "内容结构:",
        f"  标题: {results['structure_analysis']['headings']['total']}",
        f"  段落: {results['structure_analysis']['paragraphs']}",
        f"  平均段落长度: {results['structure_analysis']['avg_paragraph_length']} 字",
        f"  内部链接: {results['structure_analysis']['links']['internal']}",
        f"  外部链接: {results['structure_analysis']['links']['external']}",
        f"",
        f"可读性: {results['readability']['level']}（得分: {results['readability']['score']}）",
        f""
    ]
    
    if results['keyword_analysis']:
        kw = results['keyword_analysis']['primary_keyword']
        output.extend([
            "关键词分析:",
            f"  主要关键词: {kw['keyword']}",
            f"  出现次数: {kw['count']}",
            f"  密度: {kw['density']:.2%}",
            f"  在第一段中: {'是' if kw['in_first_paragraph'] else '否'}",
            f""
        ])
        
        if results['keyword_analysis']['lsi_keywords']:
            output.append("  发现的相关关键词:")
            for lsi in results['keyword_analysis']['lsi_keywords'][:5]:
                output.append(f"    • {lsi}")
            output.append("")
    
    if results['meta_suggestions']:
        output.extend([
            "元标签建议:",
            f"  标题: {results['meta_suggestions']['title']}",
            f"  描述: {results['meta_suggestions']['meta_description']}",
            f"  URL slug: {results['meta_suggestions']['url_slug']}",
            f""
        ])
    
    output.extend([
        "建议:",
    ])
    
    for rec in results['recommendations']:
        output.append(f"  • {rec}")
    
    return '\n'.join(output)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            content = f.read()
        
        keyword = sys.argv[2] if len(sys.argv) > 2 else None
        secondary = sys.argv[3] if len(sys.argv) > 3 else None
        
        print(optimize_content(content, keyword, secondary))
    else:
        print("用法: python seo_optimizer.py <文件> [主要关键词] [次要关键词]")
