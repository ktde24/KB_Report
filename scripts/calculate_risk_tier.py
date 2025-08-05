"""
ETF 위험도 분류 스크립트
- ETF 시세 데이터를 기반으로 위험도 지표 계산
- R/E (Risk-averse/Eager) 분류: 위험 회피형 vs 공격 투자형
- B/P (Buy-and-hold/Portfolio) 분류: 장기 보유형 vs 포트폴리오 조정형
- Risk Tier 계산: 5단계 위험 등급 (0~4)

주요 기능:
1. 변동성, 최대낙폭, VaR, 베타, 샤프비율, 소르티노비율 계산
2. 위험도 지표 정규화 및 가중합으로 Risk Score 계산
3. Risk Score 기반 R/E 분류 (Risk-averse/Eager)
4. 최대낙폭 기반 B/P 분류 (Buy-and-hold/Portfolio)
5. Risk Tier 5단계 등급화 (0: 매우 안전 ~ 4: 매우 위험)
"""

import pandas as pd
import numpy as np

# =============================================================================
# 설정 파라미터
# =============================================================================

# 입력/출력 파일 경로
INPUT_CSV   = 'data/ETF_시세_데이터_20240101_20250729.csv'  # ETF 시세 데이터
OUTPUT_CSV  = 'data/etf_re_bp_simplified.csv'              # 위험도 분류 결과

# 롤링 윈도우 크기 (약 6개월, 126영업일 기준)
WINDOW = 126

# 위험도 지표별 가중치 설정 (총합 = 1.0)
W_RISK = {
    'vol':     0.25,  # 변동성 (25%)
    'max_dd':  0.15,  # 최대낙폭 (15%)
    'VaR':     0.20,  # Value at Risk (20%)
    'beta':    0.10,  # 베타 (10%)
    'sharpe':  0.15,  # 샤프비율 (15%)
    'sortino': 0.10,  # 소르티노비율 (10%)
    'down_dev':0.05   # 하방편차 (5%)
}

# B/P 분류 임계값 (최대낙폭 기준)
TH_MDD = 0.20  # MDD ≤ 20% → B (Buy-and-hold), 그 외 P (Portfolio)

# =============================================================================
# 데이터 로드 및 전처리
# =============================================================================

print("데이터 로딩 중")
# ETF 시세 데이터 로드
df = pd.read_csv(INPUT_CSV, parse_dates=['basDt'], dtype={'srtnCd':str})

# 날짜순으로 정렬 (ETF별, 날짜별)
df = df.sort_values(['srtnCd','basDt']).reset_index(drop=True)
print(f"데이터 로딩 완료: {len(df)}행, {df['srtnCd'].nunique()}개 ETF")

# =============================================================================
# 수익률 계산
# =============================================================================

print("수익률 계산 중...")
# ETF 일간 수익률 계산
df['r'] = df.groupby('srtnCd')['clpr'].pct_change()

# 기초지수 일간 수익률 계산 (베타 계산용)
df['mkt_r'] = df.groupby('srtnCd')['bssIdxClpr'].pct_change(fill_method=None)

# =============================================================================
# 최대낙폭 계산 함수
# =============================================================================

def max_drawdown(returns):
    """
    최대낙폭(Maximum Drawdown) 계산
    
    Args:
        returns: 수익률 시계열
    
    Returns:
        최대낙폭 (0~1 사이 값)
    """
    # 누적 수익률 계산
    cum = np.cumprod(1 + returns)
    
    # 최고점 대비 하락폭 계산
    running_max = np.maximum.accumulate(cum)
    drawdown = (running_max - cum) / running_max
    
    return np.max(drawdown)

# =============================================================================
# 위험도 지표 계산 (롤링 윈도우 적용)
# =============================================================================

print("위험도 지표 계산 중...")
grp = df.groupby('srtnCd', group_keys=False)

# 1. 변동성 (Volatility) - 연율화된 표준편차
df['vol'] = grp['r'].rolling(WINDOW, min_periods=WINDOW).std(ddof=1)\
                .mul(np.sqrt(252)).reset_index(level=0, drop=True)

# 2. 최대낙폭 (Maximum Drawdown)
df['max_dd'] = grp['r'].rolling(WINDOW, min_periods=WINDOW)\
                .apply(max_drawdown, raw=True).reset_index(level=0, drop=True)

# 3. VaR (Value at Risk) - 95% 신뢰구간 하위 5% 수익률
df['VaR'] = grp['r'].rolling(WINDOW, min_periods=WINDOW).quantile(0.05)\
                .reset_index(level=0, drop=True)

# 4. 베타 (Beta) - 시장 대비 민감도
print("베타 계산 중...")
beta = df.groupby('srtnCd').apply(
    lambda x: x['r']
        .rolling(WINDOW, min_periods=WINDOW)
        .cov(x['mkt_r'])
      / x['mkt_r']
        .rolling(WINDOW, min_periods=WINDOW)
        .var(ddof=1)
)
df['beta'] = beta.reset_index(level=0, drop=True)

# 5. 샤프비율 (Sharpe Ratio) - 위험 대비 초과수익률
mean_r = grp['r'].rolling(WINDOW, min_periods=WINDOW).mean() \
                .reset_index(level=0, drop=True)
std_r = grp['r'].rolling(WINDOW, min_periods=WINDOW).std(ddof=1) \
                .mul(np.sqrt(252)).reset_index(level=0, drop=True)
df['sharpe'] = mean_r.div(std_r).mul(np.sqrt(252))

# 6. 하방편차 (Downside Deviation) - 손실 구간의 표준편차
df['down_dev'] = grp['r'].rolling(WINDOW, min_periods=WINDOW)\
                .apply(lambda x: np.sqrt(np.mean(np.minimum(x,0)**2)*252), raw=True)\
                .reset_index(level=0, drop=True)

# 7. 소르티노비율 (Sortino Ratio) - 하방위험 대비 초과수익률
df['sortino'] = mean_r.div(df['down_dev']).mul(np.sqrt(252))

# =============================================================================
# 데이터 필터링 및 정규화
# =============================================================================

print("데이터 정규화 중...")
# 위험도 지표가 모두 계산된 유효한 행만 필터링
risk_metrics = ['vol','max_dd','VaR','beta','sharpe','sortino','down_dev']
df = df.dropna(subset=risk_metrics)

# 지표별 최대값으로 정규화 (0~1 스케일)
max_vals = {m: df[m].abs().max() for m in risk_metrics}
for m in risk_metrics:
    df[f'n_{m}'] = df[m].abs() / max_vals[m]

# =============================================================================
# Risk Score 계산 및 분류
# =============================================================================

print("Risk Score 계산 및 분류 중")

# 1. Risk Score 계산 (가중합)
df['Risk_Score'] = sum(W_RISK[m] * df[f'n_{m}'] for m in risk_metrics)

# 2. R/E 분류 (Risk-averse vs Eager)
# Risk_Score ≤ 0.4: R (Risk-averse, 위험 회피형)
# Risk_Score > 0.4: E (Eager, 공격 투자형)
df['risk_bin'] = np.where(df['Risk_Score'] <= 0.4, 'R', 'E')

# 3. Risk Tier 계산 (5단계 등급화)
if not df['Risk_Score'].empty:
    # 날짜별로 Risk_Score를 5개 구간으로 분할
    df['risk_tier'] = df.groupby('basDt')['Risk_Score']\
                        .transform(lambda x: pd.qcut(x, 5, labels=False, duplicates='drop'))

# 4. B/P 분류 (Buy-and-hold vs Portfolio)
# 최대낙폭 ≤ 20%: B (Buy-and-hold, 장기 보유형)
# 최대낙폭 > 20%: P (Portfolio, 포트폴리오 조정형)
df['strat_bin'] = np.where(df['max_dd'] <= TH_MDD, 'B', 'P')

# =============================================================================
# 결과 저장
# =============================================================================

# 필요한 컬럼만 선택하여 저장
cols = [
    'basDt',      # 기준일자
    'srtnCd',     # 종목코드
    'itmsNm',     # 종목명
    'Risk_Score', # 위험도 점수
    'risk_bin',   # R/E 분류
    'risk_tier',  # 위험 등급 (0~4)
    'strat_bin'   # B/P 분류
]

df[cols].to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')

# =============================================================================
# 결과 요약 출력
# =============================================================================

print(f"\n{'='*60}")
print("ETF 위험도 분류 완료!")
print(f"{'='*60}")

# 기본 통계
total_records = len(df)
unique_etfs = df['srtnCd'].nunique()
date_range = f"{df['basDt'].min().strftime('%Y-%m-%d')} ~ {df['basDt'].max().strftime('%Y-%m-%d')}"

print(f"처리 결과:")
print(f"   - 총 레코드: {total_records:,}개")
print(f"   - 고유 ETF: {unique_etfs}개")
print(f"   - 기간: {date_range}")

# 분류별 통계
print(f"\n분류 통계:")
print(f"   - R/E 분류: R(위험회피형) {len(df[df['risk_bin']=='R']):,}개, E(공격투자형) {len(df[df['risk_bin']=='E']):,}개")
print(f"   - B/P 분류: B(장기보유형) {len(df[df['strat_bin']=='B']):,}개, P(포트폴리오형) {len(df[df['strat_bin']=='P']):,}개")

# Risk Tier 분포
if 'risk_tier' in df.columns:
    tier_counts = df['risk_tier'].value_counts().sort_index()
    print(f"   - Risk Tier 분포:")
    for tier, count in tier_counts.items():
        tier_desc = ['매우안전', '안전', '보통', '위험', '매우위험'][int(tier)]
        print(f"     Tier {int(tier)} ({tier_desc}): {count:,}개")

print(f"\n결과 파일: {OUTPUT_CSV}")
print(f"{'='*60}") 