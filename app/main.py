"""
맞춤형 데일리 금융 리포트 애플리케이션
- 모듈화된 구조로 유지보수성 향상
- 사용자 레벨 및 WMTI 투자 성향별 맞춤 리포트
- 챗봇과 동일한 설정 및 추천 로직 사용
"""

import streamlit as st
import pandas as pd
import sys
import os
import logging
from typing import Dict, List
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 모듈 임포트
from modules.market_data import RealTimeMarketData
from modules.daily_briefing import DailyBriefing
from modules.recommendations import Recommendations
from modules.news_analyzer import NewsAnalyzer

# 임포트
try:
    from chatbot.config import Config
    from chatbot.utils import safe_read_csv_with_fallback
    from chatbot.gpt_client import GPTClient
    import openai
    CHATBOT_MODULES_AVAILABLE = True
except ImportError as e:
    CHATBOT_MODULES_AVAILABLE = False
    st.warning(f"일부 chatbot 모듈을 불러올 수 없습니다: {e}")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DailyReportApp:
    """데일리 리포트 애플리케이션"""
    
    def __init__(self):
        """초기화"""
        try:
            if CHATBOT_MODULES_AVAILABLE:
                self.config = Config()
                self.data = self._load_data()
                # GPT 클라이언트 초기화
                self.gpt_client = GPTClient()
            else:
                self.config = None
                self.data = {}
                self.gpt_client = None
            
            # 모듈 초기화
            self.market_data = RealTimeMarketData()
            self.daily_briefing = DailyBriefing()
            self.recommendations = Recommendations()
            self.news_analyzer = NewsAnalyzer()
            
        except Exception as e:
            logger.error(f"앱 초기화 실패: {e}")
            self.config = None
            self.data = {}
            self.gpt_client = None
    
    @st.cache_data
    def _load_data(_self) -> Dict[str, pd.DataFrame]:
        """데이터 로드"""
        try:
            if not CHATBOT_MODULES_AVAILABLE:
                return {}
            
            data = {}
            
            # ETF 캐시 데이터
            cache_path = _self.config.get_data_path('cache')
            if cache_path and os.path.exists(cache_path):
                data['etf_cache'] = safe_read_csv_with_fallback(cache_path)
                logger.info(f"ETF 캐시 데이터 로드: {len(data['etf_cache'])}행")
            else:
                logger.warning(f"ETF 캐시 파일을 찾을 수 없습니다: {cache_path}")
                data['etf_cache'] = pd.DataFrame()
            
            # 기타 데이터 파일들
            for key, path in _self.config.DATA_PATHS.items():
                if key != 'cache' and path and os.path.exists(path):
                    data[key] = safe_read_csv_with_fallback(path)
                    logger.info(f"{key} 데이터 로드: {len(data[key])}행")
                else:
                    data[key] = pd.DataFrame()
            
            logger.info(f"데이터 로드 완료: {len(data)}개 파일")
            return data
            
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
            return {}
    
    def _get_level_description(self, level: int) -> str:
        """레벨별 설명 반환 (챗봇과 동일)"""
        descriptions = {
            1: "초보자",
            2: "입문자", 
            3: "중급자",
            4: "중상급자",
            5: "전문가"
        }
        return descriptions.get(level, "알 수 없음")
    
    def _display_market_overview(self, level: int, mpti_type: str):
        """시장 개요 표시"""
        st.markdown(f'<div class="section-header">📈 시장 개요 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        try:
            # 실시간 시장 데이터 가져오기
            korean_market_data = self.market_data.get_korean_market_data()
            global_market_data = self.market_data.get_global_market_data()
            
            # 한국 시장 지표
            st.subheader("🇰🇷 한국 시장")
            col1, col2 = st.columns(2)
            
            with col1:
                if 'KOSPI' in korean_market_data:
                    kospi = korean_market_data['KOSPI']
                    st.metric(
                        "KOSPI",
                        f"{kospi['current_price']:,.1f}",
                        f"{kospi['change_percent']:+.2f}%"
                    )
            
            with col2:
                if 'KOSDAQ' in korean_market_data:
                    kosdaq = korean_market_data['KOSDAQ']
                    st.metric(
                        "KOSDAQ",
                        f"{kosdaq['current_price']:,.1f}",
                        f"{kosdaq['change_percent']:+.2f}%"
                    )
            
            # 글로벌 시장 지표
            st.subheader("🌍 글로벌 시장")
            col1, col2 = st.columns(2)
            
            with col1:
                if 'S&P 500' in global_market_data:
                    sp500 = global_market_data['S&P 500']
                    st.metric(
                        "S&P 500",
                        f"{sp500['current_price']:,.1f}",
                        f"{sp500['change_percent']:+.2f}%"
                    )
            
            with col2:
                if 'NASDAQ' in global_market_data:
                    nasdaq = global_market_data['NASDAQ']
                    st.metric(
                        "NASDAQ",
                        f"{nasdaq['current_price']:,.1f}",
                        f"{nasdaq['change_percent']:+.2f}%"
                    )
            
            # 레벨별 시장 해석
            self._display_market_interpretation(level, mpti_type, korean_market_data, global_market_data)
            
        except Exception as e:
            st.error(f"시장 개요 표시 중 오류: {e}")
            logger.error(f"시장 개요 표시 오류: {e}")
    
    def _display_market_interpretation(self, level: int, mpti_type: str, korean_market_data: Dict, global_market_data: Dict):
        """시장 해석 표시"""
        st.markdown("**📊 시장 해석**")
        
        try:
            # 실시간 데이터 기반 해석
            interpretation = self._generate_realtime_market_interpretation(level, mpti_type, korean_market_data, global_market_data)
            st.write(interpretation)
            
        except Exception as e:
            # 기본 해석으로 fallback
            basic_interpretation = self._generate_basic_market_interpretation(level, mpti_type)
            st.write(basic_interpretation)
    
    def _generate_realtime_market_interpretation(self, level: int, mpti_type: str, korean_market_data: Dict, global_market_data: Dict) -> str:
        """실시간 시장 해석 생성 """
        try:
            # GPT 클라이언트가 사용 가능한 경우
            if self.gpt_client and self.gpt_client.is_configured():
                # 사용자 프로필 생성
                user_profile = {
                    'level': level,
                    'investor_type': mpti_type
                }
                
                # 시장 데이터 준비
                market_data = {
                    'kospi_change': korean_market_data.get('KOSPI', {}).get('change_percent', 0),
                    'kosdaq_change': korean_market_data.get('KOSDAQ', {}).get('change_percent', 0),
                    'sp500_change': global_market_data.get('S&P 500', {}).get('change_percent', 0),
                    'nasdaq_change': global_market_data.get('NASDAQ', {}).get('change_percent', 0),
                    'date': pd.Timestamp.now().strftime('%Y-%m-%d')
                }
                
                # GPT를 통한 시장 해석 생성
                return self.gpt_client.generate_market_interpretation(market_data, user_profile)
            else:
                # GPT 클라이언트가 없는 경우 기본 해석으로 fallback
                return self._generate_fallback_market_interpretation(level, mpti_type, korean_market_data, global_market_data)
                
        except Exception as e:
            logger.error(f"GPT 시장 해석 생성 실패: {e}")
            return self._generate_fallback_market_interpretation(level, mpti_type, korean_market_data, global_market_data)
    
    def _generate_basic_market_interpretation(self, level: int, mpti_type: str) -> str:
        """기본 시장 해석 생성 """
        try:
            # GPT 클라이언트가 사용 가능한 경우
            if self.gpt_client and self.gpt_client.is_configured():
                # 사용자 프로필 생성
                user_profile = {
                    'level': level,
                    'investor_type': mpti_type
                }
                
                # 기본 시장 데이터
                market_data = {
                    'kospi_change': 0,
                    'kosdaq_change': 0,
                    'sp500_change': 0,
                    'nasdaq_change': 0,
                    'date': pd.Timestamp.now().strftime('%Y-%m-%d')
                }
                
                # GPT를 통한 기본 시장 해석 생성
                return self.gpt_client.generate_market_interpretation(market_data, user_profile)
            else:
                # GPT 클라이언트가 없는 경우 기본 해석으로 fallback
                return self._generate_fallback_basic_interpretation(level, mpti_type)
                
        except Exception as e:
            logger.error(f"GPT 기본 시장 해석 생성 실패: {e}")
            return self._generate_fallback_basic_interpretation(level, mpti_type)
    
    def _generate_fallback_market_interpretation(self, level: int, mpti_type: str, korean_market_data: Dict, global_market_data: Dict) -> str:
        """GPT API 실패 시 기본 시장 해석 생성"""
        try:
            # GPT 클라이언트의 fallback 메서드 사용
            if self.gpt_client:
                user_profile = {'level': level, 'investor_type': mpti_type}
                market_data = {
                    'kospi_change': korean_market_data.get('KOSPI', {}).get('change_percent', 0),
                    'kosdaq_change': korean_market_data.get('KOSDAQ', {}).get('change_percent', 0),
                    'sp500_change': global_market_data.get('S&P 500', {}).get('change_percent', 0),
                    'nasdaq_change': global_market_data.get('NASDAQ', {}).get('change_percent', 0),
                    'date': pd.Timestamp.now().strftime('%Y-%m-%d')
                }
                return self.gpt_client._generate_fallback_market_interpretation(market_data, user_profile)
            else:
                # GPT 클라이언트가 없는 경우 기본 텍스트
                kospi_change = korean_market_data.get('KOSPI', {}).get('change_percent', 0)
                kosdaq_change = korean_market_data.get('KOSDAQ', {}).get('change_percent', 0)
                return f"오늘 시장은 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. KOSPI {kospi_change}%, KOSDAQ {kosdaq_change}% 변동이 있었습니다."
        except Exception as e:
            logger.error(f"Fallback 시장 해석 생성 실패: {e}")
            return "시장 데이터를 분석 중입니다."
    
    def _generate_fallback_basic_interpretation(self, level: int, mpti_type: str) -> str:
        """GPT API 실패 시 기본 해석 생성"""
        try:
            # GPT 클라이언트의 fallback 메서드 사용
            if self.gpt_client:
                user_profile = {'level': level, 'investor_type': mpti_type}
                market_data = {
                    'kospi_change': 0,
                    'kosdaq_change': 0,
                    'sp500_change': 0,
                    'nasdaq_change': 0,
                    'date': pd.Timestamp.now().strftime('%Y-%m-%d')
                }
                return self.gpt_client._generate_fallback_market_interpretation(market_data, user_profile)
            else:
                # GPT 클라이언트가 없는 경우 기본 텍스트
                if level == 1:
                    return "시장 데이터를 확인하고 있어요. 잠시만 기다려주세요!"
                elif level == 2:
                    return "실시간 시장 데이터를 분석 중입니다."
                elif level == 3:
                    return "시장 상황을 종합적으로 분석하고 있습니다."
                elif level == 4:
                    return "시장 상황을 심화 분석하고 있습니다."
                else:
                    return "시장 상황을 전문적으로 분석하고 있습니다."
        except Exception as e:
            logger.error(f"Fallback 기본 해석 생성 실패: {e}")
            return "시장 데이터를 분석 중입니다."
    
    def generate_report(self, level: int, wmti_type: str, mpti_type: str, interest_stocks: str, show_portfolio: bool, show_price_comparison: bool):
        """리포트 생성"""
        params = {
            'level': level,
            'wmti_type': wmti_type,
            'mpti_type': mpti_type,
            'interest_stocks': interest_stocks,
            'show_portfolio': show_portfolio,
            'show_price_comparison': show_price_comparison
        }
        return self.generate_integrated_report(params)
    
    def generate_integrated_report(self, params: Dict):
        """통합 리포트 생성"""
        try:
            level = params['level']
            wmti_type = params['wmti_type']
            mpti_type = params['mpti_type']
            interest_stocks = params['interest_stocks']
            
            # 관심 종목 파싱
            if isinstance(interest_stocks, list):
                interest_list = interest_stocks
            else:
                interest_list = [stock.strip() for stock in interest_stocks.split(',') if stock.strip()]
            
            # 1. 시장 개요
            self._display_market_overview(level, mpti_type)
            
            st.markdown("---")
            
            # 2. 데일리 브리핑
            self.daily_briefing.display_daily_briefing(level, interest_list, mpti_type, self.data)
            
            st.markdown("---")
            
            # 3. 추천 종목 (챗봇과 동일한 로직)
            self.recommendations.set_data(self.data)  # 데이터 설정
            self.recommendations.display_recommendations(level, wmti_type, mpti_type, self.data)
            
        
            
        except Exception as e:
            st.error(f"리포트 생성 중 오류: {e}")
            logger.error(f"리포트 생성 오류: {e}")
    
    def run(self):
        """메인 애플리케이션 실행"""
        # 페이지 설정
        st.set_page_config(
            page_title="Just Fit It",
            page_icon="📊",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # CSS 스타일 
        st.markdown("""
        <style>
        .welcome-section {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 2px solid #f59e0b;
            border-radius: 15px;
            padding: 2rem;
            margin: 1rem 0;
            text-align: center;
        }
        .section-header {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            padding: 1rem;
            border-radius: 10px;
            margin: 1rem 0;
            font-size: 1.2rem;
            font-weight: bold;
        }
        .level-indicator {
            background: #92400e;
            padding: 0.2rem 0.5rem;
            border-radius: 5px;
            font-size: 0.9rem;
            margin-left: 0.5rem;
        }
        .kb-card {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 2px solid #f59e0b;
            border-radius: 15px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .kb-metric {
            background: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 0.5rem;
            margin: 0.5rem 0;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 사이드바 설정 (챗봇과 동일한 구조)
        with st.sidebar:
            st.markdown("## 🎯 투자자 프로필 설정")
            
            # GPT API 상태 표시
            if CHATBOT_MODULES_AVAILABLE and hasattr(self, 'gpt_client') and self.gpt_client is not None:
                if self.gpt_client.is_configured():
                    st.success("✅ GPT API가 설정되어 맞춤형 분석을 제공합니다.")
                else:
                    st.info("ℹ️ GPT API 키가 .env 파일에 설정되지 않았습니다. 기본 분석을 제공합니다.")
            elif CHATBOT_MODULES_AVAILABLE:
                st.info("ℹ️ GPT 클라이언트를 초기화할 수 없습니다. 기본 분석을 제공합니다.")
            
            # 현재 선택된 값 가져오기 (챗봇과 동일)
            current_profile = st.session_state.get('user_profile', {})
            current_level = current_profile.get('level', 1)
            current_wmti = current_profile.get('wmti_type', 'IBMC')
            current_mpti = current_profile.get('mpti_type', 'Fact')
            
            # 투자 레벨 선택 (챗봇과 동일)
            level = st.selectbox(
                "투자 경험 레벨",
                options=[1, 2, 3, 4, 5],
                index=current_level-1,  # 0-based index
                format_func=lambda x: f"Level {x} - {self._get_level_description(x)}",
                help="투자 경험 수준을 선택하세요."
            )
            
            # WMTI 투자자 유형 선택
            if CHATBOT_MODULES_AVAILABLE and self.config:
                wmti_options = list(self.config.WMTI_TYPE_DESCRIPTIONS.keys())
                wmti_type = st.selectbox(
                    "투자 성향 (WMTI)",
                    options=wmti_options,
                    index=wmti_options.index(current_wmti) if current_wmti in wmti_options else 0,
                    format_func=lambda x: f"{x} - {self.config.WMTI_TYPE_DESCRIPTIONS[x]['name']}",
                    help="투자 성향 유형을 선택하세요."
                )
            else:
                wmti_type = st.selectbox(
                    "투자 성향 (WMTI)",
                    options=['APWL', 'APML', 'APWC', 'APMC'],
                    help="투자 성향을 선택하세요"
                )
            
            # MPTI 투자 스타일 선택
            if CHATBOT_MODULES_AVAILABLE and self.config:
                mpti_options = list(self.config.MPTI_STYLES.keys())
                mpti_type = st.selectbox(
                    "설명 스타일 (MPTI)",
                    options=mpti_options,
                    index=mpti_options.index(current_mpti) if current_mpti in mpti_options else 0,
                    format_func=lambda x: f"{self.config.MPTI_STYLES[x]['name']} - {self.config.MPTI_STYLES[x]['description']}",
                    help="선호하는 설명 스타일을 선택하세요."
                )
            else:
                mpti_type = st.selectbox(
                    "설명 스타일 (MPTI)",
                    options=['보수형', '안정형', '균형형', '성장형', '공격형', '극공격형'],
                    help="설명 스타일을 선택하세요"
                )
            
            # 관심 종목 입력
            default_stocks = "KBSTAR 200, 반도체 ETF"
            interest_stocks = st.text_area(
                "관심 종목",
                value=default_stocks,
                help="분석하고 싶은 종목들을 쉼표로 구분하여 입력하세요 (예: KBSTAR 200, 반도체 ETF)",
                height=100
            )
            
    
            
            # 사용자 프로필 저장
            st.session_state.user_profile = {
                'level': level,
                'wmti_type': wmti_type,
                'mpti_type': mpti_type
            }
            
            # 리포트 생성 버튼
            if st.button("📊 리포트 생성", type="primary", use_container_width=True):
                st.session_state.generate_report = True
        
        # 메인 콘텐츠
        if not st.session_state.get('generate_report', False):
            # 초기 화면
            st.markdown("""
            <div class="welcome-section">
                <h1>Just Fit It</h1>
                <p style="font-size: 1.1rem; margin: 1rem 0;">
                    왼쪽 사이드바에서 투자자 프로필을 설정하고 리포트 생성 버튼을 클릭하세요!
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            # 리포트 생성
            self.generate_integrated_report({
                'level': level,
                'wmti_type': wmti_type,
                'mpti_type': mpti_type,
                'interest_stocks': interest_stocks,
                'show_portfolio': False,
                'show_price_comparison': False
            })

def main():
    """메인 함수"""
    app = DailyReportApp()
    app.run()

if __name__ == "__main__":
    main()
