"""
GPT API 클라이언트 모듈
- OpenAI GPT API 연동을 통한 자연어 응답 생성
- ETF 분석, 추천, 비교 결과를 사용자 친화적으로 변환
- 에러 처리 및 로깅 기능

주요 기능:
1. GPT API 초기화 및 설정
2. ETF 분석 결과를 자연어로 변환
3. 사용자 레벨에 맞는 응답 생성
4. API 호출 에러 처리 및 로깅

의존성:
- openai
- streamlit (API 키 관리용)
- logging (로깅용)

"""

import streamlit as st
import re
from typing import Dict, Any, Optional, List
import logging
import os

# OpenAI 라이브러리 임포트 
try:
    import openai
except ImportError:
    openai = None
    logging.warning("OpenAI 라이브러리가 설치되지 않았습니다. GPT API 기능을 사용할 수 없습니다.")

from .config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GPTClient:
    """
    GPT API 클라이언트 클래스
    
    OpenAI GPT API를 사용하여 ETF 분석 결과를 자연어로 변환하고,
    사용자의 투자 레벨에 맞는 맞춤형 응답을 생성합니다.
    
    주요 기능:
    - API 키 관리 및 인증
    - 프롬프트 생성 및 API 호출
    - 응답 파싱 및 에러 처리
    - 사용자 레벨별 맞춤 응답 생성
    """

    def __init__(self):
        """
        GPT 클라이언트 초기화
        
        환경변수에서 API 키를 가져와 OpenAI 클라이언트를 초기화합니다.
        API 키가 없거나 라이브러리가 설치되지 않은 경우 기본 설정으로 동작합니다.
        """
        # 환경 변수에서 API 키 가져오기 (우선순위: 환경변수 > Streamlit 세션)
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        
        # Streamlit 세션에서도 확인 (환경변수가 없는 경우)
        if not self.api_key:
            try:
                import streamlit as st
                self.api_key = st.session_state.get("gpt_api_key", "")
            except ImportError:
                pass
        
        # GPT 모델 설정
        self.model = "gpt-3.5-turbo"  # 모델 변경
        self.max_tokens = 1000  # 토큰 수 감소 
        
        # OpenAI 클라이언트 객체
        self.client = None
        
        # 설정 관리 객체
        try:
            self.config = Config()
        except Exception as e:
            logger.error(f"Config 초기화 실패: {e}")
            self.config = None
        
        # OpenAI 클라이언트 초기화 시도
        if self.api_key and openai:
            try:
                # OpenAI 1.0.0+ 버전용 클라이언트 초기화
                self.client = openai.OpenAI(api_key=self.api_key)
                logger.info("OpenAI 클라이언트 초기화 완료")
            except Exception as e:
                logger.error(f"OpenAI 클라이언트 초기화 실패: {e}")
                self.client = None
        else:
            if not self.api_key:
                logger.warning("GPT API 키가 설정되지 않았습니다. .env 파일에 OPENAI_API_KEY를 설정하거나 Streamlit 세션에 gpt_api_key를 설정하세요.")
            if not openai:
                logger.warning("OpenAI 라이브러리가 설치되지 않았습니다.")

    def is_configured(self) -> bool:
        """
        GPT API 설정 완료 여부 확인
        
        Returns:
            bool: API 키와 클라이언트가 모두 설정되었는지 여부
        """
        return bool(self.api_key and self.client and openai and len(self.api_key.strip()) > 0)

    def generate_response(self, prompt: str = None, system_prompt: str = None, user_prompt: str = None, max_tokens: Optional[int] = None) -> str:
        """
        GPT API를 통해 응답 생성
        
        주어진 프롬프트를 GPT에 전송하여 자연어 응답을 생성합니다.
        
        Args:
            prompt: GPT에 전송할 프롬프트 문자열
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            max_tokens: 최대 토큰 수
        
        Returns:
            str: GPT가 생성한 응답 텍스트
                 API 설정이 안된 경우 경고 메시지 반환
        """
        # API 설정 확인
        if not self.is_configured():
            return "GPT API 키가 설정되지 않았거나 라이브러리가 설치되지 않았습니다."
        
        try:
            # 메시지 구성
            messages = []
            
            if system_prompt and user_prompt:
                # 분리된 프롬프트 사용
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            else:
                # 단일 프롬프트 사용
                messages = [
                    {"role": "system", "content": "당신은 ETF 투자 전문가입니다. 사용자의 투자 레벨에 맞는 친근하고 이해하기 쉬운 답변을 제공해주세요."},
                    {"role": "user", "content": prompt}
                ]
            
            # GPT API 호출 (OpenAI 1.0.0+ 버전)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or self.max_tokens,
                temperature=0.7
            )
            
            # 응답 파싱
            content = self._parse_response(response)
            logger.info(f"GPT API 호출 성공: {len(content)} 글자")
            return content
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"GPT API 호출 중 오류 발생: {error_msg}")
            
            # 할당량 초과 또는 API 키 문제인 경우 대체 응답 제공
            if "insufficient_quota" in error_msg or "quota" in error_msg.lower():
                return self._generate_fallback_response(prompt, system_prompt, user_prompt)
            elif "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                return "⚠️ OpenAI API 키가 유효하지 않습니다. API 키를 확인해주세요."
            else:
                return f"⚠️ GPT API 호출 중 오류 발생: {error_msg}"

    def _parse_response(self, response: Any) -> str:
        """
        GPT API 응답 파싱
        
        GPT API의 응답을 파싱하여 텍스트 내용을 추출합니다.
        
        Args:
            response: GPT API 응답 객체
        
        Returns:
            str: 파싱된 텍스트 내용
        """
        try:
            # OpenAI 1.0.0+ ChatCompletion 응답에서 content 추출
            if hasattr(response, 'choices') and response.choices:
                return response.choices[0].message.content
            elif isinstance(response, dict) and 'choices' in response:
                return response['choices'][0]['message']['content']
            else:
                return str(response)
        except Exception as e:
            logger.error(f"응답 파싱 중 오류: {e}")
            return str(response)

    def generate_etf_analysis(self, etf_info: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """
        ETF 분석 응답 생성
        
        ETF 정보와 사용자 프로필을 바탕으로 GPT를 통해
        맞춤형 ETF 분석 결과를 자연어로 생성합니다.
        
        Args:
            etf_info: ETF 분석 정보 딕셔너리
                     (시세분석, 수익률/보수, 자산규모/유동성, 위험 등 포함)
            user_profile: 사용자 프로필 딕셔너리
                         (level: 투자 레벨, investor_type: 투자자 유형)
        
        Returns:
            str: 사용자 레벨에 맞는 ETF 분석 텍스트
        """
        # API 설정 확인
        if not self.is_configured():
            return "GPT API가 설정되지 않았습니다. ETF 분석을 생성할 수 없습니다."
        
        try:
            # 1. 시스템 프롬프트 생성 (사용자 레벨별 설정)
            system_prompt = self.config.get_system_prompt(user_profile)
            
            # 2. 사용자 요청 프롬프트 생성 (ETF 분석 요청)
            user_request = self._create_analysis_request(etf_info, user_profile)
            
            # 4. GPT API 호출하여 응답 생성
            return self.generate_response(system_prompt=system_prompt, user_prompt=user_request)
            
        except Exception as e:
            error_msg = f"ETF 분석 생성 중 오류: {str(e)}"
            logger.error(error_msg)
            return f"{error_msg}"

    def _create_analysis_request(self, etf_info: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """
        ETF 분석 요청 프롬프트 생성
        
        ETF 정보와 사용자 프로필을 바탕으로 GPT에게 전달할
        상세한 분석 요청 프롬프트를 생성합니다.
        
        Args:
            etf_info: ETF 정보 딕셔너리
            user_profile: 사용자 프로필 딕셔너리
        
        Returns:
            str: ETF 분석 요청 프롬프트
        """
        # ETF 기본 정보 추출
        etf_name = etf_info.get('ETF명', '알 수 없는 ETF')
        
        # 사용자 프로필 정보 추출
        user_level = user_profile.get('level', 3)  # 기본값: Level 3 (중급자)
        mpti_type = user_profile.get('investor_type', 'IFSA')  # MPTI (설명용)
        wmti_type = user_profile.get('wmti_type', 'BALANCED')  # WMTI (추천용)
        
        # 투자자 유형 설명 가져오기
        mpti_description = self.config.get_investor_type_description(mpti_type)
        wmti_description = self.config.get_wmti_type_description(wmti_type)
        
        # ETF 정보 포맷팅
        formatted_etf_info = self._format_etf_info(etf_info)
        
        # 분석 요청 프롬프트 생성
        request_prompt = f"""
아래 ETF에 대한 종합적인 분석을 제공해주세요.

분석 대상: {etf_name}
사용자 정보: Level {user_level}
MPTI 유형: {mpti_type} ({mpti_description}) - 설명 스타일용
WMTI 유형: {wmti_type} ({wmti_description}) - 투자 관점용

ETF 상세 정보:
{formatted_etf_info}

분석 요청사항:
1. 시세 데이터 분석 (수익률, 변동성, 최대낙폭)
2. 공식 데이터 분석 (수익률, 보수, 자산규모, 거래량)
3. 장점과 단점 분석
4. WMTI 유형 관점에서의 투자 적합성 평가
5. MPTI 유형에 맞는 설명 스타일 적용
6. 구체적인 투자 전략 및 주의사항
7. 실전 투자 팁과 예시

답변은 사용자 레벨({user_level})과 MPTI 유형에 맞는 어투와 깊이로 작성해주세요.
"""
        return request_prompt

    def _format_etf_info(self, etf_info: Dict[str, Any]) -> str:
        """
        ETF 정보를 보기 좋게 포맷팅
        
        ETF 분석 결과 딕셔너리를 읽기 쉬운 형태의 문자열로 변환합니다.
        
        Args:
            etf_info: ETF 정보 딕셔너리
                     (기본정보, 시세분석, 수익률/보수, 자산규모/유동성, 위험 등)
        
        Returns:
            str: 포맷팅된 ETF 정보 문자열
        """
        formatted_parts = []
        
        # 1. 기본 정보 포맷팅
        if '기본정보' in etf_info and etf_info['기본정보']:
            basic_info = etf_info['기본정보']
            formatted_parts.append(f"기본정보: {basic_info}")
        
        # 2. 시세 분석 포맷팅
        if '시세분석' in etf_info and etf_info['시세분석']:
            market_data = etf_info['시세분석']
            formatted_parts.append(f"시세분석: {market_data}")
        
        # 3. 수익률/보수 포맷팅
        if '수익률/보수' in etf_info and etf_info['수익률/보수']:
            performance = etf_info['수익률/보수']
            formatted_parts.append(f"수익률/보수: {performance}")
        
        # 4. 자산규모/유동성 포맷팅
        if '자산규모/유동성' in etf_info and etf_info['자산규모/유동성']:
            aum_data = etf_info['자산규모/유동성']
            formatted_parts.append(f"자산규모/유동성: {aum_data}")
        
        # 5. 위험 정보 포맷팅
        if '위험' in etf_info and etf_info['위험']:
            risk_data = etf_info['위험']
            formatted_parts.append(f"위험정보: {risk_data}")
        
        # 포맷팅된 정보가 있으면 반환, 없으면 기본 메시지
        if formatted_parts:
            return "\n".join(formatted_parts)
        else:
            return "상세 정보를 확인할 수 없습니다."

    def generate_recommendation(self, user_profile: Dict[str, Any], recommendations: List[Dict[str, Any]]) -> str:
        """
        ETF 추천 응답 생성
        
        사용자 프로필과 추천 ETF 목록을 바탕으로 GPT를 통해
        맞춤형 추천 설명을 생성합니다.
        
        Args:
            user_profile: 사용자 프로필 딕셔너리
            recommendations: 추천 ETF 목록
        
        Returns:
            str: 사용자 레벨에 맞는 추천 설명 텍스트
        """
        # API 설정 확인
        if not self.is_configured():
            return "⚠️ GPT API가 설정되지 않았습니다. 추천 설명을 생성할 수 없습니다."
        
        try:
            # 추천 ETF 정보 포맷팅
            formatted_recommendations = self._format_recommendations(recommendations)
            
            # 사용자 프로필 정보
            user_level = user_profile.get('level', 3)  # 기본값: Level 3 (중급자)
            investor_type = user_profile.get('investor_type', 'IFSA')  # 기본값: 일독형+팩트형+속독형+집중형
            investor_description = self.config.get_investor_type_description(investor_type)
            
            # 추천 요청 프롬프트 생성
            request_prompt = f"""
다음 ETF 추천 목록에 대한 상세한 설명을 제공해주세요.

사용자 정보: Level {user_level}, {investor_description}

추천 ETF 목록:
{formatted_recommendations}

설명 요청사항:
1. 각 ETF의 주요 특징과 장점
2. 사용자 유형에 맞는 투자 적합성
3. 투자 시 주의사항과 리스크
4. 포트폴리오 구성 제안
5. 실전 투자 전략

답변은 사용자 레벨({user_level})에 맞는 어투로 작성해주세요.
"""
            
            return self.generate_response(request_prompt)
            
        except Exception as e:
            error_msg = f"추천 설명 생성 중 오류: {str(e)}"
            logger.error(error_msg)
            return f"{error_msg}"

    def _format_recommendations(self, recommendations: List[Dict[str, Any]]) -> str:
        """
        추천 ETF 목록을 포맷팅
        
        Args:
            recommendations: 추천 ETF 목록
        
        Returns:
            str: 포맷팅된 추천 ETF 정보
        """
        formatted_parts = []
        
        for i, rec in enumerate(recommendations, 1):
            etf_name = rec.get('ETF명', '알 수 없는 ETF')
            score = rec.get('점수', 'N/A')
            category = rec.get('분류체계', 'N/A')
            
            formatted_parts.append(f"{i}. {etf_name}")
            formatted_parts.append(f"   - 추천점수: {score}")
            formatted_parts.append(f"   - 분류: {category}")
            formatted_parts.append("")
        
        return "\n".join(formatted_parts) 

    def _generate_fallback_response(self, prompt: str = None, system_prompt: str = None, user_prompt: str = None) -> str:
        """
        API 할당량 초과 시 대체 응답 생성
        
        Args:
            prompt: 원본 프롬프트
            system_prompt: 시스템 프롬프트
            user_prompt: 사용자 프롬프트
            
        Returns:
            str: 대체 응답 텍스트
        """
        try:
            # 사용자 입력에서 ETF 정보 추출
            user_input = prompt or user_prompt or ""
            
            # 기본 대체 응답
            fallback_response = """
⚠️ **OpenAI API 할당량 초과 안내**

현재 OpenAI API 사용량이 한도를 초과했습니다. 

**해결 방법:**
1. OpenAI 계정에서 결제 정보를 확인하세요
2. 새로운 API 키를 발급받으세요
3. 잠시 후 다시 시도해주세요

**임시 분석 결과:**
ETF 데이터는 정상적으로 분석되었으며, 차트와 수치 정보를 참고하시기 바랍니다.
"""
            
            # ETF 관련 키워드가 있으면 더 구체적인 응답
            if any(keyword in user_input.lower() for keyword in ['etf', '투자', '분석', '추천']):
                fallback_response += """
**ETF 투자 참고사항:**
- 수익률과 위험도를 함께 고려하세요
- 분산 투자로 리스크를 관리하세요
- 장기 투자 관점에서 접근하세요
"""
            
            return fallback_response.strip()
            
        except Exception as e:
            logger.error(f"대체 응답 생성 중 오류: {e}")
            return "API 할당량 초과로 인해 상세 분석을 제공할 수 없습니다. 잠시 후 다시 시도해주세요." 

    def generate_market_interpretation(self, market_data: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """
        시장 해석 생성
        
        Args:
            market_data: 시장 데이터 (지수 변동률 등)
            user_profile: 사용자 프로필 (level, investor_type)
        
        Returns:
            str: 레벨별 맞춤 시장 해석
        """
        try:
            # MPTI 스타일 프롬프트 가져오기
            mpti_type = user_profile.get('investor_type', 'Fact')
            if self.config:
                mpti_styles = getattr(self.config, 'MPTI_STYLES', {})
                mpti_prompt = mpti_styles.get(mpti_type, {}).get('prompt', '일반적으로 설명해주세요.')
                
                # 레벨별 프롬프트 가져오기
                level = user_profile.get('level', 1)
                level_prompts = getattr(self.config, 'LEVEL_PROMPTS', {})
                level_prompt = level_prompts.get(level, level_prompts.get(3, ""))
            else:
                mpti_prompt = '일반적으로 설명해주세요.'
                level_prompt = '일반적인 수준으로 설명해주세요.'
            
            # 시스템 프롬프트 생성 (MPTI 프롬프트 포함)
            system_prompt = f"""당신은 한국 주식시장 전문 분석가입니다. 

{level_prompt}

{mpti_prompt}

시장 데이터를 분석할 때는 다음 원칙을 따라주세요:
1. 사용자의 투자 레벨에 맞는 어투와 깊이로 작성
2. MPTI 유형에 맞는 설명 스타일을 자연스럽게 적용
3. 구체적인 수치와 근거 포함
4. 실전 투자 팁과 예시 포함
5. 투자 위험 고지 포함
6. 1-2줄로 간결하게 작성"""
            
            # 사용자 프롬프트 생성
            user_prompt = f"""
다음 시장 데이터를 바탕으로 시장 해석을 제공해주세요.

시장 데이터:
- KOSPI 변동률: {market_data.get('kospi_change', 0)}%
- KOSDAQ 변동률: {market_data.get('kosdaq_change', 0)}%
- S&P 500 변동률: {market_data.get('sp500_change', 0)}%
- NASDAQ 변동률: {market_data.get('nasdaq_change', 0)}%
- 날짜: {market_data.get('date', '')}

시장 해석을 제공해주세요.
"""
            
            # API 호출
            response = self.generate_response(system_prompt=system_prompt, user_prompt=user_prompt)
            
            if response and not response.startswith("⚠️"):
                return response
            else:
                return self._generate_fallback_market_interpretation(market_data, user_profile)
                
        except Exception as e:
            logger.error(f"시장 해석 생성 중 오류: {e}")
            return self._generate_fallback_market_interpretation(market_data, user_profile)
    
    def _generate_fallback_market_interpretation(self, market_data: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """GPT API 실패 시 기본 시장 해석 생성"""
        try:
            # MPTI 스타일 프롬프트 가져오기
            mpti_type = user_profile.get('investor_type', 'Fact')
            if self.config:
                mpti_styles = getattr(self.config, 'MPTI_STYLES', {})
                mpti_prompt = mpti_styles.get(mpti_type, {}).get('prompt', '일반적으로 설명해주세요.')
            else:
                mpti_prompt = '일반적으로 설명해주세요.'
            
            level = user_profile.get('level', 1)
            kospi_change = market_data.get('kospi_change', 0)
            kosdaq_change = market_data.get('kosdaq_change', 0)
            
            if level == 1:
                base_text = f"오늘 시장은 조금 움직였어요. 코스피는 {kospi_change}% {'올랐' if kospi_change > 0 else '내려갔'}고, 코스닥은 {kosdaq_change}% {'올랐' if kosdaq_change > 0 else '내려갔'}답니다."
            elif level == 2:
                base_text = f"오늘 시장은 소폭 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 시장이 안정적인 흐름을 보였습니다."
            elif level == 3:
                base_text = f"오늘 시장은 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 글로벌 시장 동향과 연관성을 보였습니다."
            elif level == 4:
                base_text = f"오늘 시장은 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 기술적 지지/저항선에서의 움직임을 보였습니다."
            else:
                base_text = f"오늘 시장은 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 기술적 분석과 기본적 요인이 복합적으로 작용했습니다."
            
            # MPTI 프롬프트에 따라 스타일 적용
            if '객관적' in mpti_prompt or '팩트' in mpti_prompt:
                return f"**데이터 기반 분석:** {base_text}"
            elif '전문가' in mpti_prompt or '오피니언' in mpti_prompt:
                return f"**전문가 관점:** {base_text}"
            elif '핵심' in mpti_prompt or '집중' in mpti_prompt:
                return f"**핵심:** {base_text}"
            elif '요약' in mpti_prompt or '간단' in mpti_prompt:
                return f"**요약:** {base_text}"
            elif '상세' in mpti_prompt or '깊이' in mpti_prompt:
                return f"**상세 분석:** {base_text}"
            else:
                return base_text
                
        except Exception as e:
            # Config 접근 실패 시 기본 로직 사용
            level = user_profile.get('level', 1)
            mpti_type = user_profile.get('investor_type', 'Fact')
            
            kospi_change = market_data.get('kospi_change', 0)
            kosdaq_change = market_data.get('kosdaq_change', 0)
            
            if level == 1:
                base_text = f"오늘 시장은 조금 움직였어요. 코스피는 {kospi_change}% {'올랐' if kospi_change > 0 else '내려갔'}고, 코스닥은 {kosdaq_change}% {'올랐' if kosdaq_change > 0 else '내려갔'}답니다."
            elif level == 2:
                base_text = f"오늘 시장은 소폭 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 시장이 안정적인 흐름을 보였습니다."
            elif level == 3:
                base_text = f"오늘 시장은 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 글로벌 시장 동향과 연관성을 보였습니다."
            elif level == 4:
                base_text = f"오늘 시장은 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 기술적 지지/저항선에서의 움직임을 보였습니다."
            else:
                base_text = f"오늘 시장은 {'상승' if kospi_change > 0 else '하락'}세를 보였습니다. 코스피 {kospi_change}%, 코스닥 {kosdaq_change}% 변동으로 기술적 분석과 기본적 요인이 복합적으로 작용했습니다."
            
            # MPTI 스타일 적용
            if mpti_type == 'Fact':
                return f"**데이터 기반 분석:** {base_text}"
            elif mpti_type == 'Opinion':
                return f"**전문가 관점:** {base_text}"
            elif mpti_type == 'Intensive':
                return f"**핵심:** {base_text}"
            elif mpti_type == 'Skimming':
                return f"**요약:** {base_text}"
            else:
                return base_text 

    def generate_portfolio_analysis(self, portfolio_data: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """
        포트폴리오 분석 생성
        
        Args:
            portfolio_data: 포트폴리오 데이터
            user_profile: 사용자 프로필
        
        Returns:
            str: 레벨별 맞춤 포트폴리오 분석
        """
        try:
            system_prompt = self.config.get_system_prompt(user_profile)
            
            user_prompt = f"""
다음 ETF 포트폴리오 데이터를 바탕으로 사용자의 투자 레벨과 MPTI 유형에 맞는 분석을 제공해주세요.

포트폴리오 데이터:
- ETF명: {portfolio_data.get('etf_name', '')}
- 최대 비중 종목: {list(portfolio_data.get('top_holdings', {}).keys())[0] if portfolio_data.get('top_holdings') else 'N/A'}
- 최대 비중: {list(portfolio_data.get('top_holdings', {}).values())[0] if portfolio_data.get('top_holdings') else 0}%
- 상위 종목 집중도: {portfolio_data.get('concentration', 0):.1f}%

사용자 정보:
- 투자 레벨: {user_profile.get('level', 1)}
- MPTI 유형: {user_profile.get('investor_type', 'Fact')}

요구사항:
1. 사용자의 투자 레벨에 맞는 어투와 깊이로 작성
2. MPTI 유형에 맞는 설명 스타일 적용
3. 포트폴리오 집중도와 위험도 분석
4. 투자 시 주의사항 포함
5. 1-2줄로 간결하게 작성

포트폴리오 분석을 제공해주세요.
"""
            
            response = self.generate_response(system_prompt=system_prompt, user_prompt=user_prompt)
            
            if response and not response.startswith("⚠️"):
                return response
            else:
                return self._generate_fallback_portfolio_analysis(portfolio_data, user_profile)
                
        except Exception as e:
            logger.error(f"포트폴리오 분석 생성 중 오류: {e}")
            return self._generate_fallback_portfolio_analysis(portfolio_data, user_profile)
    
    def generate_price_analysis(self, price_data: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """
        시세 분석 생성
        
        Args:
            price_data: 시세 데이터
            user_profile: 사용자 프로필
        
        Returns:
            str: 레벨별 맞춤 시세 분석
        """
        try:
            system_prompt = self.config.get_system_prompt(user_profile)
            
            user_prompt = f"""
다음 시세 데이터를 바탕으로 사용자의 투자 레벨과 MPTI 유형에 맞는 분석을 제공해주세요.

시세 데이터:
- 종목명: {price_data.get('stock_name', '')}
- 최신 종가: {price_data.get('latest_price', 0):,.0f}원
- 변동률: {price_data.get('change_percent', 0):+.1f}%
- 최고가: {price_data.get('high', 0):,.0f}원
- 최저가: {price_data.get('low', 0):,.0f}원
- 평균 거래량: {price_data.get('volume', 0):,.0f}주

사용자 정보:
- 투자 레벨: {user_profile.get('level', 1)}
- MPTI 유형: {user_profile.get('investor_type', 'Fact')}

요구사항:
1. 사용자의 투자 레벨에 맞는 어투와 깊이로 작성
2. MPTI 유형에 맞는 설명 스타일 적용
3. 가격 변동과 거래량 분석
4. 투자 시 주의사항 포함
5. 1-2줄로 간결하게 작성

시세 분석을 제공해주세요.
"""
            
            response = self.generate_response(system_prompt=system_prompt, user_prompt=user_prompt)
            
            if response and not response.startswith("⚠️"):
                return response
            else:
                return self._generate_fallback_price_analysis(price_data, user_profile)
                
        except Exception as e:
            logger.error(f"시세 분석 생성 중 오류: {e}")
            return self._generate_fallback_price_analysis(price_data, user_profile)
    
    def _generate_fallback_portfolio_analysis(self, portfolio_data: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """GPT API 실패 시 기본 포트폴리오 분석 생성"""
        level = user_profile.get('level', 1)
        mpti_type = user_profile.get('investor_type', 'Fact')
        
        etf_name = portfolio_data.get('etf_name', '')
        concentration = portfolio_data.get('concentration', 0)
        
        if level == 1:
            base_text = f"{etf_name}는 여러 종목을 모아놓은 상자예요. 상위 종목들이 전체의 {concentration:.1f}%를 차지하고 있어요!"
        elif level == 2:
            base_text = f"{etf_name}의 포트폴리오를 분석해보면, 상위 종목들이 전체의 {concentration:.1f}%를 차지하여 비교적 집중도가 높은 편입니다."
        elif level == 3:
            base_text = f"{etf_name}의 포트폴리오 분석 결과, 상위 종목들의 집중도가 {concentration:.1f}%로 높은 편이며, 이는 특정 섹터에 집중 투자하는 특성을 보여줍니다."
        elif level == 4:
            base_text = f"{etf_name}의 포트폴리오 분석 결과, 상위 종목들의 집중도가 {concentration:.1f}%로 높은 편이며, 이는 특정 섹터나 테마에 집중 투자하는 특성을 보여줍니다."
        else:
            base_text = f"{etf_name}의 포트폴리오 분석 결과, 상위 종목들의 집중도가 {concentration:.1f}%로 높은 편이며, 이는 특정 섹터나 테마에 집중 투자하는 특성을 보여줍니다. 투자 시 분산 투자의 중요성을 고려해야 합니다."
        
        # MPTI 스타일 적용
        if mpti_type == 'Fact':
            return f"**데이터 기반 분석:** {base_text}"
        elif mpti_type == 'Opinion':
            return f"**전문가 관점:** {base_text}"
        elif mpti_type == 'Intensive':
            return f"**핵심:** {base_text}"
        elif mpti_type == 'Skimming':
            return f"**요약:** {base_text}"
        else:
            return base_text
    
    def _generate_fallback_price_analysis(self, price_data: Dict[str, Any], user_profile: Dict[str, Any]) -> str:
        """GPT API 실패 시 기본 시세 분석 생성"""
        level = user_profile.get('level', 1)
        mpti_type = user_profile.get('investor_type', 'Fact')
        
        stock_name = price_data.get('stock_name', '')
        latest_price = price_data.get('latest_price', 0)
        change_percent = price_data.get('change_percent', 0)
        
        if level == 1:
            base_text = f"{stock_name}는 어제 {latest_price:,.0f}원으로 마감했어요. 전날보다 {change_percent:+.1f}% 변동했답니다!"
        elif level == 2:
            base_text = f"{stock_name}의 최근 5거래일 추이를 보면, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다."
        elif level == 3:
            base_text = f"{stock_name}의 최근 5거래일 분석 결과, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다."
        elif level == 4:
            base_text = f"{stock_name}의 최근 5거래일 분석 결과, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다. 기술적 지표를 참고하여 투자 판단을 하시기 바랍니다."
        else:
            base_text = f"{stock_name}의 최근 5거래일 분석 결과, 어제 종가 {latest_price:,.0f}원으로 전일 대비 {change_percent:+.1f}% 변동했습니다. 기술적 지표와 기본적 분석을 종합하여 투자 판단을 하시기 바랍니다."
        
        # MPTI 스타일 적용
        if mpti_type == 'Fact':
            return f"**데이터 기반 분석:** {base_text}"
        elif mpti_type == 'Opinion':
            return f"**전문가 관점:** {base_text}"
        elif mpti_type == 'Intensive':
            return f"**핵심:** {base_text}"
        elif mpti_type == 'Skimming':
            return f"**요약:** {base_text}"
        else:
            return base_text 

    def call_gpt_simple(self, messages: list, model: str = None, temperature: float = 0.1) -> str:
        """
        간단한 GPT API 호출 (dart_api 호환성)
        messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        """
        if not self.is_configured():
            raise RuntimeError("GPT API가 설정되지 않았습니다.")
        
        model = model or self.model
        
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens
            )
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"GPT API 호출 실패: {e}")
            return self._generate_fallback_response_from_messages(messages)
    
    def parse_with_gpt(self, text: str, model: str = None) -> str:
        """
        GPT를 사용한 문서 파싱 및 요약 (dart_api 호환성)
        text: 순수 텍스트(한글 포함)
        """
        system_prompt = (
            "당신은 금융 애널리스트이자 기업공시 전문 파서입니다.\n"
            "아래에 주어진 DART 공시 전문 텍스트를 읽고, 투자자 관점에서 요약해 주세요:\n\n"
            "원본 자료 : URL을 꼭 명시해주세요. \n"
            "핵심 요약: 필수적인 내용 반드시 포함해주세요. \n"
            "주요 수치: 항목별로 (숫자 + 단위 + 증감률(%))\n\n"
            "※ 증감률 표기 시 '–6.49%' 와 같이 '%'만 사용하세요.\n"
            "※ 불필요한 'p' 또는 'p.p.' 표기는 제거합니다.\n"
            "3) 투자 시사점: 👍 긍정 / 👎 부정 신호 포함 \n"
            "4) 설명 난이도 (Level 1~3): \n"
            "• Level 1 – 유치원/초1 스타일 (쉬운 비유와 함께, 아주 쉽게 알려줘야합니다) \n"
            "• Level 2 – 중고등학생용 (핵심+이유, 너무 전문적이진 않지만, 이해되는 수준으로 Level1보다는 어렵게 설명해주세요.) \n"
            "• Level 3 – 고급 분석(실전 투자가이드, 실전투자자용 설명이면 좋습니다.) \n"
            "각 level별로 응답해주세요."
        )
        
        user_content = f"다음 공시 텍스트를 분석해주세요:\n\n{text}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        
        return self.call_gpt_simple(messages, model)
    
    def _generate_fallback_response_from_messages(self, messages: list) -> str:
        """메시지 리스트로부터 폴백 응답 생성"""
        try:
            # 마지막 사용자 메시지 찾기
            user_message = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if user_message:
                return f"⚠️ GPT API 호출에 실패했습니다. 요청 내용: {user_message[:100]}..."
            else:
                return "⚠️ GPT API 호출에 실패했습니다."
        except Exception:
            return "⚠️ GPT API 호출에 실패했습니다." 