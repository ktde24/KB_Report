"""
ETF 비교 분석 모듈
- 다중 ETF 비교 분석 (최대 6개)
- 사용자 레벨/투자 유형별 맞춤 비교
- 캐시 기반 고속 점수 계산 + 실시간 데이터 조회
- 종합 점수, 위험-수익률, 비용 효율성 등 분석
- 인터랙티브 시각화 (바차트, 산점도, 레이더차트, 히트맵)
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.figure_factory as ff
import logging
import os
from typing import List, Dict, Any, Optional, Tuple

# 공통 유틸리티 임포트
from .etf_analysis import analyze_etf
from .config import Config
from .recommendation_engine import ETFRecommendationEngine
from .config import Config
from .utils import (
    normalize_etf_name, safe_float, format_percentage, 
    format_aum, format_volume, validate_user_profile,
    create_error_result, extract_etf_name_from_input
)

# 로깅 설정
logger = logging.getLogger(__name__)

# =============================================================================
# 상수 정의
# =============================================================================
MAX_COMPARISON_ETFS = 6
MIN_COMPARISON_ETFS = 2

# 변동성 등급 점수 매핑
VOLATILITY_SCORE_MAP = {
    '매우낮음': 1, '낮음': 2, '보통': 3, '높음': 4, '매우높음': 5
}

# 변동성 등급별 안정성 점수 (역방향)
STABILITY_SCORE_MAP = {
    '매우높음': 20, '높음': 40, '보통': 60, '낮음': 80, '매우낮음': 100
}

# 차트 색상 팔레트
CHART_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']

class ETFComparison:
    """ETF 비교 분석 클래스"""
    
    def __init__(self):
        """초기화"""
        self.engine = ETFRecommendationEngine()
        self.config = Config()
        self.cache_df = None
        self._load_cache()
        logger.info("ETF 비교 분석 엔진 초기화 완료")
    
    def _load_cache(self):
        """캐시 데이터 로드"""
        try:
            cache_path = self.config.get_data_path('cache')
            if os.path.exists(cache_path):
                self.cache_df = pd.read_csv(cache_path, encoding='utf-8-sig')
                logger.info(f"캐시 데이터 로드 완료: {len(self.cache_df)}개 레코드")
            else:
                logger.warning("캐시 데이터 파일을 찾을 수 없습니다.")
                self.cache_df = None
        except Exception as e:
            logger.error(f"캐시 데이터 로드 중 오류: {e}")
            self.cache_df = None
    
    def compare_etfs(
        self, 
        etf_names: List[str], 
        user_profile: Dict[str, Any], 
        price_df: pd.DataFrame, 
        info_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        여러 ETF를 사용자 프로필에 맞게 비교 분석 (멀티레이어 최적화)
        
        Args:
            etf_names: 비교할 ETF명 리스트
            user_profile: 사용자 프로필 (level, investor_type)
            price_df: 시세 데이터 DataFrame
            info_df: ETF 기본 정보 DataFrame
        
        Returns:
            비교 분석 결과 딕셔너리
        """
        try:
            # 1단계: 입력 검증
            validation_error = self._validate_input(etf_names)
            if validation_error:
                return {'error': validation_error}
            
            # 2단계: 멀티레이어 분석 (캐시 + 실시간)
            scored_etfs, valid_etfs = self._analyze_etfs_hybrid(
                etf_names, user_profile, price_df, info_df
            )
            
            if len(valid_etfs) < MIN_COMPARISON_ETFS:
                return {
                    'error': f'비교 가능한 ETF가 {len(valid_etfs)}개뿐입니다. 최소 {MIN_COMPARISON_ETFS}개 이상 필요합니다.'
                }
            
            # 3단계: 비교 분석 결과 생성
            comparison_result = self._generate_comparison_result(scored_etfs, user_profile)
            
            logger.info(f"ETF 비교 분석 완료: {len(scored_etfs)}개 ETF")
            return comparison_result
            
        except Exception as e:
            logger.error(f"ETF 비교 분석 중 오류: {e}")
            return {'error': f'비교 분석 중 오류가 발생했습니다: {str(e)}'}
    
    def _validate_input(self, etf_names: List[str]) -> Optional[str]:
        """입력 검증"""
        if len(etf_names) < MIN_COMPARISON_ETFS:
            return f'ETF 비교를 위해서는 최소 {MIN_COMPARISON_ETFS}개 이상의 ETF가 필요합니다.'
        
        if len(etf_names) > MAX_COMPARISON_ETFS:
            return f'ETF 비교는 최대 {MAX_COMPARISON_ETFS}개까지만 가능합니다.'
        
        return None
    
    def _analyze_etfs_hybrid(
        self, 
        etf_names: List[str], 
        user_profile: Dict[str, Any],
        price_df: pd.DataFrame, 
        info_df: pd.DataFrame
    ) -> Tuple[List[Dict], List[str]]:
        """ETF 분석"""
        scored_etfs = []
        valid_etfs = []
        
        # 사용자 프로필 정규화
        level = self._normalize_user_level(user_profile.get('level', 3))  # 기본값: Level 3 (중급자)
        investor_type = user_profile.get('investor_type', 'IFSA')  # 기본값: 일독형+팩트형+속독형+집중형
        
        for etf_name in etf_names:
            try:
                # ETF명 정규화
                clean_name = extract_etf_name_from_input(etf_name, info_df)
                
                if not clean_name:
                    logger.warning(f"ETF명을 찾을 수 없음: {etf_name}")
                    continue
                
                # 1. 캐시에서 기본 점수 및 공식 데이터 조회
                cache_data = self._get_cache_data(clean_name, level, investor_type)
                
                # 2. 실시간 시세 데이터 조회
                realtime_data = self._get_realtime_data(clean_name, price_df, info_df)
                
                # 3. 데이터 통합
                if cache_data and realtime_data:
                    # 캐시에서 공식 데이터 추출
                    official_data = {
                        '수익률/보수': {'총 보수': cache_data.get('총보수')},
                        '자산규모/유동성': {
                            '자산규모': cache_data.get('자산규모'),
                            '평균 거래량': cache_data.get('거래량')
                        },
                        '위험': {'변동성': cache_data.get('변동성')},
                        '기본정보': {
                            '종목코드': cache_data.get('종목코드'),
                            '분류체계': cache_data.get('분류체계'),
                            '기초지수': cache_data.get('기초지수')
                        }
                    }
                    
                    etf_data = {
                        'ETF명': clean_name,
                        '시세분석': realtime_data,
                        '수익률/보수': official_data['수익률/보수'],
                        '자산규모/유동성': official_data['자산규모/유동성'],
                        '위험': official_data['위험'],
                        '기본정보': official_data['기본정보']
                    }
                    
                    scored_etfs.append({
                        'etf_data': etf_data,
                        'base_score': cache_data['base_score'],
                        'type_weight': cache_data['type_weight'],
                        'final_score': cache_data['final_score'],
                        'risk_tier': cache_data['risk_tier'],
                        'rank': 0
                    })
                    valid_etfs.append(clean_name)
                else:
                    logger.warning(f"ETF 데이터 수집 실패: {clean_name}")
                    
            except Exception as e:
                logger.error(f"ETF {etf_name} 분석 중 오류: {e}")
                continue
        
        # 점수순 정렬 및 순위 부여
        scored_etfs.sort(key=lambda x: x['final_score'], reverse=True)
        for i, etf in enumerate(scored_etfs):
            etf['rank'] = i + 1
        
        logger.info(f"ETF 분석 완료: {len(valid_etfs)}개 성공")
        return scored_etfs, valid_etfs

    def _get_cache_data(self, etf_name: str, level: int, investor_type: str) -> Optional[Dict]:
        """캐시에서 ETF 점수 및 공식 데이터 조회"""
        if self.cache_df is None:
            logger.warning("캐시 데이터가 없어 실시간 계산으로 대체합니다.")
            return None
        
        try:
            # 캐시에서 해당 ETF의 점수 조회
            etf_cache = self.cache_df[
                (self.cache_df['ETF명'] == etf_name) &
                (self.cache_df['level'] == level) &
                (self.cache_df['wmti_type'] == investor_type)
            ]
            
            if not etf_cache.empty:
                cache_row = etf_cache.iloc[0]
                return {
                    # 점수 정보
                    'base_score': cache_row['base_score'],
                    'type_weight': 1.0,  # 기본값 사용
                    'final_score': cache_row['final_score'],
                    'risk_tier': cache_row['risk_tier'],
                    
                    # 공식 데이터 (캐시에 저장된)
                    '종목코드': cache_row['종목코드'],
                    '분류체계': cache_row['분류체계'],
                    '기초지수': cache_row['기초지수'],
                    '자산규모': cache_row['자산규모'],
                    '거래량': cache_row['거래량'],
                    '변동성': cache_row['변동성'],
                    '총보수': cache_row['총보수']
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"캐시 데이터 조회 중 오류: {e}")
            return None

    def _calculate_fallback_scores(self, etf_data: Dict, user_profile: Dict) -> Dict:
        """캐시가 없을 때 실시간 점수 계산 (fallback)"""
        try:
            # 기본 점수 계산
            base_score = self.engine.calculate_base_score(etf_data)
            
            # 투자자 유형 가중치 계산 (기본값 사용)
            investor_type = user_profile.get('investor_type', 'IFSA')
            type_weight = 1.0  # 기본 가중치
            
            # 최종 점수 계산
            final_score = base_score * type_weight
            
            return {
                'base_score': base_score,
                'type_weight': type_weight,
                'final_score': final_score,
                'risk_tier': 2  # 기본 risk tier
            }
            
        except Exception as e:
            logger.error(f"Fallback 점수 계산 중 오류: {e}")
            return {
                'base_score': 0.5,
                'type_weight': 1.0,
                'final_score': 0.5,
                'risk_tier': 2
            }

    def _get_realtime_data(self, etf_name: str, price_df: pd.DataFrame, info_df: pd.DataFrame) -> Optional[Dict]:
        """실시간 시세 데이터 조회"""
        try:
            # ETF 코드 찾기
            etf_info = info_df[info_df['종목명'] == etf_name]
            if etf_info.empty:
                return None
            
            etf_code = etf_info.iloc[0].get('단축코드', etf_info.iloc[0].get('종목코드', ''))
            if not etf_code:
                return None
            
            # 시세 데이터 분석 (내부 함수로 구현)
            market_data = self._analyze_market_data_internal(price_df, etf_code)
            return market_data
            
        except Exception as e:
            logger.error(f"실시간 데이터 조회 중 오류: {e}")
            return None

    def _analyze_market_data_internal(self, price_df: pd.DataFrame, etf_code: str) -> Optional[Dict[str, Any]]:
        """시세 데이터 분석"""
        try:
            # ETF 시세 데이터 추출
            etf_prices = price_df[price_df['srtnCd'].astype(str) == str(etf_code)].copy()
            
            if etf_prices.empty:
                return None
            
            # 데이터 전처리
            etf_prices['date'] = pd.to_datetime(etf_prices['basDt'], format='%Y%m%d', errors='coerce')
            etf_prices['clpr'] = pd.to_numeric(etf_prices['clpr'], errors='coerce')
            
            # 결측치 및 중복 제거
            etf_prices = etf_prices.dropna(subset=['date', 'clpr'])
            etf_prices = etf_prices.drop_duplicates(subset=['date'])
            etf_prices = etf_prices.sort_values('date').reset_index(drop=True)
            
            if len(etf_prices) < 2:
                return None
            
            # 수익률 계산
            returns = {}
            for period, days in [('3개월', 63), ('1년', 252)]:
                if len(etf_prices) >= days + 1:
                    start_price = etf_prices.iloc[-(days+1)]['clpr']
                    end_price = etf_prices.iloc[-1]['clpr']
                    if start_price > 0:
                        returns[f'{period} 수익률'] = ((end_price / start_price) - 1) * 100
                    else:
                        returns[f'{period} 수익률'] = None
                else:
                    returns[f'{period} 수익률'] = None
            
            # 변동성 계산 (일간 수익률의 표준편차)
            price_changes = etf_prices['clpr'].pct_change().dropna()
            volatility = price_changes.std() * 100 * np.sqrt(252) if len(price_changes) > 1 else None  # 연환산
            
            # 최대낙폭 계산
            rolling_max = etf_prices['clpr'].cummax()
            drawdown = (etf_prices['clpr'] - rolling_max) / rolling_max
            max_drawdown = drawdown.min() * 100 if not drawdown.empty else None
            
            return {
                **returns,
                '변동성': volatility,
                '최대낙폭': max_drawdown
            }
            
        except Exception as e:
            logger.error(f"시세 데이터 분석 오류: {e}")
            return None

    # _get_official_data 메서드는 캐시에서 공식 데이터를 조회하므로 제거됨

    def _normalize_user_level(self, user_level: Any) -> int:
        """
        사용자 레벨 정규화 (1-5단계)
        
        Args:
            user_level: 사용자 레벨 (문자열 또는 숫자)
        
        Returns:
            정규화된 레벨 (1, 2, 3, 4, 5)
        """
        validated_profile = validate_user_profile({'level': user_level})
        return validated_profile['level']
    

    
    def _generate_comparison_result(self, scored_etfs: List[Dict], user_profile: Dict[str, Any]) -> Dict[str, Any]:
        """비교 분석 결과 생성"""
        if not scored_etfs:
            return {
                'user_profile': user_profile,
                'etf_count': 0,
                'etfs': [],
                'comparison_table': None,
                'visualizations': {},
                'summary': '비교 가능한 ETF가 없습니다. ETF명을 다시 확인해 주세요.',
                'recommendations': '비교 가능한 ETF가 없습니다. ETF명을 다시 확인해 주세요.'
            }
        return {
            'user_profile': user_profile,
            'etf_count': len(scored_etfs),
            'etfs': scored_etfs,
            'comparison_table': self._create_comparison_table(scored_etfs),
            'visualizations': self._create_visualizations(scored_etfs, user_profile),
            'summary': self._create_summary(scored_etfs, user_profile),
            'recommendations': self._create_recommendations(scored_etfs, user_profile)
        }
    
    # =============================================================================
    # 비교 테이블 생성
    # =============================================================================
    
    def _create_comparison_table(self, scored_etfs: List[Dict]) -> pd.DataFrame:
        """
        비교 테이블 생성
        
        Args:
            scored_etfs: 점수 계산된 ETF 리스트
        
        Returns:
            비교 테이블 DataFrame
        """
        table_data = []
        
        for etf in scored_etfs:
            try:
                etf_data = etf['etf_data']
                market_data = etf_data.get('시세분석', {})
                performance_data = etf_data.get('수익률/보수', {})
                aum_data = etf_data.get('자산규모/유동성', {})
                risk_data = etf_data.get('위험', {})
                
                row = {
                    'ETF명': etf_data['ETF명'],
                    '순위': etf['rank'],
                    '종합점수': f"{etf['final_score']:.3f}",
                    '1년수익률(%)': self._format_percentage(market_data.get('1년 수익률')),
                    '3개월수익률(%)': self._format_percentage(market_data.get('3개월 수익률')),
                    '총보수(%)': self._format_percentage(performance_data.get('총 보수'), 3),
                    '자산규모(억원)': self._format_aum(aum_data.get('평균 순자산총액')),
                    '거래량': self._format_volume(aum_data.get('평균 거래량')),
                    '변동성': risk_data.get('변동성', 'N/A'),
                    '최대낙폭(%)': self._format_percentage(market_data.get('최대낙폭'))
                }
                table_data.append(row)
                
            except Exception as e:
                logger.error(f"테이블 행 생성 오류: {e}")
                continue
        
        return pd.DataFrame(table_data)
    
    def _format_percentage(self, value: Any, decimals: int = 2) -> str:
        """
        퍼센트 값 포맷팅 (기존 함수와의 호환성을 위해 유지)
        
        Args:
            value: 포맷팅할 값
            decimals: 소수점 자릿수
        
        Returns:
            포맷팅된 퍼센트 문자열
        """
        return format_percentage(value, decimals)
    
    def _format_aum(self, value: Any) -> str:
        """
        자산규모 포맷팅 (기존 함수와의 호환성을 위해 유지)
        
        Args:
            value: 자산규모 값
        
        Returns:
            포맷팅된 AUM 문자열
        """
        return format_aum(value)
    
    def _format_volume(self, value: Any) -> str:
        """
        거래량 포맷팅 (기존 함수와의 호환성을 위해 유지)
        
        Args:
            value: 거래량 값
        
        Returns:
            포맷팅된 거래량 문자열
        """
        return format_volume(value)
    
    # =============================================================================
    # 시각화 생성
    # =============================================================================
    
    def _create_visualizations(self, scored_etfs: List[Dict], user_profile: Dict) -> Dict[str, go.Figure]:
        """
        시각화 생성
        
        Args:
            scored_etfs: 점수 계산된 ETF 리스트
            user_profile: 사용자 프로필
        
        Returns:
            시각화 딕셔너리
        """
        visualizations = {}
        
        try:
            # 1. 종합 점수 바 차트
            visualizations['score_bar'] = self._create_score_bar_chart(scored_etfs)
            
            # 2. 수익률 vs 위험 산점도
            visualizations['risk_return_scatter'] = self._create_risk_return_scatter(scored_etfs)
            
            # 3. 레이더 차트 (다차원 비교)
            visualizations['radar_chart'] = self._create_radar_chart(scored_etfs)
            
            # 4. 히트맵 (상관관계)
            visualizations['heatmap'] = self._create_correlation_heatmap(scored_etfs)
            
            # 5. 수익률 시계열 비교 
            visualizations['returns_comparison'] = self._create_returns_comparison(scored_etfs)
            
            # 6. 비용 vs 성과 분석
            visualizations['cost_performance'] = self._create_cost_performance_chart(scored_etfs)
            
        except Exception as e:
            logger.error(f"시각화 생성 중 오류: {e}")
        
        return visualizations
    
    def _create_score_bar_chart(self, scored_etfs: List[Dict]) -> go.Figure:
        """종합 점수 바 차트"""
        try:
            etf_names = [etf['etf_data']['ETF명'] for etf in scored_etfs]
            scores = [etf['final_score'] for etf in scored_etfs]
            colors = CHART_COLORS[:len(etf_names)]
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=etf_names,
                y=scores,
                marker_color=colors,
                text=[f"{score:.3f}" for score in scores],
                textposition='auto',
                name='종합점수',
                hovertemplate='%{x}<br>종합점수: <b>%{y:.3f}</b><extra></extra>'
            ))
            
            fig.update_layout(
                title="🏆 ETF 종합 점수 비교",
                xaxis_title="ETF",
                yaxis_title="종합 점수",
                template="plotly_white",
                font=dict(size=12, family="Pretendard, NanumGothic"),
                showlegend=False,
                height=400,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"점수 바차트 생성 오류: {e}")
            return self._create_error_chart("점수 바차트 생성 중 오류")
    
    def _create_risk_return_scatter(self, scored_etfs: List[Dict]) -> go.Figure:
        """수익률 vs 위험 산점도"""
        try:
            fig = go.Figure()
            
            for i, etf in enumerate(scored_etfs):
                etf_data = etf['etf_data']
                market_data = etf_data.get('시세분석', {})
                risk_data = etf_data.get('위험', {})
                
                # 수익률 (1년 우선, 없으면 3개월)
                return_val = market_data.get('1년 수익률') or market_data.get('3개월 수익률') or 0
                
                # 변동성을 숫자로 변환
                risk_val = VOLATILITY_SCORE_MAP.get(risk_data.get('변동성', '보통'), 3)
                
                fig.add_trace(go.Scatter(
                    x=[risk_val],
                    y=[return_val],
                    mode='markers+text',
                    marker=dict(
                        size=15, 
                        opacity=0.7,
                        color=CHART_COLORS[i % len(CHART_COLORS)]
                    ),
                    text=[etf_data['ETF명'][:10] + ('...' if len(etf_data['ETF명']) > 10 else '')],
                    textposition="top center",
                    name=etf_data['ETF명'],
                    hovertemplate=f"<b>{etf_data['ETF명']}</b><br>" +
                                 f"수익률: {return_val:.2f}%<br>" +
                                 f"위험도: {risk_data.get('변동성', 'N/A')}<br>" +
                                 f"점수: {etf['final_score']:.3f}<extra></extra>"
                ))
            
            fig.update_layout(
                title="수익률 vs 위험도 분석",
                xaxis_title="위험도 (1:매우낮음 ~ 5:매우높음)",
                yaxis_title="수익률 (%)",
                template="plotly_white",
                font=dict(size=12, family="Pretendard, NanumGothic"),
                showlegend=False,
                height=500,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"위험-수익률 산점도 생성 오류: {e}")
            return self._create_error_chart("위험-수익률 산점도 생성 중 오류")
    
    def _create_radar_chart(self, scored_etfs: List[Dict]) -> go.Figure:
        """레이더 차트 (다차원 비교)"""
        try:
            fig = go.Figure()
            categories = ['수익률', '비용효율성', '유동성', '안정성', '규모']
            
            for etf in scored_etfs:
                values = self._calculate_radar_values(etf['etf_data'])
                
                fig.add_trace(go.Scatterpolar(
                    r=values + [values[0]],  # 닫힌 도형을 위해 첫 값 반복
                    theta=categories + [categories[0]],
                    fill='toself',
                    name=etf['etf_data']['ETF명'],
                    opacity=0.6
                ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )),
                title="🕸️ ETF 다차원 비교 (레이더 차트)",
                font=dict(size=12, family="Pretendard, NanumGothic"),
                height=600,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"레이더 차트 생성 오류: {e}")
            return self._create_error_chart("레이더 차트 생성 중 오류")
    
    def _calculate_radar_values(self, etf_data: Dict[str, Any]) -> List[float]:
        """레이더 차트용 지표 값 계산 (0-100 스케일)"""
        market_data = etf_data.get('시세분석', {})
        performance_data = etf_data.get('수익률/보수', {})
        aum_data = etf_data.get('자산규모/유동성', {})
        risk_data = etf_data.get('위험', {})
        
        # 1. 수익률 점수 (-50%~50% → 0~100)
        return_val = market_data.get('1년 수익률') or market_data.get('3개월 수익률') or 0
        try:
            return_val = float(return_val)
        except (ValueError, TypeError):
            return_val = 0
        return_score = max(0, min(100, (return_val + 50) * 2))
        
        # 2. 비용 효율성 (총보수 2%~0% → 0~100)
        fee_val = safe_float(performance_data.get('총 보수')) or 1.0
        cost_score = max(0, min(100, (2 - fee_val) * 50))
        
        # 3. 유동성 (거래량 기준)
        volume_val = safe_float(aum_data.get('평균 거래량')) or 0
        liquidity_score = max(0, min(100, volume_val / 10000))
        
        # 4. 안정성 (변동성 등급 역방향)
        stability_score = STABILITY_SCORE_MAP.get(risk_data.get('변동성', '보통'), 60)
        
        # 5. 규모 (자산규모 기준)
        aum_val = safe_float(aum_data.get('평균 순자산총액')) or 0
        size_score = max(0, min(100, aum_val / 10000))
        
        return [return_score, cost_score, liquidity_score, stability_score, size_score]
    
    def _create_correlation_heatmap(self, scored_etfs: List[Dict]) -> go.Figure:
        """상관관계 히트맵"""
        try:
            # 주요 지표들 추출
            data_matrix = []
            etf_names = []
            
            for etf in scored_etfs:
                etf_data = etf['etf_data']
                etf_names.append(etf_data['ETF명'][:15])
                
                market_data = etf_data.get('시세분석', {})
                performance_data = etf_data.get('수익률/보수', {})
                aum_data = etf_data.get('자산규모/유동성', {})
                
                row = [
                    market_data.get('1년 수익률', 0) or 0,
                    safe_float(performance_data.get('총 보수')) or 1,
                    safe_float(aum_data.get('평균 거래량')) or 0,
                    market_data.get('변동성', 0) or 0,
                    etf['final_score']
                ]
                data_matrix.append(row)
            
            # DataFrame 생성 및 상관계수 계산
            df = pd.DataFrame(
                data_matrix, 
                columns=['수익률', '총보수', '거래량', '변동성', '종합점수'],
                index=etf_names
            )
            corr_matrix = df.corr()
            
            fig = go.Figure(data=go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.index,
                colorscale='RdYlBu',
                zmid=0,
                text=np.round(corr_matrix.values, 2),
                texttemplate="%{text}",
                textfont={"size": 10},
                hoverongaps=False
            ))
            
            fig.update_layout(
                title="지표 간 상관관계 히트맵",
                font=dict(size=12, family="Pretendard, NanumGothic"),
                height=500,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"히트맵 생성 오류: {e}")
            return self._create_error_chart("히트맵 생성 중 오류")
    
    def _create_returns_comparison(self, scored_etfs: List[Dict]) -> go.Figure:
        """수익률 비교 차트"""
        try:
            fig = go.Figure()
            
            periods = ['3개월', '1년']
            etf_names = [etf['etf_data']['ETF명'] for etf in scored_etfs]
            
            for period in periods:
                returns = []
                for etf in scored_etfs:
                    market_data = etf['etf_data'].get('시세분석', {})
                    return_val = market_data.get(f'{period} 수익률', 0) or 0
                    returns.append(return_val)
                
                fig.add_trace(go.Bar(
                    name=f'{period} 수익률',
                    x=etf_names,
                    y=returns,
                    text=[f"{r:.1f}%" for r in returns],
                    textposition='auto'
                ))
            
            fig.update_layout(
                title="📊 기간별 수익률 비교",
                xaxis_title="ETF",
                yaxis_title="수익률 (%)",
                barmode='group',
                template="plotly_white",
                font=dict(size=12, family="Pretendard, NanumGothic"),
                height=400,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"수익률 비교 차트 생성 오류: {e}")
            return self._create_error_chart("수익률 비교 차트 생성 중 오류")
    
    def _create_cost_performance_chart(self, scored_etfs: List[Dict]) -> go.Figure:
        """비용 vs 성과 분석"""
        try:
            fig = go.Figure()
            
            for i, etf in enumerate(scored_etfs):
                etf_data = etf['etf_data']
                market_data = etf_data.get('시세분석', {})
                performance_data = etf_data.get('수익률/보수', {})
                
                return_val = market_data.get('1년 수익률') or market_data.get('3개월 수익률') or 0
                if return_val is None:
                    return_val = 0
                    
                fee_val = safe_float(performance_data.get('총 보수')) or 1.0
                
                # 비용 대비 성과 비율
                cost_efficiency = return_val / fee_val if fee_val > 0 else 0
                
                fig.add_trace(go.Scatter(
                    x=[fee_val],
                    y=[return_val],
                    mode='markers+text',
                    marker=dict(
                        size=max(10, min(30, abs(cost_efficiency) * 2)),
                        opacity=0.7,
                        color=cost_efficiency,
                        colorscale='Viridis',
                        showscale=True,
                        colorbar=dict(title="비용효율성")
                    ),
                    text=[etf_data['ETF명'][:8]],
                    textposition="top center",
                    name=etf_data['ETF명'],
                    hovertemplate=f"<b>{etf_data['ETF명']}</b><br>" +
                                 f"수익률: {return_val:.2f}%<br>" +
                                 f"총보수: {fee_val:.3f}%<br>" +
                                 f"비용효율성: {cost_efficiency:.1f}<extra></extra>"
                ))
            
            fig.update_layout(
                title="💰 비용 vs 성과 효율성 분석",
                xaxis_title="총보수 (%)",
                yaxis_title="1년 수익률 (%)",
                template="plotly_white",
                font=dict(size=12, family="Pretendard, NanumGothic"),
                showlegend=False,
                height=500,
                margin=dict(l=50, r=50, t=80, b=50)
            )
            
            return fig
            
        except Exception as e:
            logger.error(f"비용-성과 차트 생성 오류: {e}")
            return self._create_error_chart("비용-성과 차트 생성 중 오류")
    
    def _create_error_chart(self, message: str) -> go.Figure:
        """에러 차트 생성"""
        fig = go.Figure()
        fig.add_annotation(
            text=f"{message}",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="red")
        )
        fig.update_layout(
            template="plotly_white",
            height=400,
            margin=dict(l=50, r=50, t=50, b=50)
        )
        return fig
    
    # =============================================================================
    # 요약 및 권장사항 생성
    # =============================================================================
    
    def _create_summary(self, scored_etfs: List[Dict], user_profile: Dict) -> str:
        """기본 데이터 요약 (LLM이 해석할 원시 데이터)"""
        if not scored_etfs:
            return '비교 가능한 ETF가 없습니다. ETF명을 다시 확인해 주세요.'
        try:
            best_etf = scored_etfs[0]['etf_data']['ETF명']
            best_score = scored_etfs[0]['final_score']
            worst_etf = scored_etfs[-1]['etf_data']['ETF명']
            worst_score = scored_etfs[-1]['final_score']
            
            # ETF별 주요 지표 정리
            etf_summary = []
            for i, etf in enumerate(scored_etfs):
                etf_data = etf['etf_data']
                market_data = etf_data.get('시세분석', {})
                performance_data = etf_data.get('수익률/보수', {})
                aum_data = etf_data.get('자산규모/유동성', {})
                risk_data = etf_data.get('위험', {})
                
                summary_text = f"""
{i+1}위: {etf_data['ETF명']} (점수: {etf['final_score']:.3f})
- 1년 수익률: {market_data.get('1년 수익률', 'N/A')}%
- 총보수: {performance_data.get('총 보수', 'N/A')}%
- 자산규모: {aum_data.get('평균 순자산총액', 'N/A')}백만원
- 거래량: {aum_data.get('평균 거래량', 'N/A')}주
- 변동성: {risk_data.get('변동성', 'N/A')}
                """.strip()
                etf_summary.append(summary_text)
            
            return "\n\n".join(etf_summary)
            
        except Exception as e:
            logger.error(f"요약 생성 오류: {e}")
            return "요약 생성 중 오류가 발생했습니다."
    
    def _create_recommendations(self, scored_etfs: List[Dict], user_profile: Dict) -> str:
        """프롬프트용 데이터 정리"""
        if not scored_etfs:
            return '비교 가능한 ETF가 없습니다. ETF명을 다시 확인해 주세요.'
        try:
            level = user_profile.get('level', 3)
            investor_type = user_profile.get('investor_type', 'IFSA')
            
            # 투자자 유형 특성 정리
            type_characteristics = self._analyze_investor_type(investor_type)
            
            return f"""
사용자 프로필:
- 레벨: {level} ({'초급' if level == 1 else '중급' if level == 2 else '고급'})
- 투자자 유형: {investor_type} ({', '.join(type_characteristics)})

비교 결과:
{self._create_summary(scored_etfs, user_profile)}
            """.strip()
            
        except Exception as e:
            logger.error(f"권장사항 생성 오류: {e}")
            return "권장사항 생성 중 오류가 발생했습니다."
    
    def _analyze_investor_type(self, investor_type: str) -> List[str]:
        """MPTI 투자자 유형 특성 분석 (설명용)"""
        characteristics = []
        
        # 콘텐츠 빈도 분석
        if investor_type[0] == 'I':
            characteristics.append("일독형(Intensive) - 깊이 있는 분석 선호")
        elif investor_type[0] == 'E':
            characteristics.append("다독형(Extensive) - 다양한 정보 선호")
        
        # 콘텐츠 종류 분석
        if investor_type[1] == 'F':
            characteristics.append("팩트형(Fact) - 객관적 데이터 선호")
        elif investor_type[1] == 'N':
            characteristics.append("오피니언형(Notion) - 주관적 의견 선호")
        
        # 읽는 속도 분석
        if investor_type[2] == 'S':
            characteristics.append("속독형(Skimming) - 핵심 요약 선호")
        elif investor_type[2] == 'P':
            characteristics.append("정독형(Perusing) - 상세 분석 선호")
        
        # 콘텐츠 소비 패턴 분석
        if investor_type[3] == 'A':
            characteristics.append("집중형(Absorbed) - 특정 분야 집중")
        elif investor_type[3] == 'P':
            characteristics.append("분산형(Diverse) - 다양한 분야 분산")
        
        return characteristics