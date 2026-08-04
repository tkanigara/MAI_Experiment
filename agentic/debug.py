from datetime import date
import json

from CentralArch.state import (
    State,
    Request,
    MetaData,
)

from agents.all_socmed_anlysis import (
    all_socmed_performance_agent_2nd,
)


def print_metadata(state):
    print("=" * 60)
    print("METADATA")
    print("=" * 60)

    print(
        json.dumps(
            state.Metadata.model_dump(mode="json"),
            indent=4,
            default=str,
        )
    )


def print_result(state):
    print("\n")
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    print(state.summary_all_socmed.summary)


def main():

    state = State(
        request=Request(
            user_intent="Summarize all social media performance",
            client_code="mai001",
            report_date=date(2026, 6, 15),
        ),
        Metadata=MetaData(
            client_id="2ab5b765-43b9-4a49-a0ef-7d22d5b2951f",
            client_code="mai001",
            client_name="Par",

            report_period_id="95c068ba-cd5b-430d-b70b-9dc9c5156c9c",

            report_date=date(2026, 6, 15),

            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),

            instagram=True,
            facebook=False,
            tiktok=True,
            youtube=True,

            loaded=True,
        ),
    )

    print_metadata(state)

    print("\nRunning Agent...\n")

    state = all_socmed_performance_agent_2nd(state)

    print_result(state)


if __name__ == "__main__":
    main()
