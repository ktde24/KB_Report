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

logger = logging.getLogger(__name__)

# 레벨별 스타일 프롬프트
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
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.timeout = 10  # 10초 타임아웃
        self.max_retries = 3  # 최대 재시도 횟수
    
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
    
    def fetch_naver_news(self, code: str) -> List[Dict]:
        """네이버 뉴스 헤드라인과 링크 가져오기"""
        try:
            # 입력 검증
            if not code or not isinstance(code, str):
                logger.warning("유효하지 않은 코드 입력")
                return []
            
            # 키워드 기반 검색
            if not code.isdigit() and ('ETF' in code.upper() or '반도체' in code or '2차전지' in code or 'KOSPI' in code.upper()):
                # 키워드별 관련 검색어 추가
                related_keywords = self._get_related_keywords(code)
                return self._search_naver_news_with_keywords(code, related_keywords)
            
            # 종목 코드 기반 검색
            stock_name = self._get_stock_name(code)
            if stock_name:
                return self._search_naver_news_simple(stock_name)
            
            # 기본 키워드로 검색
            return self._search_naver_news_simple('주식 투자')
            
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
        
        related_keywords = set([keyword])  # 원본 키워드 (set으로 중복 방지)
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
        
        # 기본 키워드 추가 (투자 관련)
        if primary_keyword != 'default':
            related_keywords.add('투자')
        
        # 키워드 품질 필터링
        filtered_keywords = []
        for kw in related_keywords:
            if len(kw) >= 2 and not kw.isdigit():  # 최소 2글자, 숫자만 있는 키워드 제외
                filtered_keywords.append(kw)
        
        # 최대 5개까지 반환 (원본 키워드 우선)
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
        
        # 2. 관련 키워드 추가 (중복 제거)
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
        """단순한 네이버 뉴스 검색 (재시도 로직 포함)"""
        if not keyword:
            return []
        
        for attempt in range(self.max_retries):
            try:
                encoded_keyword = urllib.parse.quote(keyword)
                url = f"https://search.naver.com/search.naver?where=news&query={encoded_keyword}"
                
                logger.info(f"뉴스 검색 시도 {attempt + 1}/{self.max_retries}: {keyword}")
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                
                soup = BeautifulSoup(resp.text, "html.parser")
                news_items = []
                
                # 뉴스 링크 찾기
                news_links = soup.select("a.news_tit")
                
                for link in news_links[:3]:  # 최대 3개만
                    headline = link.get_text(strip=True)
                    href = link.get('href', '')
                    
                    # 유효한 헤드라인 필터링
                    if (headline and 
                        len(headline) > 10 and 
                        '언론사' not in headline and 
                        '구독' not in headline and
                        '선정' not in headline):
                        
                        # URL 정규화 및 보안 검사
                        sanitized_url = self._sanitize_url(href)
                        if sanitized_url:
                            news_items.append({
                                'headline': headline,
                                'url': sanitized_url
                            })
                
                logger.info(f"수집된 뉴스: {len(news_items)}개")
                return news_items
                
            except requests.exceptions.Timeout:
                logger.warning(f"뉴스 검색 타임아웃 ({keyword}), 재시도 {attempt + 1}/{self.max_retries}")
                if attempt == self.max_retries - 1:
                    break
            except requests.exceptions.RequestException as e:
                logger.error(f"뉴스 검색 네트워크 오류 ({keyword}): {e}")
                break
            except Exception as e:
                logger.error(f"뉴스 검색 실패 ({keyword}): {e}")
                break
        
        return []
    
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
            
            for news_item in news_items[:3]:  # 최대 3개만 분석
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
    
    def generate_level_summary(self, news_items: List[Dict], level: int, api_key: str = None) -> str:
        """레벨별 뉴스 요약 생성"""
        if not news_items:
            return "분석할 뉴스 데이터가 없습니다."
        
        if not api_key:
            import os
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            return "OpenAI API 키가 필요합니다."
        
        try:
            # 뉴스 헤드라인 추출
            headlines = [item.get('headline', '') for item in news_items[:3] if item.get('headline')]
            if not headlines:
                return "분석할 뉴스 헤드라인이 없습니다."
            
            news_summary = " ".join(headlines)
            
            client = openai.OpenAI(api_key=api_key)
            level_prompt = LEVEL_PROMPTS.get(level, LEVEL_PROMPTS[3])
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"뉴스 분석 전문가입니다. {level_prompt}"},
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
                    
                    for i, result in enumerate(sentiment_results[:3], 1):
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
                    st.warning("뉴스 감정분석을 수행할 수 없습니다.")
            else:
                st.info("최근 뉴스 데이터를 찾을 수 없습니다.")
        
        except Exception as e:
            st.error(f"뉴스 분석 중 오류: {e}")
            logger.error(f"뉴스 분석 오류: {e}")

