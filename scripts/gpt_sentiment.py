"""
ETF 뉴스 감성분석 - GPT 버전
- OpenAI GPT API를 사용한 뉴스 헤드라인 감성분석
- 레벨별 맞춤형 요약 제공
"""

import streamlit as st
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pandas as pd
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# ── 레벨별 스타일 프롬프트 (Config에서 가져오기) ───────────────────────────────────
try:
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from chatbot.config import Config
    LEVEL_PROMPTS = Config.LEVEL_PROMPTS
except ImportError:
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

SYSTEM_PROMPT_ANALYSIS = """
- 당신은 뉴스 헤드라인 감성 분석기입니다.
- 사용자가 보낸 뉴스 헤드라인을 보고, 다음 3개의 필드만 "|" 로 구분해 한 줄로 출력하세요:
  1) 뉴스기사(원문 그대로)
  2) 긍부정 결과 (긍정/부정/중립 중 하나)
  3) 이유 (한 문장)
- 반드시 위 순서대로 "뉴스기사|긍부정 결과|이유" 형태로만 출력하고, 다른 설명은 절대 덧붙이지 마세요.
"""

# ── 종목명 크롤러 ─────────────────────────────────────────
def fetch_stock_name(code: str) -> str:
    """네이버 금융에서 종목명 가져오기"""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        tag = soup.select_one("div.wrap_company h2 a")
        return tag.get_text(strip=True) if tag else code
    except:
        return code

# ── 헤드라인 크롤러 ─────────────────────────────────────────
def fetch_naver_news(code: str) -> list[str]:
    """네이버 금융에서 최근 14일 뉴스 헤드라인 가져오기"""
    url = f"https://finance.naver.com/item/news_news.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        headlines = []
        for row in soup.select("table.type5 tbody tr"):
            a = row.select_one("td.title a.tit")
            date_tag = row.select_one("td.date")
            if not a or not date_tag:
                continue
            try:
                dt = datetime.strptime(date_tag.get_text(strip=True), "%Y.%m.%d %H:%M")
            except:
                continue
            if dt < datetime.now() - timedelta(days=14):
                continue
            headlines.append(a.get_text(strip=True))
        return headlines
    except:
        return []

# ── GPT API Executor ───────────────────────────────────────
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
    st.set_page_config(page_title='ETF 뉴스 감성분석 (GPT)', layout='wide')
    
    # API 키 입력
    api_key = st.text_input("OpenAI API Key", type="password", 
                           help="OpenAI API 키를 입력하거나 환경변수 OPENAI_API_KEY를 설정하세요")
    
    symbol = st.text_input("ETF 종목 코드 입력", value="102110")
    level = st.selectbox("요약・분석 스타일 레벨 선택", [1,2,3,4,5], index=2)
    
    stock_name = fetch_stock_name(symbol) if symbol else ''
    st.title(f"ETF 뉴스 감성분석_{stock_name} (GPT)")

    # 1) 뉴스 크롤
    if st.button("뉴스 가져오기 (최근 14일)"):
        st.session_state['headlines'] = fetch_naver_news(symbol)
        st.session_state['results'] = []

    headlines = st.session_state.get('headlines', [])
    if not headlines:
        return

    st.subheader(f"{stock_name} ({symbol}) 최근 뉴스 헤드라인")
    for i, h in enumerate(headlines,1):
        st.write(f"{i}. {h}")

    # 2) 감성분석
    if st.button("감성분석 실행"):
        gpt = GPTExecutor(api_key)
        results = []
        with st.spinner("감성 분석 진행중..."):
            for title in headlines:
                msgs = [
                    {"role":"system","content":SYSTEM_PROMPT_ANALYSIS},
                    {"role":"user","content":title}
                ]
                raw = gpt.analyze(msgs)
                parts = raw.split('|',2)
                results.append({
                    '뉴스기사': parts[0] if len(parts)>0 else '',
                    '결과':     parts[1] if len(parts)>1 else '',
                    '이유':     parts[2] if len(parts)>2 else ''
                })
        st.session_state['results'] = results

    # 3) 결과 테이블
    if st.session_state.get('results'):
        st.subheader("감성분석 결과")
        st.table(pd.DataFrame(st.session_state['results']))

        # 4) 레벨별 요약
        st.subheader("레벨별 최종 요약")
        gpt = GPTExecutor(api_key)
        summary_prompt = LEVEL_PROMPTS[level] + "\n\n" + "\n".join(f"- {h}" for h in headlines)
        msgs = [
            {"role":"system","content": summary_prompt},
            {"role":"user",  "content": "위 헤드라인을 요약해줘."}
        ]
        summary = gpt.analyze(msgs)
        st.write(summary)

        # 5) 레벨별 요약문 감성분석
        st.subheader("요약문 감성분석")
        sent_prompt = [
            {"role":"system","content": LEVEL_PROMPTS[level] + "\n- 요약문에 대해 '감정:긍정/부정/중립' 한 줄로만 출력하세요."},
            {"role":"user","content": summary}
        ]
        sentiment = gpt.analyze(sent_prompt)
        # "감정:~" 부분만
        sent = next((ln.split(":",1)[1].strip()
                     for ln in sentiment.splitlines() if ln.startswith("감정:")), sentiment)
        st.write(f"감정: {sent}")

if __name__ == '__main__':
    main() 