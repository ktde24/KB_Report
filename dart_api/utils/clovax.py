import os
import requests

CLOVA_ENDPOINT = "https://api.clova.ai/v1/document/parse"
HEADERS = {
    "Content-Type": "application/json",
    "X-API-KEY": os.getenv("CLOVA_API_KEY")
}

def parse_with_clovax(text: str) -> dict:
    """
    ClovaX 문서 파싱 API 호출.
    text: 순수 텍스트(한글 포함)만 보내세요.
    """
    resp = requests.post(
        CLOVA_ENDPOINT,
        headers=HEADERS,
        json={"text": text},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()
