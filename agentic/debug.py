from agents.retrieval import retrieval_agent

user_input = input("ASk AI: ")
AI_result = retrieval_agent(user_input)
print(AI_result)