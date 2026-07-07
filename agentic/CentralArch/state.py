from typing_extensions import TypedDict
from datetime import date
from pydantic import BaseModel


class Request(BaseModel):
    user_intent: str
    client_code: str | None = None
    report_date: date | None = None

class Workflow(BaseModel):
    current_process: str | None = None
    current_agent: str | None = None

    next_process: str | None = None
    next_agent: str | None = None

    status: str | None = None
    
class MetaData(BaseModel):
    client_code:str | None = None
    client_name:str | None = None
    instagram: bool =  False
    facebook: bool = False
    tiktok: bool = False
    youtube: bool = False

    loaded: bool = False

class DataRequirements(BaseModel):
    pass
class State(BaseModel):
    #request
    request: Request

    #metadata
    metadata: MetaData

    #workflows
    workflow: Workflow


    














    
    
