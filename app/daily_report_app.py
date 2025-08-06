"""
맞춤형 데일리 금융 리포트 애플리케이션
- 사용자 레벨 및 WMTI 투자 성향별 맞춤 리포트
- 시장개요, 데일리 브리핑, 추천 종목 제공
- 감정분석, 뉴스 크롤링, ETF 분석 기능 통합
- ETF 포트폴리오 분석 및 시세 비교 기능 추가
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 기존 모듈들 임포트
from chatbot.config import Config
from chatbot.recommendation_engine import ETFRecommendationEngine
from chatbot.etf_analysis import analyze_etf
from chatbot.utils import safe_read_csv_with_fallback
from chatbot.gpt_client import GPTClient

# 뉴스 분석 모듈 임포트
from news_analyzer import NewsAnalyzer, StockPriceAnalyzer

# 추가 분석 모듈들
try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False
    st.warning("pykrx 라이브러리가 설치되지 않았습니다. ETF 포트폴리오 분석 기능을 사용할 수 없습니다.")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CSS 스타일 정의 (KB 색상 테마)
CUSTOM_CSS = """
<style>
    /* 전체 페이지 스타일 */
    .main {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #60a5fa 100%);
        padding: 0;
    }
    
    .stApp {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #60a5fa 100%);
    }
    
    /* KB 스타일 헤더 */
    .kb-header {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 2.5rem;
        border-radius: 0 0 25px 25px;
        text-align: center;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }
    
    .kb-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
        animation: shimmer 3s infinite;
    }
    
    @keyframes shimmer {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    
    .kb-logo {
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.8rem;
        text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.4);
        position: relative;
        z-index: 1;
    }
    
    .kb-subtitle {
        font-size: 1.3rem;
        opacity: 0.95;
        font-weight: 400;
        position: relative;
        z-index: 1;
    }
    
    /* 섹션 헤더 */
    .section-header {
        background: linear-gradient(90deg, #1e40af 0%, #3b82f6 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 15px;
        margin: 1.5rem 0;
        font-size: 1.4rem;
        font-weight: 700;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
        border-left: 6px solid #fbbf24;
        position: relative;
        overflow: hidden;
    }
    
    .section-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%);
        transform: translateX(-100%);
        transition: transform 0.8s ease;
    }
    
    .section-header:hover::before {
        transform: translateX(100%);
    }
    
    /* 카드 스타일 */
    .metric-card {
        background: rgba(255, 255, 255, 0.98);
        padding: 2rem;
        border-radius: 20px;
        margin: 1.5rem 0;
        box-shadow: 0 12px 50px rgba(0, 0, 0, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        backdrop-filter: blur(20px);
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.08), transparent);
        transition: left 0.6s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-10px) scale(1.02);
        box-shadow: 0 25px 80px rgba(0, 0, 0, 0.25);
    }
    
    .metric-card:hover::before {
        left: 100%;
    }
    
    /* 레벨 인디케이터 */
    .level-indicator {
        background: linear-gradient(45deg, #fbbf24, #f59e0b);
        color: white;
        padding: 0.5rem 1.2rem;
        border-radius: 30px;
        font-size: 0.9rem;
        font-weight: 700;
        margin-left: 1.5rem;
        box-shadow: 0 4px 15px rgba(251, 191, 36, 0.4);
        animation: pulse 2.5s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.08); opacity: 0.9; }
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(90deg, #1e40af 0%, #3b82f6 100%);
        color: white;
        border: none;
        border-radius: 35px;
        padding: 1rem 3rem;
        font-weight: 700;
        font-size: 1.1rem;
        transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 8px 25px rgba(30, 64, 175, 0.4);
        position: relative;
        overflow: hidden;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.25), transparent);
        transition: left 0.6s ease;
    }
    
    .stButton > button:hover {
        background: linear-gradient(90deg, #1e3a8a 0%, #2563eb 100%);
        transform: translateY(-4px) scale(1.05);
        box-shadow: 0 15px 40px rgba(30, 64, 175, 0.6);
    }
    
    .stButton > button:hover::before {
        left: 100%;
    }
    
    /* 사이드바 스타일 */
    .stSidebar {
        background: rgba(255, 255, 255, 0.98);
        backdrop-filter: blur(25px);
        border-right: 2px solid rgba(255, 255, 255, 0.3);
    }
    
    .stSidebar .sidebar-content {
        background: transparent;
    }
    
    /* 선택박스 스타일 */
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        border: 2px solid #e5e7eb;
        transition: all 0.4s ease;
    }
    
    .stSelectbox > div > div:hover {
        border-color: #3b82f6;
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.25);
        transform: translateY(-2px);
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 1rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 12px;
        color: #374151;
        font-weight: 600;
        transition: all 0.4s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #1e40af 0%, #3b82f6 100%);
        color: white;
        box-shadow: 0 6px 20px rgba(30, 64, 175, 0.4);
        transform: scale(1.05);
    }
    
    /* 메트릭 스타일 */
    .stMetric {
        background: rgba(255, 255, 255, 0.95);
        padding: 1.5rem;
        border-radius: 15px;
        border: 1px solid #e5e7eb;
        transition: all 0.4s ease;
    }
    
    .stMetric:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        border-color: #3b82f6;
    }
    
    /* 데이터프레임 스타일 */
    .stDataFrame {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        overflow: hidden;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
    }
    
    /* 차트 스타일 */
    .stPlotlyChart {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 1.5rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
    }
    
    /* 알림 스타일 */
    .stAlert {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
    }
    
    .stSuccess {
        background: rgba(34, 197, 94, 0.1);
        border-color: #22c55e;
        border-left: 5px solid #22c55e;
    }
    
    .stInfo {
        background: rgba(59, 130, 246, 0.1);
        border-color: #3b82f6;
        border-left: 5px solid #3b82f6;
    }
    
    .stWarning {
        background: rgba(245, 158, 11, 0.1);
        border-color: #f59e0b;
        border-left: 5px solid #f59e0b;
    }
    
    .stError {
        background: rgba(239, 68, 68, 0.1);
        border-color: #ef4444;
        border-left: 5px solid #ef4444;
    }
    
    /* KB 특별 카드 */
    .kb-card {
        background: rgba(255, 255, 255, 0.98);
        border-radius: 25px;
        padding: 2.5rem;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
        backdrop-filter: blur(25px);
        transition: all 0.5s ease;
    }
    
    .kb-card:hover {
        transform: translateY(-8px);
        box-shadow: 0 30px 80px rgba(0, 0, 0, 0.3);
    }
</style>
"""
    
    /* 섹션 헤더 */
    .section-header {
        font-size: 1.8rem;
        font-weight: 600;
        color: #2c3e50;
        margin: 2rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #667eea;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* 사이드바 스타일 */
    .css-1d391kg {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(135deg, #667eea, #764ba2);
        border: none;
        border-radius: 25px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    
    /* 추천 카드 스타일 */
    .recommendation-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 20px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
        position: relative;
        overflow: hidden;
    }
    
    .recommendation-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.1) 50%, transparent 70%);
        transform: translateX(-100%);
        transition: transform 0.6s ease;
    }
    
    .recommendation-card:hover::before {
        transform: translateX(100%);
    }
    
    /* 뉴스 카드 스타일 */
    .news-card {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #667eea;
    }
    
    /* 지표 스타일 */
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #2c3e50;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* 레벨 표시 */
    .level-indicator {
        display: inline-block;
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    
    /* 로딩 애니메이션 */
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    .loading {
        animation: pulse 2s infinite;
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 10px;
        padding: 10px 20px;
        border: none;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea, #764ba2);
        color: white;
    }
</style>
"""

class DailyReportApp:
    """맞춤형 데일리 리포트 애플리케이션"""
    
    def __init__(self):
        """애플리케이션 초기화"""
        self.config = Config()
        self.gpt_client = GPTClient()
        self.recommendation_engine = ETFRecommendationEngine()
        
        # 뉴스 분석기 초기화
        self.news_analyzer = NewsAnalyzer()
        self.price_analyzer = StockPriceAnalyzer()
        
        # 데이터 로딩
        self.data = self._load_data()
        
        logger.info("데일리 리포트 애플리케이션 초기화 완료")

    @st.cache_data
    def _load_data(_self) -> Dict[str, pd.DataFrame]:
        """데이터 로딩 (캐싱 적용)"""
        try:
            data = {}
            
            # ETF 캐시 데이터
            cache_path = os.path.join(_self.config.DATA_DIR, "etf_scores_cache.csv")
            if os.path.exists(cache_path):
                data['etf_cache'] = safe_read_csv_with_fallback(cache_path)
                logger.info(f"ETF 캐시 데이터 로딩 완료: {len(data['etf_cache'])}행")
            
            # ETF 시세 데이터
            price_path = os.path.join(_self.config.DATA_DIR, "ETF_시세_데이터_20240101_20250729.csv")
            if os.path.exists(price_path):
                data['etf_prices'] = safe_read_csv_with_fallback(price_path)
                logger.info(f"ETF 시세 데이터 로딩 완료: {len(data['etf_prices'])}행")
            
            # 기타 데이터
            data_types = ['etf_info', 'etf_performance', 'etf_aum']
            for data_type in data_types:
                file_path = _self.config.get_data_path(data_type)
                if file_path and os.path.exists(file_path):
                    data[data_type] = safe_read_csv_with_fallback(file_path)
                    logger.info(f"{data_type} 데이터 로딩 완료")
            
            return data
            
        except Exception as e:
            logger.error(f"데이터 로딩 중 오류: {e}")
            return {}

    def setup_ui(self):
        """UI 설정"""
        st.set_page_config(
            page_title="맞춤형 데일리 리포트", 
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # 커스텀 CSS 적용
        st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
        
        # 헤더
        self._display_header()
        
        # 사이드바 설정
        self._setup_sidebar()

    def _display_header(self):
        """KB 스타일 헤더 표시"""
        st.markdown("""
        <div class="kb-header">
            <div class="kb-logo">🏦 KB 금융그룹</div>
            <div class="kb-subtitle">맞춤형 데일리 금융 리포트 & ETF 추천 시스템</div>
        </div>
        """, unsafe_allow_html=True)

    def _setup_sidebar(self):
        """사이드바 설정"""
        st.sidebar.markdown("""
        <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 1rem; border-radius: 15px; color: white; margin-bottom: 2rem;">
            <h3 style="margin: 0; text-align: center;">👤 사용자 프로필</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # 투자 레벨 선택
        level = st.sidebar.selectbox(
            "🎯 투자 레벨",
            options=[1, 2, 3, 4, 5],
            format_func=lambda x: f"Level {x} - {'초보자' if x == 1 else '입문자' if x == 2 else '중급자' if x == 3 else '고급자' if x == 4 else '전문가'}",
            help="Level 1: 초보자, Level 5: 전문가"
        )
        
        # WMTI 투자 성향 선택
        wmti_types = list(self.config.WMTI_TYPE_WEIGHTS.keys())
        wmti_type = st.sidebar.selectbox(
            "🧠 투자 성향 (WMTI)",
            options=wmti_types,
            help="WMTI 투자자 유형별 맞춤 추천"
        )
        
        # MPTI 설명 스타일 선택
        mpti_types = list(self.config.INVESTOR_TYPE_DESCRIPTIONS.keys())
        mpti_type = st.sidebar.selectbox(
            "📝 설명 스타일 (MPTI)",
            options=mpti_types,
            index=mpti_types.index('IFSA'),  # 기본값
            help="MPTI 기반 설명 스타일 (팩트형/오피니언형, 집중형/분산형)"
        )
        
        # 관심 종목 (반도체, 2차전지 고정)
        st.sidebar.markdown("### 📈 관심 종목")
        st.sidebar.info("반도체 및 2차전지 테마 종목으로 고정 설정")
        interest_stocks = "TIGER 반도체\nTIGER 2차전지테마\n삼성전자\nSK하이닉스\nLG에너지솔루션"
        
        # 추가 분석 옵션
        st.sidebar.markdown("### 🔍 추가 분석")
        show_portfolio_analysis = st.sidebar.checkbox("ETF 포트폴리오 분석", value=False)
        show_price_comparison = st.sidebar.checkbox("시세 비교 분석", value=False)
        show_news_sentiment = st.sidebar.checkbox("뉴스 감정분석", value=False)
        
        # 리포트 생성 버튼
        if st.sidebar.button("🚀 리포트 생성", type="primary", use_container_width=True):
            self.generate_report(level, wmti_type, mpti_type, interest_stocks, show_portfolio_analysis, show_price_comparison, show_news_sentiment)
        
        return level, wmti_type, mpti_type, interest_stocks, show_portfolio_analysis, show_price_comparison, show_news_sentiment

    def generate_report(self, level: int, wmti_type: str, mpti_type: str, interest_stocks: str, show_portfolio: bool, show_price_comparison: bool, show_news_sentiment: bool):
        """맞춤형 리포트 생성"""
        
        # 관심 종목 파싱
        interest_list = [stock.strip() for stock in interest_stocks.split('\n') if stock.strip()]
        
        # 탭으로 구분된 리포트 생성
        tabs = ["📈 시장 개요", "📰 데일리 브리핑", "🎯 추천 종목"]
        
        # 추가 분석 탭들 추가
        if show_portfolio:
            tabs.append("📊 포트폴리오 분석")
        if show_price_comparison:
            tabs.append("📈 시세 비교")
        if show_news_sentiment:
            tabs.append("📰 뉴스 감정분석")
        
        tab_list = st.tabs(tabs)
        
        with tab_list[0]:
            # 로딩 표시
            with st.spinner("📊 시장 개요를 생성하고 있습니다..."):
                self._display_market_overview(level, mpti_type)
        
        with tab_list[1]:
            with st.spinner("📰 데일리 브리핑을 생성하고 있습니다..."):
                self._display_daily_briefing(level, interest_list, mpti_type)
        
        with tab_list[2]:
            with st.spinner("🎯 추천 종목을 분석하고 있습니다..."):
                self._display_recommendations(level, wmti_type, mpti_type)
        
        # 추가 분석 탭들
        tab_index = 3
        
        if show_portfolio:
            with tab_list[tab_index]:
                with st.spinner("📊 포트폴리오 분석을 수행하고 있습니다..."):
                    self._display_portfolio_analysis_module(level, interest_list)
            tab_index += 1
        
        if show_price_comparison:
            with tab_list[tab_index]:
                with st.spinner("📈 시세 비교 분석을 수행하고 있습니다..."):
                    self._display_price_comparison_module(level, interest_list)
            tab_index += 1
        
        if show_news_sentiment:
            with tab_list[tab_index]:
                with st.spinner("📰 뉴스 감정분석을 수행하고 있습니다"):
                    self._display_news_sentiment_module(level, interest_list)
        
        st.success("리포트 생성이 완료되었습니다!")

    def _display_market_overview(self, level: int, mpti_type: str):
        """시장개요 표시"""
        st.markdown(f'<div class="section-header">📈 시장 개요 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        # 날짜 표시
        today = datetime.now()
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h3 style="color: #2c3e50; margin: 0;">{today.strftime('%Y년 %m월 %d일')} ({today.strftime('%A')[:3]})</h3>
            <p style="color: #666; margin: 0;">오늘의 시장 동향</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 실제 시장 지수 데이터 수집
        market_indices = self.price_analyzer.get_market_indices()
        
        # 국내 시장 지표
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("**🇰🇷 국내 시장**")
            
            # KOSPI
            if 'KOSPI' in market_indices:
                kospi_data = market_indices['KOSPI']
                st.metric(
                    label="KOSPI",
                    value=kospi_data['value'],
                    delta=f"{kospi_data['change']}%",
                    delta_color="normal" if kospi_data['change'] >= 0 else "inverse"
                )
            else:
                st.metric(label="KOSPI", value="2,750.32", delta="0.5%")
            
            # KOSDAQ
            if 'KOSDAQ' in market_indices:
                kosdaq_data = market_indices['KOSDAQ']
                st.metric(
                    label="KOSDAQ",
                    value=kosdaq_data['value'],
                    delta=f"{kosdaq_data['change']}%",
                    delta_color="normal" if kosdaq_data['change'] >= 0 else "inverse"
                )
            else:
                st.metric(label="KOSDAQ", value="850.15", delta="-0.2%")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("**🌍 해외 시장**")
            
            # S&P 500
            if 'S&P500' in market_indices:
                sp500_data = market_indices['S&P500']
                st.metric(
                    label="S&P 500",
                    value=sp500_data['value'],
                    delta=f"{sp500_data['change']}%",
                    delta_color="normal" if sp500_data['change'] >= 0 else "inverse"
                )
            else:
                st.metric(label="S&P 500", value="4,850.25", delta="0.8%")
            
            # NASDAQ
            if 'NASDAQ' in market_indices:
                nasdaq_data = market_indices['NASDAQ']
                st.metric(
                    label="NASDAQ",
                    value=nasdaq_data['value'],
                    delta=f"{nasdaq_data['change']}%",
                    delta_color="normal" if nasdaq_data['change'] >= 0 else "inverse"
                )
            else:
                st.metric(label="NASDAQ", value="15,250.80", delta="1.2%")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # 레벨별 시장 해석
        self._display_market_interpretation(level, mpti_type)

    def _display_market_interpretation(self, level: int, mpti_type: str):
        """레벨별 시장 해석"""
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("**📊 시장 해석**")
        
        if level == 1:
            interpretation = """
            **🎯 Level 1 - 초보자용 해석**
            
            오늘 시장은 조금 올랐어요! KOSPI가 0.5% 올라서 2,750점을 넘었답니다. 
            마치 우리가 좋은 점수를 받았을 때 기분이 좋은 것처럼, 시장도 기분이 좋아 보여요! 😊
            
            하지만 KOSDAQ은 조금 내려갔어요. 마치 친구 중에 한 명이 아픈 것처럼, 
            모든 주식이 다 같이 올라가는 건 아니에요.
            """
        elif level == 2:
            interpretation = """
            **📊 Level 2 - 입문자용 해석**
            
            오늘 시장은 안정적인 흐름을 보였습니다. KOSPI가 0.5% 상승하여 2,750선을 회복했고,
            이는 글로벌 시장의 안정화와 국내 경제 전망 개선이 반영된 것으로 보입니다.
            
            KOSDAQ은 소폭 하락했는데, 이는 기술주들의 일시적 조정세입니다.
            전반적으로 투자 심리는 긍정적인 상태를 유지하고 있습니다.
            """
        elif level == 3:
            interpretation = """
            **📈 Level 3 - 중급자용 해석**
            
            오늘 국내 시장은 소폭 상승세를 보였습니다. KOSPI가 0.5% 상승하여 2,750선을 회복했으며,
            이는 최근 글로벌 금리 인하 기대감과 기업 실적 개선 전망이 반영된 것으로 보입니다.
            
            KOSDAQ은 0.2% 하락했는데, 이는 반도체 등 기술주들의 일시적 조정세로 판단됩니다.
            전반적으로 시장은 안정적인 흐름을 보이고 있습니다.
            """
        elif level == 4:
            interpretation = """
            **🔬 Level 4 - 고급자용 해석**
            
            오늘 시장은 기술적 분석 관점에서 긍정적인 신호를 보였습니다. KOSPI 2,750선 회복은
            주요 지지선에서의 반등으로 해석되며, 거래량 증가와 함께 매수세가 강화되고 있습니다.
            
            섹터별로는 반도체, 자동차 등 주요 업종에서 매수세가 우세하며,
            외국인 자금 유입과 기관 투자자들의 포지션 정리가 맞물려 안정적인 상승세를 보이고 있습니다.
            """
        else:  # level == 5
            interpretation = """
            **🔍 Level 5 - 전문가용 해석**
            
            오늘 시장은 기술적 지지선에서 반등세를 보였습니다. KOSPI 2,750선 회복은 
            외국인 자금 유입과 기관 투자자들의 매수세가 맞물린 결과로 분석됩니다.
            
            섹터별로는 반도체, 2차전지 등 성장주 중심의 매수가 이어졌으며,
            금리 인하 기대감과 함께 리스크 온(risk-on) 분위기가 지속되고 있습니다.
            """
        
        # MPTI 스타일 적용
        styled_interpretation = self._apply_mpti_style(interpretation, mpti_type)
        st.markdown(styled_interpretation)
        st.markdown('</div>', unsafe_allow_html=True)

    def _apply_mpti_style(self, text: str, mpti_type: str) -> str:
        """MPTI에 따른 텍스트 스타일 적용"""
        try:
            from chatbot.config import Config
            
            # MPTI 스타일 정의 가져오기
            mpti_styles = Config.MPTI_STYLES
            
            # MPTI 유형별 스타일 적용
            if mpti_type in mpti_styles:
                style = mpti_styles[mpti_type]
                
                # 텍스트 변환 적용
                for old_text, new_text in style['transformations'].items():
                    text = text.replace(old_text, new_text)
                
                # 추가 문구 삽입
                if style['additions']:
                    import random
                    addition = random.choice(style['additions'])
                    if text and not text.endswith('.'):
                        text += '. '
                    text = f"{addition} {text}"
                
                # 제거할 문구 처리
                for removal in style['removals']:
                    text = text.replace(removal, '')
                
                # 문장 길이 제한 (Intensive, Skimming형)
                if 'max_sentence_length' in style:
                    max_length = style['max_sentence_length']
                    sentences = text.split('. ')
                    shortened_sentences = []
                    for sentence in sentences:
                        if len(sentence) > max_length:
                            # 핵심 키워드만 추출하여 간단히
                            words = sentence.split()
                            if len(words) > 5:
                                shortened_sentences.append(' '.join(words[:5]) + '...')
                            else:
                                shortened_sentences.append(sentence)
                        else:
                            shortened_sentences.append(sentence)
                    text = '. '.join(shortened_sentences)
                
                # 특별한 스타일 적용
                if mpti_type == 'Skimming':
                    # 요약형: 핵심 포인트만 추출
                    lines = text.split('\n')
                    if len(lines) > 2:
                        text = f"**핵심:** {lines[0]}\n**요약:** {lines[1] if len(lines) > 1 else ''}"
                
                elif mpti_type == 'Perusing':
                    # 상세형: 추가 설명 포함
                    if "분석" not in text:
                        text += "\n\n**상세 분석:** 위 결과는 기술적 지표, 기본적 분석, 시장 동향을 종합적으로 고려한 것입니다."
                
                elif mpti_type == 'Extensive':
                    # 다각형: 다양한 관점 추가
                    if "다양한 관점" not in text:
                        text += "\n\n**다양한 관점:** 이 외에도 다른 섹터와의 비교, 글로벌 시장 동향, 정책적 요인 등도 고려해볼 수 있습니다."
                
                elif mpti_type == 'Intensive':
                    # 집중형: 핵심만 강조
                    if "**핵심**" not in text:
                        text = f"**핵심:** {text}"
                
                elif mpti_type == 'Fact':
                    # 팩트형: 데이터 기반 강조
                    if "데이터" not in text:
                        text = f"**데이터 기반 분석:** {text}"
                
                elif mpti_type == 'Opinion':
                    # 오피니언형: 전문가 관점 강조
                    if "전문가" not in text:
                        text = f"**전문가 관점:** {text}"
            
            return text
            
        except Exception as e:
            logger.error(f"MPTI 스타일 적용 실패: {e}")
            return text

    def _display_daily_briefing(self, level: int, interest_list: List[str], mpti_type: str):
        """데일리 브리핑 표시"""
        st.markdown(f'<div class="section-header">📰 데일리 브리핑 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        if not interest_list:
            st.info("💡 관심 종목을 입력해주세요!")
            return
        
        # 관심 종목별 브리핑
        for stock in interest_list[:3]:  # 최대 3개까지만 표시
            self._display_stock_briefing(stock, level, mpti_type)

    def _display_stock_briefing(self, stock: str, level: int, mpti_type: str):
        """개별 종목 브리핑"""
        st.markdown(f'<div class="metric-card">', unsafe_allow_html=True)
        st.markdown(f"**📊 {stock}**")
        
        # 실제 주가 정보 수집
        price_info = self.price_analyzer.get_stock_price_info(stock)
        
        # 종목 정보 표시
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            # 현재가 및 변동
            current_price = price_info['current_price']
            change_percent = price_info['change_percent']
            change_amount = price_info['change_amount']
            
            st.metric(
                label="현재가",
                value=f"{current_price}원",
                delta=f"{change_percent}% ({change_amount}원)",
                delta_color="normal" if change_percent >= 0 else "inverse"
            )
        
        with col2:
            st.markdown("**거래량**")
            st.write(price_info['volume'])
        
        with col3:
            st.markdown("**시가총액**")
            st.write(price_info['market_cap'])
        
        # 어제종목요약.py 스타일의 시세 분석 추가
        if "TIGER" in stock or "ETF" in stock:
            self._display_etf_price_analysis(stock, level, mpti_type)
        else:
            self._display_stock_price_analysis(stock, level, mpti_type)
        
        # 실제 뉴스 수집 및 분석
        news_list = self.news_analyzer.get_stock_news(stock, days=1)
        
        # 레벨별 뉴스 요약 생성
        if news_list:
            summarized_news = self.news_analyzer.get_level_specific_summary(news_list, level)
            
            # 이슈 요약 (가장 중요한 뉴스 기반)
            if summarized_news:
                main_news = summarized_news[0]
                st.markdown("**📝 이슈 요약**")
                st.info(main_news.get('level_summary', main_news['summary']))
            
            # 구성 종목 뉴스 (ETF인 경우)
            if "TIGER" in stock or "ETF" in stock:
                self._display_constituent_news(summarized_news, level, mpti_type)
        else:
            # 뉴스가 없는 경우 기본 요약
            st.markdown("**📝 이슈 요약**")
            if level == 1:
                summary = f"{stock}에 대한 최신 뉴스가 없어요. 하지만 주가가 {change_percent}% 변동했으니 관심을 가져보세요!"
            else:
                summary = f"{stock}의 최신 뉴스 정보가 제한적입니다. 주가 변동률 {change_percent}%를 참고하시기 바랍니다."
            st.info(summary)
        
        st.markdown('</div>', unsafe_allow_html=True)

    def _display_constituent_news(self, news_list: List[Dict], level: int, mpti_type: str):
        """구성 종목 뉴스 표시 (data_analysis.py 통합)"""
        st.markdown("**📰 구성 종목 주요 뉴스**")
        
        # ETF 구성종목 분석 추가
        try:
            # ETF 코드 가져오기
            etf_name = "TIGER 반도체"  # 기본값
            etf_code = self._get_etf_code(etf_name)
            
            # ETF 구성종목 정보 가져오기
            constituent_info = self._get_etf_constituents(etf_code)
            
            if constituent_info:
                st.markdown("**📊 구성종목 정보**")
                st.info(f"상위 3개 구성종목: {', '.join(constituent_info['top_3_names'])}")
                
        except Exception as e:
            logger.error(f"ETF 구성종목 분석 실패: {e}")
        
        # 상위 3개 뉴스만 표시
        for news in news_list[:3]:
            st.markdown('<div class="news-card">', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 3, 1])
            
            with col1:
                # 회사명 추출 (뉴스 제목에서)
                company_name = self._extract_company_name(news['title'])
                st.markdown(f"**{company_name}**")
            
            with col2:
                # 레벨별 요약 표시
                summary = news.get('level_summary', news['summary'])
                st.write(summary)
            
            with col3:
                sentiment_emoji = "👍" if news['sentiment'] == "긍정적" else "👎"
                st.markdown(f"{sentiment_emoji} {news['sentiment']}")
                st.caption(f"출처: {news['source']}")
            st.markdown('</div>', unsafe_allow_html=True)

    def _get_etf_constituents(self, etf_code: str) -> Dict:
        """ETF 구성종목 정보 가져오기 (data_analysis.py 기능)"""
        try:
            from pykrx.stock import get_etf_portfolio_deposit_file, get_market_ticker_name
            
            # ETF 구성 종목 가져오기
            df = get_etf_portfolio_deposit_file(etf_code)
            
            if df.empty:
                return None
            
            # 상위 3개 종목 정보
            top_3 = df.head(3)
            
            # 종목명 매핑
            ticker_names = {}
            for ticker in top_3.index:
                try:
                    name = get_market_ticker_name(ticker)
                    ticker_names[ticker] = name
                except:
                    ticker_names[ticker] = ticker
            
            # 결과 포맷팅
            result = {
                'top_3_names': [ticker_names.get(ticker, ticker) for ticker in top_3.index],
                'top_3_weights': top_3['비중'].tolist(),
                'total_constituents': len(df)
            }
            
            return result
            
        except Exception as e:
            logger.error(f"ETF 구성종목 정보 가져오기 실패: {e}")
            return None
    
    def _extract_company_name(self, title: str) -> str:
        """뉴스 제목에서 회사명 추출"""
        # 주요 기업명 리스트
        companies = ['삼성전자', 'SK하이닉스', 'LG에너지솔루션', '현대차', '기아', 'POSCO홀딩스']
        
        for company in companies:
            if company in title:
                return company
        
        # 회사명을 찾지 못한 경우 첫 번째 단어 반환
        return title.split()[0] if title.split() else "기업"

    def _display_recommendations(self, level: int, wmti_type: str, mpti_type: str):
        """추천 종목 표시"""
        st.markdown(f'<div class="section-header">🎯 오늘의 추천 ETF <span class="level-indicator">{wmti_type}</span></div>', unsafe_allow_html=True)
        
        # 더보기 버튼
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("더보기", type="secondary"):
                st.session_state.show_more = True
        
        # 추천 ETF 생성
        recommendations = self._generate_recommendations(level, wmti_type)
        
        # 추천 ETF 카드들 표시
        for i, rec in enumerate(recommendations[:3]):
            self._display_recommendation_card(rec, level, i+1, mpti_type)

    def _generate_recommendations(self, level: int, wmti_type: str) -> List[Dict]:
        """추천 ETF 생성"""
        try:
            if 'etf_cache' not in self.data:
                logger.warning("ETF 캐시 데이터가 없습니다. 샘플 데이터를 사용합니다.")
                return self._get_sample_recommendations()
            
            # 사용자 프로필 생성
            user_profile = {
                "level": level,
                "wmti_type": wmti_type
            }
            
            # 캐시 데이터에서 직접 WMTI 점수로 추천 생성
            cache_df = self.data['etf_cache'].copy()
            
            # 1. 레벨 필터링
            cache_df['level'] = pd.to_numeric(cache_df['level'], errors='coerce')
            level_filtered = cache_df[cache_df['level'] == level]
            
            if level_filtered.empty:
                logger.warning(f"Level {level}에 맞는 ETF가 없습니다.")
                return self._get_sample_recommendations()
            
            # 2. WMTI 점수 컬럼 확인
            wmti_score_column = f'score_{wmti_type}'
            if wmti_score_column not in level_filtered.columns:
                logger.warning(f"WMTI 점수 컬럼 {wmti_score_column}이 없습니다. total_score 사용")
                wmti_score_column = 'total_score'
            
            # 3. WMTI 점수로 정렬
            level_filtered = level_filtered.sort_values(wmti_score_column, ascending=False)
            
            # 4. 상위 3개 선택
            top_etfs = level_filtered.head(3)
            
            # 5. 추천 결과 포맷팅
            recommendations = []
            for _, row in top_etfs.iterrows():
                rec = {
                    "종목명": row.get('종목명', '알 수 없음'),
                    "종목코드": row.get('종목코드', '000000'),
                    "현재가": str(row.get('현재가', 0)),
                    "수익률_1개월": round(row.get('수익률_1개월', 0), 2),
                    "추천이유": [
                        f"WMTI {wmti_type} 점수: {row.get(wmti_score_column, 0):.3f}",
                        f"위험도: {row.get('risk_tier', 'N/A')}",
                        f"분류: {row.get('분류체계', 'N/A')}"
                    ]
                }
                recommendations.append(rec)
            
            logger.info(f"Level {level}, WMTI {wmti_type} 기반 추천 완료: {len(recommendations)}개")
            return recommendations
            
        except Exception as e:
            logger.error(f"추천 생성 중 오류: {e}")
            return self._get_sample_recommendations()

    def _get_sample_recommendations(self) -> List[Dict]:
        """실제 캐시 데이터에서 추천 생성 (fallback)"""
        try:
            if 'etf_cache' in self.data and not self.data['etf_cache'].empty:
                # 캐시 데이터에서 상위 ETF 선택
                cache_df = self.data['etf_cache'].copy()
                
                # 기본 정렬 (총점 기준)
                if 'total_score' in cache_df.columns:
                    cache_df = cache_df.sort_values('total_score', ascending=False)
                elif 'final_score' in cache_df.columns:
                    cache_df = cache_df.sort_values('final_score', ascending=False)
                
                # 상위 3개 선택
                top_etfs = cache_df.head(3)
                
                recommendations = []
                for _, row in top_etfs.iterrows():
                    rec = {
                        "종목명": row.get('종목명', row.get('ETF명', '알 수 없음')),
                        "종목코드": row.get('종목코드', row.get('srtnCd', '000000')),
                        "현재가": str(row.get('현재가', 0)),
                        "수익률_1개월": round(row.get('수익률_1개월', 0), 2),
                        "추천이유": [
                            f"총점: {row.get('total_score', row.get('final_score', 0)):.2f}",
                            f"위험도: {row.get('risk_tier', 'N/A')}",
                            f"수익률: {row.get('수익률_1개월', 0):.2f}%"
                        ]
                    }
                    recommendations.append(rec)
                
                return recommendations
            else:
                # 캐시 데이터가 없는 경우 기본 샘플 데이터
                return [
                    {
                        "종목명": "TIGER 2차전지테마",
                        "종목코드": "306540",
                        "현재가": "15,865",
                        "수익률_1개월": 2.00,
                        "추천이유": [
                            "2차전지 산업은 5년 이상 장기 성장 전망",
                            "최근 6개월 수익률 기준 우려한 회복세",
                            "SK이노베이션 우량 포함"
                        ]
                    },
                    {
                        "종목명": "TIGER 미국 S&P500",
                        "종목코드": "390750", 
                        "현재가": "67,665",
                        "수익률_1개월": 5.70,
                        "추천이유": [
                            "장기 분산투자에 강한 ETF",
                            "미국 시장의 거시 트렌드 반영",
                            "6개월 기준 안정적 상승세 유지"
                        ]
                    },
                    {
                        "종목명": "TIGER 반도체",
                        "종목코드": "091230",
                        "현재가": "38,310",
                        "수익률_1개월": 3.20,
                        "추천이유": [
                            "AI 반도체 수요 증가 전망",
                            "글로벌 반도체 업종 회복세",
                            "주요 기업 실적 개선 예상"
                        ]
                    }
                ]
        except Exception as e:
            logger.error(f"샘플 추천 생성 중 오류: {e}")
            return []

    def _display_recommendation_card(self, rec: Dict, level: int, card_num: int, mpti_type: str):
        """추천 ETF 카드 표시"""
        st.markdown(f'''
        <div class="recommendation-card">
            <h3 style="margin: 0 0 1rem 0; color: white;">{card_num}. {rec['종목명']} ({rec['종목코드']})</h3>
        </div>
        ''', unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 2])
        
        with col1:
            st.metric(
                label="현재가",
                value=f"{rec['현재가']}원"
            )
        
        with col2:
            st.metric(
                label="수익률 (1개월)",
                value=f"{rec['수익률_1개월']}%",
                delta_color="normal" if rec['수익률_1개월'] >= 0 else "inverse"
            )
        
        with col3:
            st.markdown("**💡 추천 이유**")
            for reason in rec['추천이유']:
                styled_reason = self._apply_mpti_style(reason, mpti_type)
                st.markdown(f"• {styled_reason}")

    def _display_detailed_analysis(self, level: int, interest_list: List[str], show_portfolio: bool, show_price_comparison: bool):
        """상세 분석 표시"""
        st.markdown(f'<div class="section-header">🔍 상세 분석 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        if not interest_list:
            st.info("💡 관심 종목을 입력해주세요!")
            return
        
        # 첫 번째 종목에 대해 상세 분석
        main_stock = interest_list[0]
        
        # ETF 포트폴리오 분석
        if show_portfolio and PYKRX_AVAILABLE and ("TIGER" in main_stock or "ETF" in main_stock):
            self._display_portfolio_analysis(main_stock, level)
        
        # 시세 비교 분석
        if show_price_comparison:
            self._display_price_comparison(main_stock, level)

    def _display_portfolio_analysis(self, etf_name: str, level: int):
        """ETF 포트폴리오 분석"""
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("**📊 ETF 포트폴리오 분석**")
        
        try:
            # ETF 코드 추출 (간단한 매핑)
            etf_codes = {
                'TIGER 반도체': '091230',
                'TIGER 2차전지테마': '306540',
                'TIGER 미국 S&P500': '390750'
            }
            
            etf_code = etf_codes.get(etf_name, '091230')
            
            # 포트폴리오 데이터 가져오기
            df = stock.get_etf_portfolio_deposit_file(etf_code)
            
            if not df.empty:
                # 상위 10개 종목 표시
                top_holdings = df.head(10)
                
                st.markdown(f"**{etf_name} 상위 10개 종목**")
                
                # 테이블로 표시
                display_df = top_holdings[['비중']].copy()
                display_df['비중'] = display_df['비중'].apply(lambda x: f"{x:.2f}%")
                st.dataframe(display_df, use_container_width=True)
                
                # 파이 차트
                fig = px.pie(
                    values=top_holdings['비중'],
                    names=top_holdings.index,
                    title=f"{etf_name} 상위 종목 비중"
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # 레벨별 해석
                if level == 1:
                    interpretation = f"{etf_name}는 여러 종목을 모아놓은 상자예요. 가장 많이 들어있는 종목은 {top_holdings.index[0]}이고, 전체의 {top_holdings['비중'].iloc[0]:.1f}%를 차지해요!"
                elif level == 3:
                    interpretation = f"{etf_name}의 포트폴리오를 분석해보면, {top_holdings.index[0]}이 {top_holdings['비중'].iloc[0]:.1f}%로 가장 큰 비중을 차지하고 있습니다. 상위 10개 종목이 전체의 약 {top_holdings['비중'].sum():.1f}%를 차지하여 비교적 집중도가 높은 편입니다."
                else:
                    interpretation = f"{etf_name}의 포트폴리오 분석 결과, {top_holdings.index[0]}이 {top_holdings['비중'].iloc[0]:.1f}%로 최대 비중을 차지하고 있습니다. 상위 10개 종목의 집중도가 {top_holdings['비중'].sum():.1f}%로 높은 편이며, 이는 특정 섹터나 테마에 집중 투자하는 특성을 보여줍니다."
                
                st.info(interpretation)
            else:
                st.warning("포트폴리오 데이터를 가져올 수 없습니다.")
                
        except Exception as e:
            st.error(f"포트폴리오 분석 중 오류: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)

    def _display_price_comparison(self, stock_name: str, level: int):
        """시세 비교 분석"""
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("**📈 최근 5거래일 시세 비교**")
        
        try:
            # 종목 코드 추출
            stock_codes = {
                '삼성전자': '005930',
                'SK하이닉스': '000660',
                'TIGER 반도체': '091230',
                'TIGER 2차전지테마': '306540'
            }
            
            stock_code = stock_codes.get(stock_name, '005930')
            
            # 최근 5거래일 데이터 가져오기
            if PYKRX_AVAILABLE:
                df_days = self._get_last_n_trading_days(stock_code, n=5)
                
                if not df_days.empty:
                    # 데이터 표시
                    st.markdown(f"**{stock_name} 최근 5거래일 시세**")
                    display_df = df_days[['시가','고가','저가','종가','거래량']].copy()
                    display_df['종가'] = display_df['종가'].apply(lambda x: f"{int(x):,}원")
                    display_df['거래량'] = display_df['거래량'].apply(lambda x: f"{int(x):,}")
                    st.dataframe(display_df, use_container_width=True)
                    
                    # 가격 변동 그래프
                    fig = px.line(
                        df_days, 
                        y='종가',
                        title=f"{stock_name} 최근 5거래일 종가 변동"
                    )
                    fig.update_layout(xaxis_title="날짜", yaxis_title="종가 (원)")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 레벨별 해석
                    latest_price = df_days['종가'].iloc[-1]
                    prev_price = df_days['종가'].iloc[-2]
                    change_percent = ((latest_price - prev_price) / prev_price) * 100
                    
                    if level == 1:
                        interpretation = f"{stock_name}는 어제 {latest_price:,.0f}원으로 마감했어요. 전날보다 {change_percent:+.1f}% 변동했답니다!"
                    elif level == 3:
                        interpretation = f"{stock_name}의 최근 5거래일 추이를 보면, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다. 최고가 {df_days['고가'].max():,.0f}원, 최저가 {df_days['저가'].min():,.0f}원을 기록했습니다."
                    else:
                        interpretation = f"{stock_name}의 최근 5거래일 분석 결과, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다. 5일간의 변동폭은 {((df_days['고가'].max() - df_days['저가'].min()) / df_days['저가'].min()) * 100:.1f}%이며, 평균 거래량은 {df_days['거래량'].mean():,.0f}주입니다."
                    
                    st.info(interpretation)
                else:
                    st.warning("시세 데이터를 가져올 수 없습니다.")
            else:
                st.warning("pykrx 라이브러리가 설치되지 않아 시세 비교 기능을 사용할 수 없습니다.")
                
        except Exception as e:
            st.error(f"시세 비교 분석 중 오류: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)

    def _display_portfolio_analysis_module(self, level: int, interest_list: List[str]):
        """포트폴리오 분석 모듈 호출"""
        st.markdown(f'<div class="section-header">📊 ETF 포트폴리오 분석 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        if not interest_list:
            st.info("💡 관심 종목을 입력해주세요!")
            return
        
        # 첫 번째 ETF 종목에 대해 분석
        etf_name = interest_list[0]
        
        if "TIGER" in etf_name or "ETF" in etf_name:
            try:
                # data_analysis.py의 기능을 호출
                etf_code = self._get_etf_code(etf_name)
                
                if PYKRX_AVAILABLE:
                    # 포트폴리오 데이터 가져오기
                    df = stock.get_etf_portfolio_deposit_file(etf_code)
                    
                    if not df.empty:
                        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                        st.markdown(f"**{etf_name} 포트폴리오 분석**")
                        
                        # 상위 10개 종목 표시
                        top_holdings = df.head(10)
                        
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.markdown("**상위 10개 종목**")
                            display_df = top_holdings[['비중']].copy()
                            display_df['비중'] = display_df['비중'].apply(lambda x: f"{x:.2f}%")
                            st.dataframe(display_df, use_container_width=True)
                        
                        with col2:
                            # 파이 차트
                            fig = px.pie(
                                values=top_holdings['비중'],
                                names=top_holdings.index,
                                title=f"{etf_name} 상위 종목 비중"
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # 레벨별 해석
                        if level == 1:
                            interpretation = f"{etf_name}는 여러 종목을 모아놓은 상자예요. 가장 많이 들어있는 종목은 {top_holdings.index[0]}이고, 전체의 {top_holdings['비중'].iloc[0]:.1f}%를 차지해요!"
                        elif level == 3:
                            interpretation = f"{etf_name}의 포트폴리오를 분석해보면, {top_holdings.index[0]}이 {top_holdings['비중'].iloc[0]:.1f}%로 가장 큰 비중을 차지하고 있습니다. 상위 10개 종목이 전체의 약 {top_holdings['비중'].sum():.1f}%를 차지하여 비교적 집중도가 높은 편입니다."
                        else:
                            interpretation = f"{etf_name}의 포트폴리오 분석 결과, {top_holdings.index[0]}이 {top_holdings['비중'].iloc[0]:.1f}%로 최대 비중을 차지하고 있습니다. 상위 10개 종목의 집중도가 {top_holdings['비중'].sum():.1f}%로 높은 편이며, 이는 특정 섹터나 테마에 집중 투자하는 특성을 보여줍니다."
                        
                        st.info(interpretation)
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.warning("포트폴리오 데이터를 가져올 수 없습니다.")
                else:
                    st.warning("pykrx 라이브러리가 설치되지 않아 포트폴리오 분석 기능을 사용할 수 없습니다.")
                    
            except Exception as e:
                st.error(f"포트폴리오 분석 중 오류: {e}")
        else:
            st.info("ETF 종목에 대해서만 포트폴리오 분석이 가능합니다.")

    def _display_price_comparison_module(self, level: int, interest_list: List[str]):
        """시세 비교 분석 모듈 호출"""
        st.markdown(f'<div class="section-header">📈 시세 비교 분석 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        if not interest_list:
            st.info("💡 관심 종목을 입력해주세요!")
            return
        
        # 첫 번째 종목에 대해 분석
        stock_name = interest_list[0]
        
        try:
            stock_code = self._get_stock_code(stock_name)
            
            if PYKRX_AVAILABLE:
                # 어제종목요약.py의 기능을 호출
                df_days = self._get_last_n_trading_days(stock_code, n=5)
                
                if not df_days.empty:
                    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                    st.markdown(f"**{stock_name} 최근 5거래일 시세 비교**")
                    
                    # 데이터 표시
                    display_df = df_days[['시가','고가','저가','종가','거래량']].copy()
                    display_df['종가'] = display_df['종가'].apply(lambda x: f"{int(x):,}원")
                    display_df['거래량'] = display_df['거래량'].apply(lambda x: f"{int(x):,}")
                    st.dataframe(display_df, use_container_width=True)
                    
                    # 가격 변동 그래프
                    fig = px.line(
                        df_days, 
                        y='종가',
                        title=f"{stock_name} 최근 5거래일 종가 변동"
                    )
                    fig.update_layout(xaxis_title="날짜", yaxis_title="종가 (원)")
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 레벨별 해석 (어제종목요약.py의 GPT 분석 기능 활용)
                    latest_price = df_days['종가'].iloc[-1]
                    prev_price = df_days['종가'].iloc[-2]
                    change_percent = ((latest_price - prev_price) / prev_price) * 100
                    
                    if level == 1:
                        interpretation = f"{stock_name}는 어제 {latest_price:,.0f}원으로 마감했어요. 전날보다 {change_percent:+.1f}% 변동했답니다!"
                    elif level == 3:
                        interpretation = f"{stock_name}의 최근 5거래일 추이를 보면, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다. 최고가 {df_days['고가'].max():,.0f}원, 최저가 {df_days['저가'].min():,.0f}원을 기록했습니다."
                    else:
                        interpretation = f"{stock_name}의 최근 5거래일 분석 결과, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다. 5일간의 변동폭은 {((df_days['고가'].max() - df_days['저가'].min()) / df_days['저가'].min()) * 100:.1f}%이며, 평균 거래량은 {df_days['거래량'].mean():,.0f}주입니다."
                    
                    st.info(interpretation)
                    st.markdown('</div>', unsafe_allow_html=True)
                else:
                    st.warning("시세 데이터를 가져올 수 없습니다.")
            else:
                st.warning("pykrx 라이브러리가 설치되지 않아 시세 비교 기능을 사용할 수 없습니다.")
                
        except Exception as e:
            st.error(f"시세 비교 분석 중 오류: {e}")

    def _display_news_sentiment_module(self, level: int, interest_list: List[str]):
        """뉴스 감정분석 모듈 호출"""
        st.markdown(f'<div class="section-header">📰 뉴스 감정분석 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        if not interest_list:
            st.info("💡 관심 종목을 입력해주세요!")
            return
        
        # 첫 번째 종목에 대해 분석
        stock_name = interest_list[0]
        
        try:
            stock_code = self._get_stock_code(stock_name)
            
            # gpt_sentiment.py의 기능을 호출
            headlines = self._fetch_naver_news(stock_code)
            
            if headlines:
                st.markdown('<div class="metric-card">', unsafe_allow_html=True)
                st.markdown(f"**{stock_name} 최근 뉴스 헤드라인**")
                
                # 뉴스 헤드라인 표시
                for i, headline in enumerate(headlines[:10], 1):
                    st.write(f"{i}. {headline}")
                
                # 감정분석 실행
                if st.button("감정분석 실행"):
                    with st.spinner("감정 분석 진행중..."):
                        results = self._analyze_news_sentiment(headlines)
                        
                        if results:
                            st.markdown("**감정분석 결과**")
                            st.table(pd.DataFrame(results))
                            
                            # 레벨별 요약
                            st.markdown("**레벨별 최종 요약**")
                            summary = self._generate_level_summary(headlines, level)
                            st.write(summary)
                
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.warning("뉴스 데이터를 가져올 수 없습니다.")
                
        except Exception as e:
            st.error(f"뉴스 감정분석 중 오류: {e}")

    def _get_etf_code(self, etf_name: str) -> str:
        """ETF명으로 종목 코드 찾기"""
        etf_codes = {
            'TIGER 반도체': '091230',
            'TIGER 2차전지테마': '306540',
            'TIGER 미국 S&P500': '390750'
        }
        return etf_codes.get(etf_name, '091230')

    def _get_stock_code(self, stock_name: str) -> str:
        """종목명으로 종목 코드 찾기"""
        stock_codes = {
            '삼성전자': '005930',
            'SK하이닉스': '000660',
            'LG에너지솔루션': '373220',
            '현대차': '005380',
            '기아': '000270',
            'POSCO홀딩스': '005490',
            'TIGER 반도체': '091230',
            'TIGER 2차전지테마': '306540',
            'TIGER 미국 S&P500': '390750'
        }
        return stock_codes.get(stock_name, '005930')

    def _get_last_n_trading_days(self, code: str, n: int = 5) -> pd.DataFrame:
        """최근 n거래일 데이터 가져오기 (어제종목요약.py 기능)"""
        days = []
        date = datetime.now()
        while len(days) < n:
            date -= timedelta(days=1)
            try:
                df = stock.get_etf_ohlcv_by_date(date.strftime('%Y%m%d'), date.strftime('%Y%m%d'), code)
                if not df.empty:
                    df.index = pd.to_datetime(df.index, format='%Y%m%d')
                    days.append(df.iloc[0])
            except:
                continue
        return pd.DataFrame(days).sort_index() if days else pd.DataFrame()

    def _fetch_naver_news(self, code: str) -> List[str]:
        """네이버 금융에서 뉴스 헤드라인 가져오기 (gpt_sentiment.py 기능)"""
        url = f"https://finance.naver.com/item/news_news.naver?code={code}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
        try:
            import requests
            from bs4 import BeautifulSoup
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            headlines = []
            for row in soup.select("table.type5 tbody tr"):
                a = row.select_one("td.title a.tit")
                date_tag = row.select_one("td.date")
                if not a or not date_tag:
                    continue
                try:
                    dt = datetime.strptime(date_tag.get_text(strip=True), "%Y.%m.%d %H:%M")
                except:
                    continue
                if dt < datetime.now() - timedelta(days=14):
                    continue
                headlines.append(a.get_text(strip=True))
            return headlines
        except:
            return []

    def _analyze_news_sentiment(self, headlines: List[str]) -> List[Dict]:
        """뉴스 감정분석 (gpt_sentiment.py 기능)"""
        results = []
        for headline in headlines[:5]:  # 상위 5개만 분석
            try:
                # GPT 감정분석
                prompt = f"""
                다음 뉴스 헤드라인을 분석하여 감정을 판단해주세요.
                
                뉴스: {headline}
                
                다음 중 하나로만 답변해주세요:
                - 긍정적: 좋은 소식, 성장, 상승, 개선 등의 내용
                - 부정적: 나쁜 소식, 하락, 위험, 문제 등의 내용
                - 중립적: 특별한 감정적 색채가 없는 내용
                """
                
                response = self.gpt_client.call_gpt([{"role": "user", "content": prompt}])
                
                sentiment = "중립적"
                if "긍정" in response:
                    sentiment = "긍정적"
                elif "부정" in response:
                    sentiment = "부정적"
                
                results.append({
                    '뉴스기사': headline,
                    '결과': sentiment,
                    '이유': response
                })
            except Exception as e:
                results.append({
                    '뉴스기사': headline,
                    '결과': '분석실패',
                    '이유': str(e)
                })
        return results

    def _generate_level_summary(self, headlines: List[str], level: int) -> str:
        """레벨별 요약 생성 (gpt_sentiment.py 기능)"""
        try:
            level_prompts = {
                1: "유치원/초등학생도 이해할 수 있는 아주 쉬운 말로 설명해주세요.",
                2: "중고등학생도 이해 가능한 쉬운 말로 설명해주세요.",
                3: "일반 성인도 이해할 수 있는 수준으로 설명해주세요.",
                4: "투자 경험이 있는 성인을 대상으로 한 전문적 설명을 해주세요.",
                5: "투자 전문가 수준의 고급 분석을 해주세요."
            }
            
            prompt = f"""
            다음 뉴스 헤드라인들을 {level_prompts.get(level, level_prompts[3])}
            
            뉴스 헤드라인:
            {chr(10).join(f"- {h}" for h in headlines[:5])}
            
            위 헤드라인들을 요약해주세요.
            """
            
            return self.gpt_client.call_gpt([{"role": "user", "content": prompt}])
        except Exception as e:
            return f"요약 생성 중 오류: {e}"

    def _display_etf_price_analysis(self, etf_name: str, level: int, mpti_type: str):
        """ETF 시세 분석 (어제종목요약.py 스타일)"""
        try:
            # ETF 코드 가져오기
            etf_code = self._get_etf_code(etf_name)
            
            # 최근 5거래일 데이터 가져오기
            df = self._get_last_n_trading_days(etf_code, 5)
            
            if not df.empty:
                # 어제 데이터
                yesterday_data = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
                current_data = df.iloc[-1]
                
                # 변동 계산
                change_amount = current_data['종가'] - yesterday_data['종가']
                change_percent = (change_amount / yesterday_data['종가']) * 100
                
                # 태그 생성
                tag = "Tech ETFs" if "반도체" in etf_name else "Theme ETFs"
                
                # 레벨별 요약 생성
                summary = self._generate_etf_summary(etf_name, change_percent, change_amount, level, mpti_type)
                
                # 표시
                st.markdown(f"""
                <div style="background: #f8f9fa; padding: 1rem; border-radius: 10px; margin: 1rem 0;">
                    <div style="display: flex; align-items: center; gap: 1rem;">
                        <div style="flex: 1;">
                            <h4 style="margin: 0; color: #1e3a8a;">{etf_name} ({etf_code})</h4>
                            <p style="margin: 0.5rem 0; font-size: 1.2rem; font-weight: bold;">
                                {current_data['종가']:,}원
                                <span style="color: {'#dc2626' if change_percent >= 0 else '#059669'}; margin-left: 0.5rem;">
                                    {'▲' if change_percent >= 0 else '▼'}{change_percent:.2f}% (+{change_amount:,}원)
                                </span>
                            </p>
                            <span style="background: #e5e7eb; padding: 0.2rem 0.5rem; border-radius: 5px; font-size: 0.8rem;">
                                {tag}
                            </span>
                        </div>
                    </div>
                    <p style="margin: 1rem 0 0 0; color: #374151; line-height: 1.5;">
                        {summary}
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            logger.error(f"ETF 시세 분석 실패: {e}")

    def _display_stock_price_analysis(self, stock_name: str, level: int, mpti_type: str):
        """개별 주식 시세 분석"""
        try:
            # 주식 코드 가져오기
            stock_code = self._get_stock_code(stock_name)
            
            # 최근 5거래일 데이터 가져오기
            df = self._get_last_n_trading_days(stock_code, 5)
            
            if not df.empty:
                # 어제 데이터
                yesterday_data = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
                current_data = df.iloc[-1]
                
                # 변동 계산
                change_amount = current_data['종가'] - yesterday_data['종가']
                change_percent = (change_amount / yesterday_data['종가']) * 100
                
                # 레벨별 요약 생성
                summary = self._generate_stock_summary(stock_name, change_percent, change_amount, level, mpti_type)
                
                # 표시
                st.markdown(f"""
                <div style="background: #f8f9fa; padding: 1rem; border-radius: 10px; margin: 1rem 0;">
                    <p style="margin: 0; color: #374151; line-height: 1.5;">
                        {summary}
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
        except Exception as e:
            logger.error(f"주식 시세 분석 실패: {e}")

    def _generate_etf_summary(self, etf_name: str, change_percent: float, change_amount: float, level: int, mpti_type: str) -> str:
        """ETF 요약 생성 (어제종목요약.py 스타일)"""
        try:
            today = datetime.now().strftime('%Y년 %m월 %d일')
            
            base_summary = ""
            if level == 1:
                base_summary = f"{today}, {etf_name}는 {change_percent:.2f}% {'올라서' if change_percent >= 0 else '내려가서'} {change_amount:,.0f}원으로 마감했어요. {'좋은 소식이 있어서' if change_percent >= 0 else '나쁜 소식이 있어서'} 사람들이 많이 {'샀어요' if change_percent >= 0 else '팔았어요'}."
            elif level == 2:
                base_summary = f"{today}, {etf_name}는 {change_percent:.2f}% {'상승하여' if change_percent >= 0 else '하락하여'} {change_amount:,.0f}원으로 마감했습니다. {'긍정적인 시장 전망과 함께' if change_percent >= 0 else '부정적인 시장 전망과 함께'} {'매수세가' if change_percent >= 0 else '매도세가'} 우세했습니다."
            elif level == 3:
                base_summary = f"{today}, {etf_name}는 {change_percent:.2f}% {'상승세를 보이며' if change_percent >= 0 else '하락세를 보이며'} {change_amount:,.0f}원으로 마감했습니다. {'기관투자자들의 매수세와 외국인 자금 유입이' if change_percent >= 0 else '기관투자자들의 매도세와 외국인 자금 유출이'} {'주요 상승 요인으로' if change_percent >= 0 else '주요 하락 요인으로'} 작용했습니다."
            elif level == 4:
                base_summary = f"{today}, {etf_name}는 {change_percent:.2f}% {'상승하여' if change_percent >= 0 else '하락하여'} {change_amount:,.0f}원으로 마감했습니다. {'기술적 지지선에서의 반등과 함께' if change_percent >= 0 else '기술적 저항선에서의 조정과 함께'} {'거래량 증가가 동반된' if change_percent >= 0 else '거래량 감소가 동반된'} {'강세 신호를' if change_percent >= 0 else '약세 신호를'} 보여주고 있습니다."
            else:  # level == 5
                base_summary = f"{today}, {etf_name}는 {change_percent:.2f}% {'상승세를 보이며' if change_percent >= 0 else '하락세를 보이며'} {change_amount:,.0f}원으로 마감했습니다. {'기술적 분석 관점에서 주요 지지선에서의 반등과 함께' if change_percent >= 0 else '기술적 분석 관점에서 주요 저항선에서의 조정과 함께'} {'거래량 증가와 함께 매수세가 강화되는' if change_percent >= 0 else '거래량 감소와 함께 매도세가 강화되는'} {'긍정적인 시장 신호를' if change_percent >= 0 else '부정적인 시장 신호를'} 보여주고 있습니다."
            
            # MPTI 스타일 적용
            return self._apply_mpti_style(base_summary, mpti_type)
                
        except Exception as e:
            logger.error(f"ETF 요약 생성 실패: {e}")
            return f"{etf_name}의 시세 정보를 분석할 수 없습니다."

    def _generate_stock_summary(self, stock_name: str, change_percent: float, change_amount: float, level: int, mpti_type: str) -> str:
        """주식 요약 생성"""
        try:
            today = datetime.now().strftime('%Y년 %m월 %d일')
            
            base_summary = ""
            if level == 1:
                base_summary = f"{today}, {stock_name}는 {change_percent:.2f}% {'올랐어요' if change_percent >= 0 else '내려갔어요'}. {'좋은 소식이 있어서' if change_percent >= 0 else '나쁜 소식이 있어서'} 주가가 {'올랐어요' if change_percent >= 0 else '내려갔어요'}."
            elif level == 2:
                base_summary = f"{today}, {stock_name}는 {change_percent:.2f}% {'상승하여' if change_percent >= 0 else '하락하여'} {change_amount:,.0f}원 {'상승했습니다' if change_percent >= 0 else '하락했습니다'}."
            elif level == 3:
                base_summary = f"{today}, {stock_name}는 {change_percent:.2f}% {'상승세를 보이며' if change_percent >= 0 else '하락세를 보이며'} {change_amount:,.0f}원 {'상승했습니다' if change_percent >= 0 else '하락했습니다'}. {'기관투자자들의 매수세가' if change_percent >= 0 else '기관투자자들의 매도세가'} 우세했습니다."
            elif level == 4:
                base_summary = f"{today}, {stock_name}는 {change_percent:.2f}% {'상승하여' if change_percent >= 0 else '하락하여'} {change_amount:,.0f}원 {'상승했습니다' if change_percent >= 0 else '하락했습니다'}. {'기술적 지지선에서의 반등과 함께' if change_percent >= 0 else '기술적 저항선에서의 조정과 함께'} {'거래량 증가가 동반된' if change_percent >= 0 else '거래량 감소가 동반된'} {'강세 신호를' if change_percent >= 0 else '약세 신호를'} 보여주고 있습니다."
            else:  # level == 5
                base_summary = f"{today}, {stock_name}는 {change_percent:.2f}% {'상승세를 보이며' if change_percent >= 0 else '하락세를 보이며'} {change_amount:,.0f}원 {'상승했습니다' if change_percent >= 0 else '하락했습니다'}. {'기술적 분석 관점에서 주요 지지선에서의 반등과 함께' if change_percent >= 0 else '기술적 분석 관점에서 주요 저항선에서의 조정과 함께'} {'거래량 증가와 함께 매수세가 강화되는' if change_percent >= 0 else '거래량 감소와 함께 매도세가 강화되는'} {'긍정적인 시장 신호를' if change_percent >= 0 else '부정적인 시장 신호를'} 보여주고 있습니다."
            
            # MPTI 스타일 적용
            return self._apply_mpti_style(base_summary, mpti_type)
                
        except Exception as e:
            logger.error(f"주식 요약 생성 실패: {e}")
            return f"{stock_name}의 시세 정보를 분석할 수 없습니다."

    def run(self):
        """애플리케이션 실행"""
        self.setup_ui()

def main():
    """메인 함수"""
    app = DailyReportApp()
    app.run()

if __name__ == "__main__":
    main() 