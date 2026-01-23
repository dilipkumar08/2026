from fastapi import FastAPI, HTTPException
from app.schemas import PostCreate, PostResponse

app=FastAPI()

text_posts={1:{"title":"New Post","content":"cool test post"},
2:{"title":"I am Gojo Satoru","content":"From the heavens to Earth I alone the honoured one"}}

@app.get(path="/posts")
def get_all_posts(limit: int=None):
    if limit:
        return list(text_posts.values())[:limit]

    return text_posts

@app.get("/posts/{id}")
def get_post(id:int)-> PostResponse:
    return text_posts.get(id)


@app.post("/posts")
def create_post(post: PostCreate) ->PostResponse:
    new_post={"title":post.title,"content":post.content}
    text_posts[max(text_posts.keys())+1]={"title":post.title,"content":post.content}
    return new_post