import asyncio
import re
import chardet
import requests
from lxml import etree
from requests_html import AsyncHTMLSession

def get_report_list(
    api_key: str,
    corp_code: str,
    start_date: str,
    end_date: str,
    count: int = 10
) -> list[dict]:
    """
    DART OpenAPI에서 공시 목록(list.json) 가져오기
    """
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": start_date,
        "end_de": end_date,
        "page_count": count
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"❌ 공시 목록 요청 실패: {e}")
        return []
    if data.get("status") != "000":
        print(f"❌ API 에러: {data.get('message')}")
        return []
    return data.get("list", [])


async def _fetch_full_html(rcp_no: str) -> str:
    """
    1) main.do에서 currentDocValues 실행 → params 얻기
    2) offset=0,length=0 → viewer.do 호출
    3) JS 렌더링(arender) 적용 → 표 안 텍스트 채움
    4) raw_html 바이트 → chardet로 인코딩 감지 후 디코딩
    5) <meta charset="utf-8"> 삽입
    6) lxml로 <link>, <img> 절대경로 보정
    7) UTF-8로 직렬화
    """
    session = AsyncHTMLSession()

    # 1) currentDocValues 얻기
    url_main = "https://dart.fss.or.kr/dsaf001/main.do"
    resp1 = await session.get(url_main, params={"rcpNo": rcp_no})
    params = await resp1.html.arender(script="currentDocValues;")
    params["offset"] = 0
    params["length"] = 0

    # 2) 전체 HTML 요청
    url_view = "https://dart.fss.or.kr/report/viewer.do"
    resp2 = await session.get(url_view, params=params)
    # 3) JS 렌더링(테이블 데이터 채우기)
    await resp2.html.arender(timeout=20)
    await session.close()

    # 4) raw_html에서 인코딩 감지 후 디코딩
    raw: bytes = resp2.html.raw_html
    enc = chardet.detect(raw).get("encoding") or "utf-8"
    html_str = raw.decode(enc, errors="replace")

    # 5) head에 UTF-8 메타 추가
    if re.search(r"(?i)<head[^>]*>", html_str):
        html_str = re.sub(
            r"(?i)(<head[^>]*>)",
            r'\1\n    <meta charset="utf-8">',
            html_str, count=1
        )
    else:
        html_str = "<meta charset=\"utf-8\">\n" + html_str

    # 6) lxml 파싱 후 <link>, <img> 절대경로 보정
    parser = etree.HTMLParser()
    tree = etree.fromstring(html_str.encode("utf-8"), parser)

    link = tree.find(".//link")
    if link is not None and "href" in link.attrib:
        link.attrib["href"] = "https://dart.fss.or.kr" + link.attrib["href"]

    for img in tree.findall(".//img"):
        if "src" in img.attrib:
            img.attrib["src"] = "https://dart.fss.or.kr" + img.attrib["src"]

    # 7) UTF-8로 직렬화
    final_html = etree.tostring(
        tree,
        encoding="utf-8",
        method="html",
        pretty_print=True
    )
    return final_html.decode("utf-8")


def get_full_html(rcp_no: str) -> str:
    """
    주어진 rcp_no에 대해 JS 실행까지 포함한 전체 HTML 반환
    """
    return asyncio.run(_fetch_full_html(rcp_no))
