"""
추천 시스템 모듈
- WMTI 기반 추천 로직
- chatbot.recommendation_engine 통합
- 추천 카드 표시
"""

import streamlit as st
import pandas as pd
import logging
from typing import Dict, List, Optional


try:
    from chatbot.recommendation_engine import ETFRecommendationEngine
    from chatbot.config import Config
    CHATBOT_MODULES_AVAILABLE = True
except ImportError:
    CHATBOT_MODULES_AVAILABLE = False

logger = logging.getLogger(__name__)

class Recommendations:
    """추천 시스템 클래스"""
    
    def __init__(self):
        self.config = Config() if CHATBOT_MODULES_AVAILABLE else None
        self.data = {}  # 데이터 저장용
    
    def set_data(self, data: Dict[str, pd.DataFrame]):
        """데이터 설정"""
        self.data = data
    
    def display_recommendations(self, level: int, wmti_type: str, mpti_type: str, data: Dict[str, pd.DataFrame]):
        """추천 종목 표시"""
        st.markdown(f'<div class="section-header">🎯 추천 종목 <span class="level-indicator">Level {level}</span></div>', unsafe_allow_html=True)
        
        try:
            # 데이터 확인 및 디버깅
            if not data:
                st.error("데이터가 로드되지 않았습니다.")
                return
            
            # ETF 캐시 데이터 확인
            if 'etf_cache' not in data or data['etf_cache'].empty:
                st.error("ETF 캐시 데이터가 없습니다.")
                logger.warning("ETF 캐시 데이터가 비어있습니다.")
                return
            
            df = data['etf_cache']
            logger.info(f"ETF 캐시 데이터 로드: {len(df)}행, 컬럼: {list(df.columns)}")
            
            # chatbot.recommendation_engine 활용
            if CHATBOT_MODULES_AVAILABLE:
                user_profile = {
                    'level': level,
                    'wmti_type': wmti_type,
                    'mpti_type': mpti_type
                }
                
                # ETFRecommendationEngine 인스턴스 생성
                recommendation_engine = ETFRecommendationEngine()
                
                # 추천 종목 가져오기
                recommendations = recommendation_engine.fast_recommend_etfs(
                    user_profile=user_profile,
                    cache_df=df,
                    category_keyword="",  # 전체 종목에서 추천
                    top_n=5
                )
                
                if recommendations and len(recommendations) > 0:
                    # 추천 종목 표시
                    for i, rec in enumerate(recommendations, 1):
                        if '안내' in rec:
                            # 안내 메시지인 경우
                            st.info(rec['안내'])
                        else:
                            # 실제 추천 종목인 경우
                            # 실시간 데이터 가져오기
                            stock_code = rec.get('종목코드', 'N/A')
                            realtime_data = self._get_realtime_stock_data(stock_code)
                            
                            # 디버깅: 추천 결과 로그
                            logger.info(f"추천 결과 {i}: {rec}")
                            logger.info(f"추천 결과 {i} 컬럼들: {list(rec.keys())}")
                            
                            # ETF 이름을 여러 필드에서 찾기
                            etf_name = (
                                rec.get('종목명') or 
                                rec.get('ETF명') or 
                                rec.get('상품명') or 
                                rec.get('name') or 
                                'N/A'
                            )
                            
                            logger.info(f"ETF 이름 추출 결과: {etf_name}")
                            
                            # 추천 엔진 결과를 카드 형식에 맞게 변환
                            card_data = {
                                'name': etf_name,
                                'code': stock_code,
                                'score': rec.get('final_score', rec.get('score', 0)),
                                'risk_tier': rec.get('risk_tier', 1),
                                'volatility': rec.get('변동성', '보통'),
                                'fee': rec.get('총보수', rec.get('fee', 0)),
                                'current_price': realtime_data.get('current_price', 0),
                                'volume': realtime_data.get('volume', 0),
                                'return_1y': rec.get('1년수익률', rec.get('return_1y', 0)),
                                'return_3y': rec.get('3년수익률', rec.get('return_3y', 0)),
                                'reasons': self._generate_recommendation_reasons(rec, level, wmti_type)
                            }
                            self._display_recommendation_card(card_data, level, i, mpti_type)
                    
                    # 추천 설명 생성 (GPT API 호출)
                    try:
                        import openai
                        import os
                        
                        api_key = os.getenv('OPENAI_API_KEY')
                        if api_key:
                            client = openai.OpenAI(api_key=api_key)
                            
                            # 프롬프트 생성
                            prompt = recommendation_engine.generate_recommendation_explanation(
                                recommendations=recommendations,
                                user_profile=user_profile,
                                category_keyword="",
                                context_docs=None
                            )
                            
                            # GPT API 호출
                            response = client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[
                                    {"role": "system", "content": "당신은 KB 투자 전문 상담사입니다. 사용자에게 친근하고 이해하기 쉬운 투자 조언을 제공하세요."},
                                    {"role": "user", "content": prompt}
                                ],
                                max_tokens=800,
                                temperature=0.3
                            )
                            
                            explanation = response.choices[0].message.content.strip()
                            
                            if explanation:
                                st.markdown("**📝 추천 근거**")
                                st.write(explanation)
                        else:
                            st.info("OpenAI API 키가 설정되지 않아 추천 근거를 생성할 수 없습니다.")
                    
                    except Exception as e:
                        logger.error(f"추천 근거 생성 실패: {e}")
                        st.info("추천 근거를 생성하는 중 오류가 발생했습니다.")
                
                else:
                    st.warning("추천 종목을 찾을 수 없습니다.")
            
            else:
                # chatbot 모듈이 없으면 기본 추천 로직 사용
                recommendations = self._get_actual_recommendations(level, wmti_type, data)
                
                if recommendations:
                    for i, rec in enumerate(recommendations, 1):
                        self._display_recommendation_card(rec, level, i, mpti_type)
                else:
                    st.warning("추천 종목을 찾을 수 없습니다.")
        
        except Exception as e:
            st.error(f"추천 종목 생성 중 오류: {e}")
            logger.error(f"추천 종목 생성 오류: {e}")
    
    def _get_actual_recommendations(self, level: int, wmti_type: str, data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """실제 추천 종목 가져오기 (fallback)"""
        try:
            if not data or 'etf_cache' not in data:
                logger.warning("ETF 캐시 데이터가 없습니다.")
                return []
            
            df = data['etf_cache']
            
            # WMTI 타입에 따른 점수 컬럼 매핑
            wmti_score_mapping = {
                'APWL': 'score_APWL', 'APML': 'score_APML', 'APWC': 'score_APWC', 'APMC': 'score_APMC',
                'APWH': 'score_APWH', 'APMH': 'score_APMH', 'APWS': 'score_APWS', 'APMS': 'score_APMS',
                'ABWL': 'score_ABWL', 'ABML': 'score_ABML', 'ABWC': 'score_ABWC', 'ABMC': 'score_ABMC',
                'ABWH': 'score_ABWH', 'ABMH': 'score_ABMH', 'ABWS': 'score_ABWS', 'ABMS': 'score_ABMS'
            }
            
            score_column = wmti_score_mapping.get(wmti_type)
            
            if score_column and score_column in df.columns:
                # 점수 기준으로 정렬
                df_sorted = df.sort_values(by=score_column, ascending=False)
                
                # 사용자 레벨에 따른 필터링
                if level <= 2:  # 초보자
                    df_filtered = df_sorted[df_sorted['risk_tier'] <= 2]
                elif level == 3:  # 중급자
                    df_filtered = df_sorted[df_sorted['risk_tier'] <= 3]
                else:  # 고급자
                    df_filtered = df_sorted
                
                # 추천 데이터 생성
                recommendations = []
                for _, row in df_filtered.head(10).iterrows():
                    # 실시간 데이터 가져오기
                    stock_code = row.get('종목코드', '')
                    realtime_data = self._get_realtime_stock_data(stock_code)
                    
                    # ETF 이름을 여러 필드에서 찾기
                    etf_name = None
                    
                    # 1. 직접적인 이름 필드들 확인
                    name_fields = ['종목명', 'ETF명', '상품명', 'name', 'ETF이름', '상품이름']
                    for field in name_fields:
                        if field in row and row[field] and str(row[field]).strip() != '' and str(row[field]).strip() != 'nan':
                            etf_name = str(row[field]).strip()
                            break
                    
                    # 2. 분류체계나 기타 필드에서 이름 추출
                    if not etf_name:
                        category_fields = ['분류체계', '기초지수', '운용사']
                        for field in category_fields:
                            if field in row and row[field] and str(row[field]).strip() != '' and str(row[field]).strip() != 'nan':
                                etf_name = str(row[field]).strip()
                                break
                    
                    # 3. 기본값 설정
                    if not etf_name or etf_name == 'nan':
                        etf_name = f"ETF_{stock_code}"
                    
                    rec = {
                        'name': etf_name,
                        'code': stock_code,
                        'score': row.get(score_column, 0),
                        'risk_tier': row.get('risk_tier', 1),
                        'volatility': row.get('변동성', '보통'),
                        'fee': row.get('총보수', 0),
                        'current_price': realtime_data.get('current_price', 0),
                        'volume': realtime_data.get('volume', 0),
                        'return_1y': row.get('1년수익률', 0),
                        'return_3y': row.get('3년수익률', 0),
                        'reasons': self._generate_recommendation_reasons(row, level, wmti_type)
                    }
                    recommendations.append(rec)
                
                return recommendations
            else:
                logger.warning(f"WMTI 타입 {wmti_type}에 대한 점수 컬럼 {score_column}이 없습니다.")
                return []
        
        except Exception as e:
            logger.error(f"추천 종목 가져오기 실패: {e}")
            return []
    
    def _generate_recommendation_reasons(self, etf_data: pd.Series, level: int, wmti_type: str) -> List[str]:
        """추천 근거 생성"""
        reasons = []
        
        # WMTI 타입별 근거
        if wmti_type.startswith('AP'):
            reasons.append("적극적 성향 투자자에게 적합")
        elif wmti_type.startswith('AB'):
            reasons.append("균형적 성향 투자자에게 적합")
        
        if wmti_type.endswith('WL'):
            reasons.append("장기 투자 전략에 최적화")
        elif wmti_type.endswith('ML'):
            reasons.append("중장기 투자 전략에 적합")
        elif wmti_type.endswith('WC'):
            reasons.append("단기 투자 전략에 최적화")
        elif wmti_type.endswith('MC'):
            reasons.append("중단기 투자 전략에 적합")
        elif wmti_type.endswith('WH'):
            reasons.append("고위험 고수익 전략")
        elif wmti_type.endswith('MH'):
            reasons.append("중위험 중수익 전략")
        elif wmti_type.endswith('WS'):
            reasons.append("안정적 투자 전략")
        elif wmti_type.endswith('MS'):
            reasons.append("보수적 투자 전략")
        
        # 위험 등급별 근거
        risk_tier = etf_data.get('risk_tier', 1)
        if risk_tier <= 2:
            reasons.append("낮은 위험도로 안정적")
        elif risk_tier <= 3:
            reasons.append("적정 위험도로 균형적")
        else:
            reasons.append("높은 수익 잠재력")
        
        # 총보수별 근거
        fee = etf_data.get('총보수', 0)
        if fee <= 0.3:
            reasons.append("낮은 총보수로 비용 효율적")
        elif fee <= 0.5:
            reasons.append("적정 수준의 총보수")
        else:
            reasons.append("높은 총보수이지만 우수한 성과")
        
        # 분류체계별 근거
        category = etf_data.get('분류체계', '')
        if category:
            reasons.append(f"{category} 섹터 투자 기회")
        
        return reasons[:3]  # 최대 3개까지만 반환
    
    def _display_recommendation_card(self, rec: Dict, level: int, card_num: int, mpti_type: str):
        """추천 종목 카드 표시"""
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 2px solid #f59e0b;
            border-radius: 15px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h3 style="margin: 0 0 1rem 0; color: #92400e;">{card_num}. {rec['name']} ({rec['code']})</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # 지표 표시
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("종합점수", f"{rec['score']:.3f}")
            st.metric("위험등급", f"Tier {rec['risk_tier']}")
        
        with col2:
            st.metric("변동성", rec['volatility'])
            st.metric("총보수", f"{rec['fee']:.2f}%" if rec['fee'] else "N/A")
        
        with col3:
            # 현재가 정보가 없는 경우 안내
            if rec['current_price'] == 0:
                st.info("실시간 가격 정보는 별도 조회가 필요합니다.")
            else:
                st.metric("현재가", f"{rec['current_price']:,.0f}원")
            
            if rec['volume'] == 0:
                st.info("거래량 정보는 별도 조회가 필요합니다.")
            else:
                st.metric("거래량", self._format_volume(rec['volume']))
        
        # 추천 근거 표시
        if 'reasons' in rec and rec['reasons']:
            st.markdown("**💡 추천 근거**")
            for reason in rec['reasons']:
                st.markdown(f"• {reason}")
        
        # 레벨별 설명 (config.py 사용)
        if CHATBOT_MODULES_AVAILABLE and self.config:
            level_prompt = self.config.LEVEL_PROMPTS.get(level, "")
            if level_prompt:
                # LEVEL_PROMPTS에서 해당 레벨의 설명 추출
                if level <= 2:
                    st.info("💡 초보 투자자를 위한 안내: 이 종목은 안정적이고 이해하기 쉬운 투자 대상입니다.")
                elif level == 3:
                    st.info("💡 중급 투자자를 위한 안내: 이 종목은 균형잡힌 위험-수익 프로필을 제공합니다.")
                else:
                    st.info("💡 고급 투자자를 위한 안내: 이 종목은 전문적인 투자 전략에 활용할 수 있습니다.")
        else:
            # fallback
            if level <= 2:
                st.info("💡 초보 투자자를 위한 안내: 이 종목은 안정적이고 이해하기 쉬운 투자 대상입니다.")
            elif level == 3:
                st.info("💡 중급 투자자를 위한 안내: 이 종목은 균형잡힌 위험-수익 프로필을 제공합니다.")
            else:
                st.info("💡 고급 투자자를 위한 안내: 이 종목은 전문적인 투자 전략에 활용할 수 있습니다.")
    
    def _get_realtime_stock_data(self, stock_code: str) -> Dict:
        """실시간 주식 데이터 가져오기"""
        try:
            if not stock_code or stock_code == 'N/A':
                return {'current_price': 0, 'volume': 0}
            
            # pykrx를 사용한 실시간 데이터
            try:
                from pykrx import stock
                import pandas as pd
                from datetime import datetime, timedelta
                
                # 최근 거래일 데이터 가져오기
                today = datetime.now()
                yesterday = today - timedelta(days=1)
                
                # 어제 데이터 가져오기 (오늘 데이터가 없을 수 있음)
                df = stock.get_etf_ohlcv_by_date(
                    yesterday.strftime('%Y%m%d'),
                    today.strftime('%Y%m%d'),
                    stock_code
                )
                
                if not df.empty:
                    latest_data = df.iloc[-1]
                    return {
                        'current_price': latest_data['종가'],
                        'volume': latest_data['거래량']
                    }
                
            except ImportError:
                logger.warning("pykrx 모듈을 사용할 수 없습니다.")
            except Exception as e:
                logger.error(f"pykrx 데이터 수집 실패: {e}")
            
            # yfinance를 사용한 대체 방법 (ETF의 경우)
            try:
                import yfinance as yf
                
                # 한국 ETF의 경우 .KS 추가
                ticker_symbol = f"{stock_code}.KS"
                ticker = yf.Ticker(ticker_symbol)
                
                # 최근 데이터 가져오기
                hist = ticker.history(period="5d")
                if not hist.empty:
                    latest_data = hist.iloc[-1]
                    return {
                        'current_price': latest_data['Close'],
                        'volume': latest_data['Volume']
                    }
                    
            except ImportError:
                logger.warning("yfinance 모듈을 사용할 수 없습니다.")
            except Exception as e:
                logger.error(f"yfinance 데이터 수집 실패: {e}")
            
            # 캐시된 데이터에서 찾기
            return self._get_cached_stock_data(stock_code)
            
        except Exception as e:
            logger.error(f"실시간 데이터 수집 실패 ({stock_code}): {e}")
            return {'current_price': 0, 'volume': 0}
    
    def _get_cached_stock_data(self, stock_code: str) -> Dict:
        """캐시된 데이터에서 주식 정보 찾기"""
        try:
            # 시세 데이터에서 최신 정보 찾기
            if hasattr(self, 'data') and 'etf_prices' in self.data:
                df = self.data['etf_prices']
                stock_data = df[df['종목코드'] == stock_code]
                
                if not stock_data.empty:
                    # 최신 날짜의 데이터
                    latest_data = stock_data.sort_values('날짜').iloc[-1]
                    return {
                        'current_price': latest_data.get('종가', 0),
                        'volume': latest_data.get('거래량', 0)
                    }
            
            return {'current_price': 0, 'volume': 0}
            
        except Exception as e:
            logger.error(f"캐시 데이터 조회 실패 ({stock_code}): {e}")
            return {'current_price': 0, 'volume': 0}
    
    def _format_volume(self, value):
        """거래량 포맷팅"""
        if pd.isna(value) or value == 0:
            return "N/A"
        
        if value >= 1e9:
            return f"{value/1e9:.1f}B"
        elif value >= 1e6:
            return f"{value/1e6:.1f}M"
        elif value >= 1e3:
            return f"{value/1e3:.1f}K"
        else:
            return f"{value:,.0f}"

