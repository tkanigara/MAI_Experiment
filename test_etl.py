from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import os
from ETL_Pipeline.transform.kpi import (
    KPI_PROCESSOR
)
from ETL_Pipeline.transform.read_file import ReadCsv
from ETL_Pipeline.transform.followers_growth import (
    FOLLOWERS_GROWTH_PROCESSOR,
    FollowersGrowthMetricProcessor,
    GSpreadReader,
    GSpreadWriter
)
from ETL_Pipeline.transform.engagement_performance import (
    ENGAGEMENT_PERFORMANCE_PROCESSOR
)

from ETL_Pipeline.transform.overview import (
    OVERVIEW_PROCESSOR
)
#======== GOOGLE SPREADSHEET CONFIGURATION =========
#==================================================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(
    BASE_DIR / ".env"
)
DATA_FOLDER = (
    BASE_DIR
    / os.getenv("DATA_FOLDER", "data").strip()
)
credential_file = os.getenv(
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "optimum-essence-497706-i6-1c879e7ef3bd.json"
).strip()
credential_path = Path(credential_file)
if not credential_path.is_absolute():
    credential_path = BASE_DIR / credential_path
CREDENTIAL_PATH = str(credential_path)
SPREADSHEET_ID = os.getenv(
    "INTERMEDIATE_SPREADSHEET_ID"
)


def dedupe_sheet_rows(df, keys):
    if df.empty:
        return df

    available_keys = [
        key for key in keys
        if key in df.columns
    ]
    if not available_keys:
        return df

    normalized = df.copy()
    for key in available_keys:
        if key in ("scrapped_at", "date", "timestamp"):
            parsed = pd.to_datetime(
                normalized[key],
                errors="coerce"
            )
            normalized[key] = parsed.dt.strftime(
                "%Y-%m-%d"
            ).fillna(normalized[key].astype(str))
        else:
            normalized[key] = normalized[key].astype(str)

    dedupe_key = normalized[available_keys].agg(
        "\x1f".join,
        axis=1
    )
    return (
        df.assign(_dedupe_key=dedupe_key)
        .drop_duplicates("_dedupe_key", keep="last")
        .drop(columns=["_dedupe_key"])
    )

#========= GOOGLE SHEETS ACTION ============
#===========================================
sheet_reader = GSpreadReader(
    credentials_path=CREDENTIAL_PATH,
    spreadsheet_id=SPREADSHEET_ID
)

writer = GSpreadWriter(
    credentials_path=CREDENTIAL_PATH,
    spreadsheet_id=SPREADSHEET_ID
)

#======= SEQUENTIAL ETL PROCESS ===========
#==========================================
for client_dir in DATA_FOLDER.iterdir():
    if not client_dir.is_dir():
        continue
    client_name = client_dir.name

    print("\n==============================")
    print(f"Processing Client: {client_name}")
    print("==============================")

    for platform_dir in client_dir.iterdir():
        if not platform_dir.is_dir():
            continue

        has_raw_files = any(platform_dir.glob("*_account_raw*.csv")) or any(
            platform_dir.glob("*_media_raw*.csv")
        )
        if not has_raw_files:
            continue

        platform = platform_dir.name
        print(f"\nPlatform: {platform}")

        account_folder = (
            platform_dir
        )
        media_folder = (
            platform_dir
        )

        #=========== READING FILE SECTION =========
        account_reader = ReadCsv(
            folder_path=account_folder,
            platform=platform,
            data_kind="account",
            client_name=client_name
        )

        account_files = (
            account_reader.read_all()
        )

        account_df = (
            pd.concat(
                account_files,
                ignore_index=True
            )
            if account_files
            else pd.DataFrame()
        )

        media_reader = ReadCsv(
            folder_path=media_folder,
            platform=platform,
            data_kind="media",
            client_name=client_name
        )

        media_files = (
            media_reader.read_all()
        )

        media_df = (
            pd.concat(
                media_files,
                ignore_index=True
            )
            if media_files
            else pd.DataFrame()
        )

        if account_df.empty and media_df.empty:
            print(
                f"Skip {client_name}/{platform} "
                f"(no data)"
            )

            continue

        #=========== FOLLOWERS GROWTH SECTION ===========
        processor_cls = (
            FOLLOWERS_GROWTH_PROCESSOR.get(
                platform.lower()
            )
        )

        if not processor_cls:
            print(
                f"[FollowersGrowth] "
                f"Processor not available "
                f"for platform '{platform}'"
            )
            continue

        followers_growth_processor = (
            processor_cls(account_df)
        )

        current_df = (
            followers_growth_processor.run()
        )

        if current_df.empty:
            print(
                "[FollowersGrowth] Empty result"
            )
            continue

        print(
            f"[FollowersGrowth] Current rows: "
            f"{len(current_df)}"
        )

        historical_df = (
            sheet_reader.read(
                "foll_growth"
            )
        )

        print(
            f"[Sheet] Historical rows: "
            f"{len(historical_df)}"
        )

        growth_processor = (
            FollowersGrowthMetricProcessor(
                current_df=current_df,
                historical_df=historical_df
            )
        )

        final_df = (
            growth_processor.run()
        )

        if final_df.empty:
            print(
                "[FollowersGrowth] Empty final result"
            )
            continue

        print(
            f"[FollowersGrowth] Final rows: "
            f"{len(final_df)}"
        )

        print(
            final_df.head()
        )
        writer.write(
            df=final_df,
            sheet_name="foll_growth",
            mode="upsert",
            dedupe_keys=[
                "client_id",
                "platform",
                "year",
                "month",
                "metric",
            ],
        )

        #================ ENGAGEMENT PERFORMANCE SECTION =============
        engagement_processor_cls = (
            ENGAGEMENT_PERFORMANCE_PROCESSOR.get(
                platform.lower()
            )
        )
        if not engagement_processor_cls:
            print(
                f"[EngagementPerformance] "
                f"Processor not available "
                f"for platform '{platform}'"
            )

        engagement_processor = (
            engagement_processor_cls(
                media_df=media_df,
                client_name=client_name
            )
        )
        current_engagement_df = (
            engagement_processor.run()
        )

        if current_engagement_df.empty:

            print(
                "[EngagementPerformance] Empty result"
            )
        engagement_processor = (
            engagement_processor_cls(
                media_df=media_df,
                client_name=client_name
            )
        )

        final_engagement_df = (
            engagement_processor.run()
        )

        print(
            f"[EngagementPerformance] Final rows: "
            f"{len(final_engagement_df)}"
        )

        print(
            final_engagement_df.head()
        )

        writer.write(
            df=final_engagement_df,
            sheet_name="engagement_performance",
            mode="upsert",
            dedupe_keys=[
                "client_id",
                "platform",
                "year",
                "month",
                "metric",
            ],
        )

        #================ OVERVIEW SECTION =============
        overview_cls = (
            OVERVIEW_PROCESSOR.get(
                platform.lower()
            )
        )

        if not overview_cls:
            print(
                f"[Overview] "
                f"Processor not available "
                f"for platform '{platform}'"
            )

        else:
            followers_sheet = (
                sheet_reader.read(
                    "foll_growth"
                )
            )
            followers_sheet = dedupe_sheet_rows(
                followers_sheet,
                [
                    "client_id",
                    "platform",
                    "year",
                    "month",
                    "metric",
                ],
            )

            engagement_sheet = (
                sheet_reader.read(
                    "engagement_performance"
                )
            )
            engagement_sheet = dedupe_sheet_rows(
                engagement_sheet,
                [
                    "client_id",
                    "platform",
                    "year",
                    "month",
                    "metric",
                ],
            )

            followers_sheet = followers_sheet[
                followers_sheet["client_id"]
                == client_name
            ]

            engagement_sheet = engagement_sheet[
                engagement_sheet["client_id"]
                == client_name
            ]

            overview_processor = (
                overview_cls(
                    followers_df=followers_sheet,
                    engagement_df=engagement_sheet,
                    client_name=client_name,
                    platform=platform
                )
            )

            overview_df = (
                overview_processor.run()
            )

            if overview_df.empty:
                print(
                    "[Overview] Empty result"
                )

            else:
                print(
                    f"[Overview] Final rows: "
                    f"{len(overview_df)}"
                )
                print(
                    overview_df.head()
                )

                writer.write(
                    df=overview_df,
                    sheet_name="content_overview",
                    mode="upsert",
                    dedupe_keys=[
                        "client",
                        "platform",
                        "scrapped_at",
                        "category",
                        "metric",
                    ],
                )

                        #================ KPI SECTION =============
        kpi_cls = (
            KPI_PROCESSOR.get(
                platform.lower()
            )
        )

        if not kpi_cls:

            print(
                f"[KPI] "
                f"Processor not available "
                f"for platform '{platform}'"
            )

        else:

            overview_sheet = (
                sheet_reader.read(
                    "content_overview"
                )
            )
            overview_sheet = dedupe_sheet_rows(
                overview_sheet,
                [
                    "client",
                    "platform",
                    "scrapped_at",
                    "category",
                    "metric",
                ],
            )

            followers_sheet = (
                sheet_reader.read(
                    "foll_growth"
                )
            )
            followers_sheet = dedupe_sheet_rows(
                followers_sheet,
                [
                    "client_id",
                    "platform",
                    "year",
                    "month",
                    "metric",
                ],
            )

            engagement_sheet = (
                sheet_reader.read(
                    "engagement_performance"
                )
            )
            engagement_sheet = dedupe_sheet_rows(
                engagement_sheet,
                [
                    "client_id",
                    "platform",
                    "year",
                    "month",
                    "metric",
                ],
            )

            target_sheet = (
                sheet_reader.read(
                    "master_target"
                )
            )

            overview_sheet = overview_sheet[
                overview_sheet["client"]
                == client_name
            ]

            followers_sheet = followers_sheet[
                followers_sheet["client_id"]
                == client_name
            ]

            engagement_sheet = engagement_sheet[
                engagement_sheet["client_id"]
                == client_name
            ]

            target_sheet = pd.DataFrame()
            kpi_processor = (
                kpi_cls(
                    overview_df=overview_sheet,
                    followers_df=followers_sheet,
                    engagement_df=engagement_sheet,
                    target_df=target_sheet,
                    client_name=client_name,
                    platform=platform
                )
            )

            kpi_df = (
                kpi_processor.run()
            )

            if kpi_df.empty:

                print(
                    "[KPI] Empty result"
                )

            else:

                print(
                    f"[KPI] Final rows: "
                    f"{len(kpi_df)}"
                )

                print(
                    kpi_df.head()
                )

                writer.write(
                    df=kpi_df,
                    sheet_name="kpi",
                    mode="upsert",
                    dedupe_keys=[
                        "client",
                        "platform",
                        "scrapped_at",
                        "metric",
                    ],
                )

print("\n=================================")
print("ETL FINISHED")
print("=================================")
