from huggingface_hub import InferenceClient
import os
from model import UserInput
from logger import logger
from fastapi import HTTPException

client=InferenceClient(model="moonshotai/Kimi-K2.5",
                       token=os.getenv("HF_TOKEN"))

# print(os.getenv("HF_TOKEN"))


def generate_code_info(user_input:UserInput)->str:

    logger.info("function: (generate_code_info) processing code....")
    logger.info(f"function: (generate_code_info) user_input: \nlanguage:{user_input.language}\ncode:\n{user_input.text}")

    try:
        response=client.chat_completion(messages=[{"role":"system","content":f"You are a expert senior python code reviewer and explainer. keep the answers precise and only give the final answer do not provide thoughts"},
                                                {"role":"user","content":f"Please, Explain this code {user_input.text} include: 1, purpose 2, line by line explanation 2,errors 3, errors 4, output 5, time complexity"},]
                                                ,max_tokens=500
                                                ,stream=False
                                                ,extra_body={"thinking":{"type":"disabled"}},)
        logger.info("function: (generate_code_info) process completed")
        return response.choices[0].message.content
    
    except Exception as e:
        logger.exception(f"function: (generate_code) {str(e)}")
        raise  HTTPException(status_code=500,detail=f"Error generating result: {str(e)}")


    


