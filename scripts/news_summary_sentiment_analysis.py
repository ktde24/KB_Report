import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import requests
import uuid
import json
import http.client
import os
from bs4 import BeautifulSoup
from IPython.display import display
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# ── 레벨별 스타일 프롬프트 ───────────────────────────────────
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from chatbot.config import LEVEL_PROMPTS

SYSTEM_PROMPT_ANALYSIS = (
    "- 당신은 뉴스 헤드라인 감성 분석기입니다.\n"
    "- 사용자가 보낸 뉴스 헤드라인을 보고, 다음 3개의 필드만 '|' 로 구분해 한 줄로 출력하세요:\n"
    "  1) 뉴스기사(원문 그대로)\n"
    "  2) 긍부정 결과 (긍정/부정/중립 중 하나)\n"
    "  3) 이유 (한 문장)\n"
    "- 반드시 위 순서대로 '뉴스기사|긍부정 결과|이유' 형태로만 출력하고, 다른 설명은 절대 덧붙이지 마세요."
)

# ── 종목명 크롤러 ─────────────────────────────────────────
def fetch_stock_name(code: str) -> str:
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tag = soup.select_one("div.wrap_company h2 a")
    return tag.get_text(strip=True) if tag else code

# ── 헤드라인 크롤러 ─────────────────────────────────────────
def fetch_naver_news(code: str) -> pd.DataFrame:
    records = []
    url = f"https://finance.naver.com/item/news_news.naver?code={code}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": url}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for row in soup.select("table.type5 tbody tr"):
        title_tag = row.select_one("td.title a.tit")
        date_tag = row.select_one("td.date")
        if not title_tag or not date_tag:
            continue
        try:
            dt = datetime.strptime(date_tag.text.strip(), "%Y.%m.%d %H:%M")
        except ValueError:
            continue
        if dt < datetime.now() - timedelta(days=14):
            continue
        records.append({'date': dt, 'headline': title_tag.text.strip()})
    df = pd.DataFrame(records)
    return df

# ── Chat Completions Executor ─────────────────────────────────
class CompletionExecutor:
    def __init__(self, host: str, api_key: str):
        self.host = host
        self.api_key = api_key
        self.endpoint = '/testapp/v3/chat-completions/HCX-005'
    def analyze(self, messages: list[dict]) -> str:
        headers = {
            'Authorization':               self.api_key,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': str(uuid.uuid4()),
            'Content-Type':                'application/json; charset=utf-8',
            'Accept':                      'text/event-stream'
        }
        payload = {
            'messages': messages,
            'topP': 0.6, 'topK': 0, 'maxTokens': 256,
            'temperature': 0.1, 'repetitionPenalty': 1.1,
            'stop': ['###'], 'includeAiFilters': True,
            'seed': 0
        }
        with requests.post(self.host + self.endpoint, headers=headers, json=payload, stream=True) as r:
            r.raise_for_status()
            evt = None
            for raw in r.iter_lines():
                if not raw: continue
                line = raw.decode('utf-8')
                if line.startswith('event:'):
                    evt = line.split(':',1)[1].strip()
                elif line.startswith('data:') and evt=='result':
                    return json.loads(line[5:])['message']['content'].strip()
        return ''

# ── Main Execution for Jupyter Notebook ─────────────────────
if __name__ == "__main__":
    code  = input("ETF 종목 코드 입력 (예: 091230): ").strip() or "102110"
    level = int(input("요약 난이도 레벨 선택 [1,2,3]: ").strip() or "1")

    stock_name   = fetch_stock_name(code)
    headlines_df = fetch_naver_news(code)
    print(f"\n{stock_name}({code}) 최근 7일 뉴스 헤드라인:")
    display(headlines_df)

    # 3) 감성분석
    import os
    clova_api_key = os.getenv("CLOVA_API_KEY")
    if not clova_api_key:
        print("경고: CLOVA_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("환경 변수를 설정하거나 .env 파일에 추가하세요.")
        exit(1)
    
    chat = CompletionExecutor(
        host='https://clovastudio.stream.ntruss.com',
        api_key=f'Bearer {clova_api_key}'
    )
    sentiments = []
    for title in headlines_df['headline']:
        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT_ANALYSIS},
            {"role": "user",   "content": title}
        ]
        raw = chat.analyze(msgs)
        parts = raw.split('|', 2)
        sentiments.append({
            '뉴스기사': parts[0] if len(parts)>0 else '',
            '결과':     parts[1] if len(parts)>1 else '',
            '이유':     parts[2] if len(parts)>2 else ''
        })
    sent_df = pd.DataFrame(sentiments)
    print("\n감성분석 결과:")
    display(sent_df)

    # 4) 헤드라인 요약 via Chat Completions with Level Prompt
    print("\n헤드라인 요약:")
    summary_msgs = [
        {"role":"system","content": LEVEL_PROMPTS[level]},
        {"role":"user","content": "아래 뉴스 헤드라인을 2줄로 요약해줘:\n" + "\n".join(f"- {h}" for h in headlines_df['headline'])}
    ]
    summary = chat.analyze(summary_msgs)
    print(summary)

    # 5) 요약문 감성분석
    sent_msgs = [
        {"role":"system","content": LEVEL_PROMPTS[level] + "\n- 요약문에 대해 '감정:긍정/부정/중립' 한 줄로만 출력하세요."},
        {"role":"user","content": summary}
    ]
    raw_sent = chat.analyze(sent_msgs)
    sentiment = next((ln.split(':',1)[1].strip() for ln in raw_sent.splitlines() if ln.startswith("감정:")), raw_sent)
    print("\n요약문 감성분석:")
    print(f"감정: {sentiment}")
