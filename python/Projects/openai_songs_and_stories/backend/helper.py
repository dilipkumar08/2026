from fastapi import HTTPException
#to raise valid erros   
from openai import OpenAI
#openai sdk for using models
import os
#interacting with operating system
from dotenv import load_dotenv
#to access the environmental variables
import base64
#to convert binary to text and text to binary
load_dotenv()

print("API KEY =", os.getenv("OPENAI_API_KEY"))
client = OpenAI ( api_key = os.getenv( "OPENAI_API_KEY" ) )
#connecting to OpenAI 


async def generate_story(user_prompt:str)->str:
   #generating a story
   try:
      response = client.chat.completions.create(model="gpt-3.5-turbo",
                     messages=[
                     {"role":"system","content":"You are a creative storyteller. Create engaging, imaginative stories. Make them vivid and entertaining. "\
                     "Keep stories between 200-400 words."},
                     {"role":"user","content":f"write a story based on this prompt: {str(user_prompt)}. Make it creative and engaging"}
                     ],max_tokens =500,
                     temperature=0.8)
      return response.choices[0].message.content
   except Exception as e:
      raise HTTPException(status_code=500,detail=f"Error generating story: {str(e)}")



async def generate_song(user_prompt:str)->str:
   #generating a song
   try:
      response = client.chat.completions.create(model="gpt-3.5-turbo",
                                                messages=[{"role":"system","content":"You are a creative songwriter. Create songs with verses, chorus, "
                                                "and bridge structure. Include [Verse], [Chorus], [Bridge] markers. Make them rhyming and musical."},{"role":"user","content":f"Write a song based on this prompt: {str(user_prompt)}. "}],
                                                max_tokens=500,temperature=0.9)
      return response.choices[0].message.content
   except Exception as e:
      raise HTTPException(status_code=500,detail=f"Error generating song:{str(e)}")
                                             
                                                       

async def text_to_speech(text:str,result_type:str=None)->str | None:
   """convert text to speech and return as base64 encoded audio"""
   try:
        voice_mapping={"story":{"voice":"fable","speed":0.9},"song":{"voice":"shimmer","speed":1.1}}
        response=client.audio.speech.create(model="tts-1",voice=voice_mapping.get(result_type,{}).get("voice","alloy"),input=text,
                                          speed=voice_mapping.get(result_type,{}).get("speed",1.0),response_format="mp3")
        return base64.b64encode(response.content).decode("utf-8")                                      
   except Exception as e:
        raise HTTPException(status_code=500,detail=f"TTS Error: {str(e)}")



def is_story_or_song_request(user_input:str):
   
   """Checks if user wants story or a song"""

   story_keywords = ["story","tale","narrate","narrative","fable"]
   song_keywords = ["song","sing","lyrics","melody"]

   user_input_lower=user_input.lower()
   is_story = any(keyword in user_input_lower for keyword in story_keywords)
   is_song  = any(keyword in user_input_lower for keyword in song_keywords)

   return is_story,is_song

