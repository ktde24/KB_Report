# 📊 KB 맞춤형 투자 분석 시스템

## 🎯 프로젝트 개요
사용자의 투자 성향(WMTI)과 설명 선호도(MPTI)에 따라 개인화된 투자 조언을 제공하는 AI 기반 투자 분석 시스템입니다. 실시간 시장 데이터, 뉴스 감정분석, GPT 기반 추천 시스템을 통합하여 사용자 맞춤형 투자 경험을 제공합니다.

## 🏆 공모전 제출 프로젝트 특징

### 🎨 **개인화 시스템**
- **WMTI (Wealth Management Type Indicator)**: 16가지 투자 성향 분류
- **MPTI (My Personal Type Indicator)**: 6가지 설명 스타일 분류
- **레벨별 맞춤화**: 초보자~전문가 레벨별 콘텐츠 제공
- **동적 프롬프트 생성**: 사용자 프로필 기반 GPT 프롬프트 최적화

### 🤖 **AI 기반 분석**
- **GPT-3.5-turbo 통합**: 모든 분석 결과를 자연어로 변환
- **실시간 뉴스 감정분석**: 네이버 금융 뉴스 크롤링 및 GPT 감정분석
- **동적 시장 해석**: 사용자 레벨별 맞춤 시장 분석
- **포트폴리오 분석**: 구성종목 상세 분석 및 뉴스 연동

### 📊 **실시간 데이터 통합**
- **다중 데이터 소스**: pykrx, yfinance, 네이버 금융, DART API
- **실시간 시장 데이터**: KOSPI, KOSDAQ, 글로벌 지수
- **성과 분석**: 수익률, 위험도, 자산규모 통합 분석
- **환율 정보**: 실시간 환율 데이터 제공

## 🔄 최근 주요 개선사항

### 📰 **뉴스 분석 시스템 개선**
- **관련성 필터링 강화**: 관련 없는 뉴스 자동 제거
- **해외 종목 매핑 개선**: NVDA, AMD, INTC 등 해외 종목 지원
- **헤드라인 표시 개선**: 뉴스 제목 명확하게 표시
- **제외 키워드 시스템**: "연체금", "신용사면" 등 관련 없는 키워드 자동 필터링

### 🎯 **추천 시스템 표시 개선**
- **일관된 형식**: "🏆 추천 ETF Top3" 형식으로 통일
- **Top3 추천**: 상위 3개 ETF만 표시하여 명확성 향상
- **추천 이유 표시**: 각 ETF별 구체적인 추천 이유 제공
- **투자 팁 섹션**: GPT 기반 일관된 투자 조언

### 🤖 **GPT 프롬프트 최적화**
- **일관된 설명 형식**: 매번 다른 형식의 설명 방지
- **구조화된 출력**: 명확한 섹션별 구분
- **사용자 레벨별 맞춤**: 레벨에 따른 설명 스타일 조정

## 🏗️ 프로젝트 구조

```
KB_Report/
├── app/                          # 메인 애플리케이션
│   ├── main.py                   # 메인 리포트 앱 (Streamlit)
│   ├── chatbot_app.py            # AI 챗봇 앱 (Streamlit)
│   └── modules/                  # 모듈화된 기능들
│       ├── __init__.py           # 모듈 초기화
│       ├── market_data.py        # 실시간 시장 데이터 
│       ├── daily_briefing.py     # 데일리 브리핑
│       ├── recommendations.py    # 추천 시스템 
│       ├── news_analyzer.py      # 뉴스 분석 
│       └── etf_constituent_analyzer.py # ETF 포트폴리오 분석
├── chatbot/                      # 챗봇 핵심 로직
│   ├── config.py                 # 설정 및 상수 (MPTI, WMTI, 레벨별 프롬프트)
│   ├── etf_analysis.py           # 종목 분석 
│   ├── etf_comparison.py         # 종목 비교 
│   ├── recommendation_engine.py  # 추천 엔진 
│   ├── gpt_client.py             # GPT 클라이언트 
│   └── utils.py                  # 유틸리티 함수 
├── dart_api/                     # DART API 연동
│   ├── main.py                   # DART 메인 실행 
│   ├── dart_api.py               # DART API 클라이언트 
│   ├── corpcode_loader.py        # 기업코드 로더 
│   ├── CORPCODE.xml              # 기업코드 데이터 
│   └── utils/                    # DART 유틸리티
│       └── text_extractor.py     # 텍스트 추출기 
├── data/                         # 데이터 파일들
│   ├── etf_scores_cache.csv      # 추천 점수 캐시 
│   ├── etf_re_bp_simplified.csv  # ETF 요약 데이터 
│   ├── 상품검색.csv              # ETF 상품 정보
│   ├── 수익률 및 총보수(기간).csv # 수익률 데이터 
│   ├── 투자위험(기간).csv        # 위험도 데이터 
│   ├── 자산규모 및 유동성(기간).csv # 자산규모 데이터
│   ├── 추적오차 및 괴리율(기간).csv # 추적오차 데이터 
│   ├── 참고지수(기간).csv        # 참고지수 데이터
│   ├── 상장법인목록.csv          # 상장법인 목록
│   └── ETF_시세_데이터_20230806_20250806.csv # 2023-2025년 시세 데이터
├── scripts/                      # 데이터 처리 스크립트
│   ├── fetch_etf_daily.py        # 일일 데이터 수집
│   ├── generate_etf_cache.py     # ETF 캐시 생성 
│   ├── calculate_risk_tier.py    # 위험도 계산 
│   ├── gpt_sentiment.py          # GPT 감정분석 
│   └── fix_encoding.py           # 인코딩 수정 
├── .git/                         # Git 저장소
├── .gitignore                    
├── README.md                     # 프로젝트 문서
├── REPORT_ANALYSIS.md            # 리포트 분석 문서
├── CHATBOT_ANALYSIS.md           # 챗봇 분석 문서 
├── run_app.py                    # 앱 실행 스크립트 
├── requirements.txt              # 의존성 패키지
└── .env                         # 환경변수 설정 (API 키 등)
```

## 🚀 실행 방법

### 1. 환경 설정
```bash
# 가상환경 생성 
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정
`.env` 파일을 생성하고 다음을 추가:
```env
# 필수 API 키
OPENAI_API_KEY=your_openai_api_key_here

# 선택적 설정 (기본값 사용 가능)
DATA_START_DATE=20230806
DATA_END_DATE=20250806
OPENAI_MODEL=gpt-3.5-turbo
NAVER_FINANCE_BASE_URL=https://finance.naver.com
DART_API_BASE_URL=https://opendart.fss.or.kr
```

### 3. 애플리케이션 실행
```bash
# 메인 리포트 앱
python -m streamlit run app/main.py

# 챗봇 앱
python -m streamlit run app/chatbot_app.py

# 또는 run_app.py 사용
python run_app.py
```

## 🎨 주요 기능

### 📊 맞춤형 데일리 리포트
- **실시간 시장 개요**: KOSPI, KOSDAQ, 글로벌 지수
- **동적 시장 해석**: GPT 기반 사용자 레벨별 맞춤 해석
- **데일리 브리핑**: 관심종목 분석 및 뉴스 크롤링 
- **추천 종목**: WMTI 기반 맞춤 추천 (GPT 기반 추천 근거 생성)
- **뉴스 감정분석**: 전체 크롤링 뉴스에 대한 GPT 기반 감정분석
- **ETF 포트폴리오 분석**: 구성종목 분석 및 상위 종목 뉴스 분석

### 🤖 AI 챗봇
- **자연어 상호작용**: 투자 관련 질문 답변
- **종목 분석**: 상세한 종목 정보 및 차트
- **포트폴리오 분석**: 포트폴리오 구성 및 최적화
- **시장 해석**: 실시간 시장 동향 분석

### 🎯 개인화 시스템
- **WMTI (Wealth Management Type Indicator)**: 16가지 투자 성향 분류
- **MPTI (My Personal Type Indicator)**: 6가지 설명 스타일
- **레벨별 맞춤화**: 초보자~전문가 레벨별 콘텐츠
- **동적 프롬프트 생성**: 사용자 프로필 기반 GPT 프롬프트 최적화

## 🔧 핵심 모듈 설명

### 1. Market Data (`modules/market_data.py`)
```python
# 실시간 시장 데이터 수집
- KOSPI/KOSDAQ 지수
- 글로벌 주요 지수 (S&P500, NASDAQ, 등)
- 환율 정보
- 다중 데이터 소스 (pykrx, yfinance, 네이버 금융)
```

### 2. Daily Briefing (`modules/daily_briefing.py`) 
```python
# 데일리 브리핑 생성
- 관심종목 시세 분석
- 뉴스 크롤링 및 요약
- 레벨별 맞춤 설명
- 종목 코드와 키워드 기반 검색 분리
```

### 3. Recommendations (`modules/recommendations.py`) 
```python
# 추천 시스템 (최근 개선사항)
- WMTI 기반 종목 추천
- 일관된 "🏆 추천 ETF Top3" 형식
- Top3 추천으로 명확성 향상
- GPT 기반 추천 근거 생성 (사용자 레벨별 맞춤)
- 추천 이유 명확하게 표시
```

### 4. News Analyzer (`modules/news_analyzer.py`) 
```python
# 뉴스 분석 시스템
- 네이버 뉴스 크롤링 (전체 뉴스 대상)
- GPT 감정분석 (모든 크롤링 뉴스)
- 레벨별 요약 생성 (1-5단계)
- 키워드 동적 생성 시스템
- 감정분석 결과 시각화
- 관련성 필터링 강화 (관련 없는 뉴스 자동 제거)
- 해외 종목 매핑 개선 (NVDA, AMD, INTC 등)
- 제외 키워드 시스템 ("연체금", "신용사면" 등)
- 헤드라인 표시 개선
```

### 5. GPT Client (`chatbot/gpt_client.py`)
```python
# GPT API 통합 클라이언트
- 동적 시장 해석 생성
- 사용자 레벨별 맞춤 콘텐츠
- MPTI 스타일 적용
- API 실패 시 폴백 로직
- 환경변수 기반 API 키 관리
- dart_api 호환성 지원
```

### 6. ETF Constituent Analyzer (`modules/etf_constituent_analyzer.py`)
```python
# ETF 포트폴리오 분석
- 구성종목 상세 분석
- 상위 3개 종목 뉴스 분석
- 업종별 분포 분석
- 포트폴리오 집중도 분석
```

### 7. Recommendation Engine (`chatbot/recommendation_engine.py`) - 개선됨
```python
# 추천 엔진
- WMTI 기반 추천 시스템
- 일관된 프롬프트 형식 생성
- 각 ETF별 구체적인 추천 이유 제공
- GPT 기반 일관된 투자 조언
```

## 📊 데이터 소스

### 정적 데이터
- **ETF 정보**: 상품검색.csv
- **성과 데이터**: 수익률 및 총보수(기간).csv
- **위험 데이터**: 투자위험(기간).csv
- **추천 점수**: etf_scores_cache.csv

### 실시간 데이터
- **pykrx**: 한국 주식/ETF 실시간 데이터
- **yfinance**: 글로벌 ETF 데이터
- **네이버 금융**: 뉴스 및 시세 정보
- **DART API**: 기업 공시 정보




