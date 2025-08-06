"""
뉴스 분석 모듈
- 종목별 뉴스 크롤링
- 감정분석 (긍정/부정)
- 레벨별 뉴스 요약
- 실시간 주가 정보 수집
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from bs4 import BeautifulSoup
import re
import time
import random
import json

# GPT 클라이언트 임포트
from chatbot.gpt_client import GPTClient

logger = logging.getLogger(__name__)

class NewsAnalyzer:
    """뉴스 분석 클래스"""
    
    def __init__(self):
        """초기화"""
        self.gpt_client = GPTClient()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_stock_news(self, stock_name: str, days: int = 1) -> List[Dict]:
        """
        종목별 뉴스 수집
        
        Args:
            stock_name: 종목명
            days: 수집할 일수
            
        Returns:
            뉴스 리스트
        """
        try:
            # 네이버 금융 뉴스 크롤링
            news_list = self._crawl_naver_finance_news(stock_name, days)
            
            # 감정분석 및 요약
            analyzed_news = []
            for news in news_list[:5]:  # 상위 5개만 분석
                sentiment = self._analyze_sentiment(news['title'] + " " + news['summary'])
                news['sentiment'] = sentiment
                analyzed_news.append(news)
            
            return analyzed_news
            
        except Exception as e:
            logger.error(f"뉴스 수집 중 오류: {e}")
            return self._get_sample_news(stock_name)
    
    def _crawl_naver_finance_news(self, stock_name: str, days: int) -> List[Dict]:
        """네이버 금융 뉴스 크롤링"""
        try:
            # 종목 코드 찾기 (간단한 매핑)
            stock_code = self._get_stock_code(stock_name)
            
            # 네이버 금융 뉴스 URL
            search_url = f"https://finance.naver.com/item/news_news.nhn?code={stock_code}&page=1"
            
            response = self.session.get(search_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            news_items = []
            
            # 뉴스 항목 파싱
            news_rows = soup.find_all('tr', class_='type5')
            
            for row in news_rows[:5]:  # 상위 5개만
                try:
                    title_elem = row.find('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = "https://finance.naver.com" + title_elem.get('href', '')
                    
                    # 날짜 추출
                    date_elem = row.find('td', class_='date')
                    date = date_elem.get_text(strip=True) if date_elem else ""
                    
                    # 요약 (제목 기반)
                    summary = self._generate_summary_from_title(title)
                    
                    news_items.append({
                        'title': title,
                        'summary': summary,
                        'date': date,
                        'link': link,
                        'source': 'NAVER Finance'
                    })
                    
                except Exception as e:
                    logger.warning(f"뉴스 항목 파싱 실패: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            logger.error(f"네이버 금융 크롤링 실패: {e}")
            return []
    
    def _get_stock_code(self, stock_name: str) -> str:
        """종목명으로 종목 코드 찾기"""
        # 주요 종목 코드 매핑
        stock_codes = {
            '삼성전자': '005930',
            'SK하이닉스': '000660',
            'LG에너지솔루션': '373220',
            '현대차': '005380',
            '기아': '000270',
            'POSCO홀딩스': '005490',
            'TIGER 반도체': '091230',
            'TIGER 2차전지테마': '306540',
            'TIGER 미국 S&P500': '390750',
            'KOSPI': 'KS11',
            'KOSDAQ': 'KQ11'
        }
        
        return stock_codes.get(stock_name, '005930') 
    
    def _analyze_sentiment(self, text: str) -> str:
        """
        텍스트 감정분석
        
        Args:
            text: 분석할 텍스트
            
        Returns:
            "긍정적" 또는 "부정적"
        """
        try:
            # GPT를 활용한 감정분석
            prompt = f"""
            다음 뉴스 제목과 내용을 읽고 감정을 분석해주세요.
            
            텍스트: {text}
            
            다음 중 하나로만 답변해주세요:
            - 긍정적: 좋은 소식, 성장, 상승, 개선 등의 내용
            - 부정적: 나쁜 소식, 하락, 위험, 문제 등의 내용
            - 중립적: 특별한 감정적 색채가 없는 내용
            """
            
            response = self.gpt_client.call_gpt([{"role": "user", "content": prompt}])
            
            if "긍정" in response:
                return "긍정적"
            elif "부정" in response:
                return "부정적"
            else:
                return "중립적"
                
        except Exception as e:
            logger.error(f"감정분석 실패: {e}")
            return "중립적"
    
    def _generate_summary_from_title(self, title: str) -> str:
        """제목에서 요약 생성"""
        try:
            # 간단한 요약 생성
            if len(title) > 50:
                return title[:50] + "..."
            return title
            
        except Exception as e:
            logger.error(f"요약 생성 실패: {e}")
            return title
    
    def get_level_specific_summary(self, news_list: List[Dict], level: int) -> List[Dict]:
        """
        레벨별 뉴스 요약 생성
        
        Args:
            news_list: 뉴스 리스트
            level: 사용자 레벨 (1-5)
            
        Returns:
            레벨별 요약된 뉴스 리스트
        """
        try:
            summarized_news = []
            
            for news in news_list:
                # 레벨별 요약 생성
                if level == 1:
                    summary = self._create_level1_summary(news)
                elif level == 3:
                    summary = self._create_level3_summary(news)
                else:
                    summary = self._create_level5_summary(news)
                
                news['level_summary'] = summary
                summarized_news.append(news)
            
            return summarized_news
            
        except Exception as e:
            logger.error(f"레벨별 요약 생성 실패: {e}")
            return news_list
    
    def _create_level1_summary(self, news: Dict) -> str:
        """Level 1 (초보자) 요약"""
        try:
            prompt = f"""
            다음 뉴스를 초등학생도 이해할 수 있게 쉽게 요약해주세요.
            친근하고 쉬운 말로 설명해주세요.
            
            뉴스 제목: {news['title']}
            뉴스 내용: {news['summary']}
            """
            
            response = self.gpt_client.call_gpt([{"role": "user", "content": prompt}])
            return response
            
        except Exception as e:
            logger.error(f"Level 1 요약 생성 실패: {e}")
            return news['summary']
    
    def _create_level3_summary(self, news: Dict) -> str:
        """Level 3 (중급자) 요약"""
        try:
            prompt = f"""
            다음 뉴스를 일반 성인이 이해할 수 있게 요약해주세요.
            핵심 내용과 이유를 포함해서 설명해주세요.
            
            뉴스 제목: {news['title']}
            뉴스 내용: {news['summary']}
            """
            
            response = self.gpt_client.call_gpt([{"role": "user", "content": prompt}])
            return response
            
        except Exception as e:
            logger.error(f"Level 3 요약 생성 실패: {e}")
            return news['summary']
    
    def _create_level5_summary(self, news: Dict) -> str:
        """Level 5 (전문가) 요약"""
        try:
            prompt = f"""
            다음 뉴스를 투자 전문가 관점에서 분석해주세요.
            시장 영향도와 투자 시사점을 포함해서 설명해주세요.
            
            뉴스 제목: {news['title']}
            뉴스 내용: {news['summary']}
            """
            
            response = self.gpt_client.call_gpt([{"role": "user", "content": prompt}])
            return response
            
        except Exception as e:
            logger.error(f"Level 5 요약 생성 실패: {e}")
            return news['summary']
    
    def _get_sample_news(self, stock_name: str) -> List[Dict]:
        """샘플 뉴스 데이터 (크롤링 실패 시 사용)"""
        return [
            {
                'title': f'{stock_name} 실적 개선 전망',
                'summary': f'{stock_name}의 최근 실적이 좋아져서 주가가 올라갈 것으로 예상됩니다.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'link': '#',
                'source': 'NAVER Finance',
                'sentiment': '긍정적',
                'level_summary': f'{stock_name}는 최근 실적이 좋아져서 주가가 올라갈 것으로 예상됩니다.'
            },
            {
                'title': f'{stock_name} 신기술 개발 성공',
                'summary': f'{stock_name}가 새로운 기술을 개발하여 시장에서 주목받고 있습니다.',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'link': '#',
                'source': '한국경제',
                'sentiment': '긍정적',
                'level_summary': f'{stock_name}가 새로운 기술을 개발하여 시장에서 주목받고 있습니다.'
            }
        ]
    
    def get_market_news(self) -> Dict:
        """시장 전체 뉴스 수집"""
        try:
            # 주요 시장 뉴스 키워드
            keywords = ['KOSPI', 'KOSDAQ', '금리', '환율', '원달러']
            
            market_news = {}
            for keyword in keywords:
                news_list = self.get_stock_news(keyword, days=1)
                if news_list:
                    market_news[keyword] = news_list[:2]  # 상위 2개만
            
            return market_news
            
        except Exception as e:
            logger.error(f"시장 뉴스 수집 실패: {e}")
            return {}

class StockPriceAnalyzer:
    """주가 분석 클래스"""
    
    def __init__(self):
        """초기화"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_stock_price_info(self, stock_name: str) -> Dict:
        """
        종목별 주가 정보 수집
        
        Args:
            stock_name: 종목명
            
        Returns:
            주가 정보 딕셔너리
        """
        try:
            # 종목 코드 찾기
            stock_code = self._get_stock_code(stock_name)
            
            # pykrx 라이브러리 사용 시도 (더 안정적)
            try:
                from pykrx import stock
                today = datetime.now().strftime('%Y%m%d')
                yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
                
                # 오늘 데이터 가져오기
                df = stock.get_market_ohlcv_by_date(fromdate=yesterday, todate=today, ticker=stock_code)
                
                if not df.empty:
                    current_price = df.iloc[-1]['종가']
                    open_price = df.iloc[-1]['시가']
                    high_price = df.iloc[-1]['고가']
                    low_price = df.iloc[-1]['저가']
                    volume = df.iloc[-1]['거래량']
                    
                    # 전일 대비 변동 계산
                    if len(df) > 1:
                        prev_close = df.iloc[-2]['종가']
                        change_amount = current_price - prev_close
                        change_percent = (change_amount / prev_close) * 100
                    else:
                        change_amount = 0
                        change_percent = 0
                    
                    # 시가총액 정보 (pykrx에서 제공하지 않으므로 별도 처리)
                    market_cap = "N/A"
                    
                    return {
                        'current_price': str(int(current_price)),
                        'change_percent': round(change_percent, 2),
                        'change_amount': str(int(change_amount)),
                        'volume': str(int(volume)),
                        'market_cap': market_cap,
                        'high': str(int(high_price)),
                        'low': str(int(low_price)),
                        'open': str(int(open_price))
                    }
            except ImportError:
                logger.info("pykrx 라이브러리가 설치되지 않았습니다. 네이버 크롤링을 사용합니다.")
            except Exception as e:
                logger.warning(f"pykrx 사용 실패: {e}. 네이버 크롤링을 사용합니다.")
            
            # 네이버 금융에서 주가 정보 크롤링 (fallback)
            price_info = self._crawl_naver_stock_price(stock_code)
            
            if price_info:
                return price_info
            else:
                # 크롤링 실패 시 샘플 데이터 반환
                return self._get_sample_price_data(stock_name)
                
        except Exception as e:
            logger.error(f"주가 정보 수집 실패: {e}")
            return self._get_sample_price_data(stock_name)
    
    def _get_stock_code(self, stock_name: str) -> str:
        """종목명으로 종목 코드 찾기"""
        # 주요 종목 코드 매핑
        stock_codes = {
            '삼성전자': '005930',
            'SK하이닉스': '000660',
            'LG에너지솔루션': '373220',
            '현대차': '005380',
            '기아': '000270',
            'POSCO홀딩스': '005490',
            'TIGER 반도체': '091230',
            'TIGER 2차전지테마': '306540',
            'TIGER 미국 S&P500': '390750',
            'KOSPI': 'KS11',
            'KOSDAQ': 'KQ11'
        }
        
        return stock_codes.get(stock_name, '005930')  # 기본값: 삼성전자
    
    def _crawl_naver_stock_price(self, stock_code: str) -> Optional[Dict]:
        """네이버 금융에서 주가 정보 크롤링"""
        try:
            # 네이버 금융 주가 페이지 URL (새로운 URL 형식 사용)
            url = f"https://finance.naver.com/item/main.naver?code={stock_code}"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 현재가 추출 (여러 방법 시도)
            current_price = "0"
            price_selectors = [
                'div.no_today span.blind',
                'div.no_today em span.blind',
                'div.today p.no_today span.blind',
                'div.today p.no_today em span.blind'
            ]
            
            for selector in price_selectors:
                price_elem = soup.select_one(selector)
                if price_elem:
                    current_price = price_elem.get_text(strip=True)
                    break
            
            # 변동 정보 추출 (여러 방법 시도)
            change_amount = "0"
            change_percent = "0"
            change_selectors = [
                'div.no_exday span.blind',
                'div.no_exday em span.blind',
                'div.today p.no_exday span.blind',
                'div.today p.no_exday em span.blind'
            ]
            
            for selector in change_selectors:
                change_elems = soup.select(selector)
                if len(change_elems) >= 2:
                    change_amount = change_elems[0].get_text(strip=True)
                    change_percent = change_elems[1].get_text(strip=True).replace('%', '')
                    break
            
            # 거래량 추출 (여러 방법 시도)
            volume = "0"
            volume_selectors = [
                'td:contains("거래량") + td',
                'th:contains("거래량") + td',
                'tr:contains("거래량") td:last-child'
            ]
            
            for selector in volume_selectors:
                try:
                    volume_elem = soup.select_one(selector)
                    if volume_elem:
                        volume = volume_elem.get_text(strip=True)
                        break
                except:
                    continue
            
            # 시가총액 추출 (여러 방법 시도)
            market_cap = "0"
            market_cap_selectors = [
                'td:contains("시가총액") + td',
                'th:contains("시가총액") + td',
                'tr:contains("시가총액") td:last-child'
            ]
            
            for selector in market_cap_selectors:
                try:
                    market_cap_elem = soup.select_one(selector)
                    if market_cap_elem:
                        market_cap = market_cap_elem.get_text(strip=True)
                        break
                except:
                    continue
            
            # 숫자 정리 (쉼표 제거)
            current_price = current_price.replace(',', '')
            change_amount = change_amount.replace(',', '')
            volume = volume.replace(',', '')
            market_cap = market_cap.replace(',', '')
            
            return {
                'current_price': current_price,
                'change_percent': float(change_percent) if change_percent != "0" else 0,
                'change_amount': change_amount,
                'volume': volume,
                'market_cap': market_cap,
                'high': "0",  # 추가 정보는 필요시 확장
                'low': "0",
                'open': "0"
            }
            
        except Exception as e:
            logger.error(f"네이버 주가 크롤링 실패: {e}")
            return None
    
    def _get_sample_price_data(self, stock_name: str) -> Dict:
        """샘플 주가 데이터 (크롤링 실패 시 사용)"""
        # 종목별 다른 샘플 데이터
        sample_data = {
            '삼성전자': {
                'current_price': '75,800',
                'change_percent': 1.2,
                'change_amount': '+900',
                'volume': '1,234만주',
                'market_cap': '45.2조원'
            },
            'SK하이닉스': {
                'current_price': '138,500',
                'change_percent': 2.8,
                'change_amount': '+3,800',
                'volume': '567만주',
                'market_cap': '95.8조원'
            },
            'TIGER 반도체': {
                'current_price': '38,310',
                'change_percent': 2.81,
                'change_amount': '+1,045',
                'volume': '1,234만주',
                'market_cap': '45.2조원'
            }
        }
        
        return sample_data.get(stock_name, {
            'current_price': '50,000',
            'change_percent': 0.5,
            'change_amount': '+250',
            'volume': '100만주',
            'market_cap': '10조원'
        })
    
    def get_market_indices(self) -> Dict:
        """주요 지수 정보 수집"""
        try:
            # 실제 지수 데이터 크롤링
            indices = self._crawl_market_indices()
            
            if indices:
                return indices
            else:
                # 크롤링 실패 시 샘플 데이터 반환
                return self._get_sample_indices_data()
                
        except Exception as e:
            logger.error(f"지수 정보 수집 실패: {e}")
            return self._get_sample_indices_data()
    
    def _crawl_market_indices(self) -> Optional[Dict]:
        """실제 시장 지수 크롤링"""
        try:
            # 네이버 금융 지수 페이지
            url = "https://finance.naver.com/sise/"
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            indices = {}
            
            # KOSPI
            kospi_elem = soup.find('span', id='KOSPI_now')
            if kospi_elem:
                kospi_value = kospi_elem.get_text(strip=True)
                kospi_change_elem = soup.find('span', id='KOSPI_change')
                if kospi_change_elem:
                    kospi_change = kospi_change_elem.get_text(strip=True)
                    indices['KOSPI'] = {
                        'value': kospi_value,
                        'change': float(kospi_change.replace('%', '')) if kospi_change != '0.00%' else 0,
                        'change_amount': kospi_change
                    }
            
            # KOSDAQ
            kosdaq_elem = soup.find('span', id='KOSDAQ_now')
            if kosdaq_elem:
                kosdaq_value = kosdaq_elem.get_text(strip=True)
                kosdaq_change_elem = soup.find('span', id='KOSDAQ_change')
                if kosdaq_change_elem:
                    kosdaq_change = kosdaq_change_elem.get_text(strip=True)
                    indices['KOSDAQ'] = {
                        'value': kosdaq_value,
                        'change': float(kosdaq_change.replace('%', '')) if kosdaq_change != '0.00%' else 0,
                        'change_amount': kosdaq_change
                    }
            
            return indices if indices else None
            
        except Exception as e:
            logger.error(f"지수 크롤링 실패: {e}")
            return None
    
    def _get_sample_indices_data(self) -> Dict:
        """샘플 지수 데이터"""
        return {
            'KOSPI': {
                'value': '2,750.32',
                'change': 0.5,
                'change_amount': '+13.75'
            },
            'KOSDAQ': {
                'value': '850.15',
                'change': -0.2,
                'change_amount': '-1.70'
            },
            'S&P500': {
                'value': '4,850.25',
                'change': 0.8,
                'change_amount': '+38.50'
            },
            'NASDAQ': {
                'value': '15,250.80',
                'change': 1.2,
                'change_amount': '+180.96'
            }
        } 