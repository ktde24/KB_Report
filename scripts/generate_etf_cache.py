"""
ETF 캐시 데이터 생성 스크립트 (WMTI 투자자 유형별)
- 객관적 데이터 기반 ETF 점수 계산
- WMTI 투자자 유형별 가중치 적용
- 캐시 파일 생성
"""

import pandas as pd
import numpy as np
import logging
import os
import sys
from typing import Dict, List, Any
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot.config import Config
from chatbot.utils import safe_float, safe_int

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ETFCacheGenerator:
    """ETF 캐시 데이터 생성기"""
    
    def __init__(self):
        """초기화"""
        self.config = Config()
        self.data_paths = self.config.DATA_PATHS
        
    def generate_cache(self) -> pd.DataFrame:
        """
        ETF 캐시 데이터 생성
        
        Returns:
            캐시 데이터 DataFrame
        """
        try:
            logger.info("ETF 캐시 데이터 생성 시작")
            
            # 1. 기본 데이터 로드
            etf_info = self._load_etf_info()
            etf_performance = self._load_etf_performance()
            etf_aum = self._load_etf_aum()
            etf_risk = self._load_etf_risk()
            risk_tier_data = self._load_risk_tier_data()
            
            # 2. 데이터 통합
            merged_data = self._merge_data(etf_info, etf_performance, etf_aum, etf_risk, risk_tier_data)
            
            # 3. 객관적 점수 계산
            scored_data = self._calculate_objective_scores(merged_data)
            
            # 4. WMTI 타입별 점수 계산
            wmti_scored_data = self._calculate_wmti_type_scores(scored_data)
            
            # 5. 레벨별 필터링
            final_data = self._apply_level_filters(wmti_scored_data)
            
            logger.info(f"캐시 데이터 생성 완료: {len(final_data)}개 ETF")
            return final_data
            
        except Exception as e:
            logger.error(f"캐시 데이터 생성 중 오류: {e}")
            raise
    
    def _load_etf_info(self) -> pd.DataFrame:
        """ETF 기본 정보 로드"""
        try:
            file_path = self.data_paths['etf_info']
            # 상품검색.csv 인코딩
            for encoding in ['utf-8', 'cp949', 'euc-kr', 'latin1']:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    logger.info(f"ETF 기본 정보 로드: {len(df)}개 (인코딩: {encoding})")
                    return df
                except:
                    continue
            
            logger.error(f"ETF 기본 정보 로드 실패: 모든 인코딩 시도 실패")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"ETF 기본 정보 로드 실패: {e}")
            return pd.DataFrame()
    
    def _load_etf_performance(self) -> pd.DataFrame:
        """ETF 성과 데이터 로드"""
        try:
            file_path = self.data_paths['etf_performance']
            df = pd.read_csv(file_path, encoding='utf-8')
            logger.info(f"ETF 성과 데이터 로드: {len(df)}개")
            return df
        except Exception as e:
            logger.error(f"ETF 성과 데이터 로드 실패: {e}")
            return pd.DataFrame()
    
    def _load_etf_aum(self) -> pd.DataFrame:
        """ETF 자산규모 데이터 로드"""
        try:
            file_path = self.data_paths['etf_aum']
            df = pd.read_csv(file_path, encoding='utf-8')
            logger.info(f"ETF 자산규모 데이터 로드: {len(df)}개")
            return df
        except Exception as e:
            logger.error(f"ETF 자산규모 데이터 로드 실패: {e}")
            return pd.DataFrame()
    
    def _load_etf_risk(self) -> pd.DataFrame:
        """ETF 위험 데이터 로드"""
        try:
            file_path = self.data_paths['etf_risk']
            df = pd.read_csv(file_path, encoding='utf-8')
            logger.info(f"ETF 위험 데이터 로드: {len(df)}개")
            return df
        except Exception as e:
            logger.error(f"ETF 위험 데이터 로드 실패: {e}")
            return pd.DataFrame()
    
    def _load_risk_tier_data(self) -> pd.DataFrame:
        """ETF 위험등급 데이터 로드"""
        try:
            file_path = self.data_paths['risk_tier']
            df = pd.read_csv(file_path, encoding='utf-8', low_memory=False)
            # 필요한 컬럼만 선택 (종목코드, 종목명, risk_tier)
            if '종목명' in df.columns and 'risk_tier' in df.columns:
                df = df[['종목명', 'risk_tier']].copy()
            elif 'itmsNm' in df.columns and 'risk_tier' in df.columns:
                df = df[['itmsNm', 'risk_tier']].copy()
                df.columns = ['종목명', 'risk_tier']
            else:
                # risk_tier 컬럼이 없으면 기본값 설정
                if '종목명' in df.columns:
                    df = df[['종목명']].copy()
                    df['risk_tier'] = 3  # 기본값
                else:
                    logger.warning("risk_tier 데이터에서 필요한 컬럼을 찾을 수 없습니다.")
                    return pd.DataFrame()
            
            # 중복 제거 (종목명 기준)
            df = df.drop_duplicates(subset=['종목명'], keep='first')
            
            logger.info(f"ETF 위험등급 데이터 로드: {len(df)}개")
            return df
        except Exception as e:
            logger.error(f"ETF 위험등급 데이터 로드 실패: {e}")
            return pd.DataFrame()
    
    def _merge_data(self, info_df: pd.DataFrame, perf_df: pd.DataFrame, 
                   aum_df: pd.DataFrame, risk_df: pd.DataFrame, risk_tier_df: pd.DataFrame) -> pd.DataFrame:
        """데이터 통합"""
        try:
            # 종목명을 기준으로 데이터 통합
            merged = info_df.copy()
            
            if not perf_df.empty:
                merged = merged.merge(perf_df, on='종목명', how='left', suffixes=('', '_perf'))
            
            if not aum_df.empty:
                merged = merged.merge(aum_df, on='종목명', how='left', suffixes=('', '_aum'))
            
            if not risk_df.empty:
                merged = merged.merge(risk_df, on='종목명', how='left', suffixes=('', '_risk'))
            
            if not risk_tier_df.empty:
                merged = merged.merge(risk_tier_df, on='종목명', how='left', suffixes=('', '_tier'))
            
            # risk_tier가 없는 경우 기본값 설정
            if 'risk_tier' not in merged.columns:
                merged['risk_tier'] = 3  # 기본값: 중간 위험도
            
            logger.info(f"데이터 통합 완료: {len(merged)}개 ETF")
            return merged
            
        except Exception as e:
            logger.error(f"데이터 통합 실패: {e}")
            return info_df
    
    def _calculate_objective_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """점수 계산 (투자자 유형별)"""
        df = df.copy()
        
        # 1. 수익률 점수 (0-1)
        df['return_score'] = df.apply(self._calculate_return_score, axis=1)
        
        # 2. 위험조정수익률 점수 (0-1)
        df['risk_adjusted_score'] = df.apply(self._calculate_risk_adjusted_score, axis=1)
        
        # 3. 비용효율성 점수 (0-1)
        df['cost_efficiency_score'] = df.apply(self._calculate_cost_efficiency_score, axis=1)
        
        # 4. 유동성 점수 (0-1)
        df['liquidity_score'] = df.apply(self._calculate_liquidity_score, axis=1)
        
        # 5. 안정성 점수 (0-1)
        df['stability_score'] = df.apply(self._calculate_stability_score, axis=1)
        
        # 6. WMTI 투자자 유형별 점수 계산
        df = self._calculate_wmti_type_scores(df)
        
        logger.info("투자자 유형별 점수 계산 완료")
        return df
    
    def _calculate_return_score(self, row: pd.Series) -> float:
        """수익률 점수 계산"""
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
        """위험조정수익률 점수 계산"""
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
        """비용효율성 점수 계산"""
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
        """유동성 점수 계산"""
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
        """안정성 점수 계산 (자산규모 기반)"""
        try:
            aum = safe_float(row.get('자산규모'))
            
            if aum is not None:
                # 0 ~ 1000억원 범위에서 정규화 (높을수록 높은 점수)
                return max(0, min(1, aum / 10000000000))  # 1000억원으로 정규화
            else:
                return 0.5
        except:
            return 0.5
    
    def _calculate_wmti_type_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """WMTI 투자자 유형별 점수 계산"""
        df = df.copy()
        
        # WMTI 투자자 유형별 가중치 가져오기
        wmti_weights = self.config.WMTI_TYPE_WEIGHTS
        
        # 각 투자자 유형별로 점수 계산
        for wmti_type, weights in wmti_weights.items():
            score_column = f'score_{wmti_type}'
            df[score_column] = (
                df['return_score'] * weights['return_weight'] +
                df['risk_adjusted_score'] * weights['risk_adjusted_return_weight'] +
                df['cost_efficiency_score'] * weights['cost_efficiency_weight'] +
                df['liquidity_score'] * weights['liquidity_weight'] +
                df['stability_score'] * weights['stability_weight']
            )
        
        # 기본 점수 (균형형 가중치)
        df['total_score'] = (
            df['return_score'] * 0.3 +
            df['risk_adjusted_score'] * 0.25 +
            df['cost_efficiency_score'] * 0.20 +
            df['liquidity_score'] * 0.15 +
            df['stability_score'] * 0.10
        )
        
        logger.info(f"WMTI 투자자 유형별 점수 계산 완료: {len(wmti_weights)}개 유형")
        return df
    
    def _apply_level_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """레벨별 필터링 적용 및 최종 컬럼 정리"""
        df = df.copy()
        
        # 레벨별 위험도 필터링
        for level in range(1, 6):
            risk_limit = self.config.get_risk_tier_limit(level)
            
            # 해당 레벨에 적합한 ETF 필터링
            level_mask = df['risk_tier'] <= risk_limit
            df.loc[level_mask, 'level'] = level
        
        # 레벨이 없는 ETF는 Level 3으로 설정
        df['level'] = df['level'].fillna(3)
        
        # 캐시에 포함할 컬럼만 선택
        cache_columns = [
            '종목명', '종목코드', '분류체계', '기초지수', '운용사',
            'return_score', 'risk_adjusted_score', 'cost_efficiency_score', 
            'liquidity_score', 'stability_score', 'total_score',
            'risk_tier', 'level', '자산규모', '거래량', '변동성', '총보수'
        ]
        
        # WMTI 투자자 유형별 점수 컬럼 추가
        wmti_score_columns = [f'score_{wmti_type}' for wmti_type in self.config.WMTI_TYPE_WEIGHTS.keys()]
        cache_columns.extend(wmti_score_columns)
        
        # 존재하는 컬럼만 선택
        available_columns = [col for col in cache_columns if col in df.columns]
        df = df[available_columns]
        
        logger.info("레벨별 필터링 및 컬럼 정리 완료")
        return df
    
    def save_cache(self, df: pd.DataFrame, file_path: str = None):
        """캐시 파일 저장"""
        if file_path is None:
            file_path = self.data_paths['cache']
        
        try:
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            logger.info(f"캐시 파일 저장 완료: {file_path}")
        except Exception as e:
            logger.error(f"캐시 파일 저장 실패: {e}")
            raise

def main():
    """메인 실행 함수"""
    try:
        generator = ETFCacheGenerator()
        cache_data = generator.generate_cache()
        generator.save_cache(cache_data)
        
        print(f"ETF 캐시 생성 완료: {len(cache_data)}개 ETF")
        print(f"점수 분포:")
        print(f"   - 평균 total_score: {cache_data['total_score'].mean():.3f}")
        print(f"   - 최고 total_score: {cache_data['total_score'].max():.3f}")
        print(f"   - 최저 total_score: {cache_data['total_score'].min():.3f}")
        
    except Exception as e:
        print(f"캐시 생성 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 