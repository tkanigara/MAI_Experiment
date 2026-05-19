from brain import llm
from tools import (
    list_csv_files,
    build_kpi_report,
    compare_target_vs_actual,
    get_top_performers,
    generate_google_slides_report,
)
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import MessagesState
from langgraph.prebuilt import ToolNode, create_react_agent
from langgraph.prebuilt import tools_condition

#Initialization model and Tools
model = llm

discovery_files_tools = list_csv_files
build_kpi_report_tools = build_kpi_report
kpi_achievement_tools= compare_target_vs_actual
top_performance_tools = get_top_performers
generate_google_slides_report_tools = generate_google_slides_report

TOOLS = [
    discovery_files_tools,
    build_kpi_report_tools,
    kpi_achievement_tools,
    top_performance_tools,
    generate_google_slides_report_tools,
]

#Initialization  Graph with state
states = MessagesState # Conversation Structure
graph = StateGraph(states)

#System Prompt
SYSTEM_PROMPT = """
You are helpful AI Report generator, KPI Analyst, and advisor.
Your task is analyze KPI files in csv format, generate report based on data and give advice for user.
and here's tools you can use to fulfill the task

============================
TOOLS
============================

1) Tool name:
list_csv_files

Description: Detect and help available CSV datasets

utility: Dataset discovery, Environment awareness, File validation, Dynamic file selection

Arguments:None

2) Tool name:
build_kpi_report

Description: Read and Generate KPI report from CSV dataset, produce KPI overview

Utility:Dataset Profiling(numbers of row, numbers of columns, missing values, data type), KPI Aggregation(produce total, avarage, minimum, maximum), Sample Context

Arguments: filename: str

3) Tool name:
compare_target_vs_actual

Description: Compare actual vs target performance, count KPI achievement KPI, evaluate business achievements

utility:KPI Achievement Analysis, Business Performance Evaluation, Executive Reporting

Arguments: filename: str, actual_column, target_column

4) Tool name:
get_top_performers

Description: Find best performers, ranking analysis, sort performance by specific metrics

utility: Ranking analysis, Comparative Analytics, Business Intelligence

Arguments:filename: str, category_column, value_column, top_n

5) Tool name:
generate_google_slides_report

Description: Generate a Google Slides social media KPI report from Instagram CSV data.

Utility: Copy Google Slides template, calculate Instagram KPIs, replace template placeholders, and return the generated presentation URL.

Arguments:
- csv_filename: str, optional. Use a file from data/processed. If empty, newest Instagram media CSV is used.
- account_csv_filename: str, optional. If empty, newest Instagram account CSV is used when available.
- client_name: str
- report_period: str
- dry_run: bool. Use true to preview mapping without creating a new Slides file.
- use_ai_insights: bool. Use true to generate insight and recommendation text with Gemini.


============================
RULES
============================
1. Understanding what users need
2. Great in planning to take step by step and use the tools and have nice reasoning
3. Never use your own knowledge
4. Never Hallucinations
5. If the user asks to generate/create/fill Google Slides, use generate_google_slides_report.
6. If the user only wants to preview slide data, call generate_google_slides_report with dry_run=true.
7. For slide reports, use_ai_insights should be true unless the user explicitly asks for template-only text.

"""
#Initialization Graph nodes
agent_node = create_react_agent(model=model, tools=TOOLS, prompt=SYSTEM_PROMPT)
tools_node = ToolNode(tools=TOOLS)

#Edges design flow
graph.add_node("agent", agent_node)
graph.add_node("tools", tools_node)

graph.add_edge(START, "agent")

graph.add_conditional_edges(
    "agent",
    tools_condition
)

graph.add_edge("tools", "agent")

app = graph.compile()


#Running
messages = []

while True:

    user_input = input("\nYou: ")

    if user_input.lower() == "exit":
        break

    messages.append(("user", user_input))

    try:

        response = app.invoke({
            "messages": messages
        })

        ai_message = response["messages"][-1]

        print("\nAssistant:")

        if isinstance(ai_message.content, str):

            print(ai_message.content)

        elif isinstance(ai_message.content, list):

            for item in ai_message.content:

                if isinstance(item, dict):

                    if item.get("type") == "text":

                        print(item.get("text"))

        else:

            print(ai_message.content)

        # Save assistant response to memory
        messages.append(("assistant", ai_message.content))

    except Exception as e:

        print(f"\nError: {str(e)}")
