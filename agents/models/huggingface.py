from langchain.messages import HumanMessage, AIMessage, SystemMessage
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from dotenv import load_dotenv
import os

load_dotenv()
API = os.getenv("HF_API")

#Model Configuration
llm = HuggingFaceEndpoint(
    repo_id ="deepseek-ai/DeepSeek-V4-Flash",
    huggingfacehub_api_token=API
)

llm = ChatHuggingFace(llm=llm)

#Running
messages = []

while True:

    #System prompt
    system_prompt = SystemMessage(
    "You are an AI Assitant"
    )
    messages.append(system_prompt)

    #User input
    input_user = input("Chat with AI: ")
    user_message = HumanMessage(input_user)
    messages.append(user_message)

    #AI Response
    response = llm.invoke(messages)
    AI_response = AIMessage(response.content)
    messages.append(AI_response)
    print(AI_response.content)





