def router(request: dict) -> str:

    analysis_type = request.get("analysis_type")

    if not analysis_type:
        raise ValueError(
            "Missing required field: analysis_type"
        )

    if analysis_type == "creative":
        return "creative"

    if analysis_type == "adset":
        return "adset"

    raise ValueError(
        f"Unsupported analysis_type: {analysis_type}"
    )