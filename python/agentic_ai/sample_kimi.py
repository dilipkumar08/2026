from huggingface_hub import InferenceClient



import os

HF_TOKEN=os.environ.get("HF_TOKEN")
# print(f"Using Hugging Face token: {HF_TOKEN}")

client=InferenceClient(model="moonshotai/Kimi-K2.5", token=HF_TOKEN)



output=client.chat.completions.create(
    messages=[{"role":"user","content":"the color of orange is "}],
    max_tokens=150,
    stream=False,
    extra_body={"thinking":{"type":"disabled"}},
)

print(output.choices[0].message.content)


output1=client.chat.completions.create(
    messages=[{"role": "user","content":"the color of orange is"}],
    stream=False,
    max_tokens=150,
    stop=["Observation:"],
    extra_body={"thinking":{"type":"disabled"}},
)

print(output1.choices[0].message.content)


