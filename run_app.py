#!/usr/bin/env python3
"""
KB 맞춤형 투자 분석 시스템 실행 스크립트
"""

import os
import sys
import subprocess
import argparse

def check_dependencies():
    """의존성 확인"""
    try:
        import streamlit
        import pandas
        import requests
        import plotly
        print("✅ 기본 의존성 확인 완료")
    except ImportError as e:
        print(f"❌ 의존성 오류: {e}")
        print("pip install -r requirements.txt 를 실행하세요.")
        return False
    return True

def check_env_file():
    """환경변수 파일 확인"""
    if not os.path.exists('.env'):
        print("⚠️  .env 파일이 없습니다.")
        print("다음 내용으로 .env 파일을 생성하세요:")
        print("OPENAI_API_KEY=your_openai_api_key_here")
        return False
    return True

def run_streamlit_app(app_path, port=8501):
    """Streamlit 앱 실행"""
    try:
        cmd = [
            sys.executable, "-m", "streamlit", "run", 
            app_path, "--server.port", str(port)
        ]
        print(f"🚀 {app_path} 실행 중... (포트: {port})")
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 앱이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 앱 실행 오류: {e}")

def main():
    parser = argparse.ArgumentParser(description="KB 맞춤형 투자 분석 시스템")
    parser.add_argument(
        "--app", 
        choices=["main", "chatbot"], 
        default="main",
        help="실행할 앱 선택 (main 또는 chatbot)"
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
    
    args = parser.parse_args()
    
    print("📊 KB 맞춤형 투자 분석 시스템")
    print("=" * 50)
    
    # 의존성 확인
    if not check_dependencies():
        sys.exit(1)
    
    # 환경변수 확인
    if not check_env_file():
        print("⚠️  환경변수 파일이 없어도 실행은 가능하지만, 일부 기능이 제한됩니다.")
    
    if args.check_only:
        print("✅ 의존성 확인 완료")
        return
    
    # 앱 실행
    app_map = {
        "main": "app/main.py",
        "chatbot": "app/chatbot_app.py"
    }
    
    app_path = app_map[args.app]
    if not os.path.exists(app_path):
        print(f"❌ 앱 파일을 찾을 수 없습니다: {app_path}")
        sys.exit(1)
    
    run_streamlit_app(app_path, args.port)

if __name__ == "__main__":
    main()
