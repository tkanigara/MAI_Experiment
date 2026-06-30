import json
from ETL_Pipeline.extract.scraper import FanpageScraper

def main():
    scraper = FanpageScraper()
    result = scraper.scrape()
    print(
        json.dumps(
            result,
            indent=4,
            ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()