from CentralArch.graph import app
from CentralArch.state import (
    State,
    Request,
    MetaData,
    Workflow
)
from datetime import date

initial_state = State(

    request=Request(
        user_intent="Generate Marketing Report",
        client_code="CL001",
        report_date=date(2026,5,24)
    ),

    metadata=MetaData(
        client_code="",
        client_name="",
        instagram=False,
        facebook=False,
        tiktok=False,
        youtube=False,
        loaded=False
    ),

    workflow=Workflow(
        current_process="",
        assigned_agent="",
        status=""
    )
)

result = app.invoke(initial_state)
print(result)