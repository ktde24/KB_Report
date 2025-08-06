"""
ETF 점수 캐시 생성 스크립트
- 모든 ETF에 대해 레벨별, 투자자 유형별 점수를 사전 계산
- risk_tier 기반 레벨별 필터링 적용

주요 기능:
1. ETF 기본 정보 및 시세 데이터 로딩
2. 개별 ETF 분석 및 기본 점수 계산
3. 투자자 유형별 가중치 적용
4. 레벨별 위험도 필터링
5. 멀티스레딩을 통한 병렬 처리
6. 캐시 파일 생성 및 저장
"""

import sys
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Tuple, List

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from chatbot.recommendation_engine import ETFRecommendationEngine
from chatbot.etf_analysis import analyze_etf
from chatbot.config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ETFCacheBuilder:
    """
    ETF 캐시 빌더 클래스
    
    모든 ETF에 대해 사용자 레벨별, 투자자 유형별 점수를 사전 계산하여
    추천 시스템의 응답 속도를 향상시키는 캐시를 생성합니다.
    """
    
    def __init__(self):
        """캐시 빌더 초기화"""
        self.config = Config()
        self.recommendation_engine = ETFRecommendationEngine()
        self.data = {}  # 로드된 데이터 저장
        
    def load_data(self):
        """
        모든 필요한 데이터 로드
        
        로드하는 데이터:
        - ETF 기본 정보 (종목명, 종목코드, 분류체계 등)
        - 시세 데이터 (수익률, 변동성 계산용)
        - 성과 데이터 (수익률, 보수 정보)
        - 자산규모 데이터 (AUM, 거래량)
        - 참고지수 데이터 (기초지수 정보)
        - 위험도 데이터 (변동성 등급)
        - Risk tier 데이터 (위험도 분류)
        """
        logger.info("데이터 로딩 시작")
        
        try:
            # 기본 ETF 데이터 타입 정의
            data_types = {
                'info': 'etf_info',           # ETF 기본 정보
                'prices': 'etf_prices',       # 시세 데이터
                'performance': 'etf_performance',  # 성과 데이터
                'aum': 'etf_aum',             # 자산규모 데이터
                'reference': 'etf_reference', # 참고지수 데이터
                'risk': 'etf_risk'            # 위험도 데이터
            }
            
            # 각 데이터 타입별로 파일 로드
            for key, data_type in data_types.items():
                file_path = self.config.get_data_path(data_type)
                if os.path.exists(file_path):
                    if key == 'prices':
                        # 시세 데이터는 메모리 효율성을 위해 타입 지정
                        self.data[key] = pd.read_csv(
                            file_path, encoding='utf-8-sig',
                            dtype={'srtnCd': str, 'basDt': str, 'clpr': float},
                            low_memory=False
                        )
                    else:
                        self.data[key] = pd.read_csv(file_path, encoding='utf-8-sig')
                    
                    logger.info(f"{key} 데이터 로딩 완료: {len(self.data[key])}행")
                else:
                    logger.error(f"{key} 파일을 찾을 수 없습니다: {file_path}")
                    raise FileNotFoundError(f"Required file not found: {file_path}")
            
            # Risk tier 데이터 로드 (위험도 분류 결과)
            risk_tier_path = self.config.get_data_path('risk_tier')
            if os.path.exists(risk_tier_path):
                self.data['risk_tier'] = pd.read_csv(risk_tier_path, encoding='utf-8-sig')
                # 날짜 컬럼을 datetime으로 변환
                self.data['risk_tier']['basDt'] = pd.to_datetime(self.data['risk_tier']['basDt'])
                logger.info(f"Risk tier 데이터 로딩 완료: {len(self.data['risk_tier'])}행")
            else:
                logger.error(f"Risk tier 파일을 찾을 수 없습니다: {risk_tier_path}")
                raise FileNotFoundError(f"Risk tier file not found: {risk_tier_path}")
            
        except Exception as e:
            logger.error(f"데이터 로딩 중 오류: {e}")
            raise

    def get_latest_risk_tier(self, etf_code: str) -> int:
        """
        ETF의 최신 risk_tier 조회
        
        Args:
            etf_code: ETF 종목코드
        
        Returns:
            risk_tier (-1: 측정불가, 0~4: 위험등급)
                - -1: 측정불가 (데이터 부족)
                - 0: 매우 안전
                - 1: 안전
                - 2: 보통
                - 3: 위험
                - 4: 매우 위험
        """
        try:
            # 해당 ETF의 risk_tier 데이터 조회
            etf_risk_data = self.data['risk_tier'][
                self.data['risk_tier']['srtnCd'].astype(str).str.strip() == str(etf_code).strip()
            ]
            
            if etf_risk_data.empty:
                return -1  # 측정불가
            
            # 최신 날짜의 risk_tier 반환
            latest_data = etf_risk_data.loc[etf_risk_data['basDt'].idxmax()]
            risk_tier = latest_data.get('risk_tier', -1)
            
            # 유효한 risk_tier 값 확인
            if pd.isna(risk_tier) or not isinstance(risk_tier, (int, float)) or risk_tier < 0:
                return -1
            
            return int(risk_tier)
            
        except Exception as e:
            logger.warning(f"ETF {etf_code}의 risk_tier 조회 오류: {e}")
            return -1

    def process_single_etf(self, etf_row: pd.Series) -> List[Dict[str, Any]]:
        """
        단일 ETF에 대한 모든 조합 처리
        
        각 ETF에 대해 다음 조합을 생성:
        - 3개 레벨 (Level 1, 2, 3, 4, 5)
        - 16개 투자자 유형
        - 총 48개 조합 per ETF
        
        Args:
            etf_row: ETF 기본 정보 (종목명, 종목코드 등)
        
        Returns:
            처리된 레코드 리스트 (최대 48개)
        """
        etf_name = etf_row['종목명']
        etf_code = etf_row.get('단축코드', etf_row.get('종목코드', ''))
        
        try:
            # ETF 분석 수행 (기본 프로필 사용)
            base_profile = {"level": 1, "wmti_type": "ABWC"}
            etf_info = analyze_etf(
                etf_name, base_profile,
                self.data['prices'], self.data['info'],
                self.data['performance'], self.data['aum'],
                self.data['reference'], self.data['risk']
            )
            
            # 분석 실패시 빈 리스트 반환
            if etf_info is None or (isinstance(etf_info, dict) and etf_info.get('설명')):
                return []
            
            # 기본 점수 계산 (수익률, 비용, 유동성, 변동성 종합)
            base_score = self._calculate_base_score(etf_info)
            
            # Risk tier 조회 (위험도 등급)
            risk_tier = self.get_latest_risk_tier(etf_code)
            
            records = []
            
            # 모든 레벨과 투자자 유형 조합 생성
            for level in [1, 2, 3, 4, 5]:
                # 레벨별 risk_tier 제한 확인
                risk_limit = self.config.get_risk_tier_limit(level)
                
                # risk_tier 필터링 적용
                if risk_tier == -1:  # 측정불가
                    # Level 1은 측정불가 제외, Level 2,3은 포함
                    if level == 1:
                        continue
                    effective_score = base_score * 0.5 
                elif risk_tier > risk_limit:
                    # 해당 레벨 제한 초과시 제외
                    continue
                else:
                    effective_score = base_score
                
                # 모든 WMTI 투자자 유형에 대해 처리
                for wmti_type in self.config.WMTI_TYPE_WEIGHTS.keys():
                    # WMTI 투자자 유형별 가중치 적용
                    wmti_weights = self.config.get_wmti_weights(wmti_type)
                    
                    # 개별 지표 점수 계산
                    return_score = self._normalize_return_score(etf_info.get('시세분석', {}))
                    risk_adjusted_score = self._calculate_risk_adjusted_score(etf_info)
                    cost_efficiency_score = self._normalize_fee_score(etf_info.get('수익률/보수', {}))
                    liquidity_score = self._normalize_volume_score(etf_info.get('자산규모/유동성', {}))
                    stability_score = self._normalize_stability_score(etf_info.get('자산규모/유동성', {}))
                    
                    # WMTI 가중치 적용한 최종 점수 계산
                    final_score = (
                        return_score * wmti_weights.get('return_weight', 0.3) +
                        risk_adjusted_score * wmti_weights.get('risk_adjusted_return_weight', 0.25) +
                        cost_efficiency_score * wmti_weights.get('cost_efficiency_weight', 0.2) +
                        liquidity_score * wmti_weights.get('liquidity_weight', 0.15) +
                        stability_score * wmti_weights.get('stability_weight', 0.1)
                    ) * effective_score
                    
                    # 레코드 생성
                    record = self._create_record(
                        etf_row, etf_info, level, wmti_type,
                        base_score, final_score, risk_tier
                    )
                    records.append(record)
            
            return records
            
        except Exception as e:
            logger.error(f"ETF {etf_name} 처리 중 오류: {e}")
            return []

    def _calculate_base_score(self, etf_info: Dict[str, Any]) -> float:
        """
        ETF 기본 점수 계산
        
        다음 요소들을 종합하여 0.0~1.0 사이의 점수 계산:
        - 수익률 (40%): 1년, 3개월, 1개월 수익률
        - 비용 (20%): 총보수 (낮을수록 높은 점수)
        - 유동성 (20%): 거래량 (높을수록 높은 점수)
        - 변동성 (20%): 변동성 등급 (낮을수록 높은 점수)
        
        Args:
            etf_info: ETF 분석 정보
        
        Returns:
            기본 점수 (0.0~1.0)
        """
        try:
            # 각 요소별 점수 계산
            return_score = self._normalize_return_score(etf_info.get('시세분석', {}))
            fee_score = self._normalize_fee_score(etf_info.get('수익률/보수', {}))
            volume_score = self._normalize_volume_score(etf_info.get('자산규모/유동성', {}))
            volatility_score = self._normalize_volatility_score(etf_info.get('위험', {}))
            
            # 가중합 계산
            base_score = (
                return_score * 0.4 +      # 수익률 40%
                fee_score * 0.2 +         # 총보수 20% 
                volume_score * 0.2 +      # 거래량 20%
                volatility_score * 0.2    # 변동성 20%
            )
            
            return max(0.0, min(1.0, base_score))
            
        except Exception as e:
            logger.warning(f"기본 점수 계산 오류: {e}")
            return 0.5  # 기본값

    def _normalize_return_score(self, market_data: Dict) -> float:
        """
        수익률 정규화 (1년 > 3개월 > 1개월 순)
        
        Args:
            market_data: 시세 분석 데이터
        
        Returns:
            정규화된 수익률 점수 (0.0~1.0)
        """
        returns = [
            market_data.get('1년 수익률'),
            market_data.get('3개월 수익률'), 
            market_data.get('1개월 수익률')
        ]
        
        for ret in returns:
            if ret is not None and not pd.isna(ret):
                # -100% ~ +100% → 0~1로 정규화
                return max(0, min(1, (ret + 100) / 200))
        
        return 0.5  # 기본값

    def _normalize_fee_score(self, perf_data: Dict) -> float:
        """
        총보수 정규화 (낮을수록 좋음)
        
        Args:
            perf_data: 성과 데이터
        
        Returns:
            정규화된 비용 점수 (0.0~1.0)
        """
        fee = perf_data.get('총 보수')
        if fee is None or pd.isna(fee):
            return 0.5
        
        try:
            fee_val = float(fee)
            # 0~10% → 1~0 (낮을수록 높은 점수)
            return max(0, min(1, 1 - (fee_val / 10)))
        except (ValueError, TypeError):
            return 0.5

    def _normalize_volume_score(self, aum_data: Dict) -> float:
        """
        거래량 정규화
        
        Args:
            aum_data: 자산규모/유동성 데이터
        
        Returns:
            정규화된 거래량 점수 (0.0~1.0)
        """
        volume = aum_data.get('평균 거래량')
        if volume is None or pd.isna(volume):
            return 0.5
        
        try:
            volume_val = float(volume)
            # 0~100만주 → 0~1로 정규화
            return max(0, min(1, volume_val / 1000000))
        except (ValueError, TypeError):
            return 0.5

    def _normalize_volatility_score(self, risk_data: Dict) -> float:
        """
        변동성 정규화
        
        Args:
            risk_data: 위험도 데이터
        
        Returns:
            정규화된 변동성 점수 (0.0~1.0)
        """
        volatility = risk_data.get('변동성', '보통')
        grade_scores = {
            '매우낮음': 0.2, '낮음': 0.4, '보통': 0.6, 
            '높음': 0.8, '매우높음': 1.0
        }
        return grade_scores.get(volatility, 0.6)
    
    def _calculate_risk_adjusted_score(self, etf_info: Dict[str, Any]) -> float:
        """
        위험조정수익률 점수 계산
        
        Args:
            etf_info: ETF 분석 정보
        
        Returns:
            위험조정수익률 점수 (0.0~1.0)
        """
        try:
            market_data = etf_info.get('시세분석', {})
            risk_data = etf_info.get('위험', {})
            
            # 1년 수익률
            return_1y = market_data.get('1년 수익률')
            if return_1y is None or pd.isna(return_1y):
                return 0.5
            
            # 변동성 (숫자로 변환)
            volatility_str = risk_data.get('변동성', '보통')
            volatility_map = {
                '매우낮음': 0.05, '낮음': 0.1, '보통': 0.15, 
                '높음': 0.25, '매우높음': 0.4
            }
            volatility = volatility_map.get(volatility_str, 0.15)
            
            if volatility > 0:
                sharpe_ratio = return_1y / volatility
                # -2 ~ +2 범위에서 정규화
                return max(0, min(1, (sharpe_ratio + 2) / 4))
            else:
                return 0.5
                
        except Exception as e:
            logger.warning(f"위험조정수익률 점수 계산 오류: {e}")
            return 0.5
    
    def _normalize_stability_score(self, aum_data: Dict) -> float:
        """
        안정성 점수 계산 (자산규모 기반)
        
        Args:
            aum_data: 자산규모/유동성 데이터
        
        Returns:
            정규화된 안정성 점수 (0.0~1.0)
        """
        aum = aum_data.get('자산규모')
        if aum is None or pd.isna(aum):
            return 0.5
        
        try:
            # 문자열에서 숫자 추출
            if isinstance(aum, str):
                # "1,234억원" 형태 처리
                aum_str = aum.replace('억원', '').replace(',', '')
                aum_val = float(aum_str) * 100000000  # 억원을 원으로 변환
            else:
                aum_val = float(aum)
            
            # 0 ~ 1000억원 범위에서 정규화
            return max(0, min(1, aum_val / 100000000000))  # 1000억원 기준
            
        except (ValueError, TypeError):
            return 0.5

    def _create_record(
        self, 
        etf_row: pd.Series, 
        etf_info: Dict[str, Any],
        level: int, 
        wmti_type: str,
        base_score: float, 
        final_score: float,
        risk_tier: int
    ) -> Dict[str, Any]:
        """
        캐시 레코드 생성
        
        Args:
            etf_row: ETF 기본 정보
            etf_info: ETF 분석 정보
            level: 사용자 레벨
            wmti_type: WMTI 투자자 유형
            base_score: 기본 점수
            final_score: 최종 점수
            risk_tier: 위험도 등급
        
        Returns:
            캐시 레코드 딕셔너리
        """
        return {
            # ETF 기본 정보
            'ETF명': etf_row['종목명'],
            '종목코드': etf_row.get('단축코드', etf_row.get('종목코드', '')),
            '분류체계': etf_row.get('분류체계', ''),
            '기초지수': etf_row.get('기초지수', ''),
            
            # 사용자 프로필
            'level': level,
            'wmti_type': wmti_type,
            
            # 점수 정보
            'base_score': round(base_score, 4),
            'final_score': round(final_score, 4),
            'risk_tier': risk_tier,
            
            # 추가 메타데이터 (추천 시 참고용)
            '자산규모': etf_info.get('자산규모/유동성', {}).get('자산규모'),
            '거래량': etf_info.get('자산규모/유동성', {}).get('평균 거래량'),
            '변동성': etf_info.get('위험', {}).get('변동성'),
            '총보수': etf_info.get('수익률/보수', {}).get('총 보수'),
        }

    def build_cache(self, max_workers: int = 4) -> pd.DataFrame:
        """
        ETF 캐시 빌드 (멀티스레딩 사용)
        
        모든 ETF에 대해 병렬로 점수를 계산하여 캐시를 생성합니다.
        
        Args:
            max_workers: 최대 워커 수 (CPU 코어 수에 따라 조정)
        
        Returns:
            완성된 캐시 DataFrame
        """
        logger.info("ETF 캐시 빌드 시작")
        start_time = time.time()
        
        # ETF 목록 준비
        etf_list = self.data['info'].copy()
        total_etfs = len(etf_list)
        
        all_records = []
        completed = 0
        
        # 멀티스레딩으로 처리
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 모든 ETF에 대해 작업 제출
            future_to_etf = {
                executor.submit(self.process_single_etf, row): idx 
                for idx, (_, row) in enumerate(etf_list.iterrows())
            }
            
            # 결과 수집
            for future in as_completed(future_to_etf):
                try:
                    records = future.result()
                    all_records.extend(records)
                    completed += 1
                    
                    # 진행률 출력 (50개마다)
                    if completed % 50 == 0:
                        progress = (completed / total_etfs) * 100
                        elapsed = time.time() - start_time
                        logger.info(f"진행률: {progress:.1f}% ({completed}/{total_etfs}) - {elapsed:.1f}초 경과")
                        
                except Exception as e:
                    logger.error(f"ETF 처리 중 오류: {e}")
                    completed += 1
        
        # DataFrame 생성
        cache_df = pd.DataFrame(all_records)
        
        # 통계 출력
        elapsed_time = time.time() - start_time
        logger.info(f"캐시 빌드 완료: {len(cache_df)}개 레코드, {elapsed_time:.1f}초 소요")
        logger.info(f"레벨별 분포: {cache_df['level'].value_counts().to_dict()}")
        logger.info(f"Risk tier별 분포: {cache_df['risk_tier'].value_counts().to_dict()}")
        
        return cache_df

    def save_cache(self, cache_df: pd.DataFrame):
        """
        캐시를 파일로 저장
        
        Args:
            cache_df: 저장할 캐시 DataFrame
        """
        cache_path = self.config.get_data_path('cache')
        
        try:
            cache_df.to_csv(cache_path, index=False, encoding='utf-8-sig')
            logger.info(f"캐시 저장 완료: {cache_path} ({len(cache_df)}개 레코드)")
            
            # 파일 크기 출력
            file_size = os.path.getsize(cache_path) / (1024 * 1024)  # MB
            logger.info(f"파일 크기: {file_size:.1f} MB")
            
        except Exception as e:
            logger.error(f"캐시 저장 중 오류: {e}")
            raise


def main():
    """
    메인 함수
    
    ETF 캐시 생성 프로세스를 실행합니다:
    1. 데이터 로딩
    2. 캐시 빌드
    3. 결과 저장
    
    Returns:
        0: 성공, 1: 실패
    """
    print("=" * 60)
    print("ETF 점수 캐시 생성 시작")
    print("=" * 60)
    
    try:
        # 캐시 빌더 초기화
        builder = ETFCacheBuilder()
        
        # 데이터 로딩
        builder.load_data()
        
        # 캐시 빌드 (4개 워커로 병렬 처리)
        cache_df = builder.build_cache(max_workers=4)
        
        # 캐시 저장
        builder.save_cache(cache_df)
        
        print("=" * 60)
        print("ETF 점수 캐시 생성 완료!")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"캐시 생성 중 오류 발생: {e}")
        print(f"오류: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main()) 