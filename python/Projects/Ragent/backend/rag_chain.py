from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.vectorstores import FAISS
import json
import os

PROMPT_DIR = os.environ.get("RAG_PROMPT_DIR", os.path.join(os.path.dirname(__file__), "prompts"))


def build_chain(vectorstore: FAISS, prompt_version: str):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    prompt_path = os.path.join(PROMPT_DIR, f"{prompt_version}.json")
    with open(prompt_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    prompt = ChatPromptTemplate.from_messages(
        [("system", data["system"]), ("human", data["human"])]
    )

    llm = ChatOllama(model="gemma2:2b", temperature=0)
    parser = StrOutputParser()

    def format_docs(docs) -> str:
        return "\n".join(chunk.page_content.strip() for chunk in docs)

    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | parser
    )

    return chain
