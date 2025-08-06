import os
import requests
from typing import Dict, Any

OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"

def call_gpt(messages: list, api_key: str, model: str = "gpt-4o-mini", temperature: float = 0.1) -> str:
    """
    OpenAI GPT API 호출
    messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 1000
    }
    
    try:
        resp = requests.post(
            OPENAI_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        
        # 응답에서 content 추출
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not content:
            raise RuntimeError(f"예상치 못한 응답 형식: {data}")
            
        return content
        
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"OpenAI API 호출 실패: {e}")

def parse_with_gpt(text: str, api_key: str, model: str = "gpt-4o-mini") -> str:
    """
    GPT를 사용한 문서 파싱 및 요약
    text: 순수 텍스트(한글 포함)
    """
    system_prompt = (
        "당신은 금융 애널리스트이자 기업공시 전문 파서입니다.\n"
        "아래에 주어진 DART 공시 전문 텍스트를 읽고, 투자자 관점에서 요약해 주세요:\n\n"
        "원본 자료 : URL을 꼭 명시해주세요. \n"
        "핵심 요약: 필수적인 내용 반드시 포함해주세요. \n"
        "주요 수치: 항목별로 (숫자 + 단위 + 증감률(%))\n\n"
        "※ 증감률 표기 시 '–6.49%' 와 같이 '%'만 사용하세요.\n"
        "※ 불필요한 'p' 또는 'p.p.' 표기는 제거합니다.\n"
        "3) 투자 시사점: 👍 긍정 / 👎 부정 신호 포함 \n"
        "4) 설명 난이도 (Level 1~3): \n"
        "• Level 1 – 유치원/초1 스타일 (쉬운 비유와 함께, 아주 쉽게 알려줘야합니다) \n"
        "• Level 2 – 중고등학생용 (핵심+이유, 너무 전문적이진 않지만, 이해되는 수준으로 Level1보다는 어렵게 설명해주세요.) \n"
        "• Level 3 – 고급 분석(실전 투자가이드, 실전투자자용 설명이면 좋습니다.) \n"
        "각 level별로 응답해주세요."
    )
    
    user_content = f"다음 공시 텍스트를 분석해주세요:\n\n{text}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content}
    ]
    
    return call_gpt(messages, api_key, model) 