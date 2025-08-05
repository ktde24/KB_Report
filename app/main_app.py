"""
ETF RAG 챗봇 메인 애플리케이션
- Streamlit 기반 웹 인터페이스
- ETF 분석, 추천, 비교 기능 제공
- 사용자 레벨 및 투자 성향별 맞춤 서비스
- 대화형 인터페이스 및 시각화 제공
"""

import streamlit as st
import pandas as pd
import sys
import os
import logging
import re
from typing import Dict, List, Optional

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 챗봇 모듈 임포트
from chatbot.etf_analysis import analyze_etf, plot_etf_bar, plot_etf_summary_bar
from chatbot.config import LEVEL_PROMPTS
from chatbot.gpt_client import GPTClient
from chatbot.recommendation_engine import ETFRecommendationEngine
from chatbot.etf_comparison import ETFComparison
from chatbot.config import Config
from chatbot.utils import (
    extract_etf_name_from_input, validate_user_profile,
    safe_read_csv_with_fallback
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ETFChatbotApp:
    """ETF 챗봇 애플리케이션 클래스"""
    
    def __init__(self):
        """애플리케이션 초기화"""
        self.config = Config()
        self.gpt_client = GPTClient()
        self.recommendation_engine = ETFRecommendationEngine()
        self.comparison_engine = ETFComparison()
        
        # 데이터 로딩 (캐싱 적용)
        self.data = self._load_data()
        
        logger.info("ETF 챗봇 애플리케이션 초기화 완료")

    @st.cache_data
    def _load_data(_self) -> Dict[str, pd.DataFrame]:
        """
        ETF 데이터 로딩 (Streamlit 캐싱 적용)
        
        Returns:
            데이터 딕셔너리
        """
        try:
            data = {}
            
            # 각 데이터 파일 로딩
            data_types = ['etf_info', 'etf_prices', 'etf_performance', 'etf_aum', 'etf_reference', 'etf_risk']
            
            for data_type in data_types:
                file_path = _self.config.get_data_path(data_type)
                if file_path and os.path.exists(file_path):
                    # 안전한 CSV 읽기 사용
                    data[data_type] = safe_read_csv_with_fallback(file_path)
                    logger.info(f"{data_type} 데이터 로딩 완료: {len(data[data_type])}행")
                else:
                    logger.warning(f"{data_type} 파일을 찾을 수 없습니다: {file_path}")
                    data[data_type] = pd.DataFrame()
            
            return data
            
        except Exception as e:
            logger.error(f"데이터 로딩 중 오류: {e}")
            return {}

    def setup_ui(self):
        """UI 설정"""
        st.set_page_config(
            page_title="ETF RAG 챗봇", 
            layout="wide",
            initial_sidebar_state="expanded"
        )
        st.title("💬 ETF RAG 챗봇")
        
        # 사이드바 설정
        self._setup_sidebar()

    def _setup_sidebar(self):
        """사이드바 설정"""
        st.sidebar.header("🛠️ 설정")
        
        # GPT API 키 입력
        gpt_api_key = st.sidebar.text_input(
            "OpenAI GPT API Key", 
            type="password",
            help="OpenAI GPT 서비스 이용을 위한 API 키를 입력하세요."
        )
        if gpt_api_key:
            st.session_state.gpt_api_key = gpt_api_key

        # 사용자 레벨 선택
        st.sidebar.subheader("👤 사용자 프로필")
        
        level_options = ["Level 1 (초보자)", "Level 2 (입문자)", "Level 3 (중급자)", "Level 4 (고급자)", "Level 5 (전문가)"]
        level_display = st.sidebar.selectbox(
            "투자 레벨",
            level_options,
            index=2,  # 기본값: Level 3 (중급자)
            help="투자 경험과 지식 수준을 선택하세요."
        )
        
        # 레벨 매핑
        level_map = {
            "Level 1 (초보자)": "level1",
            "Level 2 (입문자)": "level2", 
            "Level 3 (중급자)": "level3",
            "Level 4 (고급자)": "level4",
            "Level 5 (전문가)": "level5"
        }
        self.user_level = level_map[level_display]

        # WMTI 투자자 유형 선택 (추천용)
        wmti_type_display = st.sidebar.selectbox(
            "WMTI 투자자 유형 (추천용)",
            list(self.config.WMTI_TYPE_DESCRIPTIONS.keys()),
            format_func=lambda x: f"{x}: {self.config.get_wmti_type_description(x)}",
            index=4,  # ABML 기본값 (외향형+탐험가형+집중형+자유형)
            help="WMTI(KB 투자자 유형) 기반 추천 로직을 선택하세요."
        )
        self.user_wmti_type = wmti_type_display
        
        # MPTI 투자자 유형 선택 (설명용)
        investor_type_display = st.sidebar.selectbox(
            "MPTI 투자자 유형 (설명용)",
            list(self.config.INVESTOR_TYPE_DESCRIPTIONS.keys()),
            format_func=lambda x: f"{x}: {self.config.get_investor_type_description(x)}",
            index=0,
            help="MPTI(마블콘텐츠선호지표) 기반 설명 스타일을 선택하세요."
        )
        self.user_investor_type = investor_type_display

    def run(self):
        """메인 애플리케이션 실행"""
        try:
            self.setup_ui()
            
            # 채팅 히스토리 초기화
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            # 채팅 스타일 설정
            self._apply_chat_styles()
            
            # 사용자 입력 처리
            self._handle_user_input()
            
            # 채팅 히스토리 표시
            self._display_chat_history()
            
        except Exception as e:
            logger.error(f"애플리케이션 오류: {e}")
            st.error(f"애플리케이션 오류가 발생했습니다: {e}")

    def _apply_chat_styles(self):
        """채팅 UI 스타일 적용"""
        st.markdown(
            """
            <style>
            .user-msg {
                background-color: #e1ffc7;
                border-radius: 10px;
                padding: 8px 12px;
                margin: 4px 0;
                text-align: right;
            }
            .bot-msg {
                background-color: #f1f0f0;
                border-radius: 10px;
                padding: 8px 12px;
                margin: 4px 0;
                text-align: left;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

    def _handle_user_input(self):
        """사용자 입력 처리"""
        user_input = st.text_input(
            "질문을 입력하세요! 💭",
            key="user_input",
            placeholder="예: 반도체 ETF 5개 추천해줘"
        )
        
        if user_input:
            # 사용자 프로필 생성
            user_profile = {
                "level": self.config.get_level_number(self.user_level),
                "investor_type": self.user_investor_type,  # MPTI (설명용)
                "wmti_type": self.user_wmti_type  # WMTI (추천용)
            }
            
            # 요청 유형 분류 및 처리
            response = self._process_user_request(user_input, user_profile)
            
            # 채팅 히스토리에 추가
            st.session_state.chat_history.append(("user", user_input))
            st.session_state.chat_history.append(("bot", response))

    def _process_user_request(self, user_input: str, user_profile: Dict) -> str:
        """
        사용자 요청 처리
        
        Args:
            user_input: 사용자 입력
            user_profile: 사용자 프로필
        
        Returns:
            처리 결과 응답
        """
        # 요청 유형 키워드 정의
        recommend_keywords = ["추천", "추천해줘", "추천해주세요", "추천해주", "추천해"]
        compare_keywords = ["비교", "비교해줘", "비교해주세요", "vs", "대", "차이", "어떤게", "어느게"]
        
        is_recommendation = any(keyword in user_input for keyword in recommend_keywords)
        is_comparison = any(keyword in user_input for keyword in compare_keywords)
        
        try:
            if is_recommendation:
                return self._handle_recommendation_request(user_input, user_profile)
            elif is_comparison:
                return self._handle_comparison_request(user_input, user_profile)
            else:
                return self._handle_analysis_request(user_input, user_profile)
                
        except Exception as e:
            logger.error(f"요청 처리 중 오류: {e}")
            return f"요청 처리 중 오류가 발생했습니다: {str(e)}"

    def _handle_recommendation_request(self, user_input: str, user_profile: Dict) -> str:
        """추천 요청 처리"""
        try:
            # 추천 개수 추출
            number_match = re.search(r'(\d+)개', user_input)
            top_n = int(number_match.group(1)) if number_match else 5
            
            # 카테고리 키워드 추출
            category_keyword = self._extract_category_keyword(user_input)
            
            # 캐시 데이터 로드
            cache_path = self.config.get_data_path('cache')
            if not os.path.exists(cache_path):
                return "추천 캐시 데이터를 찾을 수 없습니다. 먼저 캐시를 생성해주세요."
            
            cache_df = pd.read_csv(cache_path, encoding='utf-8-sig')
            
            # ETF 추천 실행
            recommendations = self.recommendation_engine.fast_recommend_etfs(
                user_profile, cache_df, category_keyword=category_keyword, top_n=top_n
            )
            
            # 안내 메시지만 있을 때는 LLM 호출 없이 안내 문구만 출력
            if recommendations and isinstance(recommendations[0], dict) and '안내' in recommendations[0]:
                return recommendations[0]['안내']
            
            if recommendations:
                # 추천 설명 생성
                explanation_prompt = self.recommendation_engine.generate_recommendation_explanation(
                    recommendations, user_profile, category_keyword
                )
                return self.gpt_client.generate_response(explanation_prompt)
            else:
                return f"'{category_keyword}' 조건에 맞는 ETF를 찾을 수 없습니다. 다른 키워드로 다시 시도해보세요."
                
        except Exception as e:
            logger.error(f"추천 요청 처리 오류: {e}")
            return f"추천 처리 중 오류가 발생했습니다: {str(e)}"

    def _handle_comparison_request(self, user_input: str, user_profile: Dict) -> str:
        """비교 요청 처리"""
        try:
            # ETF명 추출
            etf_names = self._extract_etf_names(user_input)
            
            if len(etf_names) < 2:
                return "비교할 ETF를 2개 이상 명확히 입력해주세요. (예: 'KODEX 200 vs TIGER 200 비교해줘')"
            
            # ETF 비교 실행
            comparison_result = self.comparison_engine.compare_etfs(
                etf_names, user_profile, 
                self.data['etf_prices'], self.data['etf_info']
            )
            
            # 비교 결과가 없거나 에러가 있으면 안내 문구만 출력
            if not comparison_result or 'error' in comparison_result or comparison_result.get('etf_count', 0) == 0:
                if 'error' in comparison_result:
                    return comparison_result['error']
                return '비교 가능한 ETF가 없습니다. ETF명을 다시 확인해 주세요.'
            
            # LLM 응답 생성
            level_num = user_profile.get('level', 3)  # 기본값: Level 3 (중급자)
            if not isinstance(level_num, int):
                try:
                    level_num = int(str(level_num).replace('level', '').replace('Level', '').replace(' ', '').replace('(중급자)', '').replace('(초보자)', '').replace('(입문자)', '').replace('(고급자)', '').replace('(전문가)', ''))
                except Exception:
                    level_num = 3
            level_prompt = LEVEL_PROMPTS.get(level_num, "")
            comparison_prompt = f"""{level_prompt}
아래 ETF 비교 분석 결과를 바탕으로 사용자에게 맞춤형 분석과 추천사항을 제공해주세요.

{comparison_result['recommendations']}

다음 내용을 포함해서 설명해주세요:
1. 사용자 프로필(레벨, 투자자 유형)에 가장 적합한 ETF를 1개만 명확히 골라 추천하고, 그 이유를 구체적으로 설명하세요.
2. 두 ETF의 장단점, 투자 시 주의사항, 구체적인 투자 전략을 비교해 설명하세요.
3. 데이터(점수, 위험, 수익률 등)에 근거한 판단을 반드시 포함하세요.
4. 각 ETF의 순위(1위, 2위 등)를 명확히 표시하세요.

사용자의 레벨에 맞는 어투와 깊이로 작성하고, 데이터 기반 근거를 포함해주세요.
"""
            response = self.gpt_client.generate_response(comparison_prompt)
            self._display_comparison_visualizations(comparison_result)
            return response
        except Exception as e:
            logger.error(f"비교 요청 처리 오류: {e}")
            return f"비교 처리 중 오류가 발생했습니다: {str(e)}"

    def _handle_analysis_request(self, user_input: str, user_profile: Dict) -> str:
        """분석 요청 처리"""
        try:
            # ETF명 추출
            etf_name = extract_etf_name_from_input(user_input.strip(), self.data['etf_info'])
            
            # ETF 분석 실행
            etf_info = analyze_etf(
                etf_name, user_profile,
                self.data['etf_prices'], self.data['etf_info'], 
                self.data['etf_performance'], self.data['etf_aum'], 
                self.data['etf_reference'], self.data['etf_risk']
            )
            
            # LLM 응답 생성
            response = self.gpt_client.generate_etf_analysis(etf_info, user_profile)
            
            # 시각화 표시 
            self._display_etf_visualizations(etf_info)
            
            return response
            
        except Exception as e:
            logger.error(f"분석 요청 처리 오류: {e}")
            return f"분석 처리 중 오류가 발생했습니다: {str(e)}"

    def _extract_category_keyword(self, user_input: str) -> str:
        """
        사용자 입력에서 카테고리 키워드 추출
        
        Args:
            user_input: 사용자 입력 텍스트
        
        Returns:
            추출된 카테고리 키워드 또는 빈 문자열
        """
        # ETF 관련 주요 키워드 정의
        keywords = [
            # 기술 관련
            '반도체', 'AI', '인공지능', '메타버스', '블록체인', '클라우드',
            # 바이오/헬스케어
            '바이오', '생명공학', '헬스케어', '제약', '의료',
            # 금융
            '금융', '은행', '보험', '증권',
            # 에너지/자원
            '에너지', '태양광', '풍력', '원자재', '원유', '가스',
            # 자동차/교통
            '자동차', '전기차', '배터리', '모빌리티',
            # 부동산
            '부동산', 'REITs', '리츠',
            # 채권
            '채권', '국채', '기업채', '회사채',
            # 원자재/통화
            '금', '은', '달러', '엔화', '유로', '위안',
            # 지역
            '중국', '미국', '일본', '유럽', '신흥국', '한국',
            # 투자 스타일
            '배당', '성장', '가치', '소형주', '대형주', '중형주'
        ]
        
        user_input_lower = user_input.lower()
        for keyword in keywords:
            if keyword in user_input_lower:
                return keyword
        
        # ETF 패턴 매칭
        import re
        etf_match = re.search(r'(.+?)\s*ETF', user_input)
        if etf_match:
            return etf_match.group(1).strip()
        
        return ""

    def _extract_etf_names(self, user_input: str) -> List[str]:
        """
        사용자 입력에서 ETF명 추출
        
        Args:
            user_input: 사용자 입력 텍스트
        
        Returns:
            추출된 ETF명 리스트 (최대 6개)
        """
        compare_keywords = ["비교", "비교해줘", "비교해주세요", "vs", "대", "차이", "어떤게", "어느게"]
        
        # 구분자로 분리 시도
        separators = [',', ' vs ', ' 대 ', ' VS ', '랑', ' 랑 ', ' 와 ', ' 과 ', '/']
        
        for sep in separators:
            if sep in user_input:
                parts = user_input.split(sep)
                etf_names = []
                
                for part in parts:
                    clean_name = part.strip()
                    # 비교 키워드 제거
                    for keyword in compare_keywords:
                        clean_name = clean_name.replace(keyword, '').strip()
                    
                    if clean_name and len(clean_name) > 2:
                        etf_names.append(clean_name)
                
                if len(etf_names) >= 2:
                    return etf_names[:6]  # 최대 6개
        
        # 구분자가 없으면 키워드 기반 추출
        clean_text = user_input
        for keyword in compare_keywords:
            clean_text = clean_text.replace(keyword, ' ')
        
        words = [w.strip() for w in clean_text.split() if len(w.strip()) > 2]
        etf_candidates = []
        
        # 각 단어로 ETF 검색
        for word in words:
            if not self.data['etf_info'].empty:
                matches = self.data['etf_info'][
                    self.data['etf_info']['종목명'].str.contains(word, case=False, na=False)
                ]
                for _, match in matches.iterrows():
                    etf_name = match['종목명']
                    if etf_name not in etf_candidates:
                        etf_candidates.append(etf_name)
        
        return etf_candidates[:6]  # 최대 6개

    def _display_comparison_visualizations(self, comparison_result: Dict):
        """비교 시각화 표시"""
        if 'visualizations' not in comparison_result:
            return
        
        st.subheader("상세 비교 분석")
        
        # 비교 테이블
        if 'comparison_table' in comparison_result:
            st.subheader("비교 테이블")
            st.dataframe(comparison_result['comparison_table'], use_container_width=True)
        
        # 시각화
        visualizations = comparison_result['visualizations']
        
        col1, col2 = st.columns(2)
        with col1:
            if 'score_bar' in visualizations:
                st.plotly_chart(visualizations['score_bar'], use_container_width=True)
        with col2:
            if 'risk_return_scatter' in visualizations:
                st.plotly_chart(visualizations['risk_return_scatter'], use_container_width=True)
        
        if 'radar_chart' in visualizations:
            st.plotly_chart(visualizations['radar_chart'], use_container_width=True)
        
        col3, col4 = st.columns(2)
        with col3:
            if 'returns_comparison' in visualizations:
                st.plotly_chart(visualizations['returns_comparison'], use_container_width=True)
        with col4:
            if 'cost_performance' in visualizations:
                st.plotly_chart(visualizations['cost_performance'], use_container_width=True)
        
        if 'heatmap' in visualizations:
            st.plotly_chart(visualizations['heatmap'], use_container_width=True)

    def _display_etf_visualizations(self, etf_info: Dict):
        """ETF 분석 시각화 표시"""
        try:
            # 시세 분석 차트
            if '시세분석' in etf_info:
                market_data = etf_info['시세분석']
                if not all(v is None for v in market_data.values()):
                    st.plotly_chart(plot_etf_bar(etf_info), use_container_width=True)
            
            # 공식 데이터 차트
            st.plotly_chart(plot_etf_summary_bar(etf_info), use_container_width=True)
            
        except Exception as e:
            logger.warning(f"시각화 표시 중 오류: {e}")

    def _display_chat_history(self):
        """채팅 히스토리 표시"""
        for role, msg in st.session_state.chat_history:
            if role == "user":
                st.markdown(f'<div class="user-msg">{msg}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="bot-msg">{msg}</div>', unsafe_allow_html=True)


def main():
    """메인 함수"""
    try:
        app = ETFChatbotApp()
        app.run()
    except Exception as e:
        st.error(f"애플리케이션 시작 중 오류: {e}")
        logger.error(f"애플리케이션 시작 오류: {e}")


if __name__ == "__main__":
    main()




