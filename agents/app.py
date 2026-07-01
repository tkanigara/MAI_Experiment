from ReAct.React import app

messages = []
while True:
    user_input = input("Chat With AI: ")
    state = {
        "messages": messages,
        "user_query": user_input,
        "agent_answer": [],
    }

    run = app.invoke(state)
    messages = run["messages"]
    output = run["agent_answer"][-1]
    print(output)
