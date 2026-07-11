from langchain_community.tools import DuckDuckGoSearchRun

search=DuckDuckGoSearchRun()

print(search.invoke("Who is the current chief minister of Tamilnadu?"))