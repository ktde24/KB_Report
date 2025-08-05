import os
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from corpcode_loader import get_corp_code
from dart_api import get_report_list, get_full_html

load_dotenv()
API_KEY       = os.getenv("DART_API_KEY")
CLOVA_API_KEY = os.getenv("CLOVA_API_KEY")
CLOVA_EP      = "https://clovastudio.stream.ntruss.com/testapp/v3/chat-completions/HCX-005"

def html_to_text(html: str) -> str:
    """HTML → 본문 텍스트만 추출"""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script","style"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)

def build_payload(report_type: str, body_text: str) -> dict:
    """클로바X 호출용 JSON 페이로드 생성"""
    system_prompt = (
        "당신은 금융 애널리스트이자 기업공시 전문 파서입니다.\n"
        "아래에 주어진 DART 공시 전문 텍스트를 읽고, 투자자 관점에서 요약해 주세요:\n\n"\
        "원본 자료 : URL을 꼭 명시해주세요. \n"
        "핵심 요약: 필수적인 내용 반드시 포함해주세요. \n"
        "주요 수치: 항목별로 (숫자 + 단위 + 증감률(%))\n\n"
        "※ 증감률 표기 시 ‘–6.49%’ 와 같이 ‘%’만 사용하세요.\n"
        "※ 불필요한 ‘p’ 또는 ‘p.p.’ 표기는 제거합니다.\n"
        "3) 투자 시사점: 👍 긍정 / 👎 부정 신호 포함 \n"
        "4) 설명 난이도 (Level 1~3): \n"
        "• Level 1 – 유치원/초1 스타일 (쉬운 비유와 함께, 아주 쉽게 알려줘야합니다) \n"
        "• Level 2 – 중고등학생용 (핵심+이유, 너무 전문적이진 않지만, 이해되는 수준으로 Level1보다는 어렵게 설명해주세요.) \n"
        "• Level 3 – 고급 분석(실전 투자가이드, 실전투자자용 설명이면 좋습니다.) \n"
        "각 level별로 응답해주세요."
    )

    user_content = (
        f"■ 문서 유형: {report_type}\n\n"
        "■ 전문 텍스트 시작\n"
        f"{body_text}\n"
        "■ 전문 텍스트 끝\n\n"
        "위 텍스트를 바탕으로, 투자자 관점의 **핵심 요약**과 **주요 수치**를 정리해 주세요."
    )

    return {
        "messages": [
            {"role":"system", "content": system_prompt},
            {"role":"user",   "content": user_content}
        ],
        "stream": False,
        "temperature": 0.1,
        "topP":        0.6,
        "maxTokens":   800,
        "seed":        0
    }

def call_clovax(payload: dict, api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    resp = requests.post(
        "https://clovastudio.stream.ntruss.com/testapp/v3/chat-completions/HCX-005",
        headers=headers,
        json=payload,
        timeout=30
    )
    data = resp.json()

    # 1) status 체크
    if data.get("status", {}).get("code") != "20000":
        raise RuntimeError(f"ClovaX API 에러: {data}")

    # 2) result → message → content 로 내려온 답변 추출
    result = data.get("result", {})
    message = result.get("message", {})
    content = message.get("content")
    if not content:
        raise RuntimeError(f"예상치 못한 응답 형식: {data}")

    return content



if __name__ == "__main__":
    # 기업명/코드 (예시), 기간 설정(예시)
    company   = "삼성전자"
    corp_code = get_corp_code(company)
    start_dt  = (datetime.today() - timedelta(days=7)).strftime("%Y%m%d")
    end_dt    = datetime.today().strftime("%Y%m%d")

    # 1) 공시 목록 불러오기
    reports = get_report_list(API_KEY, corp_code, start_dt, end_dt)
    print(f"\n📌 {company} 최근 공시 목록 ({len(reports)}건):\n")

    # 2) 각 rcept_no별로 바로 요약 처리
    for r in reports:
        rcept_no = r["rcept_no"]
        title    = r["report_nm"]
        print(f"\n🔍 처리 중: {title} ({rcept_no})")

        try:
            html = get_full_html(rcept_no)
        except Exception as e:
            print("HTML fetch/렌더링 실패:", e)
            continue

        text = html_to_text(html)
        payload = build_payload(title, text)

        try:
            summary = call_clovax(payload, CLOVA_API_KEY)
            print("\n=== 요약 결과 ===\n")
            print(summary)
        except Exception as e:
            print("ClovaX 호출 실패:", e)
