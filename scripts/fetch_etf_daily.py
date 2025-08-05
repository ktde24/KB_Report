"""
ETF 일별 시세 데이터 수집 스크립트
- 금융위원회 증권상품시세정보 API를 통해 ETF 일별 시세 데이터 수집
- 시작일자와 종료일자를 설정하여 기간별 데이터 수집 가능
- CSV 형태로 저장하여 분석 시스템에서 활용

주요 기능:
1. 금융위원회 API 호출 (증권상품시세정보 - ETF 시세)
2. ETF 일별 시세 데이터 수집 (기간 설정 가능)
3. XML 응답을 DataFrame으로 변환
4. CSV 파일로 저장

사용법:
    python scripts/fetch_etf_daily.py
    python scripts/fetch_etf_daily.py --start_date 20240101 --end_date 20240131
    python scripts/fetch_etf_daily.py --start_date 20240101 --days 30

출력:
    data/ETF_시세_데이터_YYYYMMDD.csv - 일별 ETF 시세 데이터
    data/ETF_시세_데이터_YYYYMMDD_YYYYMMDD.csv - 기간별 ETF 시세 데이터

참고:
    - API 키는 공공데이터포털에서 발급 필요 (https://www.data.go.kr/data/15094806/openapi.do)
    - 데이터는 영업일 기준으로 제공됨
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pandas as pd
import os
import argparse
import time
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# =============================================================================
# 설정 파라미터
# =============================================================================

# 금융위원회 증권상품시세정보 API 서비스 키
service_key = os.getenv("PUBLIC_DATA_API_KEY")
if not service_key:
    print("경고: PUBLIC_DATA_API_KEY 환경 변수가 설정되지 않았습니다.")
    print("환경 변수를 설정하거나 .env 파일에 추가하세요.")
    print("API 키 발급: https://www.data.go.kr/data/15094806/openapi.do")
    exit(1)

# ETF 시세 정보 API 엔드포인트
url = "http://apis.data.go.kr/1160100/service/GetSecuritiesProductInfoService/getETFPriceInfo"

# API 호출 간격 (초) - API 한도 초과 방지
API_DELAY = 1.0

def parse_arguments():
    """
    명령행 인수 파싱
    
    Returns:
        argparse.Namespace: 파싱된 인수들
    """
    parser = argparse.ArgumentParser(description='ETF 일별 시세 데이터 수집')
    
    parser.add_argument(
        '--start_date', 
        type=str, 
        help='시작일자 (YYYYMMDD 형식, 기본값: 오늘)'
    )
    
    parser.add_argument(
        '--end_date', 
        type=str, 
        help='종료일자 (YYYYMMDD 형식, 기본값: 오늘)'
    )
    
    parser.add_argument(
        '--days', 
        type=int, 
        help='수집할 일수 (start_date로부터, end_date와 함께 사용 불가)'
    )
    
    parser.add_argument(
        '--output_dir', 
        type=str, 
        default='data',
        help='출력 디렉토리 (기본값: data)'
    )
    
    parser.add_argument(
        '--delay', 
        type=float, 
        default=1.0,
        help='API 호출 간격 (초, 기본값: 1.0)'
    )
    
    return parser.parse_args()

def validate_date_format(date_str):
    """
    날짜 형식 검증
    
    Args:
        date_str: 날짜 문자열 (YYYYMMDD)
    
    Returns:
        bool: 유효한 형식인지 여부
    """
    try:
        datetime.strptime(date_str, '%Y%m%d')
        return True
    except ValueError:
        return False

def get_date_range(start_date, end_date, days=None):
    """
    날짜 범위 생성
    
    Args:
        start_date: 시작일자 (YYYYMMDD)
        end_date: 종료일자 (YYYYMMDD)
        days: 일수 (start_date로부터)
    
    Returns:
        list: 날짜 리스트
    """
    if days is not None:
        # days가 지정된 경우
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        date_list = []
        for i in range(days):
            current_date = start_dt + timedelta(days=i)
            date_list.append(current_date.strftime('%Y%m%d'))
        return date_list
    else:
        # start_date와 end_date가 지정된 경우
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        
        date_list = []
        current_dt = start_dt
        while current_dt <= end_dt:
            date_list.append(current_dt.strftime('%Y%m%d'))
            current_dt += timedelta(days=1)
        
        return date_list

def fetch_etf_data_for_date(date_str, service_key, url, delay=1.0):
    """
    특정 날짜의 ETF 데이터 수집
    
    Args:
        date_str: 날짜 (YYYYMMDD)
        service_key: API 서비스 키
        url: API URL
        delay: API 호출 간격
    
    Returns:
        list: ETF 데이터 리스트
    """
    # API 요청 파라미터
    params = {
        "serviceKey": service_key,
        "numOfRows": "1000",        # 한 번에 가져올 레코드 수 
        "pageNo": "1",              # 페이지 번호
        "resultType": "xml",        # 응답 형식 (XML)
        "basDt": date_str           # 기준일자
    }
    
    try:
        print(f"  {date_str} 데이터 수집 중...")
        
        # API 호출
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        # XML 파싱
        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        
        # 데이터 변환
        data_list = []
        for item in items:
            record = {elem.tag: elem.text for elem in item}
            data_list.append(record)
        
        print(f"  {date_str} 완료: {len(data_list)}개 ETF")
        
        # API 호출 간격 대기
        if delay > 0:
            time.sleep(delay)
        
        return data_list
        
    except requests.exceptions.RequestException as e:
        print(f"  {date_str} API 호출 실패: {e}")
        return []
    except ET.ParseError as e:
        print(f"  {date_str} XML 파싱 실패: {e}")
        return []
    except Exception as e:
        print(f"  {date_str} 처리 중 오류: {e}")
        return []

def save_data_to_csv(all_data, output_dir, start_date, end_date):
    """
    데이터를 CSV 파일로 저장
    
    Args:
        all_data: 모든 ETF 데이터
        output_dir: 출력 디렉토리
        start_date: 시작일자
        end_date: 종료일자
    """
    if not all_data:
        print("저장할 데이터가 없습니다.")
        return
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    # DataFrame 생성
    df = pd.DataFrame(all_data)
    
    # 파일명 생성
    if start_date == end_date:
        # 단일 날짜
        filename = f"ETF_시세_데이터_{start_date}.csv"
    else:
        # 기간
        filename = f"ETF_시세_데이터_{start_date}_{end_date}.csv"
    
    save_path = os.path.join(output_dir, filename)
    
    # CSV 저장
    df.to_csv(save_path, index=False, encoding='utf-8-sig')
    
    print(f"CSV 저장 완료: {save_path}")
    print(f"파일 크기: {os.path.getsize(save_path) / 1024:.1f} KB")
    print(f"총 레코드: {len(df)}개")
    
    # 데이터 샘플 출력
    print(f"\n데이터 샘플:")
    print(f"컬럼 수: {len(df.columns)}")
    print(f"주요 컬럼: {list(df.columns[:5])}...")
    
    if not df.empty:
        print(f"첫 번째 ETF: {df.iloc[0].get('itmsNm', 'N/A')}")
        print(f"마지막 ETF: {df.iloc[-1].get('itmsNm', 'N/A')}")
    
    return save_path

def main():
    """
    메인 함수
    """
    print("=" * 60)
    print("ETF 일별 시세 데이터 수집 시작")
    print("=" * 60)
    
    # 명령행 인수 파싱
    args = parse_arguments()
    
    # 날짜 설정
    today = datetime.today().strftime('%Y%m%d')
    
    if args.start_date:
        start_date = args.start_date
        if not validate_date_format(start_date):
            print(f"잘못된 시작일자 형식: {start_date} (YYYYMMDD 형식 필요)")
            return 1
    else:
        start_date = today
    
    if args.days is not None:
        # days 옵션이 지정된 경우
        if args.end_date:
            print("days와 end_date는 함께 사용할 수 없습니다.")
            return 1
        end_date = start_date  # 실제로는 사용하지 않음
        date_list = get_date_range(start_date, None, args.days)
    elif args.end_date:
        # end_date가 지정된 경우
        end_date = args.end_date
        if not validate_date_format(end_date):
            print(f"잘못된 종료일자 형식: {end_date} (YYYYMMDD 형식 필요)")
            return 1
        date_list = get_date_range(start_date, end_date)
    else:
        # 단일 날짜 (오늘)
        end_date = start_date
        date_list = [start_date]
    
    # 설정 정보 출력
    print(f"수집 기간: {start_date} ~ {end_date}")
    print(f"수집 일수: {len(date_list)}일")
    print(f"출력 디렉토리: {args.output_dir}")
    print(f"API 호출 간격: {args.delay}초")
    print()
    
    # 데이터 수집
    all_data = []
    successful_dates = 0
    
    for date_str in date_list:
        data = fetch_etf_data_for_date(
            date_str, service_key, url, args.delay
        )
        
        if data:
            all_data.extend(data)
            successful_dates += 1
    
    # 결과 저장
    if all_data:
        save_path = save_data_to_csv(
            all_data, args.output_dir, start_date, end_date
        )
        
        print(f"\n{'='*60}")
        print("ETF 일별 시세 데이터 수집 완료!")
        print(f"{'='*60}")
        print(f"저장 위치: {save_path}")
        print(f"성공한 날짜: {successful_dates}/{len(date_list)}일")
        print(f"총 ETF 데이터: {len(all_data)}개")
        print(f"{'='*60}")
        
        return 0
    else:
        print("수집된 데이터가 없습니다.")
        return 1

if __name__ == "__main__":
    exit(main())
