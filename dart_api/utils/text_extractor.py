from bs4 import BeautifulSoup

def html_to_text(html: str) -> str:
    """
    HTML 문자열을 입력받아, script/style/head/meta/link 태그 제거 후
    순수 문자열로 반환합니다.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script","style","head","meta","link"]):
        tag.decompose()
    return " ".join(soup.stripped_strings)
