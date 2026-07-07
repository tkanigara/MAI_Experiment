from CentralArch.state import State

def routing(state: State):
    if not state.metadata.loaded:
        return "retrieval"

    return "end"