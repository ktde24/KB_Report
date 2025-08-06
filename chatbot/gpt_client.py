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
        
        Streamlit 세션에서 API 키를 가져와 OpenAI 클라이언트를 초기화합니다.
        API 키가 없거나 라이브러리가 설치되지 않은 경우 기본 설정으로 동작합니다.
        """
        # Streamlit 세션에서 API 키 가져오기
        self.api_key = st.session_state.get("gpt_api_key", "")
        
        # 환경 변수에서도 확인
        if not self.api_key:
            self.api_key = os.getenv("OPENAI_API_KEY", "")
        
        # GPT 모델 설정
        self.model = "gpt-4o-mini"  # GPT 모델명
        self.max_tokens = 1500  # 최대 토큰 수
        
        # OpenAI 클라이언트 객체
        self.client = None
        
        # 설정 관리 객체
        self.config = Config()
        
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
                logger.warning("GPT API 키가 설정되지 않았습니다.")
            if not openai:
                logger.warning("OpenAI 라이브러리가 설치되지 않았습니다.")

    def is_configured(self) -> bool:
        """
        GPT API 설정 완료 여부 확인
        
        Returns:
            bool: API 키와 클라이언트가 모두 설정되었는지 여부
        """
        return bool(self.api_key and self.client)

    def generate_response(self, prompt: str = None, system_prompt: str = None, user_prompt: str = None, max_tokens: Optional[int] = None) -> str:
        """
        GPT API를 통해 응답 생성
        
        주어진 프롬프트를 GPT에 전송하여 자연어 응답을 생성합니다.
        
        Args:
            prompt: GPT에 전송할 프롬프트 문자열 (단일 프롬프트 사용 시)
            system_prompt: 시스템 프롬프트 (분리된 프롬프트 사용 시)
            user_prompt: 사용자 프롬프트 (분리된 프롬프트 사용 시)
            max_tokens: 최대 토큰 수 (None인 경우 기본값 사용)
        
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
            return "⚠️ API 할당량 초과로 인해 상세 분석을 제공할 수 없습니다. 잠시 후 다시 시도해주세요." 