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
        'etf_prices': 'data/ETF_시세_데이터_20230806_20250806.csv',
        'etf_performance': 'data/수익률 및 총보수(기간).csv',
        'etf_aum': 'data/자산규모 및 유동성(기간).csv',
        'etf_reference': 'data/참고지수(기간).csv',
        'etf_risk': 'data/투자위험(기간).csv',
        'risk_tier': 'data/etf_re_bp_simplified.csv',
        'cache': 'data/etf_scores_cache.csv'
    }
    
        # =============================================================================
    # WMTI 투자자 유형별 설명 
    # =============================================================================
    WMTI_TYPE_DESCRIPTIONS = {
        "APWL": {
            "name": "똘똘한 분산투자 능력자",
            "description": "뛰어난 금융지식과 능숙한 투자 방법론 보유로 자신감이 뛰어남. #미래지향 #능숙한 #성장주"
        },
        "APML": {
            "name": "타고난 리더형 투자 지도자",
            "description": "공격적인 투자방식을 보유로 기회와 리스크의 이해가 뛰어남. #리더형 #종목발굴 #분석적인"
        },
        "APWC": {
            "name": "당당하고 유능한 투자자",
            "description": "나만의 투자 원칙과 능숙한 투자 방법론 보유로 판단력이 뛰어남. #박학다식 #자신감 #분산투자"
        },
        "APMC": {
            "name": "박학다식한 투자의 달인",
            "description": "뛰어난 금융지식과 금융시장 분석능력으로 전략적인 판단력이 뛰어남. #전문가형 #대담함 #집중투자"
        },
        "ABWL": {
            "name": "통찰력있는 투자 예술인",
            "description": "뛰어난 직관력과 통찰력 보유로 탁월한 커뮤니케이션 능력이 있음. #자신감 #적극적인 #응용통성"
        },
        "ABML": {
            "name": "똑똑한 투자 트렌디세터",
            "description": "전략적인 투자 접근법과 해박한 지식을 보유하고 있음. #전략적인 #호기심 #재능있는"
        },
        "ABWC": {
            "name": "용감한 투자 탐정가",
            "description": "뛰어난 직관력과 통찰력 보유로 탁월한 커뮤니케이션 능력이 있음. #트렌디한 #보수적인 #장재학"
        },
        "ABMC": {
            "name": "시대를 앞서는 투자 리더",
            "description": "폭넓은 관심과 해박한 지식 보유로 현실적인 계획 수립 능력이 있음. #박학다식극적인 수익추구"
        },
        "IPWL": {
            "name": "노련한 투자의 아이콘",
            "description": "구체적인 투자 목표와 확실한 비전으로 현실적인 계획수립에 능함. #현실적인 #성장형 #합리적인"
        },
        "IPML": {
            "name": "전략적인 투자 연구자",
            "description": "호기심 많은 투자자로 현실적인 계획수립 능력이 있음. #도전적인 #가치주 #전략적인"
        },
        "IPWC": {
            "name": "다재다능한 투자 지휘관",
            "description": "구체적인 투자 목표와 확실한 비전으로 장기적인 안목과 판단력이 뛰어남. #섬세한 #도전적인 #자산배분"
        },
        "IPMC": {
            "name": "미래지향적 투자 탐험가",
            "description": "호기심 많은 투자자로 현실적인 계획수립 능력이 있음. #자신감 #주도적인 #통찰력"
        },
        "IBWL": {
            "name": "호기심 가득한 투자 관찰가",
            "description": "호기심이 많고 신중하며 투자에 대한 합리적인 분별력이 뛰어남. #안정적인 #잠재력 #분산투자"
        },
        "IBML": {
            "name": "도전을 즐기는 투자 샛별",
            "description": "뛰어난 정보력과 빠른 판단력으로 현실적인 계획수립 능력이 있음. #보수적인 #경험중시 #수익추구"
        },
        "IBWC": {
            "name": "잠재력있는 새싹 투자자",
            "description": "호기심많고 신중하며 안전자산에 관심이 많음. #꼼꼼한 #팔로워형 #자산배분"
        },
        "IBMC": {
            "name": "탐구하는 투자 탐색가",
            "description": "투자의 대한 완벽주의를 보이며 투자 잠재력이 뛰어남. #통찰력 #실용적인 #객관적인"
        }
    }

    # =============================================================================
    # WMTI 투자자 유형별 가중치 
    # 각 유형의 특성에 맞춰 가중치 조정
    # =============================================================================
    WMTI_TYPE_WEIGHTS = {
        # 외향형 + 전문가형 (공격적 투자 선호)
        "APWL": {"return_weight": 0.35, "risk_adjusted_return_weight": 0.30, "cost_efficiency_weight": 0.15, "liquidity_weight": 0.15, "stability_weight": 0.05},
        "APML": {"return_weight": 0.40, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.15, "liquidity_weight": 0.15, "stability_weight": 0.05},
        "APWC": {"return_weight": 0.35, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.20, "liquidity_weight": 0.15, "stability_weight": 0.05},
        "APMC": {"return_weight": 0.40, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.15, "liquidity_weight": 0.15, "stability_weight": 0.05},
        
        # 외향형 + 신중형 (균형적 투자 선호)
        "ABWL": {"return_weight": 0.30, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.20, "liquidity_weight": 0.15, "stability_weight": 0.10},
        "ABML": {"return_weight": 0.30, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.20, "liquidity_weight": 0.15, "stability_weight": 0.10},
        "ABWC": {"return_weight": 0.25, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.25, "liquidity_weight": 0.15, "stability_weight": 0.10},
        "ABMC": {"return_weight": 0.30, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.20, "liquidity_weight": 0.15, "stability_weight": 0.10},
        
        # 내향형 + 전문가형 (전략적 투자 선호)
        "IPWL": {"return_weight": 0.25, "risk_adjusted_return_weight": 0.30, "cost_efficiency_weight": 0.25, "liquidity_weight": 0.10, "stability_weight": 0.10},
        "IPML": {"return_weight": 0.30, "risk_adjusted_return_weight": 0.30, "cost_efficiency_weight": 0.20, "liquidity_weight": 0.10, "stability_weight": 0.10},
        "IPWC": {"return_weight": 0.25, "risk_adjusted_return_weight": 0.30, "cost_efficiency_weight": 0.25, "liquidity_weight": 0.10, "stability_weight": 0.10},
        "IPMC": {"return_weight": 0.30, "risk_adjusted_return_weight": 0.30, "cost_efficiency_weight": 0.20, "liquidity_weight": 0.10, "stability_weight": 0.10},
        
        # 내향형 + 신중형 (안정적 투자 선호)
        "IBWL": {"return_weight": 0.20, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.25, "liquidity_weight": 0.15, "stability_weight": 0.15},
        "IBML": {"return_weight": 0.25, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.25, "liquidity_weight": 0.15, "stability_weight": 0.10},
        "IBWC": {"return_weight": 0.20, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.30, "liquidity_weight": 0.15, "stability_weight": 0.10},
        "IBMC": {"return_weight": 0.25, "risk_adjusted_return_weight": 0.25, "cost_efficiency_weight": 0.25, "liquidity_weight": 0.15, "stability_weight": 0.10},
    }

    # =============================================================================
    # MPTI 스타일 정의
    # =============================================================================
    MPTI_STYLES = {
        'Fact': {
            'name': '팩트형',
            'description': '객관적 데이터와 사실에 기반한 설명을 선호합니다. 구체적인 수치, 통계, 검증 가능한 정보를 중심으로 설명하며, 주관적 판단보다는 객관적 사실을 중시합니다.',
            'prompt': '객관적 데이터와 사실에 기반하여 설명해주세요. 구체적인 수치, 통계, 검증 가능한 정보를 중심으로 설명하고, 주관적 판단보다는 객관적 사실을 중시하여 답변해주세요.',
            'transformations': {},
            'additions': [],
            'removals': []
        },
        'Opinion': {
            'name': '오피니언형',
            'description': '전문가의 관점과 주관적 분석을 포함한 설명을 선호합니다. 시장 분석가나 투자 전문가의 의견, 전망, 해석을 포함하여 종합적인 관점을 제공합니다.',
            'prompt': '전문가의 관점과 주관적 분석을 포함하여 설명해주세요. 시장 분석가나 투자 전문가의 의견, 전망, 해석을 포함하여 종합적인 관점을 제공해주세요.',
            'transformations': {},
            'additions': [],
            'removals': []
        },
        'Intensive': {
            'name': '집중형',
            'description': '핵심 정보만 간결하고 집중적으로 제공하는 설명을 선호합니다. 불필요한 부연설명을 줄이고 가장 중요한 포인트에 집중하여 명확하게 전달합니다.',
            'prompt': '핵심 정보만 간결하고 집중적으로 설명해주세요. 불필요한 부연설명을 줄이고 가장 중요한 포인트에 집중하여 명확하게 전달해주세요.',
            'transformations': {},
            'additions': [],
            'removals': []
        },
        'Extensive': {
            'name': '다각형',
            'description': '다양한 관점과 배경 정보를 포함한 포괄적인 설명을 선호합니다. 여러 각도에서 분석하고, 관련된 배경 정보와 맥락을 함께 제공합니다.',
            'prompt': '다양한 관점과 배경 정보를 포함하여 포괄적으로 설명해주세요. 여러 각도에서 분석하고, 관련된 배경 정보와 맥락을 함께 제공해주세요.',
            'transformations': {},
            'additions': [],
            'removals': []
        },
        'Skimming': {
            'name': '요약형',
            'description': '핵심 내용만 요약하여 빠르게 파악할 수 있는 설명을 선호합니다. 긴 설명보다는 핵심 포인트를 간단명료하게 정리하여 제공합니다.',
            'prompt': '핵심 내용만 요약하여 빠르게 파악할 수 있도록 설명해주세요. 긴 설명보다는 핵심 포인트를 간단명료하게 정리하여 제공해주세요.',
            'transformations': {},
            'additions': [],
            'removals': []
        },
        'Perusing': {
            'name': '상세형',
            'description': '상세한 분석과 배경 정보를 포함한 깊이 있는 설명을 선호합니다. 기술적 지표, 기본적 분석, 시장 동향을 종합적으로 고려한 심층 분석을 제공합니다.',
            'prompt': '상세한 분석과 배경 정보를 포함하여 깊이 있게 설명해주세요. 기술적 지표, 기본적 분석, 시장 동향을 종합적으로 고려한 심층 분석을 제공해주세요.',
            'transformations': {},
            'additions': [],
            'removals': []
        }
    }
    
    # =============================================================================
    # MPTI 투자자 유형별 설명 (MPTI_STYLES와 동일)
    # =============================================================================
    INVESTOR_TYPE_DESCRIPTIONS = MPTI_STYLES
    
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
       • 길이: 1-2줄로 핵심만 요약
       • 포함 요소: ETF의 가장 기본적인 특징 1-2개, 투자 시 주의사항 1개""",
       
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
        """MPTI 투자자 유형 설명 반환"""
        # MPTI 스타일인 경우
        if investor_type in cls.MPTI_STYLES:
            return cls.MPTI_STYLES[investor_type]['name']
        # WMTI 유형인 경우
        elif investor_type in cls.WMTI_TYPE_DESCRIPTIONS:
            return cls.WMTI_TYPE_DESCRIPTIONS[investor_type]['name']
        return "알 수 없는 유형"
    
    @classmethod
    def get_wmti_type_description(cls, wmti_type: str) -> str:
        """WMTI 투자자 유형 설명 반환 (추천용)"""
        wmti_info = cls.WMTI_TYPE_DESCRIPTIONS.get(wmti_type, {})
        if isinstance(wmti_info, dict):
            return f"{wmti_info.get('name', '알 수 없는 유형')} - {wmti_info.get('description', '')}"
        return str(wmti_info)
    
    @classmethod
    def get_risk_tier_limit(cls, level: int) -> int:
        """레벨별 risk_tier 허용 한계 반환"""
        return cls.LEVEL_RISK_TIER_LIMITS.get(level, 4)
    
    @classmethod
    def get_wmti_weights(cls, wmti_type: str) -> Dict[str, float]:
        """WMTI 투자자 유형별 가중치 반환"""
        return cls.WMTI_TYPE_WEIGHTS.get(wmti_type, {
            'return_weight': 0.30,
            'risk_adjusted_return_weight': 0.25,
            'cost_efficiency_weight': 0.20,
            'liquidity_weight': 0.15,
            'stability_weight': 0.10,
        })
    
    @classmethod
    def get_scoring_criteria(cls) -> str:
        """추천 점수 계산 기준 설명"""
        return """
        ETF 추천 점수 계산 기준:
        
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
        
        • 과거 성과가 미래 성과를 보장하지 않습니다.
        • 전문가 의견은 포함되지 않습니다.
    
        """
