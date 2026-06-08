from ETL_Pipeline.transform.transform_csv import DATA_FOLDER
import os

for root, dir, files in os.walk(DATA_FOLDER):
    print(f"Folder:{root}")
    print(f"files:{files}")