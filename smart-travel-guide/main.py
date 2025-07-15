import os
import uuid
import traceback
from datetime import datetime

import google.generativeai as genai
import gspread
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates 
from pydantic import BaseModel

# 실행 : python -m uvicorn main:app --reload

# --- 1. 초기 설정 ---

# .env 파일에서 환경 변수 로드
load_dotenv()

# FastAPI 앱 생성
app = FastAPI()

# 정적 파일(css, js) 및 템플릿(html) 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Gemini API 설정
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# Google Sheets API 설정
sheet = None
try:
    client = gspread.service_account(filename='google-credentials.json')
    sheet = client.open_by_key("1draadvTPBbu9K-hhNHD7rbCa3_8R7xeYfBAIftO2Z2A").worksheet("해외여행") 
except Exception as e:
    # 발생한 예외의 상세 메시지와 전체 호출 스택을 출력
    error_message = str(e)
    stack_trace = traceback.format_exc()
    print(f"⚠️ 경고: 구글 시트 초기화 중 심각한 오류가 발생했습니다. (오류: {error_message})")
    print("\n--- 상세 디버그 정보 ---")
    print(stack_trace)
    print("-----------------------\n")
    print("👉 해결 방법: 위의 상세 오류 메시지를 확인하고, 아래 사항들을 점검해주세요.")


# --- 2. 데이터 모델 정의 (Pydantic) ---

# 프론트엔드에서 받을 요청 본문의 구조를 정의합니다.
class TravelRequest(BaseModel):
    destination: str
    duration: str
    headcount: str
    gender: str
    age: str
    style: str
    budget: str

# --- 3. API 엔드포인트 ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """메인 페이지를 렌더링합니다."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/recommend")
async def get_travel_recommendation(req: TravelRequest):
    """여행 경로 추천 요청을 처리하고 결과를 반환합니다."""
    request_id = str(uuid.uuid4())
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prompt = ""
    result_text = ""
    status = "실패"
    error_message = ""

    try:
        # 1. Gemini API에 보낼 프롬프트 생성
        prompt = f"""
        당신은 세계 최고의 여행 플래너입니다. 아래 조건에 맞춰 여행 계획을 짜주세요.
        결과는 각 일차별로 구분해서 상세한 활동과 추천 맛집을 포함하여 자연스러운 문장으로 설명해 주세요.

        - 여행지: {req.destination}
        - 여행 기간: {req.duration}
        - 인원 및 구성: {req.headcount}, {req.gender}, {req.age}
        - 여행 스타일: {req.style}
        - 1인당 예산: {req.budget}
        
        ---
        [출력 형식 예시]
        ### ✨ {req.destination} {req.duration} 추천 여행 코스 ✨

        **1일차: 도시의 심장을 느끼다**
        - 오전: [장소]에 방문하여 [활동]을 즐겨보세요.
        - 점심: [맛집 이름] (추천 메뉴: [메뉴])
        - 오후: [장소]를 산책하며 여유를 만끽하세요.
        - 저녁: [맛집 이름]에서 로맨틱한 저녁 식사를 즐겨보세요.

        **2일차: ...**
        """

        # 2. Gemini API 호출
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = await model.generate_content_async(prompt)
        result_text = response.text
        status = "성공"

    except Exception as e:
        print(f"API 호출 오류: {e}")
        error_message = str(e)
        raise HTTPException(status_code=500, detail="AI 모델을 호출하는 중 오류가 발생했습니다.")

    finally:
        # 3. 구글 시트에 결과 기록 (성공/실패 모두)
        if sheet:
            try:
                row = [
                    request_id, timestamp, req.destination, req.headcount,
                    req.gender, req.age, req.style, req.duration, req.budget,
                    prompt, result_text, status, error_message
                ]
                sheet.append_row(row)
            except Exception as e:
                print(f"구글 시트 작성 오류: {e}")
                # 시트 작성에 실패하더라도 사용자에게는 결과를 반환해야 하므로, 여기서 에러를 발생시키지 않음

    return {"recommendation": result_text}


# --- 4. 서버 실행 ---

if __name__ == "__main__":
    # 터미널에서 `uvicorn main:app --reload` 명령어로 실행할 수 있습니다.
    uvicorn.run(app, host="0.0.0.0", port=8000)

