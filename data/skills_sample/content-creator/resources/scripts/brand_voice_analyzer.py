#!/usr/bin/env python3
"""
品牌语调分析器 - 分析内容以建立和维护品牌语调的一致性
"""

import re
from typing import Dict, List, Tuple
import json

class BrandVoiceAnalyzer:
    def __init__(self):
        self.voice_dimensions = {
            'formality': {
                'formal': ['hereby', 'therefore', 'furthermore', 'pursuant', 'regarding'],
                'casual': ['hey', 'cool', 'awesome', 'stuff', 'yeah', 'gonna']
            },
            'tone': {
                'professional': ['expertise', 'solution', 'optimize', 'leverage', 'strategic'],
                'friendly': ['happy', 'excited', 'love', 'enjoy', 'together', 'share']
            },
            'perspective': {
                'authoritative': ['proven', 'research shows', 'experts agree', 'data indicates'],
                'conversational': ['you might', 'let\'s explore', 'we think', 'imagine if']
            }
        }
    
    def analyze_text(self, text: str) -> Dict:
        """分析文本的品牌语调特征"""
        text_lower = text.lower()
        word_count = len(text.split())
        
        results = {
            'word_count': word_count,
            'readability_score': self._calculate_readability(text),
            'voice_profile': {},
            'sentence_analysis': self._analyze_sentences(text),
            'recommendations': []
        }
        
        # 分析语调维度
        for dimension, categories in self.voice_dimensions.items():
            dim_scores = {}
            for category, keywords in categories.items():
                score = sum(1 for keyword in keywords if keyword in text_lower)
                dim_scores[category] = score
            
            # 确定主导语调
            if sum(dim_scores.values()) > 0:
                dominant = max(dim_scores, key=dim_scores.get)
                results['voice_profile'][dimension] = {
                    'dominant': dominant,
                    'scores': dim_scores
                }
        
        # 生成建议
        results['recommendations'] = self._generate_recommendations(results)
        
        return results
    
    def _calculate_readability(self, text: str) -> float:
        """计算Flesch阅读易度得分"""
        sentences = re.split(r'[.!?]+', text)
        words = text.split()
        syllables = sum(self._count_syllables(word) for word in words)
        
        if len(sentences) == 0 or len(words) == 0:
            return 0
        
        avg_sentence_length = len(words) / len(sentences)
        avg_syllables_per_word = syllables / len(words)
        
        # Flesch阅读易度公式
        score = 206.835 - 1.015 * avg_sentence_length - 84.6 * avg_syllables_per_word
        return max(0, min(100, score))
    
    def _count_syllables(self, word: str) -> int:
        """计算单词中的音节数（简化版）"""
        word = word.lower()
        vowels = 'aeiou'
        syllable_count = 0
        previous_was_vowel = False
        
        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel
        
        # 调整静音e
        if word.endswith('e'):
            syllable_count -= 1
        
        return max(1, syllable_count)
    
    def _analyze_sentences(self, text: str) -> Dict:
        """分析句子结构"""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return {'average_length': 0, 'variety': 'low'}
        
        lengths = [len(s.split()) for s in sentences]
        avg_length = sum(lengths) / len(lengths) if lengths else 0
        
        # 计算多样性
        if len(set(lengths)) < 3:
            variety = 'low'
        elif len(set(lengths)) < 5:
            variety = 'medium'
        else:
            variety = 'high'
        
        return {
            'average_length': round(avg_length, 1),
            'variety': variety,
            'count': len(sentences)
        }
    
    def _generate_recommendations(self, analysis: Dict) -> List[str]:
        """根据分析生成建议"""
        recommendations = []
        
        # 可读性建议
        if analysis['readability_score'] < 30:
            recommendations.append("考虑简化语言以提高可读性")
        elif analysis['readability_score'] > 70:
            recommendations.append("内容非常易读 - 考虑是否与您的目标受众匹配")
        
        # 句子多样性
        if analysis['sentence_analysis']['variety'] == 'low':
            recommendations.append("变化句子长度以获得更好的流畅度和参与度")
        
        # 语调一致性
        if analysis['voice_profile']:
            recommendations.append("在所有内容中保持一致的语调")
        
        return recommendations

def analyze_content(content: str, output_format: str = 'json') -> str:
    """分析内容的主函数"""
    analyzer = BrandVoiceAnalyzer()
    results = analyzer.analyze_text(content)
    
    if output_format == 'json':
        return json.dumps(results, indent=2)
    else:
        # 人类可读格式
        output = [
            f"=== 品牌语调分析 ===",
            f"字数: {results['word_count']}",
            f"可读性得分: {results['readability_score']:.1f}/100",
            f"",
            f"语调特征:"
        ]
        
        for dimension, profile in results['voice_profile'].items():
            output.append(f"  {dimension.title()}: {profile['dominant']}")
        
        output.extend([
            f"",
            f"句子分析:",
            f"  平均长度: {results['sentence_analysis']['average_length']} 字",
            f"  多样性: {results['sentence_analysis']['variety']}",
            f"  总句子数: {results['sentence_analysis']['count']}",
            f"",
            f"建议:"
        ])
        
        for rec in results['recommendations']:
            output.append(f"  • {rec}")
        
        return '\n'.join(output)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            content = f.read()
        
        output_format = sys.argv[2] if len(sys.argv) > 2 else 'text'
        print(analyze_content(content, output_format))
    else:
        print("用法: python brand_voice_analyzer.py <文件> [json|text]")
