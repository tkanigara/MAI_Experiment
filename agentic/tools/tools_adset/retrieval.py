from langchain_core.tools import tool
from config.db import get_connection
from datetime import datetime

@tool
def retrieval(client)