from pypdf import PdfReader
from typing import List
from sentence_transformers import SentenceTransformer,CrossEncoder
import faiss
import re
import numpy as np
from huggingface_hub import InferenceClient
import os

client=InferenceClient(model="moonshotai/Kimi-K2.5",
                       token=os.getenv("HF_TOKEN"))


def pdf_extractor()->str:
    reader=PdfReader("mahabharata.pdf")
    print(f"Pages: {len(reader.pages)}")
    pdf_content=""
    for page_num,page in enumerate(reader.pages,start=1):
        print("processing page:",page_num)
        if page.extract_text():
            pdf_content+=" "+page.extract_text()
        
    pdf_content = re.sub(r'\s+', ' ', pdf_content).strip()
    return pdf_content

def chunker(content:str,chunk_size:int)->List[str]:
    chunks=[]
    skip_size=(chunk_size*90)//100
    for size in range(0,len(content),skip_size):
        chunks.append(content[size:size+chunk_size])
    return chunks


def vectorizer(chunks:List[str])->List[float]:
    model=SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    vectors=model.encode(chunks)
    print(vectors.shape)
    return vectors

def store_vector(vectors):
    vectors=np.array(vectors).astype("float32")
    dimension=vectors.shape[1]
    index=faiss.IndexFlatL2(dimension)
    index.add(vectors)
    return index

def reranking(query:str,retrived_chunks:List):
    reranker=CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    pairs=[[query,chunk] for chunk in retrived_chunks]
    scores=reranker.predict(pairs)
    reranked=sorted(zip(retrived_chunks,scores),key=lambda x:x[1],reverse=True)


def llm_call(user_prompt:str,similar_content)->str:
    response=client.chat_completion(messages=[{"role":"user","content":f"{user_prompt}"},{"role":"system","content":""\
    f"you are a content creator and a story teller. this given detail <{similar_content}> has 2 things "\
    "one is similar content at index 0 and second is the score of how similar to the user prompt in index 1."
    "your role is summarize the similar content and answer the user query in a precise way neglect unwanted information unrelated metrics.  "},],max_tokens=500,stream=False,extra_body={"thinking":{"type":"disabled"}},)
    return response.choices[0].message.content


if __name__=="__main__":
    content=pdf_extractor()
    chunks=chunker(content,int(input("Enter the chunk size:")))
    vectors=vectorizer(chunks)
    index=store_vector(vectors)
    chat=True
    while(chat):
        user_query=str(input("Enter your query:"))
        query_vector=vectorizer([user_query])
        distance,indices=index.search(np.array(query_vector).astype("float32"),3)
        retrived_chunks=[chunks[i] for i in indices[0]]
        reranked=reranking(user_query,retrived_chunks)
        response=llm_call(user_query,reranked)
        print(f"response:{response}")


        

