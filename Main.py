from Brain import call_llm
from tools import (
    list_csv_files,
    load_csv_data,
    get_dataset_overview,
    generate_kpi_summary,
    compare_target_vs_actual,
    get_top_performers,
    get_sample_data,
    build_kpi_report_data,
)
import re

SYSTEM_PROMPT = """
You are an AI KPI and Business Intelligence Assistant.

Your task is to analyze CSV datasets,
calculate KPI metrics,
identify business insights,
and generate professional KPI reports.

You have access to external tools.

==================================================
AVAILABLE TOOLS
==================================================

Tool Name:
LIST_FILES

Description:
List all available CSV files inside the data folder.

Arguments:
None

Use When:
- User does not specify filename
- You need to discover available datasets


--------------------------------------------------

Tool Name:
LOAD_CSV

Description:
Load CSV file into pandas DataFrame.

Arguments:
- filename (string)

Use When:
- Raw dataset access is required
- Dataset inspection is needed


--------------------------------------------------

Tool Name:
BUILD_KPI_REPORT

Description:
Generate complete KPI report data including:
- dataset overview
- KPI summary
- sample data

Arguments:
- filename (string)

Use When:
- User requests KPI report
- User requests business analysis
- User requests summary or insights


--------------------------------------------------

Tool Name:
KPI_SUMMARY

Description:
Generate KPI statistics for numeric columns.

Arguments:
- filename (string)

Use When:
- KPI metrics are needed
- Statistical summaries are needed


--------------------------------------------------

Tool Name:
COMPARE_TARGET

Description:
Compare actual KPI against target KPI.

Arguments:
- filename (string)
- actual_column (string)
- target_column (string)

Use When:
- User asks about target achievement
- KPI performance comparison is needed


--------------------------------------------------

Tool Name:
TOP_PERFORMERS

Description:
Identify top performing categories,
employees, products, or regions.

Arguments:
- filename (string)
- category_column (string)
- value_column (string)
- top_n (integer, default 5)

Use When:
- Ranking analysis is needed
- Best performers are requested


==================================================
REACT FORMAT
==================================================

You MUST follow this format.

THOUGHT:
reasoning about the problem

ACTION:
TOOL_NAME: arguments


Examples:

ACTION:
LIST_FILES


ACTION:
BUILD_KPI_REPORT: sales.csv


ACTION:
COMPARE_TARGET: filename=sales.csv, actual=revenue, target=target_revenue


ACTION:
TOP_PERFORMERS: filename=sales.csv, category=region, value=revenue, top_n=5


==================================================
TOOL USAGE RULES
==================================================

- If filename is unknown:
  use LIST_FILES first

- If user requests KPI report:
  use BUILD_KPI_REPORT

- If KPI comparison is requested:
  use COMPARE_TARGET

- If ranking analysis is requested:
  use TOP_PERFORMERS

- NEVER hallucinate dataset information

- NEVER invent columns or KPI values

- ONLY use information from observations


==================================================
IMPORTANT EXECUTION RULES
==================================================

- You NEVER execute tools

- The orchestrator executes tools

- Tool calls are instructions only

- STOP generation immediately after ACTION

- Do not generate explanations after ACTION


==================================================
AFTER OBSERVATION
==================================================

When observation is provided:

- Analyze ONLY the observation

- Use the observation as the source of truth

- If enough information exists:
  generate FINAL ANSWER immediately

- Do NOT call unnecessary tools repeatedly

- Do NOT hallucinate missing information


==================================================
FINAL ANSWER FORMAT
==================================================

Generate a professional KPI report containing:

1. Executive Summary

2. Dataset Overview

3. KPI Highlights

4. Important Trends or Patterns

5. Target Achievement Analysis

6. Top Performers

7. Key Business Insights

8. Recommendations

9. Short Conclusion


==================================================
REPORTING STYLE
==================================================

- Use professional business language

- Keep explanations concise but informative

- Focus on business insights

- Highlight important KPI changes

- Mention risks or underperformance if detected

- Provide actionable recommendations
"""

messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]

df_cache = {}

TOOLS = {
    "LIST_FILES":       list_csv_files,
    "LOAD_CSV":         load_csv_data,
    "BUILD_KPI_REPORT": build_kpi_report_data,
    "KPI_SUMMARY":      generate_kpi_summary,
    "COMPARE_TARGET":   compare_target_vs_actual,
    "TOP_PERFORMERS":   get_top_performers,
    "DATASET_OVERVIEW": get_dataset_overview,
    "GET_SAMPLE_DATA":  get_sample_data,
}


def parse_action(text):
    action_blocks = re.split(r"ACTION\s*:", text, flags=re.IGNORECASE)
    if len(action_blocks) < 2:
        return None, None

    block = action_blocks[-1].strip()

    if re.match(r"LIST_FILES", block, re.IGNORECASE):
        return "LIST_FILES", None

    m = re.match(r"LOAD_CSV\s*:\s*([^\n,]+)", block, re.IGNORECASE)
    if m:
        return "LOAD_CSV", {"filename": m.group(1).strip()}
    
    m = re.match(r"BUILD_KPI_REPORT\s*:\s*([^\n,]+)", block, re.IGNORECASE)
    if m:
        return "BUILD_KPI_REPORT", {"filename": m.group(1).strip()}

    m = re.match(r"KPI_SUMMARY\s*:\s*([^\n,]+)", block, re.IGNORECASE)
    if m:
        return "KPI_SUMMARY", {"filename": m.group(1).strip()}

    m = re.match(r"DATASET_OVERVIEW\s*:\s*([^\n,]+)", block, re.IGNORECASE)
    if m:
        return "DATASET_OVERVIEW", {"filename": m.group(1).strip()}

    m = re.match(r"GET_SAMPLE_DATA\s*:\s*([^\n,]+)", block, re.IGNORECASE)
    if m:
        return "GET_SAMPLE_DATA", {"filename": m.group(1).strip()}

    if re.match(r"COMPARE_TARGET", block, re.IGNORECASE):
        args = _parse_kwargs(block)
        return "COMPARE_TARGET", args

    if re.match(r"TOP_PERFORMERS", block, re.IGNORECASE):
        args = _parse_kwargs(block)
        return "TOP_PERFORMERS", args

    return None, None


def _parse_kwargs(text):
    return {
        k.strip(): v.strip()
        for k, v in re.findall(r"(\w+)\s*=\s*([^,\n]+)", text)
    }

def _get_df(filename):
    if filename not in df_cache:
        try:
            df = load_csv_data(filename)          
            df_cache[filename] = df
        except Exception as e:
            return None, f"ERROR loading '{filename}': {e}"
    return df_cache[filename], None


def execute_tool(action_type, args):
    if action_type == "LIST_FILES":
        return list_csv_files()

    if action_type == "LOAD_CSV":
        filename = args.get("filename", "")
        df, err = _get_df(filename)
        if err:
            return err
        return (
            f"File '{filename}' loaded successfully.\n"
            f"Shape: {df.shape[0]} rows x {df.shape[1]} columns.\n"
            f"Columns: {list(df.columns)}"
        )

    if action_type == "BUILD_KPI_REPORT":
        filename = args.get("filename", "")
        try:
            return build_kpi_report_data(filename)
        except Exception as e:
            return f"ERROR: {e}"

    if action_type == "KPI_SUMMARY":
        filename = args.get("filename", "")
        df, err = _get_df(filename)
        if err:
            return err
        try:
            return generate_kpi_summary(df)
        except Exception as e:
            return f"ERROR: {e}"

    if action_type == "DATASET_OVERVIEW":
        filename = args.get("filename", "")
        df, err = _get_df(filename)
        if err:
            return err
        try:
            return get_dataset_overview(df)
        except Exception as e:
            return f"ERROR: {e}"

    if action_type == "GET_SAMPLE_DATA":
        filename = args.get("filename", "")
        df, err = _get_df(filename)
        if err:
            return err
        try:
            return get_sample_data(df)
        except Exception as e:
            return f"ERROR: {e}"

    if action_type == "COMPARE_TARGET":
        filename       = args.get("filename", "")
        actual_column  = args.get("actual", "")
        target_column  = args.get("target", "")

        if not actual_column or not target_column:
            return "ERROR: COMPARE_TARGET requires 'actual' and 'target' column names."

        df, err = _get_df(filename)
        if err:
            return err
        try:
            return compare_target_vs_actual(df, actual_column, target_column)
        except Exception as e:
            return f"ERROR: {e}"

    if action_type == "TOP_PERFORMERS":
        filename         = args.get("filename", "")
        category_column  = args.get("category", "")
        value_column     = args.get("value", "")
        top_n            = int(args.get("top_n", 5))

        if not category_column or not value_column:
            return "ERROR: TOP_PERFORMERS requires 'category' and 'value' column names."

        df, err = _get_df(filename)
        if err:
            return err
        try:
            return get_top_performers(df, category_column, value_column, top_n)
        except Exception as e:
            return f"ERROR: {e}"

    return f"ERROR: Unknown tool '{action_type}'"



while True:

    user_input = input("\nYou: ")

    if user_input.lower() == "exit":
        break

    messages.append({
        "role": "user",
        "content": user_input
    })

    max_iterations = 8
    for step in range(max_iterations):

        print(f"\n================ STEP {step + 1} ================")

        try:
            assistant_output = call_llm(messages)
        except Exception as e:
            print("\n[LLM ERROR]")
            print(str(e))
            break

        print("\n[LLM OUTPUT]")
        print(assistant_output)

        messages.append({
            "role": "assistant",
            "content": assistant_output
        })

        action_type, action_args = parse_action(assistant_output)

        if not action_type:
            print("\nAssistant:")
            print(assistant_output)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            break

        print(f"\n[TOOL EXECUTION] {action_type}({action_args})")

        tool_result = execute_tool(action_type, action_args or {})

        observation = f"""
OBSERVATION:

{tool_result}

Tool execution completed.

IMPORTANT:
- If enough information exists: generate FINAL ANSWER immediately
- Do NOT call tools again unnecessarily
- Use ONLY the observation above
- NEVER hallucinate
"""

        print("\n[OBSERVATION]")
        print(observation)

        messages.append({
            "role": "user",
            "content": observation
        })

    else:
        print("\n[WARNING] Max iterations reached.")