"""
뉴스 분석 모듈
- 네이버 뉴스 크롤링 및 GPT 감정분석
- 레벨별 맞춤형 요약
"""

import streamlit as st
import requests
import logging
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import openai
import urllib.parse
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 레벨별 스타일 프롬프트
try:
    from chatbot.config import Config
    LEVEL_PROMPTS = Config.LEVEL_PROMPTS
except ImportError:
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

SYSTEM_PROMPT_ANALYSIS = """
- 당신은 뉴스 헤드라인 감성 분석기입니다.
- 사용자가 보낸 뉴스 헤드라인을 보고, 다음 3개의 필드만 "|" 로 구분해 한 줄로 출력하세요:
  1) 뉴스기사(원문 그대로)
  2) 긍부정 결과 (긍정/부정/중립 중 하나)
  3) 이유 (한 문장)
- 반드시 위 순서대로 "뉴스기사|긍부정 결과|이유" 형태로만 출력하고, 다른 설명은 절대 덧붙이지 마세요.
"""

class NewsAnalyzer:
    """뉴스 분석 클래스"""
    
    def __init__(self):
        """초기화"""
        self.session = requests.Session()
        self.max_retries = 3
        self.timeout = 10
        self.request_delay = 2
        

        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        
        import random
        selected_agent = random.choice(user_agents)
        
        # 더 현실적인 헤더 설정
        self.session.headers.update({
            'User-Agent': selected_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Referer': 'https://www.naver.com/',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        })
        
        # 세션 쿠키 설정 (네이버 차단 우회)
        self.session.cookies.update({
            'NNB': 'random_string_here',
            'nx_ssl': '2',
            'ASID': 'random_string_here'
        })
        
        self.timeout = 20  # 20초 타임아웃으로 증가
        self.max_retries = 3  # 최대 재시도 횟수
        self.request_delay = 3  # 요청 간격 증가 (3초)
    
    def _is_valid_url(self, url: str) -> bool:
        """URL 유효성 검사"""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def _sanitize_url(self, url: str) -> str:
        """URL 정규화 및 보안 검사"""
        if not url:
            return ""
        
        # 상대 경로를 절대 경로로 변환
        if url.startswith('/'):
            url = f"https://search.naver.com{url}"
        elif not url.startswith('http'):
            url = f"https://search.naver.com/{url}"
        
        # URL 유효성 검사
        if not self._is_valid_url(url):
            return ""
        
        # 허용된 도메인만 허용
        allowed_domains = ['search.naver.com', 'news.naver.com', 'finance.naver.com']
        parsed = urlparse(url)
        if parsed.netloc not in allowed_domains:
            return ""
        
        return url
    
    def _is_relevant_news(self, headline: str, keyword: str) -> bool:
        """뉴스 헤드라인이 키워드와 관련있는지 검증"""
        if not headline or not keyword:
            return False
        
        headline_lower = headline.lower()
        keyword_lower = keyword.lower()
        
        # 키워드별 관련 단어 정의
        keyword_related_words = {
            'kbstar': ['kbstar', 'kb스타', 'kb star', 'etf', '투자', '주식', '펀드'],
            '200': ['200', 'kospi', '코스피', '지수', '시장'],
            '반도체': ['반도체', '삼성전자', 'sk하이닉스', '메모리', '칩'],
            '2차전지': ['2차전지', '배터리', 'lg에너지솔루션', '삼성sdi', '전기차'],
            '삼성전자': ['삼성전자', '삼성', '전자', '반도체', '메모리'],
            'sk하이닉스': ['sk하이닉스', 'sk', '하이닉스', '메모리', '반도체'],
            'lg에너지솔루션': ['lg에너지솔루션', 'lg', '에너지', '배터리', '2차전지']
        }
        
        # 키워드에서 관련 단어 찾기
        related_words = []
        for key, words in keyword_related_words.items():
            if key in keyword_lower:
                related_words.extend(words)
        
        # 기본 관련 단어 추가
        related_words.extend(['투자', '주식', 'etf', '펀드', '금융', '시장'])
        
        # 헤드라인에 관련 단어가 포함되어 있는지 확인
        for word in related_words:
            if word in headline_lower:
                return True
        
        # 키워드 자체가 헤드라인에 포함되어 있는지 확인
        if keyword_lower in headline_lower:
            return True
        
        return False
    
    def _search_naver_finance_news(self, keyword: str) -> List[Dict]:
        """네이버 금융 뉴스 검색 (Jupyter Notebook 코드 참고)"""
        try:
            # 네이버 금융 뉴스 URL (사용자 코드와 동일)
            url = f"https://finance.naver.com/item/news_news.naver?code={keyword}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer": url
            }
            
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            news_items = []
            
            # 사용자 코드와 동일한 방식으로 뉴스 수집
            for row in soup.select("table.type5 tbody tr"):
                title_tag = row.select_one("td.title a.tit")
                date_tag = row.select_one("td.date")
                
                if not title_tag or not date_tag:
                    continue
                
                try:
                    # 날짜 파싱 (사용자 코드와 동일)
                    date_str = date_tag.text.strip()
                    dt = datetime.strptime(date_str, "%Y.%m.%d %H:%M")
                    
                    # 14일 이내 뉴스만
                    if dt < datetime.now() - timedelta(days=14):
                        continue
                    
                    headline = title_tag.text.strip()
                    
                    # URL 생성 (사용자 코드와 동일)
                    href = title_tag.get('href', '')
                    if href.startswith('/'):
                        href = f"https://finance.naver.com{href}"
                    
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
        
        return []
    
    def fetch_naver_news(self, code: str) -> List[Dict]:
        """네이버 뉴스 헤드라인과 링크 가져오기"""
        try:
            # 입력 검증
            if not code or not isinstance(code, str):
                logger.warning("유효하지 않은 코드 입력")
                return []
            
            # 종목명을 종목코드로 변환
            stock_code_mapping = {
                '삼성전자': '005930',
                'SK하이닉스': '000660',
                '한미반도체': '042700',
                'NAVER': '035420',
                '카카오': '035720',
                'LG에너지솔루션': '373220',
                '삼성바이오로직스': '207940',
                '현대차': '005380',
                '기아': '000270',
                'POSCO홀딩스': '005490',
                'LG화학': '051910',
                '삼성SDI': '006400',
                'SK이노베이션': '096770',
                'LG전자': '066570',
                '삼성생명': '032830',
                'KB금융': '105560',
                '신한지주': '055550',
                '하나금융지주': '086790'
            }
            
            # 종목명이면 종목코드로 변환
            if code in stock_code_mapping:
                code = stock_code_mapping[code]
            
            # 키워드 기반 검색 (ETF, 반도체 등)
            if not code.isdigit() and ('ETF' in code.upper() or '반도체' in code or '2차전지' in code or 'KOSPI' in code.upper()):
                # 키워드별 관련 검색어 추가
                related_keywords = self._get_related_keywords(code)
                news_items = self._search_naver_news_with_keywords(code, related_keywords)
                
                # 뉴스 수집 실패 시 빈 리스트 반환
                if not news_items:
                    logger.warning(f"뉴스 수집 실패: {code}")
                    return []
                
                return news_items
            
            # 종목 코드 기반 검색
            if code.isdigit():
                # 종목코드로 직접 네이버 금융 뉴스 검색
                news_items = self._search_naver_finance_news(code)
                
                # 뉴스 수집 실패 시 빈 리스트 반환
                if not news_items:
                    logger.warning(f"뉴스 수집 실패: {code}")
                    return []
                
                return news_items
            
            # 기본 키워드로 검색
            news_items = self._search_naver_news_simple('주식 투자')
            
            # 뉴스 수집 실패 시 빈 리스트 반환
            if not news_items:
                logger.warning(f"뉴스 수집 실패: {code}")
                return []
            
            return news_items
            
        except Exception as e:
            logger.error(f"뉴스 크롤링 실패 ({code}): {e}")
            return []
    
    def _get_stock_name(self, code: str) -> str:
        """종목 코드로 종목명 가져오기"""
        stock_names = {
            '091160': 'KBSTAR 200',
            '091170': 'KBSTAR 코스닥150',
            '091230': 'KBSTAR 반도체',
            '306540': 'KBSTAR 2차전지테마',
            '233740': 'KBSTAR K-뉴딜디지털플러스',
            '005930': '삼성전자',
            '000660': 'SK하이닉스',
            '035420': 'NAVER',
            '035720': '카카오',
            '373220': 'LG에너지솔루션'
        }
        return stock_names.get(code, '')
    
    def _get_keyword_mapping(self) -> Dict[str, List[str]]:
        """키워드 매핑 규칙 정의"""
        return {
            # ETF 관련 키워드
            'etf': {
                '반도체': ['반도체', '반도체주', '반도체 ETF'],
                '2차전지': ['2차전지', '배터리', '2차전지 ETF'],
                '배터리': ['2차전지', '배터리', '배터리 ETF'],
                'kospi': ['KOSPI', '코스피', '대형주', 'KOSPI ETF'],
                'kosdaq': ['KOSDAQ', '코스닥', '중소형주', 'KOSDAQ ETF'],
                'default': ['주식', '투자']
            },
            # 섹터별 키워드
            '반도체': ['반도체', '반도체주', '반도체 산업', '메모리'],
            '2차전지': ['2차전지', '배터리', '전기차 배터리', '리튬'],
            '배터리': ['2차전지', '배터리', '전기차 배터리', '리튬'],
            'kospi': ['KOSPI', '코스피', '대형주', '주식시장'],
            'kosdaq': ['KOSDAQ', '코스닥', '중소형주', '기술주'],
            'ai': ['AI', '인공지능', '머신러닝', '딥러닝'],
            '바이오': ['바이오', '제약', '의료', '헬스케어'],
            '게임': ['게임', '게임주', '모바일게임', '콘텐츠'],
            '전기차': ['전기차', 'EV', '테슬라', '전기자동차'],
            '신재생': ['신재생', '태양광', '풍력', '친환경'],
            '금융': ['금융', '은행', '보험', '증권'],
            '부동산': ['부동산', 'REITs', '아파트', '건설']
        }
    
    def _extract_primary_keyword(self, keyword: str) -> str:
        """키워드에서 주요 키워드 추출"""
        keyword_lower = keyword.lower()
        
        # 우선순위가 높은 키워드부터 매칭
        priority_keywords = [
            '반도체', '2차전지', '배터리', 'kospi', 'kosdaq', 
            'ai', '바이오', '게임', '전기차', '신재생', '금융', '부동산'
        ]
        
        for primary in priority_keywords:
            if primary in keyword_lower:
                return primary
        
        # ETF 키워드 체크
        if 'etf' in keyword_lower:
            return 'etf'
        
        return 'default'
    
    def _get_related_keywords(self, keyword: str) -> List[str]:
        """키워드에 따른 관련 검색어 생성 """
        if not keyword or not isinstance(keyword, str):
            return []
        
        # 키워드 정규화
        keyword = keyword.strip()
        if not keyword:
            return []
        
        related_keywords = set([keyword])  # 원본 키워드 
        keyword_mapping = self._get_keyword_mapping()
        
        # 주요 키워드 추출
        primary_keyword = self._extract_primary_keyword(keyword)
        
        # ETF 키워드인 경우 특별 처리
        if primary_keyword == 'etf':
            etf_mapping = keyword_mapping.get('etf', {})
            
            # ETF 키워드에서 세부 주제 추출
            keyword_lower = keyword.lower()
            for etf_type, related_list in etf_mapping.items():
                if etf_type != 'default' and etf_type in keyword_lower:
                    related_keywords.update(related_list)
                    break
            else:
                # 기본 ETF 키워드
                related_keywords.update(etf_mapping.get('default', ['주식', '투자']))
        
        # 일반 섹터 키워드 처리
        elif primary_keyword in keyword_mapping:
            related_keywords.update(keyword_mapping[primary_keyword])
        
        # 기본 키워드 추가 
        if primary_keyword != 'default':
            related_keywords.add('투자')
        
        # 키워드 품질 필터링
        filtered_keywords = []
        for kw in related_keywords:
            if len(kw) >= 2 and not kw.isdigit():  # 최소 2글자, 숫자만 있는 키워드 제외
                filtered_keywords.append(kw)
        
        # 최대 5개까지 반환
        result = [keyword]  # 원본 키워드를 첫 번째로
        for kw in filtered_keywords:
            if kw != keyword and len(result) < 5:
                result.append(kw)
        
        logger.info(f"키워드 '{keyword}' -> 관련 키워드: {result}")
        return result
    
    def _search_naver_news_with_keywords(self, main_keyword: str, related_keywords: List[str]) -> List[Dict]:
        """여러 키워드로 뉴스 검색 (개선된 버전)"""
        all_news = []
        seen_headlines = set()  # 중복 헤드라인 추적
        
        # 키워드별 검색 우선순위 설정
        search_keywords = []
        
        # 1. 원본 키워드 우선
        if main_keyword:
            search_keywords.append(main_keyword)
        
        # 2. 관련 키워드 추가
        for keyword in related_keywords:
            if keyword not in search_keywords:
                search_keywords.append(keyword)
        
        # 최대 3개 키워드만 검색
        search_keywords = search_keywords[:3]
        
        for keyword in search_keywords:
            if len(all_news) >= 3:  # 최대 3개 뉴스면 중단
                break
                
            logger.info(f"키워드 '{keyword}'로 뉴스 검색 시도")
            keyword_news = self._search_naver_news_simple(keyword)
            
            # 중복 제거하면서 추가
            for news in keyword_news:
                if len(all_news) >= 3:
                    break
                # 중복 체크 (제목 기준)
                headline = news.get('headline', '')
                if headline and headline not in seen_headlines:
                    seen_headlines.add(headline)
                    all_news.append(news)
        
        logger.info(f"키워드 '{main_keyword}'로 최종 {len(all_news)}개 뉴스 수집")
        return all_news
    
    def _search_naver_news_simple(self, keyword: str) -> List[Dict]:
        """네이버 뉴스 검색 (재시도 로직 포함)"""
        if not keyword:
            return []
        
        # 먼저 네이버 금융 뉴스 시도 (사용자 코드와 동일한 방식)
        finance_news = self._search_naver_finance_news(keyword)
        if finance_news:
            return finance_news
        
        # 네이버 금융 뉴스 실패 시 일반 검색 시도
        for attempt in range(self.max_retries):
            try:
                # 요청 간격 추가 (첫 번째 요청 제외)
                if attempt > 0:
                    import time
                    time.sleep(self.request_delay)
                
                encoded_keyword = urllib.parse.quote(keyword)
                url = f"https://search.naver.com/search.naver?where=news&query={encoded_keyword}"
                
                logger.info(f"뉴스 검색 시도 {attempt + 1}/{self.max_retries}: {keyword}")
                
                # 요청 전에 세션 헤더 재설정 (403 오류 방지)
                if attempt > 0:
                    import random
                    user_agents = [
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    ]
                    self.session.headers['User-Agent'] = random.choice(user_agents)
                
                resp = self.session.get(url, timeout=self.timeout)
                
                # 403 오류 특별 처리
                if resp.status_code == 403:
                    logger.warning(f"403 Forbidden 오류 발생 ({keyword}), 대체 방법 시도")
                    # 대체 검색 방법 시도
                    alternative_news = self._search_alternative_news(keyword)
                    if alternative_news:
                        return alternative_news
                    continue
                
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, "html.parser")
                news_items = []
                
                # 뉴스 링크 찾기 (여러 선택자 시도)
                news_links = soup.select("a.news_tit")
                if not news_links:
                    news_links = soup.select(".news_area a")
                if not news_links:
                    news_links = soup.select("a[href*='news.naver.com']")
                
                for link in news_links[:5]:  # 더 많은 뉴스 수집 후 필터링
                    headline = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # 강화된 헤드라인 필터링
                    if (headline and 
                        len(headline) > 10 and 
                        '언론사' not in headline and 
                        '구독' not in headline and
                        '선정' not in headline and
                        '날씨' not in headline and  # 날씨 뉴스 제외
                        '북한' not in headline and  # 북한 관련 뉴스 제외
                        '정치' not in headline and  # 정치 뉴스 제외
                        '사회' not in headline):    # 사회 뉴스 제외
                        
                        # 키워드 관련성 검증
                        if self._is_relevant_news(headline, keyword):
                            # URL 정규화 및 보안 검사
                            sanitized_url = self._sanitize_url(href)
                            if sanitized_url:
                                news_items.append({
                                    'headline': headline,
                                    'url': sanitized_url
                                })
                
                # 최대 3개만 반환
                if news_items:
                    logger.info(f"수집된 뉴스: {len(news_items)}개")
                    return news_items[:3]
                
            except requests.exceptions.Timeout:
                logger.warning(f"뉴스 검색 타임아웃 ({keyword}), 재시도 {attempt + 1}/{self.max_retries}")
                if attempt == self.max_retries - 1:
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"뉴스 검색 네트워크 오류 ({keyword}): {e}")
                if "403" in str(e):
                    logger.warning("403 오류로 인한 대체 방법 시도")
                    alternative_news = self._search_alternative_news(keyword)
                    if alternative_news:
                        return alternative_news
                break
            except Exception as e:
                logger.error(f"뉴스 검색 실패 ({keyword}): {e}")
                break
        
        return []
    
    def _search_alternative_news(self, keyword: str) -> List[Dict]:
        """대체 뉴스 검색 방법 (403 오류 시 사용)"""
        try:
            # 더 간단한 키워드로 재시도
            simple_keywords = self._get_simple_keywords(keyword)
            
            for simple_keyword in simple_keywords:
                try:
                    # 1. 네이버 뉴스 직접 URL 시도
                    encoded_keyword = urllib.parse.quote(simple_keyword)
                    url = f"https://news.naver.com/main/search/search.naver?query={encoded_keyword}"
                    
                    resp = self.session.get(url, timeout=self.timeout)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        news_items = []
                        
                        # 뉴스 링크 찾기
                        news_links = soup.select(".news_area a, .news_tit")
                        
                        for link in news_links[:3]:
                            headline = link.get_text(strip=True)
                            href = link.get('href', '')
                            
                            if (headline and len(headline) > 10):
                                sanitized_url = self._sanitize_url(href)
                                if sanitized_url:
                                    news_items.append({
                                        'headline': headline,
                                        'url': sanitized_url
                                    })
                        
                        if news_items:
                            logger.info(f"네이버 뉴스로 {len(news_items)}개 뉴스 수집")
                            return news_items
                
                except Exception as e:
                    logger.debug(f"네이버 뉴스 '{simple_keyword}' 검색 실패: {e}")
                    continue
            
            # 2. 한국경제 뉴스 시도
            for simple_keyword in simple_keywords:
                try:
                    encoded_keyword = urllib.parse.quote(simple_keyword)
                    url = f"https://search.hankyung.com/apps.frm/search.news?query={encoded_keyword}"
                    
                    resp = self.session.get(url, timeout=self.timeout)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        news_items = []
                        
                        # 한국경제 뉴스 링크 찾기
                        news_links = soup.select(".news_tit a, .tit a")
                        
                        for link in news_links[:3]:
                            headline = link.get_text(strip=True)
                            href = link.get('href', '')
                            
                            if (headline and len(headline) > 10):
                                # 한국경제 URL 정규화
                                if href.startswith('/'):
                                    href = f"https://www.hankyung.com{href}"
                                elif not href.startswith('http'):
                                    href = f"https://www.hankyung.com/{href}"
                                
                                news_items.append({
                                    'headline': headline,
                                    'url': href
                                })
                        
                        if news_items:
                            logger.info(f"한국경제로 {len(news_items)}개 뉴스 수집")
                            return news_items
                
                except Exception as e:
                    logger.debug(f"한국경제 '{simple_keyword}' 검색 실패: {e}")
                    continue
            
            # 3. 매일경제 뉴스 시도
            for simple_keyword in simple_keywords:
                try:
                    encoded_keyword = urllib.parse.quote(simple_keyword)
                    url = f"https://www.mk.co.kr/search/?word={encoded_keyword}"
                    
                    resp = self.session.get(url, timeout=self.timeout)
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        news_items = []
                        
                        # 매일경제 뉴스 링크 찾기
                        news_links = soup.select(".news_ttl a, .tit a")
                        
                        for link in news_links[:3]:
                            headline = link.get_text(strip=True)
                            href = link.get('href', '')
                            
                            if (headline and len(headline) > 10):
                                # 매일경제 URL 정규화
                                if href.startswith('/'):
                                    href = f"https://www.mk.co.kr{href}"
                                elif not href.startswith('http'):
                                    href = f"https://www.mk.co.kr/{href}"
                                
                                news_items.append({
                                    'headline': headline,
                                    'url': href
                                })
                        
                        if news_items:
                            logger.info(f"매일경제로 {len(news_items)}개 뉴스 수집")
                            return news_items
                
                except Exception as e:
                    logger.debug(f"매일경제 '{simple_keyword}' 검색 실패: {e}")
                    continue
            
            # 4. 모든 뉴스 소스 실패
            logger.warning("모든 뉴스 소스 실패")
            return []
            
        except Exception as e:
            logger.error(f"대체 뉴스 검색 실패: {e}")
            return []
    

    
    def _get_simple_keywords(self, keyword: str) -> List[str]:
        """키워드를 더 간단한 형태로 변환"""
        # 복잡한 키워드를 단순화
        if 'KBSTAR' in keyword:
            if '반도체' in keyword:
                return ['반도체', '반도체 ETF', '반도체주']
            elif '200' in keyword:
                return ['KOSPI', '대형주', '주식시장']
            else:
                return ['ETF', '주식', '투자']
        
        # 일반적인 키워드 단순화
        simple_mapping = {
            '반도체 ETF': ['반도체', '반도체주'],
            '2차전지 ETF': ['2차전지', '배터리'],
            'KOSPI ETF': ['KOSPI', '주식시장'],
            'KOSDAQ ETF': ['KOSDAQ', '기술주']
        }
        
        for complex_key, simple_keys in simple_mapping.items():
            if complex_key in keyword:
                return simple_keys
        
        return [keyword.split()[0] if keyword.split() else keyword]
    
    def analyze_news_sentiment(self, news_items: List[Dict], api_key: str = None) -> List[Dict]:
        """뉴스 감정분석 (GPT 활용)"""
        if not news_items:
            return []
        
        if not api_key:
            import os
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            logger.warning("OpenAI API 키가 없습니다.")
            return []
        
        try:
            client = openai.OpenAI(api_key=api_key)
            results = []
            
            logger.info(f"총 {len(news_items)}개 뉴스에 대해 감정분석 시작")
            
            for i, news_item in enumerate(news_items, 1):  # 모든 뉴스 분석
                logger.info(f"뉴스 {i}/{len(news_items)} 분석 중: {news_item.get('headline', '')[:50]}...")
                headline = news_item.get('headline', '')
                url = news_item.get('url', '')
                
                if not headline:
                    continue
                
                try:
                    response = client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT_ANALYSIS},
                            {"role": "user", "content": headline}
                        ],
                        max_tokens=100,
                        temperature=0.1
                    )
                    
                    result_text = response.choices[0].message.content.strip()
                    
                    # 결과 파싱
                    if "|" in result_text:
                        parts = result_text.split("|")
                        if len(parts) >= 3:
                            results.append({
                                'headline': parts[0].strip(),
                                'sentiment': parts[1].strip(),
                                'reason': parts[2].strip(),
                                'url': url,
                                'score': 0.8,
                                'confidence': 0.9
                            })
                
                except openai.RateLimitError:
                    logger.warning("OpenAI API rate limit 도달")
                    break
                except openai.APIError as e:
                    logger.error(f"OpenAI API 오류: {e}")
                    continue
                except Exception as e:
                    logger.error(f"개별 뉴스 감정분석 실패: {e}")
                    continue
            
            return results
            
        except Exception as e:
            logger.error(f"뉴스 감정분석 실패: {e}")
            return []
    
    def generate_level_summary(self, news_items: List[Dict], level: int, api_key: str = None, mpti_type: str = 'Fact') -> str:
        """레벨별 뉴스 요약 생성 (MPTI 스타일 적용)"""
        if not news_items:
            return "분석할 뉴스 데이터가 없습니다."
        
        if not api_key:
            import os
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            return "OpenAI API 키가 필요합니다."
        
        try:
            # 뉴스 헤드라인 추출
            headlines = [item.get('headline', '') for item in news_items if item.get('headline')]
            if not headlines:
                return "분석할 뉴스 헤드라인이 없습니다."
            
            news_summary = " ".join(headlines)
            
            client = openai.OpenAI(api_key=api_key)
            level_prompt = LEVEL_PROMPTS.get(level, LEVEL_PROMPTS[3])
            
            # MPTI 스타일 프롬프트 추가
            try:
                from chatbot.config import Config
                mpti_styles = Config.MPTI_STYLES
                mpti_prompt = mpti_styles.get(mpti_type, {}).get('prompt', '')
            except ImportError:
                mpti_prompt = ""
            
            # 레벨과 MPTI 스타일을 결합한 프롬프트
            combined_prompt = f"{level_prompt}"
            if mpti_prompt:
                combined_prompt += f" {mpti_prompt}"
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"뉴스 분석 전문가입니다. {combined_prompt}"},
                    {"role": "user", "content": f"다음 뉴스들을 분석해서 요약해주세요: {news_summary}"}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except openai.RateLimitError:
            logger.warning("OpenAI API rate limit 도달")
            return "API 사용량 한계로 요약을 생성할 수 없습니다."
        except openai.APIError as e:
            logger.error(f"OpenAI API 오류: {e}")
            return "API 오류로 요약을 생성할 수 없습니다."
        except Exception as e:
            logger.error(f"레벨별 요약 생성 실패: {e}")
            return "요약을 생성할 수 없습니다."
    
    def display_news_analysis(self, code: str, level: int, mpti_type: str):
        """뉴스 분석 결과 표시"""
        st.markdown(f'<div class="section-header">📰 뉴스 감정분석 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        try:
            # 입력 검증
            if not code or not isinstance(code, str):
                st.error("유효하지 않은 코드입니다.")
                return
            
            # 뉴스 데이터 가져오기
            with st.spinner("뉴스 데이터를 수집하고 있습니다..."):
                news_items = self.fetch_naver_news(code)
            
            if news_items:
                # 감정분석 수행
                with st.spinner("뉴스 감정을 분석하고 있습니다..."):
                    sentiment_results = self.analyze_news_sentiment(news_items)
                
                # 뉴스는 있지만 감정분석이 실패한 경우에도 기본 정보 표시
                if sentiment_results:
                    # 감정 분포 계산
                    sentiment_counts = {}
                    for result in sentiment_results:
                        sentiment = result.get('sentiment', '')
                        if sentiment:
                            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
                    
                    # 감정 분포 섹션
                    st.markdown("### 📊 감정 분포")
                    
                    # 감정별 카드
                    if sentiment_counts:
                        cols = st.columns(len(sentiment_counts))
                    sentiment_config = {
                        '긍정': {'color': '#28a745', 'icon': '😊', 'bg_color': '#d4edda'},
                        '부정': {'color': '#dc3545', 'icon': '😞', 'bg_color': '#f8d7da'},
                        '중립': {'color': '#6c757d', 'icon': '😐', 'bg_color': '#e2e3e5'}
                    }
                    
                    for i, (sentiment, count) in enumerate(sentiment_counts.items()):
                        with cols[i]:
                            config = sentiment_config.get(sentiment, {'color': '#6c757d', 'icon': '⚪', 'bg_color': '#f8f9fa'})
                            st.markdown(f"""
                            <div style="
                                background: {config['bg_color']};
                                border: 2px solid {config['color']};
                                border-radius: 10px;
                                padding: 1rem;
                                text-align: center;
                                margin: 0.5rem 0;">
                                <h3 style="color: {config['color']}; margin: 0;">{config['icon']} {sentiment}</h3>
                                <h2 style="color: {config['color']}; margin: 0.5rem 0;">{count}</h2>
                                <p style="margin: 0; color: #666;">개 뉴스</p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # 파이 차트
                    if len(sentiment_counts) > 1:
                        try:
                            import plotly.graph_objects as go
                            
                            colors = [sentiment_config.get(s, {}).get('color', '#6c757d') for s in sentiment_counts.keys()]
                            
                            fig = go.Figure(data=[go.Pie(
                                labels=list(sentiment_counts.keys()),
                                values=list(sentiment_counts.values()),
                                hole=0.4,
                                marker_colors=colors,
                                textinfo='label+percent',
                                textfont_size=14
                            )])
                            
                            fig.update_layout(
                                title="뉴스 감정 분포",
                                showlegend=True,
                                height=400,
                                margin=dict(t=50, b=50, l=50, r=50)
                            )
                            
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            logger.error(f"차트 생성 실패: {e}")
                            st.warning("차트를 생성할 수 없습니다.")
                    
                    # 상세 분석 결과
                    st.markdown("### 📝 상세 분석 결과")
                    
                    for i, result in enumerate(sentiment_results, 1):
                        sentiment = result.get('sentiment', '')
                        config = sentiment_config.get(sentiment, {'color': '#6c757d', 'icon': '⚪', 'bg_color': '#f8f9fa'})
                        url = result.get('url', '')
                        
                        # 뉴스 카드
                        st.markdown(f"""
                        <div style="
                            background: {config['bg_color']};
                            border-left: 5px solid {config['color']};
                            border-radius: 8px;
                            padding: 1.5rem;
                            margin: 1rem 0;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <div style="display: flex; align-items: center; margin-bottom: 0.5rem;">
                                <span style="font-size: 1.5rem; margin-right: 0.5rem;">{config['icon']}</span>
                                <h4 style="margin: 0; color: {config['color']};">{sentiment}</h4>
                            </div>
                            <h5 style="margin: 0.5rem 0; color: #333;">{result.get('headline', '')}</h5>
                            <p style="margin: 0.5rem 0; color: #666; font-size: 0.9rem;">💡 {result.get('reason', '')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 링크 버튼
                        if url and self._is_valid_url(url):
                            if st.button(f"🔗 뉴스 보기 ({i})", key=f"news_link_{i}"):
                                st.markdown(f"[뉴스 원문 보기]({url})")
                    
                    # 레벨별 요약
                    summary = self.generate_level_summary(news_items, level)
                    if summary:
                        st.markdown("### 📋 종합 요약")
                        st.markdown(f"""
                        <div style="
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            padding: 1.5rem;
                            border-radius: 10px;
                            margin: 1rem 0;">
                            <h4 style="margin: 0 0 1rem 0;">🎯 AI 분석 요약</h4>
                            <p style="margin: 0; line-height: 1.6;">{summary}</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                else:
                    # 뉴스는 있지만 감정분석이 실패한 경우, 기본 뉴스 정보 표시
                    st.warning("뉴스 감정분석을 수행할 수 없습니다.")
                    
                    # 기본 뉴스 목록 표시
                    st.markdown("### 📰 수집된 뉴스")
                    for i, news in enumerate(news_items, 1):
                        st.markdown(f"""
                        <div style="
                            background: white;
                            border-left: 5px solid #FFD700;
                            border-radius: 8px;
                            padding: 1.5rem;
                            margin: 1rem 0;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                            <h5 style="margin: 0.5rem 0; color: #333;">{i}. {news.get('headline', '')}</h5>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 링크 버튼
                        url = news.get('url', '')
                        if url and self._is_valid_url(url):
                            if st.button(f"🔗 뉴스 보기 ({i})", key=f"basic_news_link_{i}"):
                                st.markdown(f"[뉴스 원문 보기]({url})")
            else:
                st.info("최근 뉴스 데이터를 찾을 수 없습니다.")
        
        except Exception as e:
            st.error(f"뉴스 분석 중 오류: {e}")
            logger.error(f"뉴스 분석 오류: {e}")

