"""
ETF 챗봇 설정 파일
- 투자자 유형별 가중치 설정
- 시스템 프롬프트 관리
- 파일 경로 중앙 관리
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()


class Config:
    """ETF 챗봇 설정 클래스"""
    
    # =============================================================================
    # 파일 경로 설정
    # =============================================================================
    DATA_PATHS = {
        'etf_info': 'data/상품검색.csv',
        'etf_prices': 'data/ETF_시세_데이터_20240101_20250729.csv',
        'etf_performance': 'data/수익률 및 총보수(기간).csv',
        'etf_aum': 'data/자산규모 및 유동성(기간).csv',
        'etf_reference': 'data/참고지수(기간).csv',
        'etf_risk': 'data/투자위험(기간).csv',
        'risk_tier': 'data/etf_re_bp_simplified.csv',
        'cache': 'data/etf_scores_cache.csv'
    }
    
        # =============================================================================
    # WMTI 투자자 유형별 가중치 설정 (KB 투자자 유형 - 추천용)
    # 4차원 8유형: 활동방향(A/I) × 투자인지(P/B) × 투자판단(M/W) × 행동패턴(L/C)
    # =============================================================================
    WMTI_TYPE_WEIGHTS = {
        # 외향형 + 전문가형 + 집중형 + 자유형
        'APML': {'return_weight': 0.4, 'risk_tolerance': 0.4, 'active_focus': 0.2},
        'APMW': {'return_weight': 0.3, 'risk_tolerance': 0.3, 'balanced_focus': 0.4},
        'APWL': {'return_weight': 0.3, 'risk_tolerance': 0.3, 'balanced_focus': 0.4},
        'APWW': {'return_weight': 0.2, 'risk_tolerance': 0.2, 'diversified_focus': 0.6},
        'ABML': {'return_weight': 0.4, 'risk_tolerance': 0.3, 'growth_focus': 0.3},
        'ABMW': {'return_weight': 0.3, 'risk_tolerance': 0.2, 'balanced_focus': 0.5},
        'ABWL': {'return_weight': 0.3, 'risk_tolerance': 0.2, 'balanced_focus': 0.5},
        'ABWW': {'return_weight': 0.2, 'risk_tolerance': 0.1, 'diversified_focus': 0.7},
        # 내향형 + 전문가형 + 집중형 + 자유형
        'IPML': {'return_weight': 0.3, 'risk_tolerance': 0.2, 'focused_focus': 0.5},
        'IPMW': {'return_weight': 0.2, 'risk_tolerance': 0.1, 'balanced_focus': 0.7},
        'IPWL': {'return_weight': 0.2, 'risk_tolerance': 0.1, 'balanced_focus': 0.7},
        'IPWW': {'return_weight': 0.1, 'risk_tolerance': 0.0, 'diversified_focus': 0.9},
        'IBML': {'return_weight': 0.3, 'risk_tolerance': 0.2, 'growth_focus': 0.5},
        'IBMW': {'return_weight': 0.2, 'risk_tolerance': 0.1, 'balanced_focus': 0.7},
        'IBWL': {'return_weight': 0.2, 'risk_tolerance': 0.1, 'balanced_focus': 0.7},
        'IBWW': {'return_weight': 0.1, 'risk_tolerance': 0.0, 'diversified_focus': 0.9}
    }
    
    # =============================================================================
    # WMTI 투자자 유형 설명 (추천용)
    # =============================================================================
    WMTI_TYPE_DESCRIPTIONS = {
        'APML': '외향형+전문가형+집중형+자유형 - 적극적 전문 투자, 집중 관리',
        'APMW': '외향형+전문가형+집중형+신중형 - 전문적 집중 투자, 신중한 접근',
        'APWL': '외향형+전문가형+분산형+자유형 - 전문적 분산 투자, 자유로운 접근',
        'APWW': '외향형+전문가형+분산형+신중형 - 전문적 분산 투자, 신중한 접근',
        'ABML': '외향형+탐험가형+집중형+자유형 - 적극적 탐험 투자, 집중 관리',
        'ABMW': '외향형+탐험가형+집중형+신중형 - 탐험적 집중 투자, 신중한 접근',
        'ABWL': '외향형+탐험가형+분산형+자유형 - 탐험적 분산 투자, 자유로운 접근',
        'ABWW': '외향형+탐험가형+분산형+신중형 - 탐험적 분산 투자, 신중한 접근',
        'IPML': '내향형+전문가형+집중형+자유형 - 보수적 전문 투자, 집중 관리',
        'IPMW': '내향형+전문가형+집중형+신중형 - 보수적 전문 투자, 신중한 접근',
        'IPWL': '내향형+전문가형+분산형+자유형 - 보수적 전문 투자, 분산 관리',
        'IPWW': '내향형+전문가형+분산형+신중형 - 보수적 전문 투자, 신중한 분산',
        'IBML': '내향형+탐험가형+집중형+자유형 - 보수적 탐험 투자, 집중 관리',
        'IBMW': '내향형+탐험가형+집중형+신중형 - 보수적 탐험 투자, 신중한 접근',
        'IBWL': '내향형+탐험가형+분산형+자유형 - 보수적 탐험 투자, 분산 관리',
        'IBWW': '내향형+탐험가형+분산형+신중형 - 보수적 탐험 투자, 신중한 분산'
    }

    # =============================================================================
    # MPTI 투자자 유형별 가중치 설정 (마블콘텐츠선호지표 - 설명용)
    # =============================================================================
    INVESTOR_TYPE_WEIGHTS = {
        # 일독형(Intensive) + 팩트형(Fact) + 속독형(Skimming) + 집중형(Absorbed)
        'IFSA': {'I': 0.3, 'F': 0.3, 'S': 0.2, 'A': 0.2},  # 집중적 팩트 속독형
        'IFSP': {'I': 0.3, 'F': 0.3, 'S': 0.2, 'P': 0.2},  # 집중적 팩트 속독형 (분산)
        'IFPA': {'I': 0.3, 'F': 0.3, 'P': 0.2, 'A': 0.2},  # 집중적 팩트 정독형
        'IFPP': {'I': 0.3, 'F': 0.3, 'P': 0.2, 'P': 0.2},  # 집중적 팩트 정독형 (분산)
        
        # 일독형(Intensive) + 오피니언형(Notion) + 속독형(Skimming) + 집중형(Absorbed)
        'INSA': {'I': 0.3, 'N': 0.3, 'S': 0.2, 'A': 0.2},  # 집중적 오피니언 속독형
        'INSP': {'I': 0.3, 'N': 0.3, 'S': 0.2, 'P': 0.2},  # 집중적 오피니언 속독형 (분산)
        'INPA': {'I': 0.3, 'N': 0.3, 'P': 0.2, 'A': 0.2},  # 집중적 오피니언 정독형
        'INPP': {'I': 0.3, 'N': 0.3, 'P': 0.2, 'P': 0.2},  # 집중적 오피니언 정독형 (분산)
        
        # 다독형(Extensive) + 팩트형(Fact) + 속독형(Skimming) + 집중형(Absorbed)
        'EFSA': {'E': 0.3, 'F': 0.3, 'S': 0.2, 'A': 0.2},  # 분산적 팩트 속독형
        'EFSP': {'E': 0.3, 'F': 0.3, 'S': 0.2, 'P': 0.2},  # 분산적 팩트 속독형 (분산)
        'EFPA': {'E': 0.3, 'F': 0.3, 'P': 0.2, 'A': 0.2},  # 분산적 팩트 정독형
        'EFPP': {'E': 0.3, 'F': 0.3, 'P': 0.2, 'P': 0.2},  # 분산적 팩트 정독형 (분산)
        
        # 다독형(Extensive) + 오피니언형(Notion) + 속독형(Skimming) + 집중형(Absorbed)
        'ENSA': {'E': 0.3, 'N': 0.3, 'S': 0.2, 'A': 0.2},  # 분산적 오피니언 속독형
        'ENSP': {'E': 0.3, 'N': 0.3, 'S': 0.2, 'P': 0.2},  # 분산적 오피니언 속독형 (분산)
        'ENPA': {'E': 0.3, 'N': 0.3, 'P': 0.2, 'A': 0.2},  # 분산적 오피니언 정독형
        'ENPP': {'E': 0.3, 'N': 0.3, 'P': 0.2, 'P': 0.2},  # 분산적 오피니언 정독형 (분산)
    }

    # =============================================================================
    # MPTI 투자자 유형 설명 (설명용)
    # =============================================================================
    INVESTOR_TYPE_DESCRIPTIONS = {
        'IFSA': '일독형(Intensive) + 팩트형(Fact) + 속독형(Skimming) + 집중형(Absorbed)',
        'IFSP': '일독형(Intensive) + 팩트형(Fact) + 속독형(Skimming) + 분산형(Diverse)',
        'IFPA': '일독형(Intensive) + 팩트형(Fact) + 정독형(Perusing) + 집중형(Absorbed)',
        'IFPP': '일독형(Intensive) + 팩트형(Fact) + 정독형(Perusing) + 분산형(Diverse)',
        'INSA': '일독형(Intensive) + 오피니언형(Notion) + 속독형(Skimming) + 집중형(Absorbed)',
        'INSP': '일독형(Intensive) + 오피니언형(Notion) + 속독형(Skimming) + 분산형(Diverse)',
        'INPA': '일독형(Intensive) + 오피니언형(Notion) + 정독형(Perusing) + 집중형(Absorbed)',
        'INPP': '일독형(Intensive) + 오피니언형(Notion) + 정독형(Perusing) + 분산형(Diverse)',
        'EFSA': '다독형(Extensive) + 팩트형(Fact) + 속독형(Skimming) + 집중형(Absorbed)',
        'EFSP': '다독형(Extensive) + 팩트형(Fact) + 속독형(Skimming) + 분산형(Diverse)',
        'EFPA': '다독형(Extensive) + 팩트형(Fact) + 정독형(Perusing) + 집중형(Absorbed)',
        'EFPP': '다독형(Extensive) + 팩트형(Fact) + 정독형(Perusing) + 분산형(Diverse)',
        'ENSA': '다독형(Extensive) + 오피니언형(Notion) + 속독형(Skimming) + 집중형(Absorbed)',
        'ENSP': '다독형(Extensive) + 오피니언형(Notion) + 속독형(Skimming) + 분산형(Diverse)',
        'ENPA': '다독형(Extensive) + 오피니언형(Notion) + 정독형(Perusing) + 집중형(Absorbed)',
        'ENPP': '다독형(Extensive) + 오피니언형(Notion) + 정독형(Perusing) + 분산형(Diverse)',
    }
    
    # =============================================================================
    # 레벨별 Risk Tier 허용 범위 (5단계)
    # =============================================================================
    LEVEL_RISK_TIER_LIMITS = {
        1: 1,  # Level 1: risk_tier 0~1 (매우 안전한 ETF만)
        2: 2,  # Level 2: risk_tier 0~2 (안전한 ETF)
        3: 3,  # Level 3: risk_tier 0~3 (중간 위험까지)
        4: 4,  # Level 4: risk_tier 0~4 (높은 위험까지)
        5: 5   # Level 5: risk_tier 0~5 (모든 위험 레벨)
    }
    
    # =============================================================================
    # 레벨별 답변 스타일 프롬프트
    # =============================================================================
    LEVEL_PROMPTS = {
        1: """- Level 1 (초보자): 
       • 어투: 유치원/초등학생도 이해할 수 있는 아주 쉬운 말로 설명
       • 내용: 투자 기초 개념 위주, 복잡한 용어는 비유와 예시로 대체
       • 구조: "이 ETF는 [간단한 설명] + [일상적 비유] + [투자 시 주의사항]"
       • 길이: 1-2줄로 핵심만 요약
       • 포함 요소: ETF의 가장 기본적인 특징 1-2개, 투자 시 주의사항 1개""",
       
        2: """- Level 2 (입문자): 
       • 어투: 중고등학생도 이해 가능한 쉬운 말로 설명
       • 내용: 핵심 개념과 이유를 포함, 기본적인 투자 지식 전달
       • 구조: "이 ETF는 [기본 설명] + [투자 이유] + [실전 팁]"
       • 길이: 2-3줄로 설명
       • 포함 요소: ETF의 주요 특징 2-3개, 투자 이유, 실전 팁 1개""",
       
        3: """- Level 3 (중급자): 
       • 어투: 일반 성인도 이해할 수 있는 수준으로 설명
       • 내용: 실전 팁과 구체적 전략 포함, 데이터 기반 분석
       • 구조: "이 ETF는 [상세 분석] + [데이터 기반 평가] + [실전 전략] + [리스크 관리]"
       • 길이: 3-4줄로 분석
       • 포함 요소: 수익률/위험도 데이터, 시장 상황 분석, 구체적 투자 전략, 리스크 관리 방법""",
       
        4: """- Level 4 (고급자): 
       • 어투: 투자 경험이 있는 성인을 대상으로 한 전문적 설명
       • 내용: 심화 분석과 고급 전략, 시장 동향과 연관성 분석
       • 구조: "이 ETF는 [심화 분석] + [시장 동향 연관성] + [고급 전략] + [포트폴리오 최적화] + [리스크 분석]"
       • 길이: 4-5줄로 상세 설명
       • 포함 요소: 심화된 시장 분석, 다른 ETF와의 비교, 고급 투자 전략, 포트폴리오 최적화 방안, 상세한 리스크 분석""",
       
        5: """- Level 5 (전문가): 
       • 어투: 투자 전문가 수준의 고급 분석과 전문 용어 사용
       • 내용: 최고 수준 분석과 실전 활용, 시장 미시구조까지 고려
       • 구조: "이 ETF는 [최고 수준 분석] + [시장 미시구조 분석] + [고급 투자 전략] + [리스크 관리 최적화] + [실전 활용 방안] + [시장 전망]"
       • 길이: 5줄 이상으로 전문적 설명
       • 포함 요소: 최고 수준의 시장 분석, 미시구조적 요소 분석, 고급 투자 전략, 리스크 관리 최적화, 실전 활용 방안, 시장 전망 및 대응 전략"""
    }
    
    # =============================================================================
    # 프롬프트 생성 메서드
    # =============================================================================
    @classmethod
    def get_system_prompt(cls, user_profile: Dict[str, Any] = None) -> str:
        """
        시스템 기본 프롬프트 생성
        
        Args:
            user_profile: 사용자 프로필 (level, investor_type)
        
        Returns:
            시스템 프롬프트 문자열
        """
        base_prompt = """당신은 ETF 투자 전문 상담사입니다.
사용자의 투자 레벨과 MPTI 투자자 유형에 맞춰 맞춤형 답변을 제공하세요.

답변 요구사항:
- 공식 데이터(수익률, 보수, 자산규모, 거래량)와 시세 데이터(수익률, 변동성, 최대낙폭)를 모두 활용
- 사용자 레벨에 맞는 어투와 깊이로 작성
- 구체적인 수치와 근거 포함
- 실전 투자 팁과 예시, 비유 포함
- 투자 위험 고지 포함

MPTI 투자자 유형별 특성:
- I (Intensive): 일독형 - 깊이 있는 분석과 상세한 정보 선호
- E (Extensive): 다독형 - 다양한 정보와 포괄적인 분석 선호
- F (Fact): 팩트형 - 객관적 데이터와 사실 중심 설명 선호
- N (Notion): 오피니언형 - 주관적 의견과 해석 중심 설명 선호
- S (Skimming): 속독형 - 핵심 요약과 간결한 설명 선호
- P (Perusing): 정독형 - 상세한 분석과 깊이 있는 설명 선호
- A (Absorbed): 집중형 - 특정 분야에 집중된 정보 선호
- D (Diverse): 분산형 - 다양한 분야와 포트폴리오 분산 선호

레벨별 답변 스타일은 LEVEL_PROMPTS에서 자동으로 적용됩니다."""
        
        if user_profile:
            level = user_profile.get('level', 1)
            investor_type = user_profile.get('investor_type', 'IFSA')
            
            level_prompt = cls.LEVEL_PROMPTS.get(level, "")
            investor_desc = cls.get_investor_type_description(investor_type)
            
            base_prompt += f"\n\n현재 사용자: Level {level}, {investor_desc}\n{level_prompt}"
        
        return base_prompt
    
    @classmethod 
    def get_recommendation_prompt(cls, user_profile: Dict[str, Any] = None) -> str:
        """ETF 추천용 프롬프트 생성"""
        base_prompt = cls.get_system_prompt(user_profile)
        
        # 투자자 유형 설명 추가
        investor_types_desc = "\n".join([
            f"- {code}: {desc}" 
            for code, desc in cls.INVESTOR_TYPE_DESCRIPTIONS.items()
        ])
        
        recommendation_prompt = f"""{base_prompt}

투자자 유형별 특성:
{investor_types_desc}

추천 시 고려사항:
1. 사용자의 투자 레벨과 유형에 맞는 적절한 위험도
2. 각 ETF의 장단점과 특징
3. 투자 시 주의사항과 실전 팁
4. 구체적인 투자 전략 제안"""
        
        return recommendation_prompt
    
    # =============================================================================
    # 유틸리티 메서드
    # =============================================================================
    @staticmethod
    def get_level_number(user_level: str) -> int:
        """레벨 문자열을 숫자로 변환 (1-5단계)"""
        if isinstance(user_level, int):
            return max(1, min(5, user_level))  # 1-5 범위로 제한
        if isinstance(user_level, str):
            # level1, level2, level3, level4, level5 형태 처리
            if user_level.startswith('level'):
                level_num = int(user_level[-1])
                return max(1, min(5, level_num))
            # Level 1, Level 2, Level 3, Level 4, Level 5 형태 처리
            if user_level.startswith('Level'):
                level_num = int(user_level[-1])
                return max(1, min(5, level_num))
        return 3  # 기본값: Level 3 (중급자)
    
    @classmethod
    def get_data_path(cls, data_type: str) -> str:
        """데이터 파일 경로 반환"""
        return cls.DATA_PATHS.get(data_type, '')
    
    @classmethod
    def get_investor_type_description(cls, investor_type: str) -> str:
        """MPTI 투자자 유형 설명 반환 (설명용)"""
        return cls.INVESTOR_TYPE_DESCRIPTIONS.get(investor_type, '알 수 없는 유형')
    
    @classmethod
    def get_wmti_type_description(cls, wmti_type: str) -> str:
        """WMTI 투자자 유형 설명 반환 (추천용)"""
        return cls.WMTI_TYPE_DESCRIPTIONS.get(wmti_type, '알 수 없는 유형')
    
    @classmethod
    def get_risk_tier_limit(cls, level: int) -> int:
        """레벨별 risk_tier 허용 한계 반환"""
        return cls.LEVEL_RISK_TIER_LIMITS.get(level, 4)
    
    @classmethod
    def get_wmti_weights(cls, wmti_type: str) -> Dict[str, float]:
        """WMTI 투자자 유형별 가중치 반환"""
        return cls.WMTI_TYPE_WEIGHTS.get(wmti_type, {
            'return_weight': 0.3, 
            'risk_tolerance': 0.2, 
            'balance_focus': 0.5
        })
    
    @classmethod
    def get_scoring_criteria(cls) -> str:
        """추천 점수 계산 기준 설명"""
        return """
        ETF 추천 점수 계산 기준 (객관적 데이터 기반):
        
        1. 수익률 (30%): 1년 수익률 기준 ('1년수익률' 데이터)
        2. 위험조정수익률 (25%): 수익률 대비 변동성 고려 ('1년수익률' / '변동성')
        3. 비용효율성 (20%): 낮은 보수율 우선 ('총보수' 데이터)
        4. 유동성 (15%): 높은 거래량 우선 ('거래량' 데이터)
        5. 안정성 (10%): 높은 자산규모 우선 ('자산규모' 데이터)
        
        WMTI 투자자 유형별 가중치 적용:
        - 외향형+전문가형: 수익률과 위험조정수익률 가중치 높음
        - 내향형+신중형: 안정성과 비용효율성 가중치 높음
        
        위험등급(risk_tier)은 사용자 레벨별 필터링에만 사용됩니다.
        모든 지표는 객관적 데이터 기반으로 계산됩니다.
        """
    
    @classmethod
    def get_system_limitations(cls) -> str:
        """시스템 한계점 설명"""
        return """
        현재 시스템의 한계:
        
        • 과거 성과가 미래 성과를 보장하지 않습니다
        • 전문가 의견은 포함되지 않습니다
        
        투자 결정 시 추가적인 분석과 전문가 상담을 권장합니다.
        """
