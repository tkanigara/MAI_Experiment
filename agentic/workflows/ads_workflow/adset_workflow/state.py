from datetime import date
from pydantic import BaseModel, Field

class Request(BaseModel):
    user_intent: str
    client_code: str | None = None
    report_date: str | None = None

class Metadata(BaseModel):
    client_id: str | None = None
    
class State(BaseModel):
    request: Request

