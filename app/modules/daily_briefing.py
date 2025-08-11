"""
데일리 브리핑 모듈
- 종목별 상세 분석
- 뉴스 크롤링 및 감정분석
- chatbot.etf_analysis 통합
- ETF 구성종목 분석
"""

import streamlit as st
import pandas as pd
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

# 임포트
try:
    from chatbot.etf_analysis import analyze_etf
    from chatbot.config import Config
    CHATBOT_MODULES_AVAILABLE = True
except ImportError:
    CHATBOT_MODULES_AVAILABLE = False

try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False

# ETF 구성종목 분석 모듈 임포트
try:
    from .etf_constituent_analyzer import ETFConstituentAnalyzer
    ETF_ANALYZER_AVAILABLE = True
except ImportError:
    ETF_ANALYZER_AVAILABLE = False

logger = logging.getLogger(__name__)

class DailyBriefing:
    """데일리 브리핑 클래스"""
    
    def __init__(self):
        self.config = Config() if CHATBOT_MODULES_AVAILABLE else None
    
    def display_daily_briefing(self, level: int, interest_list: List[str], mpti_type: str, data: Dict[str, pd.DataFrame]):
        """데일리 브리핑 표시"""
        st.markdown(f'<div class="section-header">📰 데일리 브리핑 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        if not interest_list:
            st.info("💡 관심 종목을 입력해주세요!")
            return
        
        # 첫 번째 종목에 대해 상세 분석
        main_stock = interest_list[0]
        
        # ETF 구성종목 분석 시도
        logger.info(f"분석 대상: {main_stock}")
        logger.info(f"ETF_ANALYZER_AVAILABLE: {ETF_ANALYZER_AVAILABLE}")
        logger.info(f"is_etf_code: {self._is_etf_code(main_stock)}")
        
        if ETF_ANALYZER_AVAILABLE and self._is_etf_code(main_stock):
            try:
                etf_analyzer = ETFConstituentAnalyzer()
                etf_code = self._get_etf_code_from_name(main_stock)
                
                if etf_code:
                    logger.info(f"ETF 코드 매핑 성공: {main_stock} → {etf_code}")
                    # ETF 종합 분석 리포트 생성 (MPTI 스타일 적용)
                    analysis_result = etf_analyzer.generate_etf_summary_report(
                        etf_code=etf_code,
                        etf_name=main_stock,
                        level=level,
                        mpti_type=mpti_type
                    )
                    
                    if "error" not in analysis_result:
                        # ETF 구성종목 분석 결과 표시
                        etf_analyzer.display_etf_analysis(analysis_result)
                        return
                    else:
                        st.warning(f"ETF 분석 실패: {analysis_result['error']}")
                else:
                    st.warning(f"ETF 코드 매핑 실패: {main_stock}")
                    st.info("기본 분석으로 진행합니다.")
                
            except Exception as e:
                st.error(f"ETF 구성종목 분석 중 오류: {e}")
                logger.error(f"ETF 분석 오류: {e}")
        
        # 기존 분석 로직 (fallback)
        try:
            # chatbot.etf_analysis의 analyze_etf 함수 활용
            if CHATBOT_MODULES_AVAILABLE and data:
                user_profile = {
                    'level': level,
                    'wmti_type': 'APWL',  # 기본값
                    'mpti_type': mpti_type
                }
                
                # analyze_etf 함수 호출
                analysis_result = analyze_etf(
                    etf_name=main_stock,
                    user_profile=user_profile,
                    price_df=data.get('etf_prices', pd.DataFrame()),
                    info_df=data.get('etf_info', pd.DataFrame()),
                    perf_df=data.get('etf_performance', pd.DataFrame()),
                    aum_df=data.get('etf_aum', pd.DataFrame()),
                    ref_idx_df=data.get('etf_reference', pd.DataFrame()),
                    risk_df=data.get('etf_risk', pd.DataFrame())
                )
                
                if analysis_result and 'error' not in analysis_result:
                    self._display_analysis_result(analysis_result, main_stock)
                else:
                    # 분석 실패시 기본 브리핑으로 fallback
                    self._display_stock_briefing(main_stock, level, mpti_type)
            
            else:
                # chatbot 모듈이 없으면 기본 브리핑
                self._display_stock_briefing(main_stock, level, mpti_type)
        
        except Exception as e:
            st.error(f"데일리 브리핑 생성 중 오류: {e}")
            # 오류시 기본 브리핑으로 fallback
            self._display_stock_briefing(main_stock, level, mpti_type)
    
    def _display_analysis_result(self, analysis_result: Dict, stock_name: str):
        """분석 결과 표시"""
        st.subheader(f"📊 {stock_name} 종합 분석")
        
        # 주요 지표 표시
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if 'market_data' in analysis_result:
                market_data = analysis_result['market_data']
                st.metric(
                    "현재가",
                    f"{market_data.get('current_price', 0):,.0f}원",
                    f"{market_data.get('change_percent', 0):+.2f}%"
                )
        
        with col2:
            if 'official_data' in analysis_result:
                official_data = analysis_result['official_data']
                if 'performance' in official_data:
                    perf_data = official_data['performance']
                    st.metric(
                        "1년 수익률",
                        f"{perf_data.get('return_1y', 0):+.2f}%"
                    )
        
        with col3:
            if 'official_data' in analysis_result:
                official_data = analysis_result['official_data']
                if 'info' in official_data:
                    info_data = official_data['info']
                    st.metric(
                        "총보수",
                        f"{info_data.get('총보수', 0):.2f}%"
                    )
        
        # 분석 요약 표시
        if 'summary' in analysis_result:
            st.markdown("**📝 분석 요약**")
            st.write(analysis_result['summary'])
        
        # 시각화 표시
        if 'charts' in analysis_result:
            st.subheader("📈 시각화")
            for chart_name, chart_fig in analysis_result['charts'].items():
                st.plotly_chart(chart_fig, use_container_width=True)
    
    def _display_stock_briefing(self, stock: str, level: int, mpti_type: str):
        """기본 종목 브리핑 표시"""
        st.subheader(f"📊 {stock} 브리핑")
        
        try:
            # 종목 코드 가져오기
            stock_code = self._get_stock_code_for_data(stock)
            
            # 최근 5거래일 데이터 가져오기
            df_days = self._get_last_n_trading_days(stock_code, 5)
            
            if not df_days.empty:
                # 어제와 오늘 데이터
                yesterday_data = df_days.iloc[-2] if len(df_days) > 1 else df_days.iloc[-1]
                current_data = df_days.iloc[-1]
                
                # 변동 계산
                change_amount = current_data['종가'] - yesterday_data['종가']
                change_percent = (change_amount / yesterday_data['종가']) * 100
                
                # 주요 지표 표시
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric(
                        "현재가",
                        f"{current_data['종가']:,.0f}원",
                        f"{change_amount:+,.0f}원 ({change_percent:+.2f}%)",
                        delta_color="normal" if change_percent >= 0 else "inverse"
                    )
                
                with col2:
                    st.metric(
                        "거래량",
                        f"{current_data['거래량']:,.0f}주",
                        help="어제 총 거래된 주식 수"
                    )
                
                with col3:
                    st.metric(
                        "거래대금",
                        f"{current_data['거래대금']:,.0f}원",
                        help="어제 총 거래대금"
                    )
                
                # 종목 요약 생성
                summary = self._generate_stock_summary(stock, change_percent, change_amount, level, mpti_type)
                st.markdown("**📝 종목 요약**")
                st.write(summary)
                
                # 뉴스 데이터 가져오기
                news_items = self._fetch_naver_news(stock_code)
                if news_items:
                    st.markdown("**📰 관련 뉴스**")
                    self._display_constituent_news(news_items, level, mpti_type)
                else:
                    st.info(f"{stock}의 최근 뉴스 데이터를 가져올 수 없습니다.")
            else:
                st.warning(f"{stock}의 시세 데이터를 가져올 수 없습니다.")
        
        except Exception as e:
            st.error(f"{stock} 브리핑 생성 중 오류: {e}")
            logger.error(f"브리핑 생성 오류: {e}")
    
    def _get_stock_code(self, stock_name: str) -> str:
        """종목명으로 종목코드 가져오기"""
        stock_codes = {
            # 뉴스가 많은 ETF (우선순위)
            'KBSTAR 200': '091160',
            'KBSTAR 코스닥150': '091170',
            'KBSTAR 반도체': '091230',
            'KBSTAR 2차전지테마': '306540',
            'KBSTAR K-뉴딜디지털플러스': '233740',
            # 대형주 (보조)
            '삼성전자': '005930',
            'SK하이닉스': '000660',
            'NAVER': '035420',
            '카카오': '035720',
            'LG에너지솔루션': '373220',
            '현대차': '005380',
            'POSCO홀딩스': '005490',
            '기아': '000270',
            '삼성바이오로직스': '207940',
            'LG화학': '051910',
            '현대모비스': '012330',
            '삼성SDI': '006400',
            'KB금융': '105560',
            '신한지주': '055550',
            '하나금융지주': '086790'
        }
        return stock_codes.get(stock_name, '091160')  # 기본값: KBSTAR 200
    
    def _get_stock_code_for_data(self, stock_name: str) -> str:
        """데이터 조회용 종목코드 가져오기 (실제 종목 코드만 반환)"""
        stock_codes = {
            # ETF 종목 코드
            'KBSTAR 200': '091160',
            'KBSTAR 코스닥150': '091170',
            'KBSTAR 반도체': '091230',
            'KBSTAR 2차전지테마': '306540',
            'KBSTAR K-뉴딜디지털플러스': '233740',
            # 대형주 종목 코드
            '삼성전자': '005930',
            'SK하이닉스': '000660',
            'NAVER': '035420',
            '카카오': '035720',
            'LG에너지솔루션': '373220',
            '현대차': '005380',
            'POSCO홀딩스': '005490',
            '기아': '000270',
            '삼성바이오로직스': '207940',
            'LG화학': '051910',
            '현대모비스': '012330',
            '삼성SDI': '006400',
            'KB금융': '105560',
            '신한지주': '055550',
            '하나금융지주': '086790'
        }
        
        # 숫자로만 구성된 경우 (이미 종목 코드)
        if stock_name.isdigit():
            return stock_name
        
        # 매핑된 종목 코드 반환
        return stock_codes.get(stock_name, '091160')  # 기본값: KBSTAR 200
    
    def _get_last_n_trading_days(self, code: str, n: int = 5) -> pd.DataFrame:
        """최근 n거래일 데이터 가져오기"""
        try:
            if not PYKRX_AVAILABLE:
                return pd.DataFrame()
            
            # 키워드가 아닌 실제 종목 코드인지 확인
            if not code.isdigit():
                logger.warning(f"유효하지 않은 종목 코드: {code}")
                return pd.DataFrame()
            
            days = []
            date = datetime.now()
            max_attempts = n * 10  # 최대 시도 횟수 제한
            attempts = 0
            
            while len(days) < n and attempts < max_attempts:
                date -= timedelta(days=1)
                attempts += 1
                
                try:
                    df = stock.get_etf_ohlcv_by_date(date.strftime('%Y%m%d'),
                                                      date.strftime('%Y%m%d'),
                                                      code)
                    if not df.empty:
                        df.index = pd.to_datetime(df.index, format='%Y%m%d')
                        days.append(df.iloc[0])
                except Exception as e:
                    logger.debug(f"날짜 {date.strftime('%Y%m%d')} 데이터 조회 실패: {e}")
                    continue
            
            if not days:
                logger.warning(f"종목 코드 {code}의 거래 데이터를 찾을 수 없습니다.")
                return pd.DataFrame()
            
            # 최신 날짜 순으로 정렬
            return pd.DataFrame(days).sort_index()
            
        except Exception as e:
            logger.error(f"거래일 데이터 수집 실패 ({code}): {e}")
            return pd.DataFrame()
    
    def _fetch_naver_news(self, code: str) -> List[Dict]:
        """네이버 뉴스 헤드라인과 링크 가져오기 (NewsAnalyzer 활용)"""
        try:
            # NewsAnalyzer 인스턴스 생성하여 뉴스 가져오기
            from .news_analyzer import NewsAnalyzer
            news_analyzer = NewsAnalyzer()
            
            # 키워드 기반 뉴스 검색이 가능한 경우
            if not code.isdigit() and ('ETF' in code.upper() or '반도체' in code or '2차전지' in code or 'KOSPI' in code.upper() or 'KOSDAQ' in code.upper()):
                # 키워드 그대로 사용
                return news_analyzer.fetch_naver_news(code)
            else:
                # 종목 코드인 경우 종목명으로 변환하여 검색
                stock_name = self._get_stock_name_by_code(code)
                if stock_name:
                    return news_analyzer.fetch_naver_news(stock_name)
                else:
                    return news_analyzer.fetch_naver_news(code)
                    
        except Exception as e:
            logger.error(f"뉴스 크롤링 실패 ({code}): {e}")
            return []
    
    def _get_stock_name_by_code(self, code: str) -> str:
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
            '373220': 'LG에너지솔루션',
            '005380': '현대차',
            '005490': 'POSCO홀딩스',
            '000270': '기아',
            '207940': '삼성바이오로직스',
            '051910': 'LG화학',
            '012330': '현대모비스',
            '006400': '삼성SDI',
            '105560': 'KB금융',
            '055550': '신한지주',
            '086790': '하나금융지주'
        }
        return stock_names.get(code, '')
    
    def _is_etf_code(self, stock_name: str) -> bool:
        """ETF 종목인지 확인"""
        etf_keywords = ['ETF', 'KBSTAR', 'TIGER', 'KODEX', 'ARIRANG', 'HANARO', 'SMART', 'RISE', 'ACE']
        return any(keyword in stock_name.upper() for keyword in etf_keywords)
    
    def _get_etf_code_from_name(self, stock_name: str) -> Optional[str]:
        """ETF 이름에서 코드 추출"""
        etf_code_map = {
            # KBSTAR ETF
            'KBSTAR 200': '091160',
            'KBSTAR 코스닥150': '091170',
            'KBSTAR 반도체': '091230',
            'KBSTAR 2차전지테마': '306540',
            'KBSTAR K-뉴딜디지털플러스': '233740',
            
            # TIGER ETF
            'TIGER 반도체': '102110',
            'TIGER 2차전지테마': '305720',
            
            # KODEX ETF
            'KODEX 반도체': '091160',
            'KODEX 2차전지': '305720',
            
            # ACE 반도체 ETF 
            'ACE AI반도체포커스': '469150',
            'ACE 글로벌AI맞춤형반도체': '494340',
            'ACE 글로벌반도체TOP4 Plus SOLACTIVE': '446770',
            'ACE 엔비디아밸류체인액티브': '483320',
            'ACE 일본반도체': '469160',
            'ACE 미국반도체데일리타겟커버드콜(합성)': '480040',
            
            # RISE ETF
            'RISE 미국반도체NYSE': '469060',  
            'RISE 미국반도체': '469060',      
            'RISE 미국반도체NYSE(H)': '469050',  
            
    
        }
        
        # 정확한 매칭
        if stock_name in etf_code_map:
            return etf_code_map[stock_name]
        
        # 부분 매칭 (반도체 관련 키워드)
        if '반도체' in stock_name:
            # 가장 대표적인 반도체 ETF로 매핑
            return '469150'  # ACE AI반도체포커스
        
        # RISE 관련 키워드 매칭
        if 'RISE' in stock_name.upper():
            if '반도체' in stock_name and '미국' in stock_name:
                return '469060'  # RISE 미국반도체NYSE (실제 미국 반도체 종목들)
            elif '반도체' in stock_name:
                return '469150'  # ACE AI반도체포커스 (한국 반도체 종목들) 
        
        # 부분 매칭
        for name, code in etf_code_map.items():
            if stock_name.upper() in name.upper() or name.upper() in stock_name.upper():
                return code
        
        # 숫자 코드인 경우
        if stock_name.isdigit() and len(stock_name) == 6:
            return stock_name
        
        return None
    
    def _display_constituent_news(self, news_items: List[Dict], level: int, mpti_type: str):
        """구성 종목 뉴스 표시 (개선된 UI)"""
        if not news_items:
            st.info("관련 뉴스가 없습니다.")
            return
        
        # 최대 3개 뉴스 표시
        max_news = 3
        
        for i, news_item in enumerate(news_items[:max_news], 1):
            headline = news_item.get('headline', '')
            url = news_item.get('url', '')
            
            # 뉴스 카드
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 1rem;
                margin: 0.5rem 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h5 style="margin: 0 0 0.5rem 0; color: #495057;">📰 {headline}</h5>
            </div>
            """, unsafe_allow_html=True)
            
            # 링크 버튼 (URL이 있는 경우)
            if url:
                if st.button(f"🔗 뉴스 보기 ({i})", key=f"briefing_news_link_{i}"):
                    st.markdown(f"[뉴스 원문 보기]({url})")
        
        if len(news_items) > max_news:
            st.info(f"그 외 {len(news_items) - max_news}개의 뉴스가 더 있습니다.")
    
    def _generate_stock_summary(self, stock_name: str, change_percent: float, change_amount: float, level: int, mpti_type: str) -> str:
        """종목 요약 생성 (사용자 프로필 고려)"""
        # config.py의 MPTI_STYLES 사용
        try:
            from chatbot.config import Config
            mpti_styles = Config.MPTI_STYLES
            style_info = mpti_styles.get(mpti_type, {})
            style = style_info.get('name', '일반적') if isinstance(style_info, dict) else '일반적'
        except ImportError:
            style = '일반적'
        
        if level == 1:
            direction = "올랐어요" if change_percent >= 0 else "내렸어요"
            return f"{stock_name}은(는) 어제보다 {abs(change_percent):.1f}% {direction}! {abs(change_amount):,.0f}원 변동했답니다. {style}적으로 보면 투자에 관심을 가져보세요!"
        elif level == 2:
            direction = "상승" if change_percent >= 0 else "하락"
            return f"{stock_name}이(가) {abs(change_percent):.1f}% {direction}했습니다. 변동폭은 {abs(change_amount):,.0f}원입니다. {style}적으로 기본 투자 지식을 쌓아보세요."
        elif level == 3:
            direction = "상승" if change_percent >= 0 else "하락"
            return f"{stock_name}은(는) 전일 대비 {abs(change_percent):.1f}% {direction}하여 {abs(change_amount):,.0f}원 변동했습니다. {style}적으로 실전 투자 전략을 고려해보세요."
        elif level == 4:
            direction = "상승" if change_percent >= 0 else "하락"
            return f"{stock_name}의 전일 대비 변동률은 {change_percent:+.1f}%({direction})이며, 변동금액은 {change_amount:+,.0f}원입니다. {style}적으로 고급 투자 기법을 활용해보세요."
        else:
            direction = "상승" if change_percent >= 0 else "하락"
            return f"{stock_name}의 전일 대비 변동률은 {change_percent:+.1f}%({direction})이며, 변동금액은 {change_amount:+,.0f}원입니다. {style}적으로 전문가 수준의 분석을 참고하세요."
