"""
시장 데이터 관리 모듈
- 실시간 시장 데이터 수집
- 캐싱 시스템
- Yahoo Finance API 활용
"""

import requests
import time
import logging
from typing import Dict, Optional
import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, Optional, List
import time

# 조건부 import
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logging.warning("yfinance 라이브러리가 설치되지 않았습니다.")

try:
    from pykrx import stock
    PYKRX_AVAILABLE = True
except ImportError:
    PYKRX_AVAILABLE = False
    logging.warning("pykrx 라이브러리가 설치되지 않았습니다.")

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# 프로젝트 루트 경로를 Python 경로에 추가
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from chatbot.config import Config

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 설정 객체
config = Config()

class RealTimeMarketData:
    """실시간 시장 데이터 수집 클래스"""
    
    def __init__(self):
        """초기화"""
        self.session = requests.Session()
        self.timeout = 10
        
        # 설정 객체
        self.config = Config()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.cache = {}
        self.cache_timeout = 30  # 30초 캐시
    
    def get_korean_market_data(self) -> Dict:
        """한국 시장 실시간 데이터 수집"""
        cache_key = 'korean_market'
        current_time = time.time()
        
        # 캐시 확인
        if cache_key in self.cache:
            cached_data, cache_time = self.cache[cache_key]
            if current_time - cache_time < self.cache_timeout:
                logger.info("캐시된 한국 시장 데이터 사용")
                return cached_data
        
        try:
            # 1차: 네이버 금융
            logger.info("네이버 금융에서 실시간 데이터 수집 시도...")
            naver_data = self._get_naver_finance_data()
            if naver_data:
                logger.info("네이버 금융 데이터 수집 성공")
                self.cache[cache_key] = (naver_data, current_time)
                return naver_data
            
            # 2차: pykrx 사용
            if PYKRX_AVAILABLE:
                logger.info("pykrx에서 실시간 데이터 수집 시도...")
                kospi_data = self._get_pykrx_data('1001')  # KOSPI
                kosdaq_data = self._get_pykrx_data('2001')  # KOSDAQ
                
                if kospi_data and kosdaq_data:
                    logger.info("pykrx 데이터 수집 성공")
                    result = {
                        'KOSPI': kospi_data,
                        'KOSDAQ': kosdaq_data
                    }
                    self.cache[cache_key] = (result, current_time)
                    return result
            
            # 3차: Yahoo Finance API 사용
            if YFINANCE_AVAILABLE:
                logger.info("Yahoo Finance에서 실시간 데이터 수집 시도...")
                kospi_data = self._get_yahoo_finance_data('^KS11')  # KOSPI
                kosdaq_data = self._get_yahoo_finance_data('^KQ11')  # KOSDAQ
                
                result = {
                    'KOSPI': kospi_data,
                    'KOSDAQ': kosdaq_data
                }
                
                logger.info("Yahoo Finance 데이터 수집 성공")
                # 캐시 저장
                self.cache[cache_key] = (result, current_time)
                return result
            
            # 4차: fallback 데이터
            logger.warning("모든 실시간 데이터 수집 실패, fallback 데이터 사용")
            return self._get_fallback_data()
            
        except Exception as e:
            logger.error(f"한국 시장 데이터 수집 실패: {e}")
            return self._get_fallback_data()
    
    def get_global_market_data(self) -> Dict:
        """글로벌 시장 실시간 데이터 수집"""
        cache_key = 'global_market'
        current_time = time.time()
        
        # 캐시 확인
        if cache_key in self.cache:
            cached_data, cache_time = self.cache[cache_key]
            if current_time - cache_time < self.cache_timeout:
                return cached_data
        
        try:
            # Yahoo Finance API 사용
            sp500_data = self._get_yahoo_finance_data('^GSPC')  # S&P 500
            nasdaq_data = self._get_yahoo_finance_data('^IXIC')  # NASDAQ
            
            result = {
                'S&P 500': sp500_data,
                'NASDAQ': nasdaq_data
            }
            
            # 캐시 저장
            self.cache[cache_key] = (result, current_time)
            return result
            
        except Exception as e:
            logger.error(f"글로벌 시장 데이터 수집 실패: {e}")
            return self._get_fallback_global_data()
    
    def _get_pykrx_data(self, index_code: str) -> Dict:
        """pykrx를 사용한 한국 지수 데이터 가져오기"""
        if not PYKRX_AVAILABLE:
            return None
        
        try:
            from datetime import datetime, timedelta
            
            # 최근 거래일 데이터 가져오기
            today = datetime.now()
            
            # 최근 5일 데이터 가져오기
            start_date = today - timedelta(days=5)
            df = stock.get_index_ohlcv_by_date(
                start_date.strftime('%Y%m%d'),
                today.strftime('%Y%m%d'),
                index_code
            )
            
            if not df.empty:
                # 최신 데이터
                latest_data = df.iloc[-1]
                
                # 이전 거래일 데이터 (최소 2개 이상 있을 때)
                if len(df) >= 2:
                    prev_data = df.iloc[-2]
                    current_price = latest_data['종가']
                    prev_price = prev_data['종가']
                    change_amount = current_price - prev_price
                    change_percent = (change_amount / prev_price) * 100
                else:
                    # 데이터가 1개만 있는 경우
                    current_price = latest_data['종가']
                    change_amount = 0
                    change_percent = 0
                
                return {
                    'current_price': current_price,
                    'change_amount': change_amount,
                    'change_percent': change_percent,
                    'volume': latest_data.get('거래량', 0),
                    'market_cap': 0  # 지수는 시가총액 정보 없음
                }
            
            return None
            
        except Exception as e:
            logger.error(f"pykrx 데이터 수집 실패 ({index_code}): {e}")
            return None
    
    def _get_yahoo_finance_data(self, symbol: str) -> Dict:
        """Yahoo Finance에서 데이터 가져오기"""
        if not YFINANCE_AVAILABLE:
            return self._get_fallback_single_data(symbol)
        
        try:
            ticker = yf.Ticker(symbol)
            
            # 최근 5일 데이터 가져오기
            hist = ticker.history(period="5d")
            
            if len(hist) >= 2:
                current_price = hist['Close'].iloc[-1]
                prev_price = hist['Close'].iloc[-2]
                change_amount = current_price - prev_price
                change_percent = (change_amount / prev_price) * 100
                
                return {
                    'current_price': current_price,
                    'change_amount': change_amount,
                    'change_percent': change_percent,
                    'volume': hist['Volume'].iloc[-1] if 'Volume' in hist.columns else 0,
                    'market_cap': 0  # 지수는 시가총액 정보 없음
                }
            else:
                # 데이터가 부족한 경우 기본 정보 사용
                info = ticker.info
                current_price = info.get('regularMarketPrice', 0)
                change_amount = info.get('regularMarketChange', 0)
                change_percent = info.get('regularMarketChangePercent', 0)
                
                return {
                    'current_price': current_price,
                    'change_amount': change_amount,
                    'change_percent': change_percent,
                    'volume': info.get('volume', 0),
                    'market_cap': info.get('marketCap', 0)
                }
            
        except Exception as e:
            logger.error(f"Yahoo Finance 데이터 수집 실패 ({symbol}): {e}")
            return self._get_fallback_single_data(symbol)
    
    def _get_naver_finance_data(self) -> Dict:
        """네이버 금융에서 실시간 데이터 가져오기"""
        try:
            from bs4 import BeautifulSoup
            
            # 네이버 금융 지수 페이지
            url = f"{self.config.NAVER_FINANCE_BASE_URL}/sise/sise_index.nhn"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # KOSPI 데이터 추출
            kospi_row = soup.find('tr', {'id': 'KOSPI'})
            if kospi_row:
                kospi_cells = kospi_row.find_all('td')
                if len(kospi_cells) >= 4:
                    kospi_price = float(kospi_cells[1].get_text(strip=True).replace(',', ''))
                    kospi_change = float(kospi_cells[2].get_text(strip=True).replace(',', ''))
                    kospi_change_percent = float(kospi_cells[3].get_text(strip=True).replace('%', ''))
                    
                    kospi_data = {
                        'current_price': kospi_price,
                        'change_amount': kospi_change,
                        'change_percent': kospi_change_percent,
                        'volume': 0,
                        'market_cap': 0
                    }
                else:
                    kospi_data = None
            else:
                kospi_data = None
            
            # KOSDAQ 데이터 추출
            kosdaq_row = soup.find('tr', {'id': 'KOSDAQ'})
            if kosdaq_row:
                kosdaq_cells = kosdaq_row.find_all('td')
                if len(kosdaq_cells) >= 4:
                    kosdaq_price = float(kosdaq_cells[1].get_text(strip=True).replace(',', ''))
                    kosdaq_change = float(kosdaq_cells[2].get_text(strip=True).replace(',', ''))
                    kosdaq_change_percent = float(kosdaq_cells[3].get_text(strip=True).replace('%', ''))
                    
                    kosdaq_data = {
                        'current_price': kosdaq_price,
                        'change_amount': kosdaq_change,
                        'change_percent': kosdaq_change_percent,
                        'volume': 0,
                        'market_cap': 0
                    }
                else:
                    kosdaq_data = None
            else:
                kosdaq_data = None
            
            if kospi_data and kosdaq_data:
                return {
                    'KOSPI': kospi_data,
                    'KOSDAQ': kosdaq_data
                }
            
            return None
            
        except Exception as e:
            logger.error(f"네이버 금융 데이터 수집 실패: {e}")
            return None
    
    def _get_fallback_data(self) -> Dict:
        """한국 시장 fallback 데이터"""
        return {
            'KOSPI': {
                'current_price': 3210.01,  # 2025년 8월 9일 기준
                'change_amount': 15.5,
                'change_percent': 0.48,
                'volume': 500000000,
                'market_cap': 2000000000000
            },
            'KOSDAQ': {
                'current_price': 1050.0,  # 2025년 8월 9일 기준
                'change_amount': -8.2,
                'change_percent': -0.77,
                'volume': 300000000,
                'market_cap': 800000000000
            }
        }
    
    def _get_fallback_global_data(self) -> Dict:
        """글로벌 시장 fallback 데이터"""
        return {
            'S&P 500': {
                'current_price': 4500.0,
                'change_amount': 25.3,
                'change_percent': 0.56,
                'volume': 2000000000,
                'market_cap': 40000000000000
            },
            'NASDAQ': {
                'current_price': 14000.0,
                'change_amount': -45.7,
                'change_percent': -0.33,
                'volume': 3000000000,
                'market_cap': 25000000000000
            }
        }
    
    def _get_fallback_single_data(self, symbol: str) -> Dict:
        """fallback 데이터"""
        fallback_data = {
            '^KS11': {'current_price': 3210.01, 'change_amount': 15.5, 'change_percent': 0.48},  # KOSPI
            '^KQ11': {'current_price': 1050.0, 'change_amount': -8.2, 'change_percent': -0.77},  # KOSDAQ
            '^GSPC': {'current_price': 4500.0, 'change_amount': 25.3, 'change_percent': 0.56},
            '^IXIC': {'current_price': 14000.0, 'change_amount': -45.7, 'change_percent': -0.33}
        }
        
        return fallback_data.get(symbol, {
            'current_price': 1000.0,
            'change_amount': 0.0,
            'change_percent': 0.0,
            'volume': 0,
            'market_cap': 0
        })
