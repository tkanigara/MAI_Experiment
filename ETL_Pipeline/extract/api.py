import requests
from dotenv import load_dotenv
import os
load_dotenv ()

BASE_URL = os.getenv("BASE_URL")
API = os.getenv("FANPAGE_KARMA")

HEADERS = {
    "Authorization": f"Bearer {API}"
}

class FanpageAPI:

    def __init__(self):
        self.base_url = BASE_URL
        self.headers = HEADERS


    def request(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint}"
        print(f"[GET] {url}")
        response = requests.get(
            url,
            headers=self.headers,
            params=params
        )

        response.raise_for_status()
        return response.json()


    def get_profiles(self):
        return self.request(
            "profiles/connected"
        )


    def get_endpoint(
        self,
        network,
        profile_id,
        endpoint,
        params=None
    ):

        url = f"{network}/{profile_id}/{endpoint}"
        return self.request(
            url,
            params=params
        )