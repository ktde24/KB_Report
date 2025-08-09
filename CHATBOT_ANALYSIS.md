# 🤖 KB 챗봇 시스템

## 📊 데이터 소스 및 구조

### 1. 정적 데이터 (CSV 파일)
```
data/
├── etf_scores_cache.csv          # 추천 점수 캐시
├── 상품검색.csv                  # ETF 기본 정보
├── ETF_시세_데이터_*.csv         # 시세 데이터
├── 수익률 및 총보수(기간).csv    # 성과 데이터
├── 자산규모 및 유동성(기간).csv  # AUM/거래량
├── 참고지수(기간).csv            # 지수 정보
├── 투자위험(기간).csv            # 위험 지표
└── etf_re_bp_simplified.csv      # 위험등급
```

### 2. 데이터 로딩 프로세스
```python
# chatbot_app.py의 _load_data() 메서드
def _load_data(self) -> Dict[str, pd.DataFrame]:
    data_types = ['etf_info', 'etf_prices', 'etf_performance', 
                  'etf_aum', 'etf_reference', 'etf_risk']
    
    for data_type in data_types:
        file_path = self.config.get_data_path(data_type)
        data[data_type] = safe_read_csv_with_fallback(file_path)
```

## 🔧 핵심 모듈 및 API

### 1. GPT API (OpenAI)
```python
# chatbot/gpt_client.py
class GPTClient:
    def __init__(self):
        self.client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    def generate_response(self, prompt: str, model="gpt-3.5-turbo"):
        response = self.client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3
        )
```

**사용 목적:**
- 자연어 질문 답변
- ETF 분석 요약
- 투자 조언 생성


### 2. 추천 엔진 API
```python
# chatbot/recommendation_engine.py
class ETFRecommendationEngine:
    def fast_recommend_etfs(self, user_profile, cache_df, category_keyword="", top_n=5):
        # WMTI 기반 점수 계산
        # 레벨별 필터링
        # 상위 N개 추천
```

**추천 로직:**
1. **WMTI 점수 계산**: 16가지 투자 성향별 가중치 적용
2. **레벨 필터링**: 사용자 레벨에 따른 위험도 제한
3. **카테고리 필터링**: 키워드 기반 섹터별 추천
4. **점수 정렬**: 최종 점수 기준 상위 종목 선별

### 3. 종목 분석 API
```python
# chatbot/etf_analysis.py
def analyze_etf(etf_code: str, data: Dict[str, pd.DataFrame]) -> Dict:
    # 기본 정보 추출
    # 성과 지표 계산
    # 위험 지표 분석
    # 차트 생성
```

**분석 항목:**
- 기본 정보 (종목명, 코드, 분류체계)
- 성과 지표 (1년/3년 수익률, 변동성)
- 위험 지표 (최대낙폭, 샤프비율)
- 시각화 (수익률 차트, 성과 비교)

### 4. 종목 비교 API
```python
# chatbot/etf_comparison.py
class ETFComparison:
    def compare_etfs(self, etf_codes: List[str], data: Dict) -> Dict:
        # 다중 종목 비교
        # 상관관계 분석
        # 포트폴리오 최적화
```

## 🧠 핵심 로직 흐름

### 1. 사용자 입력 처리
```python
def _process_user_request(self, prompt: str, user_profile: Dict) -> str:
    # 1. 카테고리 분류
    category = self._extract_category_keyword(prompt)
    
    # 2. 요청 타입별 처리
    if "추천" in prompt:
        return self._handle_recommendation_request(prompt, user_profile)
    elif "비교" in prompt:
        return self._handle_comparison_request(prompt, user_profile)
    elif "분석" in prompt:
        return self._handle_analysis_request(prompt, user_profile)
```

### 2. 추천 로직
```python
def _handle_recommendation_request(self, prompt: str, user_profile: Dict) -> str:
    # 1. 추천 엔진 호출
    recommendations = self.recommendation_engine.fast_recommend_etfs(
        user_profile=user_profile,
        cache_df=self.data['etf_cache'],
        category_keyword=category,
        top_n=5
    )
    
    # 2. GPT 설명 생성
    explanation = self.recommendation_engine.generate_recommendation_explanation(
        recommendations=recommendations,
        user_profile=user_profile
    )
    
    # 3. MPTI 스타일 적용
    return self._apply_mpti_style(explanation, user_profile['mpti_type'])
```

### 3. MPTI 스타일 적용
```python
def _apply_mpti_style(self, text: str, mpti_type: str) -> str:
    # 6가지 설명 스타일
    styles = {
        'Fact': '객관적 데이터 중심',
        'Opinion': '전문가 관점 포함',
        'Intensive': '핵심 정보 집중',
        'Extensive': '포괄적 분석',
        'Skimming': '요약형 설명',
        'Perusing': '상세한 분석'
    }
```

## 📈 데이터 처리 파이프라인

### 1. 실시간 데이터 수집
```python
# pykrx를 통한 실시간 데이터
from pykrx import stock
from datetime import datetime
today = datetime.now().strftime('%Y%m%d')
df = stock.get_etf_ohlcv_by_date(today, today, "091160")
```

### 2. 캐시 데이터 활용
```python
# 사전 계산된 점수 활용
cache_df = self.data['etf_cache']
filtered_df = cache_df[cache_df['risk_tier'] <= user_level]
```

### 3. 시각화 생성
```python
# Plotly를 통한 인터랙티브 차트
import plotly.graph_objects as go
fig = go.Figure(data=[go.Bar(x=dates, y=prices)])
```

## 🔄 사용자 프로필 시스템

### 1. WMTI (Wealth Management Type Indicator)
```python
# 16가지 투자 성향 분류
WMTI_TYPES = {
    'APWL': '적극적-외향적-전문가형-장기투자',
    'APML': '적극적-외향적-전문가형-단기투자',
    # ... 14개 더
}
```

### 2. MPTI (My Personal Type Indicator)
```python
# 6가지 설명 스타일
MPTI_STYLES = {
    'Fact': '팩트형 - 객관적 데이터 중심',
    'Opinion': '오피니언형 - 전문가 관점',
    'Intensive': '집중형 - 핵심 정보',
    'Extensive': '다각형 - 포괄적 분석',
    'Skimming': '요약형 - 간결한 설명',
    'Perusing': '상세형 - 깊이 있는 분석'
}
```

### 3. 레벨 시스템
```python
# 5단계 투자 경험 레벨
LEVEL_DESCRIPTIONS = {
    1: '초보자 - 투자 기초 개념',
    2: '입문자 - 기본 지식 보유',
    3: '중급자 - 실전 경험',
    4: '고급자 - 전문적 지식',
    5: '전문가 - 투자 전문가'
}
```

## 🎯 주요 기능별 처리 로직

### 1. ETF 추천
```
사용자 입력 → WMTI 분석 → 점수 계산 → 필터링 → GPT 설명 → MPTI 스타일 적용
```

### 2. ETF 분석
```
종목코드 → 데이터 조회 → 지표 계산 → 차트 생성 → GPT 요약 → 결과 표시
```

### 3. ETF 비교
```
다중 종목 → 성과 비교 → 상관관계 분석 → 포트폴리오 제안 → 시각화
```

### 4. 시장 해석
```
시장 데이터 → GPT 분석 → 레벨별 요약 → MPTI 스타일 적용 → 결과 제공
```

