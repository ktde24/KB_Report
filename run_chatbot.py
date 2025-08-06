#!/usr/bin/env python3
"""
KB ETF 챗봇 실행 스크립트
"""

import subprocess
import sys
import os

def main():
    """챗봇 앱 실행"""
    try:
        # 현재 디렉토리를 KB_Report로 변경
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Streamlit 앱 실행
        cmd = [sys.executable, "-m", "streamlit", "run", "app/chatbot_app.py"]
        
        print("🏦 KB ETF 챗봇을 시작합니다...")
        print("📱 브라우저에서 http://localhost:8501 으로 접속하세요.")
        print("⏹️  종료하려면 Ctrl+C를 누르세요.")
        print("-" * 50)
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n👋 챗봇을 종료합니다.")
    except Exception as e:
        print(f"❌ 오류가 발생했습니다: {e}")
        print("💡 필요한 패키지가 설치되어 있는지 확인해주세요:")
        print("   pip install streamlit pandas openai")

if __name__ == "__main__":
    main() 