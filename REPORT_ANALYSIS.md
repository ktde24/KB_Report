# 📊 KB 리포트 시스템 상세 분석

## 📊 데이터 소스 및 구조

### 1. 데이터 (챗봇과 동일)
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
# main.py의 _load_data() 메서드
def _load_data(self) -> Dict[str, pd.DataFrame]:
    # 1. ETF 캐시 데이터
    cache_path = self.config.get_data_path('cache')
    data['etf_cache'] = safe_read_csv_with_fallback(cache_path)
    
    # 2. 기타 데이터 파일들
    for key, path in self.config.DATA_PATHS.items():
        if key != 'cache' and path and os.path.exists(path):
            data[key] = safe_read_csv_with_fallback(path)
```

## 🔧 핵심 모듈 및 API

### 1. 실시간 시장 데이터 API
```python
# app/modules/market_data.py
class RealTimeMarketData:
    def get_korean_market_data(self) -> Dict:
        # KOSPI, KOSDAQ 실시간 데이터
        # pykrx 또는 yfinance 활용
    
    def get_global_market_data(self) -> Dict:
        # S&P500, NASDAQ, 다우존스
        # yfinance 활용
```

**데이터 소스:**
- **pykrx**: 한국 주식/ETF 실시간 데이터
- **yfinance**: 글로벌 지수 및 ETF 데이터
- **Fallback**: 정적 데이터 (API 실패 시)

### 2. 데일리 브리핑 API
```python
# app/modules/daily_briefing.py
class DailyBriefing:
    def display_daily_briefing(self, level, interest_list, mpti_type, data):
        # 관심종목별 분석
        # 뉴스 크롤링
        # 종목 요약 생성
```

**주요 기능:**
- 관심종목 시세 분석
- 뉴스 크롤링 및 요약
- 레벨별 맞춤 설명
- 실시간 데이터 수집

### 3. 추천 시스템 API
```python
# app/modules/recommendations.py
class Recommendations:
    def display_recommendations(self, level, wmti_type, mpti_type, data):
        # WMTI 기반 추천
        # 실시간 가격/거래량
        # GPT 설명 생성
```

**추천 로직:**
1. **챗봇 추천 엔진 활용**: `chatbot.recommendation_engine.ETFRecommendationEngine`
2. **실시간 데이터 수집**: pykrx/yfinance를 통한 최신 가격
3. **GPT 설명 생성**: OpenAI API를 통한 추천 근거


### 4. 뉴스 분석 API
```python
# app/modules/news_analyzer.py
class NewsAnalyzer:
    def fetch_naver_news(self, code: str) -> List[str]:
        # 네이버 뉴스 크롤링
    
    def analyze_news_sentiment(self, headlines: List[str]) -> List[Dict]:
        # GPT 감정분석
    
    def generate_level_summary(self, headlines: List[str], level: int) -> str:
        # 레벨별 요약 생성
```

**뉴스 처리:**
- **크롤링**: BeautifulSoup을 통한 네이버 뉴스 수집
- **감정분석**: GPT API를 통한 뉴스 감정 분석
- **요약**: 레벨별 맞춤 요약 생성

## 🧠 핵심 로직 흐름

### 1. 리포트 생성 메인 플로우
```python
def generate_integrated_report(self, params: Dict):
    # 1. 시장 개요
    self._display_market_overview(level, mpti_type)
    
    # 2. 데일리 브리핑
    self.daily_briefing.display_daily_briefing(level, interest_list, mpti_type, self.data)
    
    # 3. 추천 종목
    self.recommendations.display_recommendations(level, wmti_type, mpti_type, self.data)
    
    # 4. 뉴스 감정분석
    if show_news_sentiment:
        self.news_analyzer.display_news_analysis(main_stock_code, level, mpti_type)
```

### 2. 시장 데이터 수집 로직
```python
def get_korean_market_data(self) -> Dict:
    try:
        # 1차: pykrx 시도
        from pykrx import stock
        from datetime import datetime
        today = datetime.now().strftime('%Y%m%d')
        kospi = stock.get_index_ohlcv_by_date(today, today, "1001")
        kosdaq = stock.get_index_ohlcv_by_date(today, today, "2001")
        
    except ImportError:
        # 2차: yfinance 시도
        import yfinance as yf
        kospi = yf.download("^KS11", period="1d")
        kosdaq = yf.download("^KQ11", period="1d")
        
    except Exception:
        # 3차: 정적 데이터
        return self._get_fallback_data()
```

### 3. 뉴스 크롤링 로직
```python
def fetch_naver_news(self, code: str) -> List[str]:
    # ETF vs 일반주식 구분
    if code.startswith('09') or code.startswith('30'):  # ETF
        return self._fetch_etf_related_news(code)
    else:  # 일반주식
        return self._fetch_stock_news(code)

def _fetch_etf_related_news(self, code: str) -> List[str]:
    # 키워드 기반 뉴스 검색
    etf_keywords = {
        '091160': 'KOSPI200',
        '091170': 'KOSDAQ150',
        '091230': '반도체',
        # ...
    }
    keyword = etf_keywords.get(code, 'ETF')
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
```

### 4. 실시간 데이터 수집 로직
```python
def _get_realtime_stock_data(self, stock_code: str) -> Dict:
    # 1차: pykrx
    try:
        from pykrx import stock
        df = stock.get_etf_ohlcv_by_date(yesterday, today, stock_code)
        return {'current_price': df['종가'].iloc[-1], 'volume': df['거래량'].iloc[-1]}
    except:
        pass
    
    # 2차: yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker(f"{stock_code}.KS")
        hist = ticker.history(period="5d")
        return {'current_price': hist['Close'].iloc[-1], 'volume': hist['Volume'].iloc[-1]}
    except:
        pass
    
    # 3차: 캐시 데이터
    return self._get_cached_stock_data(stock_code)
```

## 📈 데이터 처리 파이프라인

### 1. 실시간 데이터 수집
```
API 호출 → 데이터 검증 → 포맷 변환 → 캐싱 → UI 표시
```

### 2. 뉴스 처리
```
크롤링 → 텍스트 정제 → 감정분석 → 요약 생성 → 레벨별 맞춤화
```

### 3. 추천 처리
```
캐시 데이터 → WMTI 필터링 → 실시간 데이터 수집 → GPT 설명 → UI 표시
```

## 🎯 주요 기능별 처리 로직

### 1. 시장 개요
```
실시간 데이터 수집 → 지수 정보 표시 → GPT 해석 → 레벨별 요약
```

### 2. 데일리 브리핑
```
관심종목 파싱 → 시세 데이터 수집 → 뉴스 크롤링 → 종목 요약 → UI 표시
```

### 3. 추천 종목
```
WMTI 기반 필터링 → 실시간 가격 수집 → GPT 설명 생성 → 카드 형태 표시
```

### 4. 뉴스 감정분석
```
종목코드 → 뉴스 크롤링 → GPT 감정분석 → 레벨별 요약 → 차트 표시
```

## 🔄 사용자 설정 시스템

### 1. 사이드바 설정
```python
def _setup_sidebar(self):
    # 레벨 선택 (1-5)
    level = st.selectbox("투자 레벨", [1, 2, 3, 4, 5], format_func=self._get_level_description)
    
    # WMTI 선택 (16가지)
    wmti_type = st.selectbox("투자 성향", list(WMTI_TYPE_DESCRIPTIONS.keys()))
    
    # MPTI 선택 (6가지)
    mpti_type = st.selectbox("설명 스타일", list(MPTI_STYLES.keys()))
    
    # 관심종목 입력
    interest_stocks = st.text_area("관심종목", value="삼성전자, 현대차, SK하이닉스")
```

### 2. 설정 저장
```python
# Streamlit session_state 활용
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        'level': 1,
        'wmti_type': 'APWL',
        'mpti_type': 'Fact'
    }
```


## 🔧 기술적 특징

### 1. 모듈화 설계
```
app/modules/
├── market_data.py      # 시장 데이터
├── daily_briefing.py   # 데일리 브리핑
├── recommendations.py  # 추천 시스템
└── news_analyzer.py    # 뉴스 분석
```

### 2. 오류 처리 및 Fallback
```python
1. pykrx (한국 데이터)
2. yfinance (글로벌 데이터)
3. 캐시된 데이터
4. 기본값
```

### 3. 성능 최적화
- **캐싱**: `@st.cache_data` 데코레이터
- **비동기 처리**: API 호출 최적화
- **데이터 사전 계산**: 추천 점수 캐시


