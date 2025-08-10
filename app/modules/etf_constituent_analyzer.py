"""
ETF 구성종목 분석 모듈
- ETF 포트폴리오 분석
- 상위 구성종목 뉴스 요약
- 어제종목요약.py 통합
"""

import streamlit as st
import pandas as pd
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

try:
    from pykrx import stock
    from pykrx.stock import get_etf_portfolio_deposit_file, get_market_ticker_name
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False

logger = logging.getLogger(__name__)

class ETFConstituentAnalyzer:
    """ETF 구성종목 분석 클래스"""
    
    def __init__(self):
        self.industry_data = None
        self._load_industry_data()
    
    def _load_industry_data(self):
        """상장법인목록.csv 로드"""
        try:
            industry_file = os.path.join(os.path.dirname(__file__), '..', '..', 'data', '상장법인목록.csv')
            if os.path.exists(industry_file):
                self.industry_data = pd.read_csv(industry_file)
                self.industry_data['종목코드'] = self.industry_data['종목코드'].astype(str).str.zfill(6)
                self.industry_data = self.industry_data[['회사명', '종목코드', '업종']]
                logger.info("상장법인목록.csv 로드 완료")
            else:
                logger.warning("상장법인목록.csv 파일을 찾을 수 없습니다.")
        except Exception as e:
            logger.error(f"상장법인목록.csv 로드 실패: {e}")
    
    def analyze_etf_portfolio(self, etf_code: str, etf_name: str = None) -> Dict:
        """ETF 포트폴리오 분석"""
        if not PYKRX_AVAILABLE:
            return {"error": "pykrx 라이브러리가 설치되지 않았습니다."}
        
        try:
            # ETF 포트폴리오 데이터 가져오기
            df = get_etf_portfolio_deposit_file(etf_code)
            if df.empty:
                return {"error": f"ETF 코드 {etf_code}의 포트폴리오 데이터를 찾을 수 없습니다."}
            
            # 티커를 종목명으로 변환
            tickers = df.index.tolist()
            ticker_name_map = {}
            for ticker in tickers:
                try:
                    name = get_market_ticker_name(ticker)
                    ticker_name_map[ticker] = name
                except:
                    ticker_name_map[ticker] = f"종목{ticker}"
            
            df["종목명"] = df.index.map(ticker_name_map)
            df = df.reset_index()
            df.rename(columns={'index': '티커'}, inplace=True)
            
            # 업종 정보 병합
            if self.industry_data is not None:
                df_merge = pd.merge(df, self.industry_data, left_on="티커", right_on="종목코드", how="left")
                df_merge.drop(['회사명', '종목코드'], axis=1, inplace=True)
            else:
                df_merge = df.copy()
                df_merge['업종'] = '기타'
            
            # 상위 30개 종목 추출
            df_top = df_merge.head(30).copy()
            df_top.loc[:, 'ETF이름'] = etf_name or f"ETF_{etf_code}"
            
            # 상위 3개 종목 추출
            top_3_stocks = df_top.head(3)
            
            return {
                "portfolio_data": df_top,
                "top_3_stocks": top_3_stocks,
                "industry_distribution": df_top['업종'].value_counts().to_dict(),
                "etf_name": etf_name or f"ETF_{etf_code}",
                "total_constituents": len(df)
            }
            
        except Exception as e:
            logger.error(f"ETF 포트폴리오 분석 실패 ({etf_code}): {e}")
            return {"error": f"포트폴리오 분석 중 오류: {e}"}
    
    def get_top_3_stocks_news(self, top_3_stocks: pd.DataFrame, level: int = 3, mpti_type: str = 'Fact') -> List[Dict]:
        """상위 3개 종목의 뉴스 수집 및 요약 (MPTI 스타일 적용)"""
        from .news_analyzer import NewsAnalyzer
        
        news_analyzer = NewsAnalyzer()
        results = []
        
        # 종목명을 종목코드로 변환하는 매핑
        stock_code_mapping = {
            '삼성전자': '005930',
            'SK하이닉스': '000660',
            '한미반도체': '042700',
            'NAVER': '035420',
            '카카오': '035720',
            'LG에너지솔루션': '373220',
            '삼성바이오로직스': '207940',
            '현대차': '005380',
            '기아': '000270',
            'POSCO홀딩스': '005490',
            'LG화학': '051910',
            '삼성SDI': '006400',
            'SK이노베이션': '096770',
            'LG전자': '066570',
            '삼성생명': '032830',
            'KB금융': '105560',
            '신한지주': '055550',
            '하나금융지주': '086790',
            'NH투자증권': '005940',
            '미래에셋증권': '006800',
            '한국투자증권': '030200',
            '대우건설': '047040',
            'GS건설': '006360',
            '현대건설': '000720',
            '포스코퓨처엠': '003670',
            'LG디스플레이': '034220',
            '삼성디스플레이': '006400',
            'SK텔레콤': '017670',
            'KT': '030200',
            'LG유플러스': '032640',
            'CJ대한통운': '000120',
            '한진': '002320',
            '아시아나항공': '020560',
            '대한항공': '003490',
            '신세계': '004170',
            '롯데쇼핑': '023530',
            '이마트': '139480',
            'CJ제일제당': '097950',
            '농심': '004370',
            '오리온': '271560',
            '롯데제과': '280360',
            '하이트진로': '000080',
            '롯데칠성': '005300',
            '동서': '026960',
            '아모레퍼시픽': '090430',
            'LG생활건강': '051900',
            '코리아나': '027050',
            '한화': '000880',
            '롯데케미칼': '011170',
            'LG화학': '051910',
            'SK이노베이션': '096770',
            'S-OIL': '010950',
            'GS칼텍스': '011780',
            '현대오일뱅크': '011790',
            'SK가스': '018670',
            '대한해운': '005880',
            '한진해운': '006650',
            '팬오션': '028670',
            '현대상선': '011200',
            '한화에어로스페이스': '012450',
            '두산에너빌리티': '034020',
            '두산인프라코어': '042670',
            '두산로보틱스': '454910',
            '두산밥캣': '241560',
            '두산퓨얼셀': '336260',
            '두산테스나': '131970',
            '두산에스앤에스': '131970',
            '두산퓨얼셀파워': '336260',
            '두산에너빌리티': '034020',
            '두산인프라코어': '042670',
            '두산로보틱스': '454910',
            '두산밥캣': '241560',
            '두산테스나': '131970',
            '두산에스앤에스': '131970',
            '두산퓨얼셀파워': '336260'
        }
        
        for idx, row in top_3_stocks.iterrows():
            stock_name = row['종목명']
            weight = row['비중']
            
            # 종목코드 찾기
            stock_code = stock_code_mapping.get(stock_name, stock_name)
            
            try:
                # 뉴스 수집 (종목명 직접 사용)
                news_items = news_analyzer.fetch_naver_news(stock_name)
                
                # 감정분석 및 요약 (모든 수집된 뉴스 사용, MPTI 스타일 적용)
                if news_items:
                    # 모든 수집된 뉴스로 감정분석 및 요약 (MPTI 스타일 적용)
                    sentiment_result = news_analyzer.analyze_news_sentiment(news_items)
                    summary_result = news_analyzer.generate_level_summary(news_items, level, mpti_type=mpti_type)
                    
                    results.append({
                        "stock_name": stock_name,
                        "weight": weight,
                        "news_count": len(news_items),
                        "sentiment": sentiment_result,
                        "summary": summary_result,
                        "news_items": news_items  # 모든 뉴스 포함
                    })
                else:
                    results.append({
                        "stock_name": stock_name,
                        "weight": weight,
                        "news_count": 0,
                        "sentiment": {"error": "뉴스를 찾을 수 없습니다."},
                        "summary": f"{stock_name} 관련 뉴스를 찾을 수 없습니다.",
                        "news_items": []
                    })
                    
            except Exception as e:
                logger.error(f"뉴스 분석 실패 ({stock_name}): {e}")
                results.append({
                    "stock_name": stock_name,
                    "weight": weight,
                    "news_count": 0,
                    "sentiment": {"error": f"분석 오류: {e}"},
                    "summary": f"{stock_name} 뉴스 분석 중 오류가 발생했습니다.",
                    "news_items": []
                })
        
        return results
    
    def generate_etf_summary_report(self, etf_code: str, etf_name: str = None, level: int = 3, mpti_type: str = 'Fact') -> Dict:
        """ETF 종합 요약 리포트 생성 (어제종목요약.py 통합, MPTI 스타일 적용)"""
        # 1. ETF 포트폴리오 분석
        portfolio_result = self.analyze_etf_portfolio(etf_code, etf_name)
        if "error" in portfolio_result:
            return portfolio_result
        
        # 2. 상위 3개 종목 뉴스 분석 (MPTI 스타일 적용)
        top_3_news = self.get_top_3_stocks_news(portfolio_result["top_3_stocks"], level, mpti_type)
        
        # 3. 어제종목요약.py 스타일의 시세 분석
        market_analysis = self._analyze_market_data(etf_code, level)
        
        return {
            "portfolio_analysis": portfolio_result,
            "top_3_news_analysis": top_3_news,
            "market_analysis": market_analysis,
            "etf_code": etf_code,
            "etf_name": etf_name or f"ETF_{etf_code}",
            "analysis_level": level,
            "mpti_type": mpti_type
        }
    
    def _analyze_market_data(self, etf_code: str, level: int) -> Dict:
        """시세 데이터 분석 (어제종목요약.py 스타일)"""
        try:
            # 최근 5거래일 데이터 가져오기
            df_days = self._get_last_n_trading_days(etf_code, n=5)
            if df_days.empty:
                return {"error": "시세 데이터를 가져올 수 없습니다."}
            
            # GPT 분석
            summary = self._generate_market_summary(df_days, level)
            
            return {
                "market_data": df_days,
                "summary": summary,
                "analysis_date": datetime.now().strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"시세 분석 실패 ({etf_code}): {e}")
            return {"error": f"시세 분석 중 오류: {e}"}
    
    def _get_last_n_trading_days(self, code: str, n: int = 5) -> pd.DataFrame:
        """최근 n거래일 데이터 가져오기"""
        if not PYKRX_AVAILABLE:
            return pd.DataFrame()
        
        days = []
        date = datetime.now()
        max_attempts = 20
        attempts = 0
        
        while len(days) < n and attempts < max_attempts:
            date -= timedelta(days=1)
            attempts += 1
            
            try:
                df = stock.get_etf_ohlcv_by_date(
                    date.strftime('%Y%m%d'),
                    date.strftime('%Y%m%d'),
                    code
                )
                if not df.empty:
                    df.index = pd.to_datetime(df.index, format='%Y%m%d')
                    days.append(df.iloc[0])
            except Exception as e:
                logger.warning(f"거래일 데이터 가져오기 실패 ({date.strftime('%Y%m%d')}): {e}")
                continue
        
        return pd.DataFrame(days).sort_index() if days else pd.DataFrame()
    
    def _generate_market_summary(self, df_days: pd.DataFrame, level: int) -> str:
        """시세 요약 생성 (GPT 활용)"""
        try:
            import openai
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return "OpenAI API 키가 설정되지 않았습니다."
            
            client = openai.OpenAI(api_key=api_key)
            
            # 레벨별 프롬프트 (Config에서 가져오기)
            try:
                from chatbot.config import Config
                level_prompts = Config.LEVEL_PROMPTS
                level_prompt = level_prompts.get(level, level_prompts[3])
            except ImportError:
                level_prompts = {
                    1: "유치원/초등학생도 이해할 수 있는 아주 쉬운 말로 설명",
                    2: "중고등학생도 이해 가능한 쉬운 말로 설명",
                    3: "일반 성인도 이해할 수 있는 수준으로 설명",
                    4: "투자 경험이 있는 성인을 대상으로 한 전문적 설명",
                    5: "투자 전문가 수준의 고급 분석과 전문 용어 사용"
                }
                level_prompt = level_prompts.get(level, level_prompts[3])
            
            # 시세 데이터 포맷팅
            lines = []
            for idx, row in df_days.iterrows():
                date_str = idx.strftime('%Y-%m-%d')
                lines.append(f"- {date_str}: 종가 {int(row['종가']):,}원, 거래량 {int(row['거래량']):,}")
            
            summary_prompt = f"""
            다음 ETF 시세 데이터를 {level_prompt}으로 분석해주세요:
            
            {chr(10).join(lines)}
            
            어제 시세를 5일간의 시세와 비교해서 요약해주세요.
            """
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": summary_prompt},
                    {"role": "user", "content": "어제 시세를 5일간의 시세와 비교해서 요약해줘."}
                ],
                max_tokens=256,
                temperature=0.1
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"GPT 요약 생성 실패: {e}")
            return f"요약 생성 중 오류가 발생했습니다: {e}"
    
    def display_etf_analysis(self, analysis_result: Dict):
        """ETF 분석 결과 표시"""
        if "error" in analysis_result:
            st.error(analysis_result["error"])
            return
        
        etf_name = analysis_result.get("etf_name", "ETF")
        level = analysis_result.get("analysis_level", 3)
        
        # KB 노란색 테마로 통일된 헤더 디자인
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
            color: #333;
            padding: 1.5rem;
            border-radius: 15px;
            margin: 1rem 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            display: flex;
            justify-content: space-between;
            align-items: center;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.5rem;">📊</span>
                <h2 style="margin: 0; color: #333; font-weight: bold;">{etf_name} 구성종목 분석</h2>
            </div>
            <div style="
                background: rgba(255,255,255,0.3);
                padding: 0.5rem 1rem;
                border-radius: 20px;
                font-weight: bold;
                color: #333;">
                Level {level}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # 1. 포트폴리오 개요 - KB 노란색 테마
        portfolio = analysis_result["portfolio_analysis"]
        
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
            padding: 2rem;
            border-radius: 15px;
            margin: 1rem 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h3 style="color: #333; margin: 0 0 1rem 0; text-align: center; font-weight: bold;">📈 포트폴리오 개요</h3>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div style="
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border-left: 4px solid #FFD700;">
                <div style="font-size: 2rem; color: #FFD700; margin-bottom: 0.5rem;">📋</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #333;">{portfolio['total_constituents']:,}</div>
                <div style="color: #666;">총 구성종목</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            top_weight = portfolio["top_3_stocks"].iloc[0]["비중"]
            st.markdown(f"""
            <div style="
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border-left: 4px solid #FFA500;">
                <div style="font-size: 2rem; color: #FFA500; margin-bottom: 0.5rem;">⚖️</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #333;">{top_weight:.2f}%</div>
                <div style="color: #666;">최대 비중</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            industry_count = len(portfolio["industry_distribution"])
            st.markdown(f"""
            <div style="
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border-left: 4px solid #FF8C00;">
                <div style="font-size: 2rem; color: #FF8C00; margin-bottom: 0.5rem;">🏭</div>
                <div style="font-size: 1.5rem; font-weight: bold; color: #333;">{industry_count}</div>
                <div style="color: #666;">업종 수</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 2. 상위 3개 종목 뉴스 분석 - KB 노란색 테마
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
            padding: 1.5rem;
            border-radius: 15px;
            margin: 2rem 0 1rem 0;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
            <h3 style="color: #333; margin: 0; display: flex; align-items: center; gap: 10px; font-weight: bold;">
                <span style="font-size: 1.5rem;">🏆</span>
                상위 3개 구성종목 뉴스 분석
            </h3>
        </div>
        """, unsafe_allow_html=True)
        
        top_3_news = analysis_result["top_3_news_analysis"]
        for i, stock_news in enumerate(top_3_news, 1):
            stock_name = stock_news["stock_name"]
            weight = stock_news["weight"]
            
            with st.expander(f"#{i} {stock_name} (비중: {weight:.2f}%)"):
                # 뉴스 요약
                if "summary" in stock_news and stock_news["summary"]:
                    st.write("📰 **뉴스 요약:**")
                    st.write(stock_news["summary"])
                
                # 감정분석
                if "sentiment" in stock_news and stock_news["sentiment"]:
                    sentiment_results = stock_news["sentiment"]
                    
                    if isinstance(sentiment_results, list) and sentiment_results:
                        # 감정분석 결과가 리스트인 경우
                        sentiments = [result.get('sentiment', '') for result in sentiment_results if result.get('sentiment')]
                        if sentiments:
                            # 가장 많이 나온 감정을 표시
                            from collections import Counter
                            sentiment_counts = Counter(sentiments)
                            most_common_sentiment = sentiment_counts.most_common(1)[0][0]
                            st.write(f"😊 **감정분석:** {most_common_sentiment}")
                            
                            # 감정 분포도 표시
                            if len(sentiment_counts) > 1:
                                sentiment_text = ", ".join([f"{sentiment}({count}개)" for sentiment, count in sentiment_counts.items()])
                                st.write(f"📊 **감정 분포:** {sentiment_text}")
                    elif isinstance(sentiment_results, dict) and "overall_sentiment" in sentiment_results:
                        sentiment = sentiment_results["overall_sentiment"]
                        st.write(f"😊 **감정분석:** {sentiment}")
                    else:
                        st.write("😊 **감정분석:** 분석 중...")
                else:
                    st.write("😊 **감정분석:** 분석 중...")
                
                # 뉴스 목록
                if stock_news["news_items"]:
                    st.write("📋 **관련 뉴스:**")
                    for j, news in enumerate(stock_news["news_items"], 1):
                        st.write(f"{j}. {news.get('headline', '제목 없음')}")
                        if news.get('url'):
                            st.markdown(f"[원문 보기]({news['url']})")
        
        # 3. 시세 분석 - KB 노란색 테마
        if "market_analysis" in analysis_result and "summary" in analysis_result["market_analysis"]:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
                padding: 1.5rem;
                border-radius: 15px;
                margin: 2rem 0 1rem 0;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                <h3 style="color: #333; margin: 0; display: flex; align-items: center; gap: 10px; font-weight: bold;">
                    <span style="font-size: 1.5rem;">📈</span>
                    시세 분석
                </h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 요약 텍스트를 카드로 표시
            st.markdown(f"""
            <div style="
                background: white;
                padding: 1.5rem;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border-left: 4px solid #FFD700;
                margin-bottom: 1rem;">
                <div style="color: #333; line-height: 1.6;">
                    {analysis_result["market_analysis"]["summary"]}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 시세 차트
            if "market_data" in analysis_result["market_analysis"]:
                market_data = analysis_result["market_analysis"]["market_data"]
                if not market_data.empty:
                    st.markdown("""
                    <div style="
                        background: white;
                        padding: 1.5rem;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        margin-bottom: 1rem;">
                        <h4 style="color: #333; margin-bottom: 1rem;">📊 최근 5일 종가 추이</h4>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Plotly 사용
                    try:
                        import plotly.express as px
                        import plotly.graph_objects as go
                        
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=market_data.index,
                            y=market_data['종가'],
                            mode='lines+markers',
                            line=dict(color='#667eea', width=3),
                            marker=dict(size=8, color='#667eea'),
                            name='종가'
                        ))
                        
                        fig.update_layout(
                            title="",
                            xaxis_title="날짜",
                            yaxis_title="종가 (원)",
                            template="plotly_white",
                            height=400,
                            margin=dict(l=50, r=50, t=30, b=50),
                            plot_bgcolor='rgba(0,0,0,0)',
                            paper_bgcolor='rgba(0,0,0,0)'
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                    except ImportError:
                        # Plotly가 없으면 기본 차트 사용
                        st.line_chart(market_data['종가'])
        
        # 4. 업종 분포 - KB 노란색 테마
        if "industry_distribution" in portfolio:
            st.markdown("""
            <div style="
                background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
                padding: 1.5rem;
                border-radius: 15px;
                margin: 2rem 0 1rem 0;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);">
                <h3 style="color: #333; margin: 0; display: flex; align-items: center; gap: 10px; font-weight: bold;">
                    <span style="font-size: 1.5rem;">🏭</span>
                    업종 분포
                </h3>
            </div>
            """, unsafe_allow_html=True)
            
            industry_df = pd.DataFrame(list(portfolio["industry_distribution"].items()), 
                                     columns=['업종', '종목수'])
            
            # Plotly를 사용한 더 예쁜 차트
            try:
                import plotly.express as px
                
                fig = px.bar(
                    industry_df,
                    x='업종',
                    y='종목수',
                    color='종목수',
                    color_continuous_scale='viridis',
                    title=""
                )
                
                fig.update_layout(
                    xaxis_title="업종",
                    yaxis_title="종목 수",
                    template="plotly_white",
                    height=400,
                    margin=dict(l=50, r=50, t=30, b=50),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)'
                )
                
                fig.update_traces(
                    marker_line_color='rgb(8,48,107)',
                    marker_line_width=1.5,
                    opacity=0.8
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
            except ImportError:
                # Plotly가 없으면 기본 차트 사용
                st.bar_chart(industry_df.set_index('업종'))
