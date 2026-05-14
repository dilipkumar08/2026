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

print("output:",output.choices[0].message.content)


output1=client.chat.completions.create(
    messages=[{"role": "user","content":"the color of orange is"}],
    stream=False,
    max_tokens=150,
    stop=["Observation:"],
    extra_body={"thinking":{"type":"disabled"}},
)

print("\n\noutput1:",output1.choices[0].message.content)


system_prompt="""Answer the following questions as best you can. You have access to the following tools:

get_color : gets the color of the given fruit

The way you use the tools is by specifying a json blob.
Specifically, this json should have an `action` key (with the name of the tool to use) and an `action_input` key (with the input to the tool going here).

The only values that should be in the "action" field are:
get_color: Get the  color for the given fruit, args: {"fruit": {"type": "string"}}
example use :

{{
  "action": "get_color", 
  "action_input": {{"fruit": "apple"}}
}}


ALWAYS use the following format:

Question: the input question you must answer
Thought: you should always think about one action to take. Only one action at a time in this format:
Action:

$JSON_BLOB (inside markdown cell)

Observation: the result of the action. This Observation is unique, complete, and the source of truth.
... (this Thought/Action/Observation can repeat N times, you should take several steps when needed. The $JSON_BLOB must be formatted as markdown and only use a SINGLE action at a time.)

You must always end your output with the following format:

Thought: I now know the final answer
Final Answer: the final answer to the original input question

Now begin! Reminder to ALWAYS use the exact characters `Final Answer:` when you provide a definitive answer. """

output2 = client.chat.completions.create(messages=[
    {"role":"system", "content": system_prompt},
    {"role":"user","content":"the color of orange is "}],
    max_tokens=150,stream=False,extra_body={"thinking":{"type":"disabled"}},stop=["Observation:"],)

print("\n\noutput2:",output2.choices[0].message.content)


def get_color(fruit:str)->str:
    if fruit=="orange":
        return "Orange"
    elif fruit=="apple":
        return "red maybe green"


output3=client.chat.completions.create(messages=[
    {"role":"system","content":system_prompt},
    {"role":"user","content":"the color of orange is"},
    {"role":"assistant","content":output2.choices[0].message.content+"Observation:\n"+get_color("orange")}],
    stream=False,
    max_tokens=150,
    stop=["Observation:"],
    extra_body={"thinking":{"type":"disabled"}},)


print("\n\noutput3:",output3.choices[0].message.content)

