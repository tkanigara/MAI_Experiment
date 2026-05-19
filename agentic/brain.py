from langchain_google_genai import ChatGoogleGenerativeAI
import getpass
import os


os.environ["GOOGLE_API_KEY"] = "AIzaSyAlPTUoK52EeHDboelVum87wVr17I6OZXo"

llm = ChatGoogleGenerativeAI(
    
    model='gemini-3.1-flash-lite-preview'
    )
