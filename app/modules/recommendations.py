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
                    # 추천 종목 표시 (일관된 형식)
                    st.markdown("## 🏆 추천 ETF Top3")
                    
                    for i, rec in enumerate(recommendations[:3], 1):  
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
                                'reasons': self._generate_recommendation_reasons(rec, level, wmti_type),
                                'classification': rec.get('분류체계', ''),
                                'reference_index': rec.get('기초지수', '')
                            }
                            self._display_recommendation_card(card_data, level, i, mpti_type)
                    
                    # 추천 설명 생성 (GPT API 호출)
                    try:
                        import openai
                        import os
                        
                        api_key = os.getenv('OPENAI_API_KEY')
                        if api_key:
                            client = openai.OpenAI(api_key=api_key)
                            
                            # 구체적인 추천 근거 프롬프트 생성
                            prompt = self._generate_detailed_recommendation_prompt(
                                recommendations=recommendations[:3],
                                user_profile=user_profile
                            )
                            
                            # GPT API 호출
                            response = client.chat.completions.create(
                                model="gpt-3.5-turbo",
                                messages=[
                                    {"role": "system", "content": "당신은 투자 전문 상담사입니다. 제공된 ETF 데이터를 기반으로 구체적이고 실용적인 투자 조언을 제공하세요. 추상적이고 일반적인 설명은 피하고, 실제 데이터와 수치를 활용한 구체적인 분석을 제공하세요."},
                                    {"role": "user", "content": prompt}
                                ],
                                max_tokens=1000,
                                temperature=0.2
                            )
                            
                            explanation = response.choices[0].message.content.strip()
                            
                            if explanation:
                                st.markdown("## 💡 투자 팁")
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
        """추천 종목 카드 표시 (일관된 형식)"""
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 2px solid #f59e0b;
            border-radius: 15px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
            <h3 style="margin: 0 0 1rem 0; color: #92400e;">{card_num}위: {rec['name']} ({rec['code']})</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # 기본 정보 표시
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
        
        # 추가 정보 표시
        if 'classification' in rec and rec['classification']:
            st.markdown(f"**분류체계:** {rec['classification']}")
        if 'reference_index' in rec and rec['reference_index']:
            st.markdown(f"**기초지수:** {rec['reference_index']}")
        
        # 추천 이유 표시 (일관된 형식)
        if 'reasons' in rec and rec['reasons']:
            st.markdown("**추천 이유:**")
            for reason in rec['reasons']:
                st.markdown(f"• {reason}")
        
        # 레벨별 설명 (간소화)
        if level <= 2:
            st.info("💡 초보 투자자를 위한 안내: 이 종목은 안정적이고 이해하기 쉬운 투자 대상입니다.")
        elif level == 3:
            st.info("💡 중급 투자자를 위한 안내: 이 종목은 균형잡힌 위험-수익 프로필을 제공합니다.")
        else:
            st.info("💡 고급 투자자를 위한 안내: 이 종목은 전문적인 투자 전략에 활용할 수 있습니다.")
        
        st.write("---")  # 구분선 추가
    
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
    
    def _generate_detailed_recommendation_prompt(self, recommendations: List[Dict], user_profile: Dict) -> str:
        """구체적인 추천 근거 프롬프트 생성"""
        level = user_profile.get('level', 1)
        wmti_type = user_profile.get('wmti_type', 'APWC')
        mpti_type = user_profile.get('mpti_type', 'Fact')
        
        # ETF 정보 상세 포맷팅
        etf_details = []
        for i, rec in enumerate(recommendations, 1):
            etf_name = rec.get('종목명', rec.get('ETF명', 'N/A'))
            stock_code = rec.get('종목코드', 'N/A')
            final_score = rec.get('final_score', 0)
            return_score = rec.get('return_score', 0)
            risk_adjusted_score = rec.get('risk_adjusted_score', 0)
            cost_efficiency_score = rec.get('cost_efficiency_score', 0)
            risk_tier = rec.get('risk_tier', 0)
            classification = rec.get('분류체계', 'N/A')
            reference_index = rec.get('기초지수', 'N/A')
            fee = rec.get('총보수', 0)
            return_1y = rec.get('1년수익률', 0)
            return_3y = rec.get('3년수익률', 0)
            volatility = rec.get('변동성', '보통')
            
            etf_details.append(f"""
{i}위: {etf_name} ({stock_code})
- 종합점수: {final_score:.3f} (수익률:{return_score:.3f}, 위험조정:{risk_adjusted_score:.3f}, 비용효율:{cost_efficiency_score:.3f})
- 위험등급: Tier {risk_tier} (변동성: {volatility})
- 분류체계: {classification}
- 기초지수: {reference_index}
- 총보수: {fee:.2f}% (1년수익률: {return_1y:.2f}%, 3년수익률: {return_3y:.2f}%)
""")
        
        etf_info_text = "\n".join(etf_details)
        
        # WMTI 유형별 설명
        wmti_descriptions = {
            'APWC': '적극적 단기 투자자 (높은 수익 추구, 단기 보유)',
            'APMC': '적극적 중단기 투자자 (높은 수익 추구, 중단기 보유)',
            'APWL': '적극적 장기 투자자 (높은 수익 추구, 장기 보유)',
            'APML': '적극적 중장기 투자자 (높은 수익 추구, 중장기 보유)',
            'ABWC': '균형적 단기 투자자 (안정적 수익 추구, 단기 보유)',
            'ABMC': '균형적 중단기 투자자 (안정적 수익 추구, 중단기 보유)',
            'ABWL': '균형적 장기 투자자 (안정적 수익 추구, 장기 보유)',
            'ABML': '균형적 중장기 투자자 (안정적 수익 추구, 중장기 보유)'
        }
        
        wmti_desc = wmti_descriptions.get(wmti_type, f'WMTI {wmti_type} 유형')
        
        # 레벨별 설명 스타일
        level_styles = {
            1: "유치원/초등학생도 이해할 수 있는 아주 쉬운 말로 설명",
            2: "중고등학생도 이해 가능한 쉬운 말로 설명", 
            3: "일반 성인도 이해할 수 있는 수준으로 설명",
            4: "투자 경험이 있는 성인을 대상으로 한 전문적 설명",
            5: "투자 전문가 수준의 고급 분석과 전문 용어 사용"
        }
        
        level_style = level_styles.get(level, level_styles[3])
        
        prompt = f"""
당신은 Just Fit It의 투자 전문 상담사입니다. 다음 ETF 추천 목록에 대해 구체적이고 실용적인 투자 조언을 제공해주세요.

**사용자 프로필:**
- 투자 레벨: Level {level} ({level_style})
- WMTI 유형: {wmti_type} ({wmti_desc})
- MPTI 스타일: {mpti_type}

**추천 ETF 목록:**
{etf_info_text}

**요청사항:**
위 ETF들에 대해 다음을 포함하여 구체적이고 실용적인 분석을 제공해주세요:

1. **각 ETF의 구체적인 특징과 투자 가치:**
   - ETF명과 기초지수를 명확히 언급
   - 분류체계에 따른 실제 투자 대상 설명
   - 제공된 수치(수익률, 위험도, 비용)를 활용한 구체적 분석
   - 다른 유사 ETF와의 차별점

2. **WMTI 유형에 맞는 구체적인 추천 이유:**
   - {wmti_type} 투자자에게 왜 이 ETF가 적합한지 구체적 설명
   - 투자 성향과 ETF 특성의 연관성
   - 예상 투자 기간과 전략

3. **실제 투자 시 고려사항:**
   - 해당 ETF의 실제 위험 요소 (기초지수, 분류체계 기반)
   - 현재 시장 상황에서의 투자 시점 조언
   - 포트폴리오 내 비중 설정 가이드

4. **Level {level} 투자자를 위한 실전 팁:**
   - 레벨에 맞는 구체적인 투자 전략
   - 모니터링 방법과 리밸런싱 시점
   - 손실 관리 방법

5. **분류체계와 기초지수 기반 분석:**
   - 기초지수의 실제 의미와 시장 포지셔닝
   - 분류체계에 따른 시장 섹터 분석
   - 글로벌/국내 시장 연관성

**중요:** 
- 추상적이고 일반적인 설명은 피하세요
- 제공된 모든 수치와 데이터를 활용하세요
- 구체적인 투자 전략과 실행 방법을 제시하세요
- 사용자 레벨에 맞는 설명 스타일을 유지하세요
- 실제 투자자가 바로 활용할 수 있는 실용적인 조언을 제공하세요

**응답 형식:**
- 각 ETF별로 구체적인 분석
- WMTI 유형별 맞춤 전략
- 실전 투자 가이드
- 주의사항과 리스크 관리
"""
        
        return prompt

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

