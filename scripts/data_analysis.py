"""
ETF 데이터 분석 스크립트
- pykrx를 사용한 ETF 포트폴리오 분석
- 산업군별 분포 시각화
"""

import pandas as pd
import plotly.express as px
from pykrx.stock import get_etf_portfolio_deposit_file, get_market_ticker_name

def analyze_etf_portfolio(etf_code: str = "102110"):
    """
    ETF 포트폴리오 분석 및 시각화
    
    Args:
        etf_code: ETF 종목 코드 (기본값: TIGER 반도체)
    """
    print(f"ETF 코드 {etf_code} 분석 시작")
    
    # 1. ETF 구성 종목 가져오기
    df = get_etf_portfolio_deposit_file(etf_code)
    print(f"총 {len(df)}개 종목 발견")
    
    # 2. 종목코드 리스트
    tickers = df.index.tolist()
    
    # 3. 종목코드 → 종목명 매핑
    print("종목명 매핑 중")
    ticker_name_map = {}
    for ticker in tickers:
        try:
            name = get_market_ticker_name(ticker)
            ticker_name_map[ticker] = name
        except:
            ticker_name_map[ticker] = ticker
    
    # 4. 종목명 컬럼 추가
    df["종목명"] = df.index.map(ticker_name_map)
    df = df.reset_index()
    
    # 5. 상장법인목록과 병합 (업종 정보 추가)
    try:
        df_industry = pd.read_csv('상장법인목록.csv')
        df_industry['종목코드'] = df_industry['종목코드'].astype(str).str.zfill(6)
        df_industry = df_industry[['회사명','종목코드','업종']]
        
        # 종목명 기준으로 merge
        df_merge = pd.merge(df, df_industry, left_on="티커", right_on="종목코드", how="left")
        df_merge.drop(['회사명', '종목코드'], axis=1, inplace=True)
        
        # 상위 30개 종목만 분석
        df_top = df_merge.head(30).copy()
        df_top['ETF이름'] = 'TIGER 반도체'
        
        print("업종별 분포:")
        print(df_top['업종'].value_counts())
        
        # 6. 시각화
        fig = px.sunburst(
            df_top,
            path=['ETF이름', '업종', '종목명'],
            values='비중',
            title='ETF 산업군/종목 계층 시각화',
            height=600
        )
        
        # 브라우저에서 표시
        fig.show()
        
        return df_top
        
    except FileNotFoundError:
        print("상장법인목록.csv 파일을 찾을 수 없습니다.")
        print("업종 정보 없이 분석을 진행합니다.")
        return df.head(30)

if __name__ == "__main__":
    # TIGER 반도체 ETF 분석
    result = analyze_etf_portfolio("102110")
    print("\n분석 완료!")
    print(result) 