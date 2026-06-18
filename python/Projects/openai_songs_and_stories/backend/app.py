from fastapi import FastAPI , HTTPException
from fastapi.responses import FileResponse
#framework to build API
from fastapi.middleware.cors import CORSMiddleware
#cross origin resource sharing 
from helper import is_story_or_song_request,text_to_speech,generate_story,generate_song
from models import ProcessResponse, UserRequest

from fastapi.staticfiles import StaticFiles



#creating fastapi instance
app=FastAPI(title="Story & Song creator",description="API for  stories and songs",
            version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")


app.add_middleware(CORSMiddleware,    
    allow_origins=["*"],  # Allows all origins (for development)
    allow_methods=["*"],   # Allows all HTTP methods
    allow_headers=["*"],   # Allows all headers
)


@app.get("/")
async def home():
    return FileResponse("template/index.html")

@app.post("/api/process",response_model=ProcessResponse)
async def process_request(request: UserRequest):
    user_input=request.input
    is_story,is_song=is_story_or_song_request(user_input)

    if not is_story and not is_song:
        apology="I apologize, but I can only create stories and songs..."
        audio_base64 = await text_to_speech(apology)
        return ProcessResponse(text=apology,audio=audio_base64,type="apology")
    
    elif is_story and is_song:
            # If both keywords present, ask for clarification
        clarification = "I can either tell you a story or sing you a song. Which would you prefer?"
        audio_base64 = await text_to_speech(clarification)
        return ProcessResponse(text=clarification,audio=audio_base64,type='clarification')

    elif is_story:
        content = await generate_story(user_input)
        response_type="story"
    elif is_song:
        content = await generate_song(user_input)
        response_type="song"
   
    audio = await text_to_speech(content,response_type)   

    return ProcessResponse(text=content, audio=audio, type=response_type)