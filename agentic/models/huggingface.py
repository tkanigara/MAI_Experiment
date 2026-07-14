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
