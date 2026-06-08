from tools.retrieve import get_data


TOOLS = [
    get_data,
]

TOOLS_BY_NAME = {
    tool.name: tool
    for tool in TOOLS
}
