import os
from huggingface_hub import InferenceClient


# Function of this is Reasoning, planning, understand human language, and response to user
# LLM Working with text, LLM don't execute Tools
client = InferenceClient(
    api_key="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",
    model="meta-llama/Meta-Llama-3-8B-Instruct")

def call_llm(messages):
    response = client.chat.completions.create(
        messages=messages,
        max_tokens=300
    )
    return response.choices[0].message.content