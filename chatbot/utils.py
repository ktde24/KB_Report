"""
ETF RAG 챗봇 공통 유틸리티 모듈
- 데이터 처리 및 변환 함수
- 문자열 정규화 및 검증 함수
- 안전한 타입 변환 함수
- 로깅 및 에러 처리 유틸리티
"""

import pandas as pd
import numpy as np
import re
import logging
import os
from typing import Any, Optional, Union, Dict, List
from datetime import datetime

# 로깅 설정
logger = logging.getLogger(__name__)

# =============================================================================
# 문자열 처리 유틸리티
# =============================================================================

def normalize_etf_name(name: str) -> str:
    """
    ETF 종목명 정규화 (공백 제거, 소문자 변환)
    
    Args:
        name: 원본 ETF명
    
    Returns:
        정규화된 ETF명
    """
    if not name:
        return ""
    return re.sub(r'\s+', '', str(name)).lower()

def extract_etf_name_from_input(user_input: str, info_df: pd.DataFrame) -> str:
    """
    사용자 입력에서 정확한 ETF명 추출
    
    Args:
        user_input: 사용자 입력 텍스트
        info_df: ETF 정보 DataFrame
    
    Returns:
        매칭된 ETF명 또는 원본 입력
    """
    if info_df.empty:
        return user_input.strip()
    
    candidates = list(info_df['종목명'].dropna())
    norm_input = normalize_etf_name(user_input)
    
    # 일반적인 ETF 브랜드 매핑
    brand_mapping = {
        '타이거': 'TIGER',
        'tiger': 'TIGER',
        '코덱스': 'KODEX',
        'kodex': 'KODEX',
        '티그': 'TIGER',
        '티거': 'TIGER',
        '코덱': 'KODEX'
    }
    
    # 브랜드 매핑 적용
    for korean, english in brand_mapping.items():
        if korean in norm_input:
            norm_input = norm_input.replace(korean, english.lower())
    
    # 1단계: 정확한 매칭
    for name in candidates:
        if normalize_etf_name(name) == norm_input:
            return name
    
    # 2단계: 부분 매칭 (포함 관계)
    for name in candidates:
        norm_name = normalize_etf_name(name)
        if norm_input in norm_name or norm_name in norm_input:
            return name
    
    # 3단계: 키워드 기반 매칭
    input_words = norm_input.split()
    for name in candidates:
        norm_name = normalize_etf_name(name)
        name_words = norm_name.split()
        
        # 입력 단어들이 ETF명에 포함되는지 확인
        matches = sum(1 for word in input_words if any(word in name_word for name_word in name_words))
        if matches >= len(input_words) * 0.7:  # 70% 이상 매칭
            return name
    
    # 4단계: 유사도 기반 매칭
    best_match = None
    best_score = 0
    
    for name in candidates:
        norm_name = normalize_etf_name(name)
        # 간단한 유사도 계산 (공통 문자 수)
        common_chars = len(set(norm_input) & set(norm_name))
        if common_chars > best_score and common_chars >= len(norm_input) * 0.3:  # 임계값 낮춤
            best_score = common_chars
            best_match = name
    
    return best_match if best_match else user_input.strip()

def find_etf_row(df: pd.DataFrame, etf_name: str) -> Optional[pd.Series]:
    """
    DataFrame에서 ETF 행 찾기
    
    Args:
        df: 검색할 DataFrame
        etf_name: 찾을 ETF명
    
    Returns:
        매칭된 행 또는 None
    """
    if df.empty:
        return None
    
    norm_target = normalize_etf_name(etf_name)
    
    # 종목명 컬럼이 있는 경우
    if '종목명' in df.columns:
        for idx, row in df.iterrows():
            if normalize_etf_name(row['종목명']) == norm_target:
                return row
    
    # ETF명 컬럼이 있는 경우
    if 'ETF명' in df.columns:
        for idx, row in df.iterrows():
            if normalize_etf_name(row['ETF명']) == norm_target:
                return row
    
    return None

# =============================================================================
# 타입 변환 유틸리티
# =============================================================================

def safe_float(value: Any) -> Optional[float]:
    """
    안전한 float 변환 (None, NaN, 빈 문자열 처리)
    
    Args:
        value: 변환할 값
    
    Returns:
        변환된 float 값 또는 None
    """
    try:
        if value is None or str(value).strip() == '' or str(value).lower() == 'nan':
            return None
        return float(str(value).replace(',', '').strip())
    except (ValueError, TypeError):
        return None

def safe_int(value: Any) -> Optional[int]:
    """
    안전한 int 변환
    
    Args:
        value: 변환할 값
    
    Returns:
        변환된 int 값 또는 None
    """
    try:
        float_val = safe_float(value)
        return int(float_val) if float_val is not None else None
    except (ValueError, TypeError):
        return None

def safe_format(value: Any, suffix: str = "", decimals: int = 2) -> str:
    """
    안전한 값 포맷팅 (None 처리)
    
    Args:
        value: 포맷팅할 값
        suffix: 접미사 (%, 원 등)
        decimals: 소수점 자릿수
    
    Returns:
        포맷팅된 문자열
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}{suffix}"
    except (ValueError, TypeError):
        return str(value)

def format_percentage(value: Any, decimals: int = 2) -> str:
    """
    퍼센트 값 포맷팅
    
    Args:
        value: 퍼센트 값
        decimals: 소수점 자릿수
    
    Returns:
        포맷팅된 퍼센트 문자열
    """
    return safe_format(value, "%", decimals)

def format_aum(value: Any) -> str:
    """
    자산규모(AUM) 포맷팅
    
    Args:
        value: 자산규모 값
    
    Returns:
        포맷팅된 AUM 문자열
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    
    try:
        val = float(value)
        if val >= 1e12:  # 1조 이상
            return f"{val/1e12:.1f}조원"
        elif val >= 1e8:  # 1억 이상
            return f"{val/1e8:.1f}억원"
        elif val >= 1e4:  # 1만 이상
            return f"{val/1e4:.1f}만원"
        else:
            return f"{val:.0f}원"
    except (ValueError, TypeError):
        return str(value)

def format_volume(value: Any) -> str:
    """
    거래량 포맷팅
    
    Args:
        value: 거래량 값
    
    Returns:
        포맷팅된 거래량 문자열
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/A"
    
    try:
        val = float(value)
        if val >= 1e8:  # 1억 이상
            return f"{val/1e8:.1f}억주"
        elif val >= 1e4:  # 1만 이상
            return f"{val/1e4:.1f}만주"
        else:
            return f"{val:.0f}주"
    except (ValueError, TypeError):
        return str(value)

# =============================================================================
# 데이터 검증 유틸리티
# =============================================================================

def validate_user_profile(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    사용자 프로필 검증 및 정규화
    
    Args:
        user_profile: 검증할 사용자 프로필
    
    Returns:
        검증된 사용자 프로필
    """
    validated = user_profile.copy()
    
    # 레벨
    level = validated.get('level', 3)  # 기본값: Level 3 (중급자)
    if isinstance(level, str):
        if '1' in level:
            validated['level'] = 1
        elif '2' in level:
            validated['level'] = 2
        elif '3' in level:
            validated['level'] = 3
        elif '4' in level:
            validated['level'] = 4
        elif '5' in level:
            validated['level'] = 5
        else:
            validated['level'] = 3
    else:
        validated['level'] = int(level) if level in [1, 2, 3, 4, 5] else 3
    
    # MPTI 투자자 유형 검증 (설명용)
    investor_type = validated.get('investor_type', 'IFSA')
    valid_mpti_types = ['IFSA', 'IFSP', 'IFPA', 'IFPP', 'INSA', 'INSP', 'INPA', 'INPP',
                       'EFSA', 'EFSP', 'EFPA', 'EFPP', 'ENSA', 'ENSP', 'ENPA', 'ENPP']
    if investor_type not in valid_mpti_types:
        validated['investor_type'] = 'IFSA'  # 기본값: 일독형+팩트형+속독형+집중형
    
    # WMTI 투자자 유형 검증 (추천용)
    wmti_type = validated.get('wmti_type', 'BALANCED')
    valid_wmti_types = ['GROWTH', 'VALUE', 'DIVIDEND', 'SAFE', 'AGGRESSIVE', 'BALANCED', 
                       'SECTOR', 'THEME', 'INTERNATIONAL', 'DOMESTIC', 'LARGE_CAP', 
                       'SMALL_CAP', 'HIGH_RISK', 'LOW_RISK', 'ACTIVE', 'PASSIVE']
    if wmti_type not in valid_wmti_types:
        validated['wmti_type'] = 'BALANCED'  # 기본값: 균형 투자 선호
    
    return validated

def is_valid_etf_name(etf_name: str) -> bool:
    """
    ETF명 유효성 검사
    
    Args:
        etf_name: 검사할 ETF명
    
    Returns:
        유효성 여부
    """
    if not etf_name or not isinstance(etf_name, str):
        return False
    
    # 기본적인 유효성 검사
    if len(etf_name.strip()) < 2:
        return False
    
    # 특수문자나 숫자만으로 구성된 경우 제외
    if re.match(r'^[0-9\s\-_\.]+$', etf_name):
        return False
    
    return True

# =============================================================================
# 에러 처리 유틸리티
# =============================================================================

def create_error_result(error_message: str, context: str = "") -> Dict[str, Any]:
    """
    에러 결과 생성
    
    Args:
        error_message: 에러 메시지
        context: 에러 컨텍스트
    
    Returns:
        에러 결과 딕셔너리
    """
    error_result = {
        'error': True,
        'message': error_message,
        'timestamp': datetime.now().isoformat()
    }
    
    if context:
        error_result['context'] = context
    
    logger.error(f"에러 발생: {error_message} (컨텍스트: {context})")
    return error_result

def handle_data_loading_error(file_path: str, error: Exception) -> Dict[str, Any]:
    """
    데이터 로딩 에러 처리
    
    Args:
        file_path: 로딩하려던 파일 경로
        error: 발생한 에러
    
    Returns:
        에러 결과 딕셔너리
    """
    error_msg = f"데이터 파일 로딩 실패: {file_path}"
    return create_error_result(error_msg, str(error))

# =============================================================================
# 데이터 처리 유틸리티
# =============================================================================

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame 정리 (NaN, 중복 제거 등)
    
    Args:
        df: 정리할 DataFrame
    
    Returns:
        정리된 DataFrame
    """
    if df.empty:
        return df
    
    # NaN 값 처리
    df = df.replace([np.inf, -np.inf], np.nan)
    
    # 중복 행 제거
    df = df.drop_duplicates()
    
    # 모든 값이 NaN인 행 제거
    df = df.dropna(how='all')
    
    return df

def filter_dataframe_by_keyword(df: pd.DataFrame, keyword: str, columns: List[str]) -> pd.DataFrame:
    """
    키워드로 DataFrame 필터링
    
    Args:
        df: 필터링할 DataFrame
        keyword: 검색 키워드
        columns: 검색할 컬럼들
    
    Returns:
        필터링된 DataFrame
    """
    if not keyword.strip() or df.empty:
        return df
    
    # 모든 지정된 컬럼에서 키워드 검색 (OR 조건)
    mask = pd.Series([False] * len(df))
    
    for col in columns:
        if col in df.columns:
            col_mask = df[col].astype(str).str.contains(keyword, case=False, na=False)
            mask = mask | col_mask
    
    return df[mask]

def calculate_percentage_change(current: float, previous: float) -> Optional[float]:
    """
    퍼센트 변화율 계산
    
    Args:
        current: 현재 값
        previous: 이전 값
    
    Returns:
        퍼센트 변화율 또는 None
    """
    if previous == 0 or previous is None or current is None:
        return None
    
    return ((current - previous) / previous) * 100

def calculate_annualized_return(returns: List[float], periods_per_year: int = 252) -> Optional[float]:
    """
    연율화 수익률 계산
    
    Args:
        returns: 수익률 리스트
        periods_per_year: 연간 기간 수 (기본값: 252일)
    
    Returns:
        연율화 수익률
    """
    if not returns:
        return None
    
    try:
        # 기하평균 수익률 계산
        total_return = 1.0
        for ret in returns:
            total_return *= (1 + ret)
        
        # 연율화
        periods = len(returns)
        if periods > 0:
            annualized = (total_return ** (periods_per_year / periods)) - 1
            return annualized
        return None
    except Exception:
        return None

# =============================================================================
# CSV 파일 읽기 유틸리티
# =============================================================================

def safe_read_csv(file_path: str, **kwargs) -> pd.DataFrame:
    """
    안전한 CSV 파일 읽기 (인코딩 문제 해결)
    
    여러 인코딩을 시도하여 CSV 파일을 읽습니다:
    1. utf-8-sig (BOM 포함 UTF-8)
    2. utf-8
    3. cp949 (한국어 Windows)
    4. euc-kr (한국어)
    
    Args:
        file_path: CSV 파일 경로
        **kwargs: pd.read_csv에 전달할 추가 인수
    
    Returns:
        읽어들인 DataFrame
    
    Raises:
        FileNotFoundError: 파일이 존재하지 않는 경우
        UnicodeDecodeError: 모든 인코딩 시도가 실패한 경우
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
    
    # kwargs에서 encoding 제거 (중복 방지)
    kwargs_copy = kwargs.copy()
    if 'encoding' in kwargs_copy:
        del kwargs_copy['encoding']
    
    # 시도할 인코딩 목록
    encodings = ['utf-8-sig', 'utf-8', 'cp949', 'euc-kr']
    
    for encoding in encodings:
        try:
            logger.info(f"CSV 파일 읽기 시도: {file_path} (인코딩: {encoding})")
            df = pd.read_csv(file_path, encoding=encoding, **kwargs_copy)
            logger.info(f"CSV 파일 읽기 성공: {file_path} (인코딩: {encoding})")
            return df
        except UnicodeDecodeError as e:
            logger.warning(f"인코딩 {encoding} 실패: {file_path} - {e}")
            continue
        except Exception as e:
            logger.error(f"CSV 읽기 오류: {file_path} - {e}")
            raise
    
    # 모든 인코딩 시도 실패
    error_msg = f"모든 인코딩 시도 실패: {file_path}"
    logger.error(error_msg)
    raise UnicodeDecodeError(error_msg, b"", 0, 0, error_msg)

def safe_read_csv_with_fallback(file_path: str, **kwargs) -> pd.DataFrame:
    """
    안전한 CSV 파일 읽기 (폴백 포함)
    
    safe_read_csv와 동일하지만, 실패 시 빈 DataFrame을 반환합니다.
    
    Args:
        file_path: CSV 파일 경로
        **kwargs: pd.read_csv에 전달할 추가 인수
    
    Returns:
        읽어들인 DataFrame 또는 빈 DataFrame
    """
    try:
        return safe_read_csv(file_path, **kwargs)
    except Exception as e:
        logger.error(f"CSV 파일 읽기 실패 (빈 DataFrame 반환): {file_path} - {e}")
        return pd.DataFrame()

def detect_csv_encoding(file_path: str) -> str:
    """
    CSV 파일의 인코딩 감지
    
    Args:
        file_path: CSV 파일 경로
    
    Returns:
        감지된 인코딩
    """
    try:
        import chardet
        
        with open(file_path, 'rb') as f:
            raw_data = f.read()
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            confidence = result['confidence']
            
            logger.info(f"인코딩 감지: {file_path} - {encoding} (신뢰도: {confidence:.2f})")
            return encoding
            
    except ImportError:
        logger.warning("chardet 라이브러리가 설치되지 않았습니다. 기본 인코딩을 반환합니다.")
        return 'cp949'
    except Exception as e:
        logger.warning(f"인코딩 감지 실패: {file_path} - {e}")
        return 'cp949'

def fix_csv_encoding(file_path: str, target_encoding: str = 'utf-8-sig') -> bool:
    """
    CSV 파일 인코딩 수정
    
    Args:
        file_path: CSV 파일 경로
        target_encoding: 목표 인코딩 (기본값: utf-8-sig)
    
    Returns:
        성공 여부
    """
    try:
        # 현재 인코딩 감지
        current_encoding = detect_csv_encoding(file_path)
        
        # 파일 읽기
        df = safe_read_csv(file_path)
        
        # 새로운 인코딩으로 저장
        df.to_csv(file_path, index=False, encoding=target_encoding)
        
        logger.info(f"인코딩 수정 완료: {file_path} ({current_encoding} → {target_encoding})")
        return True
        
    except Exception as e:
        logger.error(f"인코딩 수정 실패: {file_path} - {e}")
        return False

# =============================================================================
# ETF 점수 정규화 함수들
# =============================================================================

def normalize_return_score(market_data: Dict[str, Any]) -> float:
    """
    수익률 정규화 (1년 > 3개월 > 1개월 순)
    
    Args:
        market_data: 시세 분석 데이터
    
    Returns:
        정규화된 수익률 점수 (0.0~1.0)
    """
    returns = [
        market_data.get('1년 수익률'),
        market_data.get('3개월 수익률'), 
        market_data.get('1개월 수익률')
    ]
    
    for ret in returns:
        if ret is not None and not pd.isna(ret):
            # -100% ~ +100% → 0~1로 정규화
            return max(0, min(1, (ret + 100) / 200))
    
    return 0.5  # 기본값

def normalize_fee_score(perf_data: Dict[str, Any]) -> float:
    """
    총보수 정규화 (낮을수록 좋음)
    
    Args:
        perf_data: 성과 데이터
    
    Returns:
        정규화된 비용 점수 (0.0~1.0)
    """
    fee = perf_data.get('총 보수')
    if fee is None or pd.isna(fee):
        return 0.5
    
    try:
        fee_val = float(fee)
        # 0~10% → 1~0 (낮을수록 높은 점수)
        return max(0, min(1, 1 - (fee_val / 10)))
    except (ValueError, TypeError):
        return 0.5

def normalize_volume_score(aum_data: Dict[str, Any]) -> float:
    """
    거래량 정규화
    
    Args:
        aum_data: 자산규모/유동성 데이터
    
    Returns:
        정규화된 거래량 점수 (0.0~1.0)
    """
    volume = aum_data.get('평균 거래량')
    if volume is None or pd.isna(volume):
        return 0.5
    
    try:
        volume_val = float(volume)
        # 0~100만주 → 0~1로 정규화
        return max(0, min(1, volume_val / 1000000))
    except (ValueError, TypeError):
        return 0.5

def normalize_volatility_score(risk_data: Dict[str, Any]) -> float:
    """
    변동성 정규화
    
    Args:
        risk_data: 위험도 데이터
    
    Returns:
        정규화된 변동성 점수 (0.0~1.0)
    """
    volatility = risk_data.get('변동성', '보통')
    grade_scores = {
        '매우낮음': 0.2, '낮음': 0.4, '보통': 0.6, 
        '높음': 0.8, '매우높음': 1.0
    }
    return grade_scores.get(volatility, 0.6)

def calculate_etf_base_score(etf_info: Dict[str, Any]) -> float:
    """
    ETF 기본 점수 계산
    
    다음 요소들을 종합하여 0.0~1.0 사이의 점수 계산:
    - 수익률 (40%): 1년, 3개월, 1개월 수익률
    - 비용 (20%): 총보수 (낮을수록 높은 점수)
    - 유동성 (20%): 거래량 (높을수록 높은 점수)
    - 변동성 (20%): 변동성 등급 (낮을수록 높은 점수)
    
    Args:
        etf_info: ETF 분석 정보
    
    Returns:
        기본 점수 (0.0~1.0)
    """
    try:
        # 각 요소별 점수 계산
        return_score = normalize_return_score(etf_info.get('시세분석', {}))
        fee_score = normalize_fee_score(etf_info.get('수익률/보수', {}))
        volume_score = normalize_volume_score(etf_info.get('자산규모/유동성', {}))
        volatility_score = normalize_volatility_score(etf_info.get('위험', {}))
        
        # 가중합 계산
        base_score = (
            return_score * 0.4 +      # 수익률 40%
            fee_score * 0.2 +         # 총보수 20% 
            volume_score * 0.2 +      # 거래량 20%
            volatility_score * 0.2    # 변동성 20%
        )
        
        return max(0.0, min(1.0, base_score))
        
    except Exception as e:
        logger.warning(f"기본 점수 계산 오류: {e}")
        return 0.5  # 기본값 