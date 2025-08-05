"""
ETF 분석 모듈
- 개별 ETF에 대한 종합적 분석
- 시세 데이터 기반 수익률, 변동성, 최대낙폭 계산
- 공식 데이터(보수, 자산규모, 거래량) 통합 분석
- 사용자 레벨별 맞춤 분석 및 시각화
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from typing import Dict, List, Any, Tuple, Optional
import warnings
warnings.filterwarnings('ignore')

from .config import Config, LEVEL_PROMPTS

# 공통 유틸리티 임포트
from .utils import (
    normalize_etf_name, safe_float, safe_format, 
    extract_etf_name_from_input, find_etf_row,
    create_error_result, clean_dataframe
)

# 로깅 설정
logger = logging.getLogger(__name__)

# =============================================================================
# ETF명 추출 함수
# =============================================================================

def extract_etf_name(user_input: str, info_df: pd.DataFrame) -> str:
    """
    사용자 입력에서 정확한 ETF명 추출
    
    Args:
        user_input: 사용자 입력 텍스트
        info_df: ETF 정보 DataFrame
    
    Returns:
        매칭된 ETF명 또는 원본 입력
    """
    return extract_etf_name_from_input(user_input, info_df)

def find_etf_row(df: pd.DataFrame, etf_name: str) -> Optional[pd.Series]:
    """
    DataFrame에서 ETF 정보 검색
    
    Args:
        df: 검색할 DataFrame
        etf_name: ETF명
    
    Returns:
        매칭된 행(Series) 또는 None
    """
    from .utils import find_etf_row as utils_find_etf_row
    return utils_find_etf_row(df, etf_name)

def get_exact_etf_info(user_input: str, info_df: pd.DataFrame) -> Tuple[Optional[str], Optional[str]]:
    """
    정확한 ETF명과 종목코드 조회
    
    Args:
        user_input: 사용자 입력
        info_df: ETF 정보 DataFrame
    
    Returns:
        (ETF명, 종목코드) 튜플
    """
    if info_df.empty:
        return None, None
    
    norm_input = normalize_etf_name(user_input)
    
    # 정확한 매칭
    for idx, row in info_df.iterrows():
        if normalize_etf_name(row['종목명']) == norm_input:
            return row['종목명'], str(row['종목코드'])
    
    # 부분 매칭 fallback
    for idx, row in info_df.iterrows():
        if norm_input in normalize_etf_name(row['종목명']):
            return row['종목명'], str(row['종목코드'])
    
    return None, None

# =============================================================================
# 핵심 분석 함수
# =============================================================================

def analyze_etf(
    etf_name: str,
    user_profile: Dict[str, Any],
    price_df: pd.DataFrame,
    info_df: pd.DataFrame,
    perf_df: pd.DataFrame,
    aum_df: pd.DataFrame,
    ref_idx_df: pd.DataFrame,
    risk_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    ETF 종합 분석 수행
    
    Args:
        etf_name: ETF명
        user_profile: 사용자 프로필 (level, investor_type)
        price_df: 가격 데이터
        info_df: 기본 정보
        perf_df: 수익률/보수 정보
        aum_df: 자산규모/유동성 정보
        ref_idx_df: 참고지수 정보
        risk_df: 위험도 정보
    
    Returns:
        ETF 분석 결과 딕셔너리
    """
    try:
        # 1단계: 정확한 ETF 정보 조회
        exact_name, etf_code = get_exact_etf_info(etf_name, info_df)
        
        if not exact_name or not etf_code:
            logger.warning(f"ETF를 찾을 수 없습니다: {etf_name}")
            return _create_error_result(etf_name, "ETF를 찾을 수 없습니다. ETF명을 다시 확인해 주세요.")
        
        # 2단계: 시세 데이터 분석
        market_analysis = _analyze_market_data(price_df, etf_code)
        
        if market_analysis is None:
            logger.warning(f"시세 데이터를 찾을 수 없습니다: {exact_name}")
            return _create_error_result(exact_name, "시세 데이터가 없습니다. ETF 시세 파일을 확인해 주세요.")
        
        # 3단계: 공식 데이터 수집
        official_data = _collect_official_data(exact_name, info_df, perf_df, aum_df, ref_idx_df, risk_df)
        
        # 4단계: 결과 통합
        result = {
            'ETF명': exact_name,
            '기본정보': official_data['basic'],
            '수익률/보수': official_data['performance'],
            '자산규모/유동성': official_data['aum'],
            '참고지수': official_data['reference'],
            '위험': official_data['risk'],
            '시세분석': market_analysis
        }
        
        # 시세 분석 불가 안내 추가
        if _is_market_analysis_insufficient(market_analysis):
            result['시세분석_안내'] = "시세 데이터가 부족하거나, 수익률/변동성/최대낙폭을 계산할 수 없습니다."
        
        logger.info(f"ETF 분석 완료: {exact_name}")
        return result
        
    except Exception as e:
        logger.error(f"ETF 분석 중 오류 발생: {e}")
        return _create_error_result(etf_name, f"분석 중 오류가 발생했습니다: {str(e)}")

def _analyze_market_data(price_df: pd.DataFrame, etf_code: str) -> Optional[Dict[str, Any]]:
    """
    시세 데이터 분석 (수익률, 변동성, 최대낙폭)
    
    Args:
        price_df: 가격 데이터
        etf_code: ETF 종목코드
    
    Returns:
        시세 분석 결과 또는 None
    """
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

def _collect_official_data(
    etf_name: str,
    info_df: pd.DataFrame,
    perf_df: pd.DataFrame,
    aum_df: pd.DataFrame,
    ref_idx_df: pd.DataFrame,
    risk_df: pd.DataFrame
) -> Dict[str, Dict]:
    """
    공식 데이터 수집 (각 CSV 파일에서)
    
    Args:
        etf_name: ETF명
        *_df: 각종 데이터 DataFrame들
    
    Returns:
        공식 데이터 딕셔너리
    """
    info_row = find_etf_row(info_df, etf_name)
    perf_row = find_etf_row(perf_df, etf_name)
    aum_row = find_etf_row(aum_df, etf_name)
    ref_row = find_etf_row(ref_idx_df, etf_name)
    risk_row = find_etf_row(risk_df, etf_name)
    return {
        'basic': dict(info_row) if info_row is not None else {},
        'performance': dict(perf_row) if perf_row is not None else {},
        'aum': dict(aum_row) if aum_row is not None else {},
        'reference': dict(ref_row) if ref_row is not None else {},
        'risk': dict(risk_row) if risk_row is not None else {}
    }

def _create_error_result(etf_name: str, error_message: str) -> Dict[str, Any]:
    """
    에러 결과 생성
    
    Args:
        etf_name: ETF명
        error_message: 에러 메시지
    
    Returns:
        에러 결과 딕셔너리
    """
    error_result = create_error_result(error_message, f"ETF: {etf_name}")
    error_result.update({
        'ETF명': etf_name,
        '기본정보': {},
        '수익률/보수': {},
        '자산규모/유동성': {},
        '참고지수': {},
        '위험': {},
        '시세분석': {},
        '설명': error_message
    })
    return error_result

def _is_market_analysis_insufficient(market_analysis: Dict[str, Any]) -> bool:
    """시세 분석이 불충분한지 확인"""
    if not market_analysis:
        return True
    
    key_metrics = ['3개월 수익률', '1년 수익률', '변동성', '최대낙폭']
    return all(market_analysis.get(metric) is None for metric in key_metrics)

# =============================================================================
# 시각화 함수들
# =============================================================================

def plot_etf_bar(etf_info: Dict[str, Any]) -> go.Figure:
    """
    ETF 시세 분석 바 차트 생성
    
    Args:
        etf_info: ETF 분석 정보
    
    Returns:
        Plotly Figure 객체
    """
    try:
        market_data = etf_info.get('시세분석', {})
        
        # 차트 데이터 준비
        metrics = ['3개월 수익률', '1년 수익률', '변동성', '최대낙폭']
        labels = ['3개월 수익률(%)', '1년 수익률(%)', '변동성(%)', '최대낙폭(%)']
        values = [market_data.get(metric, 0) or 0 for metric in metrics]
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
        
        # 바 차트 생성
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=labels,
            y=values,
            marker_color=colors,
            text=[safe_format(v, '%') for v in values],
            textposition='auto',
            hovertemplate='%{x}: <b>%{y:.2f}%</b><extra></extra>'
        ))
        
        # 레이아웃 설정
        fig.update_layout(
            title=f"📈 {etf_info.get('ETF명', 'ETF')} 시세 분석",
            xaxis_title="분석 지표",
            yaxis_title="값 (%)",
            template="plotly_white",
            font=dict(size=14, family="Pretendard, NanumGothic, Arial"),
            plot_bgcolor="#F8F9FA",
            paper_bgcolor="#F8F9FA",
            height=450,
            margin=dict(l=50, r=50, t=80, b=50)
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"시세 분석 차트 생성 오류: {e}")
        return _create_empty_chart("시세 분석 차트 생성 중 오류가 발생했습니다.")

def plot_etf_summary_bar(etf_info: Dict[str, Any]) -> go.Figure:
    """
    ETF 공식 데이터 요약 바 차트 생성
    
    Args:
        etf_info: ETF 분석 정보
    
    Returns:
        Plotly Figure 객체
    """
    try:
        performance_data = etf_info.get('수익률/보수', {})
        aum_data = etf_info.get('자산규모/유동성', {})
        
        # 데이터 수집 및 검증
        chart_data = []
        
        # 공식 1년 수익률
        official_return = safe_float(performance_data.get('수익률'))
        if official_return is not None:
            chart_data.append(('공식 1년 수익률(%)', official_return, '#1f77b4'))
        
        # 총 보수
        total_fee = safe_float(performance_data.get('총 보수'))
        if total_fee is not None:
            chart_data.append(('총보수(%)', total_fee, '#ff7f0e'))
        
        # 평균 순자산총액 (억원 단위로 변환)
        avg_aum = safe_float(aum_data.get('평균 순자산총액'))
        if avg_aum is not None:
            chart_data.append(('평균 자산규모(억원)', avg_aum / 100, '#2ca02c'))
        
        # 평균 거래량 (천주 단위로 변환)
        avg_volume = safe_float(aum_data.get('평균 거래량'))
        if avg_volume is not None:
            chart_data.append(('평균 거래량(천주)', avg_volume / 1000, '#d62728'))
        
        # 차트 생성
        fig = go.Figure()
        
        if chart_data:
            labels, values, colors = zip(*chart_data)
            
            fig.add_trace(go.Bar(
                x=list(labels),
                y=list(values),
                marker=dict(
                    color=list(colors),
                    line=dict(color='#333', width=1)
                ),
                text=[safe_format(v) for v in values],
                textposition='outside',
                hovertemplate='%{x}: <b>%{y:,.2f}</b><extra></extra>'
            ))
        else:
            # 데이터가 없는 경우
            fig.add_annotation(
                text="데이터가 부족합니다",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16, color="gray")
            )
        
        # 레이아웃 설정
        fig.update_layout(
            title=f"{etf_info.get('ETF명', 'ETF')} 공식 데이터 요약",
            xaxis_title="공식 지표",
            yaxis_title="값",
            template="plotly_white",
            font=dict(size=14, family="Pretendard, NanumGothic, Arial"),
            plot_bgcolor="#F8F9FA",
            paper_bgcolor="#F8F9FA",
            height=450,
            margin=dict(l=50, r=50, t=80, b=50),
            showlegend=False
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"공식 데이터 차트 생성 오류: {e}")
        return _create_empty_chart("공식 데이터 차트 생성 중 오류가 발생했습니다.")

def _create_empty_chart(message: str) -> go.Figure:
    """빈 차트 생성 (오류 시 사용)"""
    fig = go.Figure()
    fig.add_annotation(
        text=f" {message}",
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
