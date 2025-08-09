"""
ETF 추천 엔진
- WMTI 기반 객관적 데이터 추천 시스템
- 사용자 레벨과 WMTI 투자 유형에 맞는 ETF 추천
- 캐시 기반 추천 시스템
- 점수 계산 기준
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Optional

# 공통 유틸리티 임포트
from .config import Config
from .utils import (
    safe_float, filter_dataframe_by_keyword, 
    validate_user_profile, create_error_result
)

# 로깅 설정
logger = logging.getLogger(__name__)

class ETFRecommendationEngine:
    """ETF 추천 엔진 클래스 (WMTI 기반)"""
    
    def __init__(self):
        """추천 엔진 초기화"""
        self.config = Config()
        logger.info("ETF 추천 엔진 초기화 완료 (WMTI 기반)")

    def fast_recommend_etfs(
        self,
        user_profile: Dict[str, Any],
        cache_df: pd.DataFrame,
        category_keyword: str = "",
        top_n: int = 5
    ) -> List[Dict[str, Any]]:
        """
        WMTI 기반 ETF 추천
        
        Args:
            user_profile: 사용자 프로필 {'level': int, 'wmti_type': str}
            cache_df: 사전 계산된 ETF 캐시 데이터
            category_keyword: 카테고리 키워드
            top_n: 추천할 ETF 개수
        
        Returns:
            추천 ETF 리스트 (Dict 형태)
        """
        try:
            # 캐시 데이터에서 중복 제거 (종목코드 기준)
            cache_df = cache_df.drop_duplicates(subset=['종목코드'], keep='first')
            logger.info(f"캐시 데이터 중복 제거 후: {len(cache_df)}개")
            
            logger.info(f"추천 시작: 키워드='{category_keyword}', top_n={top_n}, 사용자레벨={user_profile.get('level')}")
            logger.info(f"캐시 데이터 총 개수: {len(cache_df)}")
            
            # 1단계: 카테고리 필터링
            filtered = self._filter_by_category(cache_df, category_keyword)
            
            # 기초지수 기준 중복 제거 (같은 지수를 추종하는 ETF 중복 방지)
            before_dedup = len(filtered)
            if '기초지수' in filtered.columns:
                # 기초지수 이름 정규화 (공백, 괄호, 특수문자 제거)
                filtered['기초지수_정규화'] = filtered['기초지수'].str.replace(r'[\(\)\s]', '', regex=True).str.lower()
                filtered = filtered.drop_duplicates(subset=['기초지수_정규화'], keep='first')
                filtered = filtered.drop(columns=['기초지수_정규화'])
                logger.info(f"기초지수 기준 중복 제거: {before_dedup} → {len(filtered)}개")
            
            if filtered.empty:
                logger.warning(f"카테고리 '{category_keyword}'에 해당하는 ETF가 없습니다.")
                return [{
                    '안내': f"'{category_keyword}' 조건에 맞는 ETF를 찾을 수 없습니다. 다른 키워드로 다시 시도해보세요."
                }]

            # 2단계: 사용자 레벨 필터링 (WMTI는 추천 로직에만 사용)
            filtered = self._filter_by_user_level(filtered, user_profile)
            if filtered.empty:
                logger.warning(f"사용자 레벨에 맞는 ETF가 없습니다: {user_profile}")
                user_level = user_profile.get('level', '알 수 없음')
                return [{
                    '안내': f"현재 선택하신 투자 레벨(Level {user_level})에 적합한 ETF가 없습니다.\n\n- 투자 레벨을 변경해서 다시 시도해보시거나,\n- 카테고리 키워드를 바꿔서 검색해보세요.\n\n(일부 테마/섹터 ETF는 초보자에게 추천되지 않을 수 있습니다.)"
                }]

            # 3단계: WMTI 투자자 유형별 점수 계산 및 정렬
            scored_etfs = self._calculate_wmti_scores(filtered, user_profile)
            
            top_etfs = scored_etfs.head(top_n)
            
            wmti_type = user_profile.get('wmti_type', 'ABWC')
            logger.info(f"WMTI {wmti_type} 유형 기반 추천 완료: {len(top_etfs)}개 ETF")
            logger.info(f"추천된 ETF들: {list(top_etfs['종목명'])}")
            return top_etfs.to_dict('records')
        
        except Exception as e:
            logger.error(f"ETF 추천 중 오류 발생: {e}")
            return [{
                '안내': f"ETF 추천 중 오류가 발생했습니다: {e}"
            }]

    def _filter_by_category(self, cache_df: pd.DataFrame, category_keyword: str) -> pd.DataFrame:
        """
        카테고리 키워드로 ETF 필터링
        
        Args:
            cache_df: 캐시 데이터
            category_keyword: 카테고리 키워드
        
        Returns:
            필터링된 DataFrame
        """
        if not category_keyword.strip():
            return cache_df
        
        # 종목명, 분류체계, 기초지수에서 키워드 검색
        search_columns = ['종목명', 'ETF명', '분류체계', '기초지수']
        filtered = filter_dataframe_by_keyword(cache_df, category_keyword, search_columns)
        
        logger.info(f"카테고리 '{category_keyword}' 필터링: {len(cache_df)} → {len(filtered)}")
        return filtered

    def _filter_by_user_level(self, cache_df: pd.DataFrame, user_profile: Dict[str, Any]) -> pd.DataFrame:
        """
        사용자 레벨로 ETF 필터링 (위험도 기반)
        
        Args:
            cache_df: 카테고리 필터링된 데이터
            user_profile: 사용자 프로필
        
        Returns:
            사용자 레벨에 맞는 ETF DataFrame
        """
        user_level = self._normalize_user_level(user_profile.get('level'))
        risk_limit = self.config.get_risk_tier_limit(user_level)

        logger.info(f"사용자 레벨 필터링 시작: Level {user_level}, Risk Tier ≤ {risk_limit}")
        logger.info(f"필터링 전 ETF 개수: {len(cache_df)}")
        logger.info(f"사용 가능한 컬럼: {list(cache_df.columns)}")

        # 타입 강제 변환
        cache_df = cache_df.copy()
        cache_df['level'] = cache_df['level'].astype(int)
        
        # risk_tier가 있는 경우 위험도 필터링
        if 'risk_tier' in cache_df.columns:
            cache_df['risk_tier'] = pd.to_numeric(cache_df['risk_tier'], errors='coerce')
            filtered = cache_df[
                (cache_df['level'] == user_level) &
                (cache_df['risk_tier'] <= risk_limit)
            ]
            logger.info(f"위험도 필터링 적용: Level {user_level} AND Risk Tier ≤ {risk_limit}")
        else:
            # risk_tier가 없는 경우 레벨만 필터링
            filtered = cache_df[cache_df['level'] == user_level]
            logger.info(f"위험도 필터링 없음: Level {user_level}만 적용")
        
        logger.info(f"사용자 레벨 필터링 완료: {len(filtered)}개 ETF")
        if len(filtered) > 0:
            logger.info(f"필터링된 ETF들: {list(filtered['종목명'])}")
        
        return filtered

    def _normalize_user_level(self, user_level: Any) -> int:
        """
        사용자 레벨 정규화
        
        Args:
            user_level: 사용자 레벨 (int, str, 또는 기타)
        
        Returns:
            정규화된 레벨 (1-5)
        """
        validated_profile = validate_user_profile({'level': user_level})
        return validated_profile['level']

    def _calculate_wmti_scores(self, filtered_df: pd.DataFrame, user_profile: Dict[str, Any]) -> pd.DataFrame:
        """
        WMTI 투자자 유형별 점수 활용
        
        Args:
            filtered_df: 필터링된 ETF 데이터
            user_profile: 사용자 프로필
        
        Returns:
            점수가 계산된 DataFrame
        """
        df = filtered_df.copy()
        wmti_type = user_profile.get('wmti_type', 'ABWC')  # 기본값: 균형형
        
        # 해당 투자자 유형의 점수 컬럼명
        score_column = f'score_{wmti_type}'
        
        # 캐시에서 해당 투자자 유형의 점수 사용
        if score_column in df.columns:
            df['final_score'] = df[score_column]
            logger.info(f"캐시의 {wmti_type} 투자자 유형 점수 사용")
        else:
            # 해당 유형의 점수가 없는 경우 기본 점수 사용
            if 'total_score' in df.columns:
                df['final_score'] = df['total_score']
                logger.info(f"{wmti_type} 점수 없음, 기본 total_score 사용")
            else:
                # 개별 점수들로 계산
                df['return_score'] = df.apply(lambda row: self._calculate_return_score(row), axis=1)
                df['risk_adjusted_score'] = df.apply(lambda row: self._calculate_risk_adjusted_score(row), axis=1)
                df['cost_efficiency_score'] = df.apply(lambda row: self._calculate_cost_efficiency_score(row), axis=1)
                df['liquidity_score'] = df.apply(lambda row: self._calculate_liquidity_score(row), axis=1)
                df['stability_score'] = df.apply(lambda row: self._calculate_stability_score(row), axis=1)
                
                # WMTI 가중치 적용
                wmti_weights = self.config.get_wmti_weights(wmti_type)
                df['final_score'] = (
                    df['return_score'] * wmti_weights.get('return_weight', 0.3) +
                    df['risk_adjusted_score'] * wmti_weights.get('risk_adjusted_return_weight', 0.25) +
                    df['cost_efficiency_score'] * wmti_weights.get('cost_efficiency_weight', 0.2) +
                    df['liquidity_score'] * wmti_weights.get('liquidity_weight', 0.15) +
                    df['stability_score'] * wmti_weights.get('stability_weight', 0.1)
                )
                logger.info(f"개별 점수로 {wmti_type} 유형 점수 계산")
        
        # 점수 기준 내림차순 정렬
        scored_etfs = df.sort_values('final_score', ascending=False, na_position='last')
        
        logger.info(f"WMTI {wmti_type} 유형 점수 계산 완료: {len(scored_etfs)}개 ETF")
        return scored_etfs

    def _calculate_return_score(self, row: pd.Series) -> float:
        """수익률 점수 계산 (0-1)"""
        try:
            # 1년 수익률 우선, 없으면 3개월 수익률
            return_1y = safe_float(row.get('1년수익률'))
            return_3m = safe_float(row.get('3개월수익률'))
            
            if return_1y is not None:
                return max(0, min(1, (return_1y + 50) / 100))  # -50% ~ +50% 범위 정규화
            elif return_3m is not None:
                return max(0, min(1, (return_3m + 20) / 40))   # -20% ~ +20% 범위 정규화
            else:
                return 0.5  # 기본값
        except:
            return 0.5

    def _calculate_risk_adjusted_score(self, row: pd.Series) -> float:
        """위험조정수익률 점수 계산 (0-1)"""
        try:
            return_1y = safe_float(row.get('1년수익률'))
            volatility = safe_float(row.get('변동성'))
            
            if return_1y is not None and volatility is not None and volatility > 0:
                sharpe_ratio = return_1y / volatility
                return max(0, min(1, (sharpe_ratio + 2) / 4))  # -2 ~ +2 범위 정규화
            else:
                return 0.5
        except:
            return 0.5

    def _calculate_cost_efficiency_score(self, row: pd.Series) -> float:
        """비용효율성 점수 계산 (0-1) - 낮은 보수율이 높은 점수"""
        try:
            expense_ratio = safe_float(row.get('총보수'))
            
            if expense_ratio is not None:
                # 0% ~ 3% 범위에서 정규화 (낮을수록 높은 점수)
                return max(0, min(1, 1 - (expense_ratio / 3)))
            else:
                return 0.5
        except:
            return 0.5

    def _calculate_liquidity_score(self, row: pd.Series) -> float:
        """유동성 점수 계산 (0-1) - 높은 거래량이 높은 점수"""
        try:
            volume = safe_float(row.get('거래량'))
            
            if volume is not None:
                # 0 ~ 100만주 범위에서 정규화
                return max(0, min(1, volume / 1000000))
            else:
                return 0.5
        except:
            return 0.5

    def _calculate_stability_score(self, row: pd.Series) -> float:
        """안정성 점수 계산 (0-1) - 자산규모 기반 안정성"""
        try:
            aum = safe_float(row.get('자산규모'))
            
            if aum is not None:
                # 0 ~ 1000억원 범위에서 정규화 (높을수록 안정적)
                return max(0, min(1, aum / 100000000000))  # 1000억원 기준
            else:
                return 0.5
        except:
            return 0.5

    def generate_recommendation_explanation(
        self,
        recommendations: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        category_keyword: str,
        context_docs: Optional[List[str]] = None
    ) -> str:
        """
        추천 결과에 대한 설명 프롬프트 생성 (MPTI 기반 설명)
        
        Args:
            recommendations: 추천된 ETF 리스트
            user_profile: 사용자 프로필
            category_keyword: 카테고리 키워드
            context_docs: 추가 참고 문서 (사용되지 않음)
        
        Returns:
            LLM용 설명 프롬프트
        """
        if not recommendations:
            return "해당 조건에 맞는 ETF를 찾을 수 없습니다. 다른 키워드로 다시 시도해보세요."
        
        # ETF 정보 포맷팅
        etf_info_list = []
        for i, rec in enumerate(recommendations, 1):
            etf_name = rec.get('ETF명', 'N/A')
            final_score = rec.get('final_score', 0)
            return_score = rec.get('return_score', 0)
            risk_adjusted_score = rec.get('risk_adjusted_score', 0)
            cost_efficiency_score = rec.get('cost_efficiency_score', 0)
            classification = rec.get('분류체계', 'N/A')
            reference_index = rec.get('기초지수', 'N/A')
            risk_tier = rec.get('risk_tier', 'N/A')
            
            etf_info_list.append(f"""
{i}위: {etf_name}
- 최종점수: {final_score:.3f}
- 수익률점수: {return_score:.3f}, 위험조정점수: {risk_adjusted_score:.3f}, 비용효율점수: {cost_efficiency_score:.3f}
- 위험등급: {risk_tier}
- 분류체계: {classification}
- 기초지수: {reference_index}
""")
        
        etf_info_text = "\n".join(etf_info_list)
        
        # 프롬프트 생성 (MPTI 기반 설명)
        user_level = self._normalize_user_level(user_profile.get('level'))
        mpti_type = user_profile.get('investor_type', 'IFSA')  # MPTI는 설명용
        wmti_type = user_profile.get('wmti_type', 'BALANCED')  # WMTI는 추천용
        mpti_description = self.config.get_investor_type_description(mpti_type)
        wmti_description = self.config.get_wmti_type_description(wmti_type)
        
        prompt = f"""{self.config.get_recommendation_prompt(user_profile)}

사용자 정보:
- 요청 카테고리: {category_keyword if category_keyword else "ETF 추천"}
- 사용자 레벨: Level {user_level}
- MPTI 유형: {mpti_type} ({mpti_description}) - 설명 스타일용
- WMTI 유형: {wmti_type} ({wmti_description}) - 추천 로직용

추천 기준:
{self.config.get_scoring_criteria()}

추천 ETF 목록:
{etf_info_text}

위 추천 ETF들에 대해 다음을 포함하여 설명해주세요:
1. 각 ETF의 주요 특징과 장점 (MPTI 유형에 맞는 설명 스타일)
2. WMTI 유형에 맞는 추천 이유
3. 투자 시 고려사항과 주의점
4. 사용자 레벨에 맞는 실전 투자 팁
5. 분류체계와 참고지수를 고려한 정확한 분석

시스템 한계:
{self.config.get_system_limitations()}
"""
        
        return prompt
