from ReAct.React import app
from graph.state import AgentState

messages = []
while True:
    user_input = input("Chat With AI: ")
    AgentState = {
        "messages": messages,
        "user_query": user_input,
        "agent_answer": None
    }

    run = app.invoke(AgentState)
    output = run["agent_answer"]
    print(output.content)