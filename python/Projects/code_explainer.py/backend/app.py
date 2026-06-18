from fastapi import FastAPI, HTTPException

from fastapi.responses import FileResponse

from fastapi.middleware.cors import CORSMiddleware

from model import UserInput

from main import generate_code_info

from logger import logger

app=FastAPI(title="Code Explainer",description="you provide your code and we will explain it",
            version="1.0.0")


app.add_middleware(CORSMiddleware,
                     allow_origins=["*"],  # Allows all origins (for development)
    allow_methods=["*"],   # Allows all HTTP methods
    allow_headers=["*"],   # Allows all headers
)


@app.get("/")
async def home():
    logger.info("function: (home) at home.html")
    return FileResponse("../frontend/home.html")

@app.get("/analyze")
async def analyze_page():
    logger.info("function: (analyze_page) at analyze.html")
    return FileResponse("../frontend/analyze.html")


@app.post("/analyze")
async def analyze_code(user_input: UserInput):
    logger.info("function : (analyze_code) recieve process request")
    result=generate_code_info(user_input)

    return {"result" :result}
