from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))  # sesuaikan

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Say hello"
)

print(response.text)