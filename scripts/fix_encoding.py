"""
CSV 파일 인코딩 수정 스크립트
- 한글이 깨진 CSV 파일들을 올바른 인코딩으로 변환
"""

import pandas as pd
import os
import chardet
from pathlib import Path

def detect_encoding(file_path):
    """파일의 인코딩 감지"""
    with open(file_path, 'rb') as f:
        raw_data = f.read()
        result = chardet.detect(raw_data)
        return result['encoding'], result['confidence']

def fix_csv_encoding(input_file, output_file=None, target_encoding='utf-8'):
    """
    CSV 파일의 인코딩을 수정
    
    Args:
        input_file: 입력 파일 경로
        output_file: 출력 파일 경로 (None이면 원본 파일 덮어쓰기)
        target_encoding: 목표 인코딩 
    """
    if output_file is None:
        output_file = input_file
    
    try:
        # 현재 인코딩 감지
        current_encoding, confidence = detect_encoding(input_file)
        print(f"파일: {input_file}")
        print(f"감지된 인코딩: {current_encoding} (신뢰도: {confidence:.2f})")
        
        # 여러 인코딩으로 시도
        encodings_to_try = ['cp949', 'euc-kr', 'utf-8', 'utf-8-sig', 'latin1']
        
        for encoding in encodings_to_try:
            try:
                print(f"  {encoding}로 읽기 시도...")
                df = pd.read_csv(input_file, encoding=encoding)
                
                # 한글이 제대로 읽혔는지 확인 (첫 번째 행의 한글 컬럼 확인)
                sample_text = str(df.iloc[0, 0]) if len(df) > 0 else ""
                if any('\u3131' <= char <= '\u318e' or '\uac00' <= char <= '\ud7af' for char in sample_text):
                    print(f"  {encoding}로 성공적으로 읽음")
                    
                    # 목표 인코딩으로 저장
                    df.to_csv(output_file, index=False, encoding=target_encoding)
                    print(f"  {target_encoding}로 저장 완료: {output_file}")
                    return True
                else:
                    print(f"  {encoding}로 읽었지만 한글이 제대로 표시되지 않음")
                    
            except Exception as e:
                print(f"  {encoding}로 읽기 실패: {e}")
                continue
        
        print(f"모든 인코딩 시도 실패: {input_file}")
        return False
        
    except Exception as e:
        print(f"파일 처리 중 오류: {e}")
        return False

def main():
    """메인 실행 함수"""
    # 수정할 파일 목록
    files_to_fix = [
        'data/상품검색.csv',
        'data/자산규모 및 유동성(기간).csv',
        'data/참고지수(기간).csv',
        'data/투자위험(기간).csv',
        'data/수익률 및 총보수(기간).csv'
    ]
    
    print("CSV 파일 인코딩 수정 시작...")
    print("=" * 50)
    
    success_count = 0
    total_count = len(files_to_fix)
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            print(f"\n처리 중: {file_path}")
            if fix_csv_encoding(file_path):
                success_count += 1
        else:
            print(f"\n파일이 존재하지 않음: {file_path}")
    
    print("\n" + "=" * 50)
    print(f"처리 완료: {success_count}/{total_count} 파일 성공")
    
    if success_count == total_count:
        print("모든 파일의 인코딩이 성공적으로 수정되었습니다!")
    else:
        print("일부 파일의 인코딩 수정에 실패했습니다.")

if __name__ == "__main__":
    main() 