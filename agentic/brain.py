from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv


load_dotenv()

# Untuk prototype cepat, key boleh fallback dari value ini.
# Nanti production sebaiknya pindahkan ke .env / secret manager.
HARDCODED_GOOGLE_API_KEY = "PASTE_GOOGLE_API_KEY_HERE"

google_api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not google_api_key and HARDCODED_GOOGLE_API_KEY != "PASTE_GOOGLE_API_KEY_HERE":
    google_api_key = HARDCODED_GOOGLE_API_KEY

if not google_api_key:
    raise RuntimeError(
        "Missing Google Gemini API key. Isi GOOGLE_API_KEY/GEMINI_API_KEY di .env "
        "atau paste ke HARDCODED_GOOGLE_API_KEY di agentic/brain.py."
    )

os.environ["GOOGLE_API_KEY"] = google_api_key

llm = ChatGoogleGenerativeAI(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
)
