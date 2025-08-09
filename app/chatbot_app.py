"""
ETF 챗봇 애플리케이션
- 개인화된 ETF 추천 및 분석
- MPTI 스타일 기반 맞춤 설명
"""

import streamlit as st
import pandas as pd
import sys
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime
import re # Added missing import for re
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 챗봇 모듈 임포트
from chatbot.etf_analysis import analyze_etf, plot_etf_bar, plot_etf_summary_bar
from chatbot.gpt_client import GPTClient
from chatbot.recommendation_engine import ETFRecommendationEngine
from chatbot.etf_comparison import ETFComparison
from chatbot.config import Config
from chatbot.utils import safe_read_csv_with_fallback, extract_etf_name_from_input

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KBChatbotApp:
    """챗봇 애플리케이션"""
    
    def __init__(self):
        """애플리케이션 초기화"""
        # .env 파일 로드
        load_dotenv()
        
        self.config = Config()
        self.gpt_client = GPTClient()
        self.recommendation_engine = ETFRecommendationEngine()
        self.comparison_engine = ETFComparison()
        
        # 데이터 로딩
        self.data = self._load_data()
        
        logger.info("KB 챗봇 애플리케이션 초기화 완료")

    @st.cache_data
    def _load_data(_self) -> Dict[str, pd.DataFrame]:
        """ETF 데이터 로딩"""
        try:
            data = {}
            data_types = ['etf_info', 'etf_prices', 'etf_performance', 'etf_aum', 'etf_reference', 'etf_risk']
            
            for data_type in data_types:
                file_path = _self.config.get_data_path(data_type)
                if file_path and os.path.exists(file_path):
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
            page_title="챗봇", 
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        
        self._apply_kb_styles()
        
        # 헤더 표시
        self._display_header()
        
        # 사이드바 설정
        self._setup_sidebar()

    def _apply_kb_styles(self):
        """CSS 적용"""
        kb_css = """
        <style>
        /* KB 메인 컨테이너 */
        .main {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 50%, #fbbf24 100%);
            min-height: 100vh;
        }
        
        /* KB 헤더 */
        .kb-header {
            background: linear-gradient(90deg, #fbbf24 0%, #fde68a 100%);
            padding: 2rem;
            border-radius: 20px;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(251, 191, 36, 0.3);
            position: relative;
            overflow: hidden;
        }
        
        .kb-header::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
            animation: shimmer 3s infinite;
        }
        
        @keyframes shimmer {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        
        .kb-logo {
            font-size: 2.5rem;
            font-weight: 700;
            color: white;
            margin-bottom: 0.5rem;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .kb-subtitle {
            font-size: 1.2rem;
            color: rgba(255,255,255,0.9);
            font-weight: 400;
        }
        
        /* 챗봇 컨테이너 */
        .chat-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 2rem;
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        /* 메시지 스타일 */
        .message {
            margin: 1rem 0;
            padding: 1.5rem;
            border-radius: 15px;
            animation: fadeIn 0.5s ease-in;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .user-message {
            background: linear-gradient(135deg, #fbbf24 0%, #fde68a 100%);
            color: #92400e;
            margin-left: 2rem;
            box-shadow: 0 8px 25px rgba(251, 191, 36, 0.3);
        }
        
        .bot-message {
            background: rgba(255, 255, 255, 0.9);
            border: 2px solid #e5e7eb;
            margin-right: 2rem;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }
        
        .bot-message:hover {
            border-color: #fbbf24;
            transform: translateY(-2px);
            transition: all 0.3s ease;
        }
        
        /* 입력 필드 */
        .stTextInput > div > div > input {
            background: rgba(255, 255, 255, 0.95);
            border: 2px solid #e5e7eb;
            border-radius: 15px;
            padding: 1rem;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #fbbf24;
            box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.1);
        }
        
        /* 버튼 스타일 */
        .stButton > button {
            background: linear-gradient(135deg, #fbbf24 0%, #fde68a 100%);
            color: #92400e;
            border: none;
            border-radius: 15px;
            padding: 0.75rem 2rem;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 8px 25px rgba(251, 191, 36, 0.3);
        }
        
        .stButton > button:hover {
            background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
            transform: translateY(-3px);
            box-shadow: 0 12px 35px rgba(251, 191, 36, 0.4);
        }
        
        /* 사이드바 */
        .stSidebar {
            background: rgba(255, 255, 255, 0.98);
            backdrop-filter: blur(25px);
            border-right: 2px solid rgba(255, 255, 255, 0.3);
        }
        
        /* 선택박스 */
        .stSelectbox > div > div {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            border: 2px solid #e5e7eb;
            transition: all 0.3s ease;
        }
        
        .stSelectbox > div > div:hover {
            border-color: #fbbf24;
            box-shadow: 0 6px 20px rgba(251, 191, 36, 0.25);
        }
        
        /* 카드 스타일 */
        .kb-card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(20px);
            border-radius: 15px;
            padding: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
        }
        
        .kb-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
        }
        
        /* 로딩 애니메이션 */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(251, 191, 36, 0.3);
            border-radius: 50%;
            border-top-color: #fbbf24;
            animation: spin 1s ease-in-out infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* 스크롤바 스타일 */
        ::-webkit-scrollbar {
            width: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(135deg, #fbbf24 0%, #fde68a 100%);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(135deg, #f59e0b 0%, #fbbf24 100%);
        }
        </style>
        """
        st.markdown(kb_css, unsafe_allow_html=True)

    def _display_header(self):
        """KB 스타일 헤더 표시"""
        st.markdown("""
        <div class="kb-header">
            <div class="kb-logo">🏦 챗봇</div>
            <div class="kb-subtitle">개인화된 투자 상담 서비스</div>
        </div>
        """, unsafe_allow_html=True)

    def _setup_sidebar(self):
        """사이드바 설정"""
        # OpenAI API 키는 .env에서 자동 로드
        openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # 사용자 프로필 설정
        st.sidebar.markdown("### 👤 사용자 프로필")
        
        # 현재 선택된 값 가져오기
        current_profile = st.session_state.get('user_profile', {})
        current_level = current_profile.get('level', 1)
        current_wmti = current_profile.get('wmti_type', 'IBMC')
        current_mpti = current_profile.get('mpti_type', 'Fact')
        
        user_level = st.sidebar.selectbox(
            "투자 경험 레벨",
            options=[1, 2, 3, 4, 5],
            index=current_level-1,  # 0-based index
            format_func=lambda x: f"Level {x} - {self._get_level_description(x)}",
            help="투자 경험 수준을 선택하세요."
        )
        
        wmti_type = st.sidebar.selectbox(
            "투자 성향 (WMTI)",
            options=list(Config.WMTI_TYPE_DESCRIPTIONS.keys()),
            index=list(Config.WMTI_TYPE_DESCRIPTIONS.keys()).index(current_wmti) if current_wmti in Config.WMTI_TYPE_DESCRIPTIONS else 0,
            format_func=lambda x: f"{x} - {Config.WMTI_TYPE_DESCRIPTIONS[x]['name']}",
            help="투자 성향 유형을 선택하세요."
        )
        
        mpti_type = st.sidebar.selectbox(
            "설명 스타일 (MPTI)",
            options=list(Config.MPTI_STYLES.keys()),
            index=list(Config.MPTI_STYLES.keys()).index(current_mpti) if current_mpti in Config.MPTI_STYLES else 0,
            format_func=lambda x: f"{Config.MPTI_STYLES[x]['name']} - {Config.MPTI_STYLES[x]['description']}",
            help="선호하는 설명 스타일을 선택하세요."
        )
        
        # 디버깅 정보 표시 (개발 중에만)
        st.sidebar.markdown("---")
        st.sidebar.markdown("**현재 설정값:**")
        st.sidebar.markdown(f"- 레벨: {user_level}")
        st.sidebar.markdown(f"- WMTI: {wmti_type}")
        st.sidebar.markdown(f"- MPTI: {mpti_type}")
        
        # 사용자 프로필 저장
        st.session_state.user_profile = {
            'level': user_level,
            'wmti_type': wmti_type,
            'mpti_type': mpti_type
        }

    def _get_level_description(self, level: int) -> str:
        """레벨별 설명 반환"""
        descriptions = {
            1: "초보자",
            2: "입문자", 
            3: "중급자",
            4: "중상급자",
            5: "전문가"
        }
        return descriptions.get(level, "알 수 없음")

    def run(self):
        """챗봇 실행"""
        # 챗 히스토리 초기화
        if "messages" not in st.session_state:
            st.session_state.messages = []
        
        # 현재 사용자 프로필 가져오기
        current_profile = st.session_state.get('user_profile', {})
        
        # 환영 메시지 생성 또는 업데이트
        if not st.session_state.messages:
            # 첫 실행 시 환영 메시지 생성
            welcome_message = self._generate_welcome_message()
            st.session_state.messages.append({"role": "assistant", "content": welcome_message})
        else:
            # 기존 메시지가 있으면 첫 번째 메시지(환영 메시지) 업데이트
            welcome_message = self._generate_welcome_message()
            st.session_state.messages[0] = {"role": "assistant", "content": welcome_message}
        
        # 챗봇 컨테이너
        with st.container():
            st.markdown('<div class="chat-container">', unsafe_allow_html=True)
            
            # 메시지 히스토리 표시
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    # HTML 태그 제거 후 표시
                    clean_content = message["content"].replace('</div>', '').replace('<div>', '')
                    st.markdown(clean_content)
            
            # 사용자 입력 처리
            if prompt := st.chat_input("궁금한 점을 물어보세요!"):
                # 사용자 메시지 추가
                st.session_state.messages.append({"role": "user", "content": prompt})
                
                # 챗봇 응답 생성
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    with st.spinner("🤔 분석 중..."):
                        response = self._generate_response(prompt)
                        # HTML 태그 제거 후 표시
                        clean_response = response.replace('</div>', '').replace('<div>', '')
                        st.markdown(clean_response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
            
            st.markdown('</div>', unsafe_allow_html=True)

    def _generate_welcome_message(self) -> str:
        """환영 메시지 생성"""
        user_profile = st.session_state.get('user_profile', {})
        level = user_profile.get('level', 1)
        wmti_type = user_profile.get('wmti_type', 'IBMC')
        mpti_type = user_profile.get('mpti_type', 'Fact')
        
        welcome = f"""
        안녕하세요! 🏦 KB 챗봇입니다.
        
        현재 설정:
        - 투자 경험: Level {level} ({self._get_level_description(level)})
        - 투자 성향: {Config.WMTI_TYPE_DESCRIPTIONS[wmti_type]['name']}
        - 설명 스타일: {Config.MPTI_STYLES[mpti_type]['name']}
        
        도움을 드릴 수 있는 것들:
        📊 ETF 추천 및 분석
        📈 시장 상황 분석
        🔍 ETF 비교 분석
        💡 투자 전략 제안
        
        무엇을 도와드릴까요?
        """
        
        return self._apply_mpti_style(welcome, mpti_type)

    def _generate_response(self, prompt: str) -> str:
        """사용자 입력에 대한 응답 생성"""
        try:
            user_profile = st.session_state.get('user_profile', {})
            
            # API 키 확인 (.env에서 자동 로드)
            openai_api_key = os.getenv('OPENAI_API_KEY')
            if not openai_api_key:
                return "⚠️ OpenAI API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 추가해주세요."
            
            # GPT 클라이언트가 설정되었는지 확인
            if not self.gpt_client.is_configured():
                return "⚠️ GPT API가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 추가해주세요."
            
            # 사용자 입력 분석 및 응답 생성
            response = self._process_user_request(prompt, user_profile)
            
            # MPTI 스타일 적용
            mpti_type = user_profile.get('mpti_type', 'Fact')
            styled_response = self._apply_mpti_style(response, mpti_type)
            
            # "다양한 관점" 문구 제거
            styled_response = styled_response.replace("다양한 관점에서 분석한 결과입니다.", "")
            styled_response = styled_response.replace("다양한 관점에서 분석한 결과입니다", "")
            
            return styled_response
            
        except Exception as e:
            logger.error(f"응답 생성 중 오류: {e}")
            return f"죄송합니다. 오류가 발생했습니다: {str(e)}"

    def _process_user_request(self, prompt: str, user_profile: Dict) -> str:
        """사용자 요청 처리"""
        prompt_lower = prompt.lower()
        
        # 추천 요청
        if any(keyword in prompt_lower for keyword in ['추천', '추천해', '추천해주', '추천해줘']):
            return self._handle_recommendation_request(prompt, user_profile)
        
        # 비교 요청
        elif any(keyword in prompt_lower for keyword in ['비교', '비교해', '비교해주', '비교해줘']):
            return self._handle_comparison_request(prompt, user_profile)
        
        # 분석 요청
        elif any(keyword in prompt_lower for keyword in ['분석', '분석해', '분석해주', '분석해줘']):
            return self._handle_analysis_request(prompt, user_profile)
        
        # 시장 상황
        elif any(keyword in prompt_lower for keyword in ['시장', '상황', '동향', '전망']):
            return self._handle_market_request(prompt, user_profile)
        
        # 일반 질문
        else:
            return self._handle_general_request(prompt, user_profile)

    def _handle_recommendation_request(self, prompt: str, user_profile: Dict) -> str:
        """ETF 추천 요청 처리"""
        try:
            # 추천 개수 추출
            number_match = re.search(r'(\d+)개', prompt)
            top_n = int(number_match.group(1)) if number_match else 5
            
            # 카테고리 키워드 추출
            category_keyword = self._extract_category_keyword(prompt)
            
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
                # 개인화된 추천 설명 생성
                level = user_profile.get('level', 3)
                wmti_type = user_profile.get('wmti_type', 'IBMC')
                mpti_type = user_profile.get('mpti_type', 'Fact')
                
                level_prompt = Config.LEVEL_PROMPTS.get(level, "")
                wmti_desc = Config.WMTI_TYPE_DESCRIPTIONS[wmti_type]['name']
                mpti_style = Config.MPTI_STYLES[mpti_type]
                
                personalized_prompt = f"""{level_prompt}

사용자 프로필:
- 투자 경험: Level {level} ({self._get_level_description(level)})
- 투자 성향: {wmti_desc}
- 설명 스타일: {mpti_style['name']} - {mpti_style['prompt']}

다음 ETF 추천 결과를 사용자 프로필에 맞춰 설명해주세요:

{recommendations}

**중요: 반드시 모든 추천 ETF를 개별적으로 설명해주세요!**

설명 요구사항:
1. 사용자 레벨에 맞는 어투와 깊이로 작성
2. 투자 성향({wmti_desc})에 맞는 관점에서 분석
3. {mpti_style['name']} 스타일로 설명 ({mpti_style['description']})
4. 모든 추천 ETF를 개별적으로 설명 (1개씩 번호를 매겨서: 1. ETF명, 2. ETF명, 3. ETF명)
5. 각 ETF의 구체적인 근거를 반드시 포함:
   - 수익률 점수, 위험조정수익률 점수, 비용효율성 점수 등 구체적 수치
   - 총보수, 변동성, 거래량 등 실제 데이터
   - 왜 이 ETF가 추천되는지 명확한 이유 제시
6. 사용자 레벨에 맞는 실전 투자 팁과 주의사항 포함

반드시 모든 ETF를 빠짐없이 설명해주세요!

사용자의 투자 성향과 설명 스타일에 맞춰 개인화된 추천을 제공해주세요."""
                
                return self.gpt_client.generate_response(personalized_prompt)
            else:
                return f"'{category_keyword}' 조건에 맞는 ETF를 찾을 수 없습니다. 다른 키워드로 다시 시도해보세요."
                
        except Exception as e:
            logger.error(f"추천 요청 처리 중 오류: {e}")
            return "추천 생성 중 오류가 발생했습니다."

    def _handle_comparison_request(self, prompt: str, user_profile: Dict) -> str:
        """ETF 비교 요청 처리"""
        try:
            # ETF 이름 추출
            etf_names = self._extract_etf_names(prompt)
            
            if len(etf_names) < 2:
                return "비교할 ETF를 2개 이상 입력해주세요. (예: TIGER 200과 KODEX 200을 비교해주세요)"
            
            # 비교 분석
            comparison_result = self.comparison_engine.compare_etfs(
                etf_names[:3], user_profile, 
                self.data['etf_prices'], self.data['etf_info']
            )
            
            # 비교 결과가 없거나 에러가 있으면 안내 문구만 출력
            if not comparison_result or 'error' in comparison_result or comparison_result.get('etf_count', 0) == 0:
                if 'error' in comparison_result:
                    return comparison_result['error']
                return '비교 가능한 ETF가 없습니다. ETF명을 다시 확인해 주세요.'
            
            # 시각화 표시
            self._display_comparison_visualizations(comparison_result)
            
            # 개인화된 비교 분석 응답 생성
            level = user_profile.get('level', 1)
            wmti_type = user_profile.get('wmti_type', 'IBMC')
            mpti_type = user_profile.get('mpti_type', 'Fact')
            
            level_prompt = Config.LEVEL_PROMPTS.get(level, "")
            wmti_desc = Config.WMTI_TYPE_DESCRIPTIONS[wmti_type]['name']
            mpti_style = Config.MPTI_STYLES[mpti_type]
            
            personalized_comparison_prompt = f"""{level_prompt}

사용자 프로필:
- 투자 경험: Level {level} ({self._get_level_description(level)})
- 투자 성향: {wmti_desc}
- 설명 스타일: {mpti_style['name']} - {mpti_style['prompt']}

다음 ETF 비교 분석 결과를 사용자 프로필에 맞춰 설명해주세요:

{comparison_result.get('recommendations', '')}

설명 요구사항:
1. 사용자 레벨에 맞는 어투와 깊이로 작성
2. 투자 성향({wmti_desc})에 맞는 관점에서 분석
3. {mpti_style['name']} 스타일로 설명 ({mpti_style['description']})
4. 사용자 프로필에 가장 적합한 ETF를 1개만 명확히 골라 추천하고, 그 이유를 구체적으로 설명
5. 두 ETF의 장단점, 투자 시 주의사항, 구체적인 투자 전략을 비교해 설명
6. 데이터(점수, 위험, 수익률 등)에 근거한 판단을 반드시 포함
7. 각 ETF의 순위(1위, 2위 등)를 명확히 표시
8. 사용자 레벨에 맞는 실전 투자 전략 제시

사용자의 투자 성향과 설명 스타일에 맞춰 개인화된 비교 분석을 제공해주세요."""
            
            response = self.gpt_client.generate_response(personalized_comparison_prompt)
            return response
            
        except Exception as e:
            logger.error(f"비교 요청 처리 중 오류: {e}")
            return "비교 분석 중 오류가 발생했습니다."

    def _handle_analysis_request(self, prompt: str, user_profile: Dict) -> str:
        """ETF 분석 요청 처리"""
        try:
            # ETF 이름 추출
            etf_name = extract_etf_name_from_input(prompt.strip(), self.data['etf_info'])
            
            if not etf_name:
                return "분석할 ETF를 입력해주세요."
            
            # ETF 분석
            analysis_result = analyze_etf(
                etf_name, user_profile,
                self.data['etf_prices'], self.data['etf_info'], 
                self.data['etf_performance'], self.data['etf_aum'], 
                self.data['etf_reference'], self.data['etf_risk']
            )
            
            # 시각화 표시
            self._display_etf_visualizations(analysis_result)
            
            # 개인화된 ETF 분석 응답 생성
            level = user_profile.get('level', 3)
            wmti_type = user_profile.get('wmti_type', 'IBMC')
            mpti_type = user_profile.get('mpti_type', 'Fact')
            
            level_prompt = Config.LEVEL_PROMPTS.get(level, "")
            wmti_desc = Config.WMTI_TYPE_DESCRIPTIONS[wmti_type]['name']
            mpti_style = Config.MPTI_STYLES[mpti_type]
            
            # 간결한 프롬프트로 변경
            personalized_analysis_prompt = f"""Level {level} 투자자, {wmti_desc} 성향, {mpti_style['name']} 스타일로 다음 ETF를 분석해주세요:

{analysis_result}

핵심 요구사항:
- 레벨 {level}에 맞는 설명
- {wmti_desc} 관점에서 분석
- {mpti_style['name']} 스타일 적용
- 공식 데이터(수익률/보수/자산규모)와 시세 데이터(수익률/변동성/최대낙폭)를 구분해서 설명
- 구체적 수치와 투자 팁 포함
- 데이터 출처를 명확히 구분 (공식 vs 시세)"""
            
            response = self.gpt_client.generate_response(personalized_analysis_prompt)
            
            return response
            
        except Exception as e:
            logger.error(f"분석 요청 처리 중 오류: {e}")
            return "분석 중 오류가 발생했습니다."

    def _handle_market_request(self, prompt: str, user_profile: Dict) -> str:
        """시장 상황 요청 처리"""
        try:
            # GPT를 통한 시장 분석
            system_prompt = f"""
            당신은 KB 국민은행의 ETF 투자 전문가입니다.
            사용자 레벨: {user_profile['level']} ({self._get_level_description(user_profile['level'])})
            투자 성향: {Config.WMTI_TYPE_DESCRIPTIONS[user_profile['wmti_type']]['name']}
            
            현재 시장 상황에 대해 사용자 레벨에 맞는 설명을 제공해주세요.
            """
            
            response = self.gpt_client.generate_response(
                system_prompt=system_prompt,
                user_prompt=prompt
            )
            
            return response
            
        except Exception as e:
            logger.error(f"시장 요청 처리 중 오류: {e}")
            return "시장 분석 중 오류가 발생했습니다."

    def _handle_general_request(self, prompt: str, user_profile: Dict) -> str:
        """일반 질문 처리"""
        try:
            system_prompt = f"""
            당신은 KB 국민은행의 ETF 투자 전문가입니다.
            사용자 레벨: {user_profile['level']} ({self._get_level_description(user_profile['level'])})
            투자 성향: {Config.WMTI_TYPE_DESCRIPTIONS[user_profile['wmti_type']]['name']}
            
            ETF 투자와 관련된 질문에 대해 친절하고 전문적으로 답변해주세요.
            """
            
            response = self.gpt_client.generate_response(
                system_prompt=system_prompt,
                user_prompt=prompt
            )
            
            return response
            
        except Exception as e:
            logger.error(f"일반 요청 처리 중 오류: {e}")
            return "답변 생성 중 오류가 발생했습니다."

    def _extract_category_keyword(self, prompt: str) -> str:
        """카테고리 키워드 추출"""
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
        
        prompt_lower = prompt.lower()
        for keyword in keywords:
            if keyword in prompt_lower:
                return keyword
        
        # ETF 패턴 매칭
        etf_match = re.search(r'(.+?)\s*ETF', prompt)
        if etf_match:
            return etf_match.group(1).strip()
        
        return ""

    def _extract_etf_names(self, prompt: str) -> List[str]:
        """ETF 이름 추출"""
        compare_keywords = ["비교", "비교해줘", "비교해주세요", "vs", "대", "차이", "어떤게", "어느게"]
        
        # 구분자로 분리 시도
        separators = [',', ' vs ', ' 대 ', ' VS ', '랑', ' 랑 ', ' 와 ', ' 과 ', '/']
        
        for sep in separators:
            if sep in prompt:
                parts = prompt.split(sep)
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
        clean_text = prompt
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

    def _apply_mpti_style(self, text: str, mpti_type: str) -> str:
        """MPTI 스타일 적용"""
        try:
            mpti_styles = Config.MPTI_STYLES
            
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
                
                # 특별한 스타일 적용
                if mpti_type == 'Skimming':
                    lines = text.split('\n')
                    if len(lines) > 2:
                        text = f"**핵심:** {lines[0]}\n**요약:** {lines[1] if len(lines) > 1 else ''}"
                
                elif mpti_type == 'Perusing':
                    if "분석" not in text:
                        text += "\n\n**상세 분석:** 위 결과는 기술적 지표, 기본적 분석, 시장 동향을 종합적으로 고려한 것입니다."
                
                elif mpti_type == 'Extensive':
                    # 다양한 관점 문구 자동 추가 제거
                    pass
                
                elif mpti_type == 'Intensive':
                    if "**핵심**" not in text:
                        text = f"**핵심:** {text}"
                
                elif mpti_type == 'Fact':
                    if "데이터" not in text:
                        text = f"**데이터 기반 분석:** {text}"
                
                elif mpti_type == 'Opinion':
                    if "전문가" not in text:
                        text = f"**전문가 관점:** {text}"
            
            return text
            
        except Exception as e:
            logger.error(f"MPTI 스타일 적용 실패: {e}")
            return text

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


def main():
    """메인 함수"""
    app = KBChatbotApp()
    app.setup_ui()
    app.run()


if __name__ == "__main__":
    main() 