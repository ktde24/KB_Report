"""
뉴스 분석 모듈
- 네이버 금융 뉴스 크롤링 및 GPT 감정분석
- 레벨별 맞춤형 요약
- 해외 종목/키워드 지원
"""

import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional, List, Tuple
import time
import re
import random
from bs4 import BeautifulSoup
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import openai
from urllib.parse import urlparse
import os

# 프로젝트 루트 경로를 Python 경로에 추가
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 설정 클래스
class Config:
    NAVER_FINANCE_BASE_URL = "https://finance.naver.com"

    LEVEL_PROMPTS = {
        1: """- Level 1 (초보자): 
        • 어투: 유치원/초등학생도 이해할 수 있는 아주 쉬운 말로 설명
        • 내용: 투자 기초 개념 위주, 복잡한 용어는 비유와 예시로 대체
        • 길이: 1-2줄로 핵심만 요약""",
        
        2: """- Level 2 (입문자): 
        • 어투: 중고등학생도 이해 가능한 쉬운 말로 설명
        • 내용: 핵심 개념과 이유를 포함, 기본적인 투자 지식 전달
        • 길이: 1-2줄로 설명""",
        
        3: """- Level 3 (중급자): 
        • 어투: 일반 성인도 이해할 수 있는 수준으로 설명
        • 내용: 실전 팁과 구체적 전략 포함, 데이터 기반 분석
        • 길이: 1-2줄로 분석""",
        
        4: """- Level 4 (고급자): 
        • 어투: 투자 경험이 있는 성인을 대상으로 한 전문적 설명
        • 내용: 심화 분석과 고급 전략, 시장 동향과 연관성 분석
        • 길이: 1-2줄로 상세 설명""",
        
        5: """- Level 5 (전문가): 
        • 어투: 투자 전문가 수준의 고급 분석과 전문 용어 사용
        • 내용: 최고 수준 분석과 실전 활용, 시장 미시구조까지 고려
        • 길이: 1-2줄 이상으로 전문적 설명"""
    }

# 설정 객체
try:
    from chatbot.config import Config
    config = Config()
except ImportError:
    config = Config()

SYSTEM_PROMPT_ANALYSIS = """
- 당신은 뉴스 헤드라인 감성 분석기입니다.
- 사용자가 보낸 뉴스 헤드라인을 보고, 다음 3개의 필드만 "|" 로 구분해 한 줄로 출력하세요:
  1) 뉴스기사(원문 그대로)
  2) 긍부정 결과 (긍정/부정/중립 중 하나)
  3) 이유 (한 문장)
- 반드시 위 순서대로 "뉴스기사|긍부정 결과|이유" 형태로만 출력하고, 다른 설명은 절대 덧붙이지 마세요.
"""

class NewsAnalyzer:
    """뉴스 분석 클래스 - 네이버 금융 뉴스 전용"""
    
    def __init__(self):
        """초기화"""
        self.session = requests.Session()
        self.timeout = 10
        
        # 설정 객체
        self.config = config
        
        # User-Agent 랜덤화
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        selected_agent = random.choice(user_agents)
        
        # 헤더 설정 (네이버 뉴스 크롤링용)
        self.headers = {
            'User-Agent': selected_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': f'{self.config.NAVER_FINANCE_BASE_URL}/',
        }
        
        # 허용된 도메인 (네이버 금융만)
        self.allowed_domains = ['finance.naver.com', 'search.naver.com']
    
    def _is_valid_url(self, url: str) -> bool:
        """URL 유효성 검사"""
        try:
            parsed = urlparse(url)
            return parsed.netloc in self.allowed_domains
        except:
            return False
    
    def _sanitize_url(self, url: str) -> str:
        """URL 정규화 및 보안 검사"""
        if not url:
            return ""
        
        # 상대 URL을 절대 URL로 변환
        if url.startswith('/'):
            url = f"https://finance.naver.com{url}"
        
        # URL 유효성 검사
        if not self._is_valid_url(url):
            return ""
        
        return url
    
    def _is_relevant_news(self, headline: str, keyword: str) -> bool:
        """뉴스 관련성 검사"""
        if not headline or not keyword:
            return False
        
        headline_lower = headline.lower()
        keyword_lower = keyword.lower()
        
        # 키워드가 제목에 포함되어 있는지 확인
        return keyword_lower in headline_lower
    
    def _is_relevant_news_relaxed(self, headline: str, keyword: str) -> bool:
        """뉴스 관련성 검사 (더 관대하게)"""
        if not headline or not keyword:
            return False
        
        headline_lower = headline.lower()
        keyword_lower = keyword.lower()
        
        # 1. 정확한 키워드 매칭
        if keyword_lower in headline_lower:
            return True
        
        # 2. 해외 종목별 고유 키워드 매핑 (중복 방지)
        overseas_keywords = {
            'nvidia': ['엔비디아', 'nvidia', 'gpu', 'ai 반도체'],
            '엔비디아': ['엔비디아', 'nvidia', 'gpu', 'ai 반도체'],
            'amd': ['amd', '라이젠', 'amd 반도체'],
            'intel': ['인텔', 'intel', 'cpu', '인텔 반도체'],
            '인텔': ['인텔', 'intel', 'cpu', '인텔 반도체'],
            '퀄컴': ['퀄컴', 'qualcomm', '모바일', '5g'],
            '브로드컴': ['브로드컴', 'broadcom', '네트워크']
        }
        
        # 해당 종목의 고유 키워드만 확인
        if keyword_lower in overseas_keywords:
            for related_keyword in overseas_keywords[keyword_lower]:
                if related_keyword.lower() in headline_lower:
                    return True
        
        # 3. 종목명 + 주가/주식 키워드 조합 (더 정확한 매칭)
        stock_price_keywords = ['주가', '주식', '매수', '매도', '상승', '하락', '급등', '급락']
        for price_keyword in stock_price_keywords:
            if price_keyword in headline_lower and keyword_lower in headline_lower:
                return True
        
        # 4. 일반적인 금융 키워드 (종목명이 포함된 경우만)
        if keyword_lower in headline_lower:
            finance_keywords = ['투자', '증시', '펀드', 'etf', '채권', '금리', '경제']
            for finance_keyword in finance_keywords:
                if finance_keyword in headline_lower:
                    return True
        
        # 5. 기술 관련 키워드 (종목명이 포함된 경우만)
        if keyword_lower in headline_lower:
            tech_keywords = ['반도체', '칩', '메모리', 'ai', '인공지능', '머신러닝', '딥러닝']
            for tech_keyword in tech_keywords:
                if tech_keyword in headline_lower:
                    return True
        
        # 6. 해외 시장 관련 키워드 (종목명이 포함된 경우만)
        if keyword_lower in headline_lower:
            market_keywords = ['나스닥', 'nasdaq', '다우', 'dow', '월가', 'wall street', '미국']
            for market_keyword in market_keywords:
                if market_keyword in headline_lower:
                    return True
        
        return False
    
    def _is_relevant_news_strict(self, headline: str, keyword: str) -> bool:
        """뉴스 관련성 검사 (매우 엄격한 버전)"""
        if not headline or not keyword:
            return False
        
        headline_lower = headline.lower()
        keyword_lower = keyword.lower()
        
        # 1. 정확한 키워드 매칭 (가장 우선)
        if keyword_lower in headline_lower:
            return True
        
        # 2. 해외 종목별 고유 키워드 매핑 (더 구체적으로)
        stock_keywords = {
            'nvidia': ['엔비디아', 'nvidia', 'gpu', 'ai 반도체', 'h100', 'a100', '데이터센터', '엔비디아 주가'],
            '엔비디아': ['엔비디아', 'nvidia', 'gpu', 'ai 반도체', 'h100', 'a100', '데이터센터', '엔비디아 주가'],
            'nvda': ['엔비디아', 'nvidia', 'gpu', 'ai 반도체', 'h100', 'a100', '데이터센터', '엔비디아 주가'],
            'amd': ['amd', '라이젠', 'ryzen', 'epyc', 'amd 반도체', 'zen', 'amd 주가'],
            'intel': ['인텔', 'intel', 'cpu', '인텔 반도체', 'idm', 'foundry', '인텔 주가'],
            '인텔': ['인텔', 'intel', 'cpu', '인텔 반도체', 'idm', 'foundry', '인텔 주가'],
            'intc': ['인텔', 'intel', 'cpu', '인텔 반도체', 'idm', 'foundry', '인텔 주가'],
            '퀄컴': ['qualcomm', '퀄컴', '스냅드래곤', 'snapdragon', '모바일', '5g', '퀄컴 주가'],
            '브로드컴': ['브로드컴', 'broadcom', '네트워크', 'network', '브로드컴 주가'],
            '005930': ['삼성전자', '메모리', 'dram', 'nand', '갤럭시', 'galaxy', '삼성전자 주가'],
            '000660': ['sk하이닉스', 'hbm', '메모리', 'dram', 'nand', 'sk하이닉스 주가']
        }
        
        # 해당 종목의 고유 키워드만 확인
        if keyword_lower in stock_keywords:
            for related_keyword in stock_keywords[keyword_lower]:
                if related_keyword.lower() in headline_lower:
                    return True
        
        # 3. 종목명 + 주가/주식 키워드 조합 (정확한 매칭)
        stock_price_keywords = ['주가', '주식', '매수', '매도', '상승', '하락', '급등', '급락', '투자', '증시']
        for price_keyword in stock_price_keywords:
            if price_keyword in headline_lower and keyword_lower in headline_lower:
                return True
        
        # 4. 종목명 + 기술 키워드 조합 (정확한 매칭)
        tech_keywords = ['반도체', '칩', '메모리', 'ai', '인공지능', '머신러닝', '딥러닝', 'gpu', 'cpu', '데이터센터']
        for tech_keyword in tech_keywords:
            if tech_keyword in headline_lower and keyword_lower in headline_lower:
                return True
        
        # 5. 종목명 + 시장 키워드 조합 (정확한 매칭)
        market_keywords = ['나스닥', 'nasdaq', '다우', 'dow', '월가', 'wall street', '미국', '증시', '주식시장']
        for market_keyword in market_keywords:
            if market_keyword in headline_lower and keyword_lower in headline_lower:
                return True
        
        # 6. 일반적인 금융/투자 키워드는 제외 (너무 광범위함)
        general_finance_words = ['주식', '투자', '시장', '경제', '금융', '은행', '증권', '연체금', '신용사면', '빚', '324만명', '5000만원']
        if any(word in headline_lower for word in general_finance_words):
            # 일반적인 금융 키워드가 있으면 반드시 종목명도 함께 있어야 함
            if keyword_lower not in headline_lower:
                return False
        
        # 7. 특정 제외 키워드 (관련 없는 뉴스)
        exclude_keywords = ['연체금', '신용사면', '324만명', '5000만원', '빚', '연내', '갚으면']
        if any(word in headline_lower for word in exclude_keywords):
            # 제외 키워드가 있으면 반드시 종목명도 함께 있어야 함
            if keyword_lower not in headline_lower:
                return False
        
        return False
    
    def _search_naver_finance_news(self, keyword: str) -> List[Dict]:
        """네이버 금융 뉴스 검색 (국내/해외 종목 모두 지원)"""
        try:
            # 해외 종목 매핑 (영어명 → 한국어명)
            overseas_stocks = {
                'NVDA': '엔비디아',
                'AMD': 'AMD',
                'INTC': '인텔',
                'QCOM': '퀄컴',
                'AVGO': '브로드컴',
                'AAPL': '애플',
                'MSFT': '마이크로소프트',
                'GOOGL': '알파벳',
                'AMZN': '아마존',
                'TSLA': '테슬라',
                'META': '메타',
                'NFLX': '넷플릭스',
                'TSM': 'TSMC',
                'ASML': 'ASML',
                'SMIC': 'SMIC'
            }
            
            # 검색 키워드 리스트 생성
            search_keywords = [keyword]
            
            # 해외 종목인 경우 한국어 이름도 추가
            if keyword.upper() in overseas_stocks:
                korean_name = overseas_stocks[keyword.upper()]
                search_keywords.append(korean_name)
                logger.info(f"해외 종목 변환: {keyword} → {korean_name}")
            elif keyword in overseas_stocks:
                korean_name = overseas_stocks[keyword]
                search_keywords.append(korean_name)
                logger.info(f"해외 종목 변환: {keyword} → {korean_name}")
            
            # 영어명도 추가 (한국어명이 입력된 경우)
            reverse_mapping = {v: k for k, v in overseas_stocks.items()}
            if keyword in reverse_mapping:
                english_name = reverse_mapping[keyword]
                search_keywords.append(english_name)
                logger.info(f"한국어명 변환: {keyword} → {english_name}")
            
            logger.info(f"검색 키워드: {search_keywords}")
            
            # 1. 네이버 금융 종목별 뉴스 (국내 종목코드인 경우)
            if keyword.isdigit() and len(keyword) == 6:
                try:
                    url = f"{self.config.NAVER_FINANCE_BASE_URL}/item/news_news.naver?code={keyword}"
                    headers = {
                        "User-Agent": "Mozilla/5.0",
                        "Referer": url
                    }
                    
                    resp = self.session.get(url, headers=headers, timeout=self.timeout)
                    resp.raise_for_status()
                    
                    soup = BeautifulSoup(resp.text, "html.parser")
                    news_items = []
                    
                    # 뉴스 수집
                    for row in soup.select("table.type5 tbody tr"):
                        title_tag = row.select_one("td.title a.tit")
                        date_tag = row.select_one("td.date")
                        
                        if not title_tag or not date_tag:
                            continue
                        
                        try:
                            # 날짜 파싱
                            date_str = date_tag.text.strip()
                            dt = datetime.strptime(date_str, "%Y.%m.%d %H:%M")
                            
                            # 14일 이내 뉴스만
                            if dt < datetime.now() - timedelta(days=14):
                                continue
                            
                            headline = title_tag.text.strip()
                            
                            # URL 생성 
                            href = title_tag.get('href', '')
                            if href.startswith('/'):
                                href = f"{self.config.NAVER_FINANCE_BASE_URL}{href}"
                            
                            news_items.append({
                                'headline': headline,
                                'url': href,
                                'date': dt
                            })
                        
                        except ValueError:
                            continue
                    
                    # 날짜순 정렬 후 최근 3개 반환
                    news_items.sort(key=lambda x: x['date'], reverse=True)
                    result = []
                    for item in news_items[:3]:
                        result.append({
                            'headline': item['headline'],
                            'url': item['url']
                        })
                    
                    if result:
                        logger.info(f"네이버 금융 뉴스 수집 성공: {len(result)}개")
                        return result
                
                except Exception as e:
                    logger.debug(f"네이버 금융 뉴스 검색 실패 ({keyword}): {e}")
            
            # 2. 해외 종목/키워드 뉴스 검색 (여러 키워드로 시도)
            for search_keyword in search_keywords:
                try:
                    overseas_news = self._search_naver_finance_news_alt(search_keyword)
                    if overseas_news:
                        # 관련성 필터링 강화
                        filtered_news = []
                        for news in overseas_news:
                            if self._is_relevant_news_strict(news['headline'], keyword):
                                filtered_news.append(news)
                            elif len(filtered_news) < 1:  # 관련성이 낮은 뉴스는 최대 1개까지만
                                filtered_news.append(news)
                        
                        if filtered_news:
                            logger.info(f"키워드 '{search_keyword}'로 뉴스 수집 성공: {len(filtered_news)}개")
                            return filtered_news
                except Exception as e:
                    logger.debug(f"키워드 '{search_keyword}' 뉴스 검색 실패: {e}")
                    continue
            
            logger.warning(f"모든 키워드로 뉴스 검색 실패: {search_keywords}")
            return []
            
        except Exception as e:
            logger.debug(f"네이버 금융 뉴스 검색 실패 ({keyword}): {e}")
        return []
    
    def _search_naver_finance_news_alt(self, keyword: str) -> List[Dict]:
        """네이버 금융 뉴스 검색 (대안 방법)"""
        try:
            encoded_keyword = requests.utils.quote(keyword)
            # 네이버 금융 뉴스 검색 URL 사용
            url = f"https://finance.naver.com/news/news_search.naver?query={encoded_keyword}&searchType=0&page=1"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Referer": f"{self.config.NAVER_FINANCE_BASE_URL}/"
            }
            
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            news_items = []
            
            # 네이버 금융 뉴스 검색 결과에서 뉴스 링크 찾기
            news_selectors = [
                "table.type06 a[href*='news_read']",
                "table.type5 a[href*='news_read']",
                ".news_list a[href*='news_read']",
                "a[href*='news_read']"
            ]
            
            for selector in news_selectors:
                news_links = soup.select(selector)
                
                for link in news_links[:10]:
                    try:
                        headline = link.text.strip()
                        if not headline or len(headline) < 5:
                            continue
                        
                        href = link.get('href', '')
                        if not href:
                            continue
                        
                        # 상대 URL을 절대 URL로 변환
                        if href.startswith('/'):
                            href = f"{self.config.NAVER_FINANCE_BASE_URL}{href}"
                        
                        # 관련성 체크 (종목별 고유 뉴스 우선)
                        if self._is_relevant_news_strict(headline, keyword):
                            news_items.append({
                                'headline': headline,
                                'url': href
                            })
                        # 관련성이 낮은 뉴스는 뉴스가 부족한 경우에만 추가
                        elif len(news_items) < 1:
                            news_items.append({
                                'headline': headline,
                                'url': href
                            })
                        
                        if len(news_items) >= 3:
                            break
                            
                    except Exception as e:
                        continue
                
                if len(news_items) >= 3:
                    break
            
            logger.info(f"키워드 '{keyword}'로 {len(news_items)}개 뉴스 수집")
            return news_items
            
        except Exception as e:
            logger.debug(f"네이버 금융 뉴스 검색 실패 ({keyword}): {e}")
            return []
    
    def _search_naver_general_news(self, keyword: str) -> List[Dict]:
        """네이버 일반 뉴스 검색 (참고 코드 기반)"""
        try:
            encoded_keyword = requests.utils.quote(keyword)
            # 네이버 일반 뉴스 검색 URL 사용
            url = f'https://search.naver.com/search.naver?where=news&query={encoded_keyword}'
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }
            
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            news_items = []
            
            # 네이버 일반 뉴스 검색 결과에서 뉴스 제목과 링크 찾기
            # 여러 선택자 시도
            news_selectors = [
                '.news_tit',
                '.group_news a',
                '.group_news .news_tit',
                '.news_area a',
                '.news_area .news_tit',
                'a[href*="news.naver.com"]',
                '.group_news a[href*="news.naver.com"]'
            ]
            
            news_links = []
            for selector in news_selectors:
                links = soup.select(selector)
                if links:
                    news_links = links
                    logger.debug(f"네이버 일반 뉴스 선택자 성공: {selector}")
                    break
            
            for link in news_links[:10]:  # 최대 10개 뉴스에서 필터링
                try:
                    headline = link.text.strip()
                    if not headline or len(headline) < 5:
                        continue
                    
                    href = link.get('href', '')
                    if not href:
                        continue
                    
                    # 관련성 체크 (매우 엄격하게)
                    if self._is_relevant_news_strict(headline, keyword):
                        news_items.append({
                            'headline': headline,
                            'url': href
                        })
                    # 관련성이 낮은 뉴스는 제외 (일반 뉴스는 더 엄격하게)
                    
                    if len(news_items) >= 3:  # 최대 3개 뉴스
                        break
                        
                except Exception as e:
                    logger.debug(f"뉴스 파싱 오류: {e}")
                    continue
            
            logger.info(f"네이버 일반 뉴스에서 키워드 '{keyword}'로 {len(news_items)}개 뉴스 수집")
            return news_items
            
        except Exception as e:
            logger.debug(f"네이버 일반 뉴스 검색 실패 ({keyword}): {e}")
            return []
                
   
    
    def _get_stock_name(self, code: str) -> str:
        """종목코드로 종목명 가져오기"""
        stock_name_mapping = {
            # 국내 종목
            '005930': '삼성전자',
            '000660': 'SK하이닉스',
            '042700': '한미반도체',
            '035420': 'NAVER',
            '035720': '카카오',
            '373220': 'LG에너지솔루션',
            '207940': '삼성바이오로직스',
            '005380': '현대차',
            '000270': '기아',
            '005490': 'POSCO홀딩스',
            '051910': 'LG화학',
            '006400': '삼성SDI',
            '096770': 'SK이노베이션',
            '066570': 'LG전자',
            '032830': '삼성생명',
            '105560': 'KB금융',
            '055550': '신한지주',
            '086790': '하나금융지주',
            # 해외 종목 (티커 → 한국어명)
            'NVDA': 'NVIDIA',
            'AMD': 'AMD',
            'INTC': 'Intel',
            'QCOM': 'Qualcomm',
            'AVGO': 'Broadcom',
            'AAPL': 'Apple',
            'MSFT': 'Microsoft',
            'GOOGL': 'Alphabet',
            'AMZN': 'Amazon',
            'TSLA': 'Tesla',
            'META': 'Meta',
            'NFLX': 'Netflix',
            'TSM': 'TSMC',
            'ASML': 'ASML',
            'SMIC': 'SMIC'
        }
        
        return stock_name_mapping.get(code, code)
    
    def _get_keyword_mapping(self) -> Dict[str, List[str]]:
        """키워드별 관련 검색어 매핑"""
        return {
            'ETF': ['ETF', '상장지수펀드', '펀드'],
            '반도체': ['반도체', '칩', '메모리', 'DRAM', 'NAND'],
            '2차전지': ['2차전지', '배터리', '리튬', '전기차'],
            'KOSPI': ['KOSPI', '코스피', '주가', '증시'],
            '나스닥': ['나스닥', 'NASDAQ', '미국', '테크'],
            '다우존스': ['다우존스', '다우', 'DOW', '미국'],
            'S&P500': ['S&P500', 'SP500', '미국', '지수'],
            '월가': ['월가', 'Wall Street', '뉴욕', '미국'],
            'Fed': ['Fed', '연준', '연방준비제도', '미국'],
            '연준': ['연준', 'Fed', '연방준비제도', '미국']
        }
    
    def _extract_primary_keyword(self, keyword: str) -> str:
        """주요 키워드 추출"""
        keyword_mapping = self._get_keyword_mapping()
        
        for primary_keyword, related_keywords in keyword_mapping.items():
            if keyword.upper() in [kw.upper() for kw in related_keywords]:
                return primary_keyword
        
        return keyword
    
    def _get_related_keywords(self, keyword: str) -> List[str]:
        """관련 키워드 가져오기"""
        keyword_mapping = self._get_keyword_mapping()
        
        # 주요 키워드 추출
        primary_keyword = self._extract_primary_keyword(keyword)
        
        # 관련 키워드 반환
        if primary_keyword in keyword_mapping:
            return keyword_mapping[primary_keyword]
        
        # 매핑되지 않은 경우 원본 키워드만 반환
        return [keyword]
    
    def _search_naver_news_with_keywords(self, main_keyword: str, related_keywords: List[str]) -> List[Dict]:
        """여러 키워드로 뉴스 검색 (중복 제거 강화)"""
        all_news = []
        seen_urls = set()  # URL 기반 중복 체크
        seen_headlines = set()  # 헤드라인 기반 중복 체크
        
        # 메인 키워드로 먼저 검색
        main_news = self._search_naver_finance_news(main_keyword)
        if main_news:
            for news in main_news:
                url = news.get('url', '')
                headline = news.get('headline', '').strip()
                
                # URL과 헤드라인 모두 체크
                if url not in seen_urls and headline not in seen_headlines:
                    all_news.append(news)
                    seen_urls.add(url)
                    seen_headlines.add(headline)
        
        # 관련 키워드로 추가 검색 (중복 제거)
        for keyword in related_keywords:
            if len(all_news) >= 5:  # 최대 5개 뉴스면 중단
                break
                
            keyword_news = self._search_naver_finance_news(keyword)
            if keyword_news:
                for news in keyword_news:
                    if len(all_news) >= 5:
                        break
                    
                    url = news.get('url', '')
                    headline = news.get('headline', '').strip()
                    
                    # URL과 헤드라인 모두 체크하여 중복 제거
                    if url not in seen_urls and headline not in seen_headlines:
                        all_news.append(news)
                        seen_urls.add(url)
                        seen_headlines.add(headline)
        
        logger.info(f"키워드 '{main_keyword}'로 중복 제거 후 {len(all_news)}개 뉴스 수집")
        return all_news
    
    def _search_naver_news_simple(self, keyword: str) -> List[Dict]:
        """네이버 금융 뉴스 검색 (중복 제거 강화)"""
        if not keyword:
            return []
        
        all_news = []
        seen_urls = set()
        seen_headlines = set()
        
        # 1. 네이버 금융 뉴스 시도
        finance_news = self._search_naver_finance_news(keyword)
        if finance_news:
            for news in finance_news:
                url = news.get('url', '')
                headline = news.get('headline', '').strip()
                if url not in seen_urls and headline not in seen_headlines:
                    all_news.append(news)
                    seen_urls.add(url)
                    seen_headlines.add(headline)
        
        # 2. 네이버 금융 뉴스 대안 검색 시도
        if len(all_news) < 3:  # 3개 미만이면 추가 검색
            alt_news = self._search_naver_finance_news_alt(keyword)
            if alt_news:
                for news in alt_news:
                    if len(all_news) >= 5:  # 최대 5개
                        break
                    url = news.get('url', '')
                    headline = news.get('headline', '').strip()
                    if url not in seen_urls and headline not in seen_headlines:
                        all_news.append(news)
                        seen_urls.add(url)
                        seen_headlines.add(headline)
        
        # 3. 키워드 변형으로 재시도 (뉴스가 부족한 경우)
        if len(all_news) < 2:
            variations = self._get_keyword_variations(keyword)
            for variation in variations:
                if variation != keyword and len(all_news) < 3:
                    news = self._search_naver_finance_news_alt(variation)
                    if news:
                        for item in news:
                            if len(all_news) >= 5:
                                break
                            url = item.get('url', '')
                            headline = item.get('headline', '').strip()
                            if url not in seen_urls and headline not in seen_headlines:
                                all_news.append(item)
                                seen_urls.add(url)
                                seen_headlines.add(headline)
                        if all_news:
                            logger.info(f"키워드 변형 '{variation}'로 뉴스 수집 성공")
                            break
        
        if not all_news:
            logger.warning(f"모든 방법으로 '{keyword}' 관련 뉴스를 찾을 수 없습니다.")
        
        logger.info(f"'{keyword}' 최종 뉴스 수집: {len(all_news)}개")
        return all_news
    
    def _get_keyword_variations(self, keyword: str) -> List[str]:
        """키워드 변형 생성 (종목별 고유화)"""
        variations = [keyword]
        
        # 해외 종목별 고유 키워드 매핑 (중복 방지)
        stock_variations = {
            'nvidia': ['엔비디아', 'nvidia', 'gpu', 'ai 반도체', '엔비디아 주가'],
            '엔비디아': ['nvidia', '엔비디아', 'gpu', 'ai 반도체', '엔비디아 주가'],
            'amd': ['amd', 'amd 주가', '라이젠', 'amd 반도체'],
            'intel': ['인텔', 'intel', 'cpu', '인텔 주가', '인텔 반도체'],
            '인텔': ['intel', '인텔', 'cpu', '인텔 주가', '인텔 반도체'], 
            '퀄컴': ['qualcomm', '퀄컴', '모바일', '5g', '퀄컴 주가'],
            '브로드컴': ['broadcom', '브로드컴', '반도체', '브로드컴 주가']
        }
        
        keyword_lower = keyword.lower()
        if keyword_lower in stock_variations:
            # 해당 종목의 고유 키워드만 사용
            variations.extend(stock_variations[keyword_lower])
        
        # 일반적인 키워드 변형 (종목별 고유화)
        if '반도체' in keyword and keyword not in ['엔비디아', 'nvidia', 'amd', 'intel', '인텔', '퀄컴', '브로드컴']:
            variations.extend(['반도체 주식', '반도체 시장', 'ai 반도체'])
        if 'etf' in keyword.lower():
            variations.extend(['ETF', '상장지수펀드', '펀드'])
        
        return list(set(variations))  # 중복 제거
    
    def fetch_naver_news(self, code: str) -> List[Dict]:
        """네이버 뉴스 헤드라인과 링크 가져오기"""
        try:
            # 입력 검증
            if not code or not isinstance(code, str):
                logger.warning("유효하지 않은 코드 입력")
                return []
            
            logger.info(f"뉴스 검색 시작: {code}")
            
            # 종목명 가져오기
            stock_name = self._get_stock_name(code)
            if not stock_name:
                logger.warning(f"종목명을 찾을 수 없음: {code}")
                return []
            
            # 해외 종목 매핑 (영어명 → 한국어명)
            overseas_stocks = {
                'NVDA': 'NVIDIA',
                'AMD': 'AMD', 
                'INTC': 'Intel',
                'QCOM': 'Qualcomm',
                'AVGO': 'Broadcom',
                'AAPL': 'Apple',
                'MSFT': 'Microsoft',
                'GOOGL': 'Alphabet',
                'AMZN': 'Amazon',
                'TSLA': 'Tesla',
                'META': 'Meta',
                'NFLX': 'Netflix',
                'TSM': 'TSMC',
                'ASML': 'ASML',
                'SMIC': 'SMIC'
            }
            
            # 검색 키워드 리스트 생성
            search_keywords = [code, stock_name]
            
            # 해외 종목인 경우 영어명과 한국어명 모두 추가
            if code.upper() in overseas_stocks:
                english_name = code.upper()
                korean_name = overseas_stocks[code.upper()]
                search_keywords.extend([english_name, korean_name])
                logger.info(f"해외 종목 변환: {code} → {english_name}, {korean_name}")
            
            # 중복 제거
            search_keywords = list(set(search_keywords))
            logger.info(f"검색 키워드: {search_keywords}")
            
        
            seen_urls = set()
            seen_headlines = set()
            all_news = []
            
            # 1. 메인 키워드로 네이버 금융 뉴스 검색
            for keyword in search_keywords[:3]:  # 최대 3개 키워드만 사용
                if len(all_news) >= 5:  # 최대 5개 뉴스로 제한
                    break
                    
                logger.info(f"키워드로 금융 뉴스 검색: {keyword}")
                finance_news = self._search_naver_finance_news(keyword)
                
                for news in finance_news:
                    if (news['url'] not in seen_urls and 
                        news['headline'] not in seen_headlines and
                        len(all_news) < 5):
                        seen_urls.add(news['url'])
                        seen_headlines.add(news['headline'])
                        all_news.append(news)
            
            # 2. 금융 뉴스가 부족한 경우 일반 뉴스 검색
            if len(all_news) < 3:
                for keyword in search_keywords[:2]:  # 최대 2개 키워드만 사용
                    if len(all_news) >= 5:
                        break
                        
                    logger.info(f"키워드로 일반 뉴스 검색: {keyword}")
                    general_news = self._search_naver_general_news(keyword)
                    
                    for news in general_news:
                        if (news['url'] not in seen_urls and 
                            news['headline'] not in seen_headlines and
                            len(all_news) < 5):
                            seen_urls.add(news['url'])
                            seen_headlines.add(news['headline'])
                            all_news.append(news)
            
            # 3. 관련성 필터링 (매우 엄격하게)
            filtered_news = []
            for news in all_news:
                # 메인 키워드와 관련성 체크
                is_relevant = False
                for keyword in search_keywords[:2]:  # 메인 키워드 2개만 체크
                    if self._is_relevant_news_strict(news['headline'], keyword):
                        is_relevant = True
                        break
                
                # 추가 필터링: 제외 키워드가 있으면 완전히 제외
                headline_lower = news['headline'].lower()
                exclude_keywords = ['연체금', '신용사면', '324만명', '5000만원', '빚', '연내', '갚으면']
                has_exclude_keyword = any(word in headline_lower for word in exclude_keywords)
                
                # 종목명이 포함되어 있지 않으면 제외
                has_stock_name = any(keyword.lower() in headline_lower for keyword in search_keywords[:2])
                
                if is_relevant and not has_exclude_keyword and has_stock_name:
                    filtered_news.append(news)
                elif len(filtered_news) < 1 and not has_exclude_keyword and has_stock_name:  # 관련성이 낮은 뉴스는 최대 1개까지만
                    filtered_news.append(news)
            
            logger.info(f"최종 수집된 뉴스: {len(filtered_news)}개")
            return filtered_news
            
        except Exception as e:
            logger.error(f"뉴스 수집 중 오류 발생 ({code}): {e}")
        return []
    
    def analyze_news_sentiment(self, news_items: List[Dict], api_key: str = None) -> List[Dict]:
        """뉴스 감정분석 (GPT 활용)"""
        try:
            # API 키 설정
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                logger.warning("OpenAI API 키가 설정되지 않았습니다.")
                return [{"error": "API 키가 설정되지 않았습니다."}]
            
            client = openai.OpenAI(api_key=api_key)
            
            results = []
            
            for news in news_items:
                headline = news.get('headline', '')
                if not headline:
                    continue
                
                try:
                    # GPT 감정분석 요청
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT_ANALYSIS},
                            {"role": "user", "content": headline}
                        ],
                        max_tokens=100,
                        temperature=0.3
                    )
                    
                    # 응답 파싱
                    analysis_text = response.choices[0].message.content.strip()
                    parts = analysis_text.split('|')
                    
                    if len(parts) >= 3:
                        sentiment_result = {
                            'headline': parts[0].strip(),
                            'sentiment': parts[1].strip(),
                            'reason': parts[2].strip()
                        }
                    else:
                        sentiment_result = {
                            'headline': headline,
                            'sentiment': '중립',
                            'reason': '분석 실패'
                        }
                    
                    results.append(sentiment_result)
                    
                except Exception as e:
                    logger.error(f"감정분석 실패 ({headline}): {e}")
                    results.append({
                        'headline': headline,
                        'sentiment': '중립',
                        'reason': f'분석 오류: {e}'
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"감정분석 중 오류 발생: {e}")
            return [{"error": f"감정분석 오류: {e}"}]
    
    def generate_level_summary(self, news_items: List[Dict], level: int, api_key: str = None, mpti_type: str = 'Fact') -> str:
        """레벨별 뉴스 요약 생성 (GPT 활용)"""
        try:
            # API 키 설정
            if not api_key:
                api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                return "OpenAI API 키가 설정되지 않았습니다."
            
            client = openai.OpenAI(api_key=api_key)
            
            # 뉴스 헤드라인 수집
            headlines = [news.get('headline', '') for news in news_items if news.get('headline')]
            
            if not headlines:
                return "분석할 뉴스가 없습니다."
            
            # 레벨별 프롬프트 가져오기
            level_prompt = config.LEVEL_PROMPTS.get(level, config.LEVEL_PROMPTS[3])
            
            # 요약 프롬프트 생성
            summary_prompt = f"""
다음 뉴스 헤드라인들을 분석하여 {level_prompt}에 맞는 요약을 생성해주세요.

뉴스 헤드라인:
{chr(10).join([f"- {headline}" for headline in headlines])}

요구사항:
1. {level_prompt}
2. MPTI 타입: {mpti_type}
3. 1-2줄로 간결하게 요약
4. 투자 관점에서 분석

요약:
"""
            
            # GPT 요약 요청
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 투자 전문가입니다. 뉴스를 분석하여 투자자에게 유용한 인사이트를 제공합니다."},
                    {"role": "user", "content": summary_prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            return summary
            
        except Exception as e:
            logger.error(f"요약 생성 중 오류 발생: {e}")
            return f"요약 생성 중 오류가 발생했습니다: {e}"
    
    def display_news_analysis(self, code: str, level: int, mpti_type: str):
        """뉴스 분석 결과 표시 (Streamlit)"""
        st.subheader("📰 뉴스 분석")
        
        # 뉴스 수집
        news_items = self.fetch_naver_news(code)
        
        if not news_items:
            st.warning("관련 뉴스를 찾을 수 없습니다.")
            return
        
        # 감정분석
        sentiment_results = self.analyze_news_sentiment(news_items)
        
        # 요약 생성
        summary = self.generate_level_summary(news_items, level, mpti_type)
        
        # 결과 표시
        st.write("**📊 뉴스 요약**")
        st.write(summary)
        
        st.write("**📈 감정분석 결과**")
        for i, result in enumerate(sentiment_results, 1):
            if 'error' in result:
                st.error(result['error'])
            else:
                col1, col2, col3 = st.columns([3, 1, 2])
                with col1:
                    st.write(f"{i}. {result['headline']}")
                with col2:
                    sentiment = result['sentiment']
                    if sentiment == '긍정':
                        st.success("긍정")
                    elif sentiment == '부정':
                        st.error("부정")
                    else:
                        st.info("중립")
                with col3:
                    st.write(result['reason'])
        
        # 원문 링크 (헤드라인 표시 개선)
        st.write("**🔗 관련 뉴스**")
        for i, news in enumerate(news_items, 1):
            headline = news.get('headline', '')
            url = news.get('url', '')
            if headline and url:
                st.markdown(f"{i}. **{headline}**")
                st.markdown(f"   [원문 보기]({url})")
                st.write("---")

    def test_news_search(self, code: str):
        """뉴스 검색 테스트 함수"""
        print(f"=== 뉴스 검색 테스트: {code} ===")
        
        # 종목명 가져오기
        stock_name = self._get_stock_name(code)
        print(f"종목명: {stock_name}")
        
        # 뉴스 검색
        news_items = self.fetch_naver_news(code)
        print(f"수집된 뉴스 수: {len(news_items)}")
        
        for i, news in enumerate(news_items, 1):
            print(f"{i}. {news['headline']}")
            print(f"   URL: {news['url']}")
            print()
        
        return news_items
