"""
최근 5거래일 ETF 시세 비교 요약 에이전트
- OpenAI GPT API를 사용한 ETF 시세 분석 및 요약
"""

import streamlit as st
from pykrx import stock
from datetime import datetime, timedelta
import pandas as pd
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# ── 레벨별 스타일 프롬프트 ───────────────────────────────────
LEVEL_PROMPTS = {
        1: """- Level 1 (초보자): 
       • 어투: 유치원/초등학생도 이해할 수 있는 아주 쉬운 말로 설명
       • 내용: 투자 기초 개념 위주, 복잡한 용어는 비유와 예시로 대체
       • 길이: 1-2줄로 핵심만 요약""",
       
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
       • 길이: 1-2줄로 전문적 설명"""
    }

# ── 최근 n거래일 데이터 가져오기 ─────────────────────────────────
def get_last_n_trading_days(code: str, n: int = 5) -> pd.DataFrame:
    """
    지정된 ETF 코드에 대해 최근 n거래일의 OHLCV 데이터를 반환
    """
    days = []
    date = datetime.now()
    while len(days) < n:
        date -= timedelta(days=1)
        df = stock.get_etf_ohlcv_by_date(date.strftime('%Y%m%d'),
                                          date.strftime('%Y%m%d'),
                                          code)
        if not df.empty:
            df.index = pd.to_datetime(df.index, format='%Y%m%d')
            days.append(df.iloc[0])
    # 최신 날짜 순으로 정렬
    return pd.DataFrame(days).sort_index()

# ── GPT API Executor ─────────────────────────────────
class GPTExecutor:
    def __init__(self, api_key: str = None):
        """GPT API 클라이언트 초기화"""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            st.error("OpenAI API 키가 설정되지 않았습니다. 환경변수 OPENAI_API_KEY를 설정하거나 직접 입력해주세요.")
            st.stop()
        
        try:
            import openai
            # OpenAI 1.0.0+ 버전용 클라이언트 초기화
            self.client = openai.OpenAI(api_key=self.api_key)
        except ImportError:
            st.error("OpenAI 라이브러리가 설치되지 않았습니다. pip install openai를 실행하세요.")
            st.stop()

    def analyze(self, messages: list[dict]) -> str:
        """GPT API 호출하여 응답 반환"""
        try:
            # OpenAI 1.0.0+ 버전용 API 호출
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=256,
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            st.error(f"GPT API 호출 중 오류: {e}")
            return ""

# ── Streamlit UI ─────────────────────────────────────────────
def main():
    st.title("최근 5거래일 ETF 시세 비교 요약 에이전트 (GPT)")
    
    # API 키 입력
    api_key = st.text_input("OpenAI API Key", type="password", 
                           help="OpenAI API 키를 입력하거나 환경변수 OPENAI_API_KEY를 설정하세요")
    
    code = st.text_input("ETF 종목 코드 입력", value="091230")
    level = st.selectbox("설명 난이도 레벨 선택", [1,2,3,4,5], index=2)

    if st.button("최근 5거래일 시세 가져와서 요약"):  
        # 1) 최근 5거래일 데이터
        df_days = get_last_n_trading_days(code, n=5)
        st.subheader(f"최근 5거래일({df_days.index[0].date()} ~ {df_days.index[-1].date()}) 시세")
        st.dataframe(df_days[['시가','고가','저가','종가','거래량','거래대금']])

        # 2) 요약 프롬프트 구성
        lines = []
        for idx, row in df_days.iterrows():
            date_str = idx.strftime('%Y-%m-%d')
            lines.append(f"- {date_str}: 종가 {int(row['종가']):,}원, 거래량 {int(row['거래량']):,}")
        summary_prompt = LEVEL_PROMPTS[level] + "\n\n" + "\n".join(lines)
        msgs = [
            {"role":"system","content": summary_prompt},
            {"role":"user","content":"어제 시세를 5일간의 시세와 비교해서 요약해줘."}
        ]

        # 3) 모델 호출
        executor = GPTExecutor(api_key)
        summary = executor.analyze(msgs)
        st.subheader("비교 요약 결과")
        st.write(summary)

if __name__ == '__main__':
    main()
