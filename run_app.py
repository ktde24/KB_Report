
"""
Just Fit It - 개인화된 투자 분석 시스템 실행 스크립트
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def check_dependencies():
    """의존성 확인"""
    required_packages = [
        ('streamlit', 'streamlit'),
        ('pandas', 'pandas'),
        ('requests', 'requests'),
        ('plotly', 'plotly'),
        ('openai', 'openai'),
        ('pykrx', 'pykrx'),
        ('yfinance', 'yfinance')
    ]
    
    missing_packages = []
    
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"{package_name}")
        except ImportError:
            print(f"{package_name} (누락)")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n누락된 패키지: {', '.join(missing_packages)}")
        print("다음 명령어로 설치하세요:")
        print("pip install -r requirements.txt")
        return False
    
    print("\n모든 의존성 확인 완료")
    return True

def check_env_file():
    """환경변수 파일 확인"""
    env_file = Path('.env')
    
    if not env_file.exists():
        print(".env 파일이 없습니다.")
        print("\n다음 단계를 따라 설정하세요:")
        print("1. env.example 파일을 .env로 복사")
        print("2. .env 파일에서 OPENAI_API_KEY 설정")
        print("3. https://platform.openai.com/api-keys 에서 API 키 발급")
        return False
    
    # .env 파일 내용 확인
    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'OPENAI_API_KEY=your_openai_api_key_here' in content:
                print(".env 파일에서 OPENAI_API_KEY를 실제 값으로 변경하세요.")
                return False
            elif 'OPENAI_API_KEY=' in content:
                print(".env 파일 확인 완료")
                return True
            else:
                print(".env 파일에 OPENAI_API_KEY가 설정되지 않았습니다.")
                return False
    except Exception as e:
        print(f".env 파일 읽기 오류: {e}")
        return False

def check_data_files():
    """데이터 파일 확인"""
    data_dir = Path('data')
    required_files = [
        '상품검색.csv',
        '수익률 및 총보수(기간).csv',
        '투자위험(기간).csv',
        '자산규모 및 유동성(기간).csv'
    ]
    
    missing_files = []
    
    for file_name in required_files:
        file_path = data_dir / file_name
        if file_path.exists():
            print(f"{file_name}")
        else:
            print(f"{file_name} (누락)")
            missing_files.append(file_name)
    
    if missing_files:
        print(f"\n누락된 데이터 파일: {', '.join(missing_files)}")
        print("데이터 파일을 data/ 디렉토리에 추가하세요.")
        return False
    
    print("\n모든 데이터 파일 확인 완료")
    return True

def run_streamlit_app(app_path, port=8501):
    """Streamlit 앱 실행"""
    try:
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            app_path, 
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        ]
        
        print(f"\n🚀 {app_path} 실행 중...")
        print(f"포트: {port}")
        print(f"🌐 브라우저: http://localhost:{port}")
        print("⏹종료하려면 Ctrl+C를 누르세요.")
        print("-" * 50)
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n\n앱이 종료되었습니다.")
    except Exception as e:
        print(f"\n앱 실행 오류: {e}")
        print("다음 사항을 확인하세요:")
        print("1. 포트가 사용 중인지 확인")
        print("2. 방화벽 설정 확인")
        print("3. 다른 포트로 시도: --port 8502")

def main():
    parser = argparse.ArgumentParser(
        description="KB 맞춤형 투자 분석 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python run_app.py                    # 메인 앱 실행
  python run_app.py --app chatbot      # 챗봇 앱 실행
  python run_app.py --port 8502        # 다른 포트로 실행
  python run_app.py --check-only       # 의존성만 확인
        """
    )
    
    parser.add_argument(
        "--app", 
        choices=["main", "chatbot"], 
        default="main",
        help="실행할 앱 선택 (기본값: main)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8501,
        help="포트 번호 (기본값: 8501)"
    )
    parser.add_argument(
        "--check-only", 
        action="store_true",
        help="의존성만 확인하고 실행하지 않음"
    )
    parser.add_argument(
        "--skip-data-check",
        action="store_true",
        help="데이터 파일 확인 건너뛰기"
    )
    
    args = parser.parse_args()
    
    print("📊 KB 맞춤형 투자 분석 시스템")
    print("=" * 50)
    
    # 의존성 확인
    print("\n🔍 의존성 확인 중...")
    if not check_dependencies():
        sys.exit(1)
    
    # 환경변수 확인
    print("\n🔍 환경변수 확인 중...")
    env_ok = check_env_file()
    
    # 데이터 파일 확인
    if not args.skip_data_check:
        print("\n🔍 데이터 파일 확인 중...")
        data_ok = check_data_files()
        if not data_ok:
            print("\n⚠️  일부 데이터 파일이 누락되었지만 실행은 가능합니다.")
    
    if args.check_only:
        print("\n모든 확인 완료")
        return
    
    # 경고 메시지
    if not env_ok:
        print("\nOpenAI API 키가 설정되지 않아 GPT 기능이 제한됩니다.")
        print("계속 진행하시겠습니까? (y/N): ", end="")
        try:
            response = input().lower()
            if response not in ['y', 'yes']:
                print("실행을 취소했습니다.")
                return
        except KeyboardInterrupt:
            print("\n실행을 취소했습니다.")
            return
    
    # 앱 실행
    app_map = {
        "main": "app/main.py",
        "chatbot": "app/chatbot_app.py"
    }
    
    app_path = app_map[args.app]
    if not os.path.exists(app_path):
        print(f"\n앱 파일을 찾을 수 없습니다: {app_path}")
        sys.exit(1)
    
    run_streamlit_app(app_path, args.port)

if __name__ == "__main__":
    main()
