from api import FanpageAPI
from endpoints import NETWORK_ENDPOINTS
from datetime import date

class FanpageScraper:

    def __init__(self, date_from: str = None, date_to: str = None):
        self.api = FanpageAPI()
        self.result = {}
        self.date_from = date_from
        self.date_to = date_to

    def scrape(self):
        response = self.api.get_profiles()

        if "profiles" not in response:
            raise ValueError("Response tidak memiliki key 'profiles'")

        profiles = response["profiles"]

        for profile in profiles:
            network = profile["network"]
            profile_id = profile["profile_id"]
            profile_name = profile["profile_name"]

            if network not in self.result:
                self.result[network] = {}

            self.result[network][profile_id] = {
                "profile_name": profile_name
            }

            endpoints = NETWORK_ENDPOINTS.get(network, [])

            for endpoint in endpoints:
                params = {}
                if self.date_from:
                    params["date_from"] = self.date_from
                if self.date_to:
                    params["date_until"] = self.date_to

                print(f"[{network}] {profile_name} -> {endpoint} ({self.date_from} s/d {self.date_until})")

                data = self.api.get_endpoint(
                    network=network,
                    profile_id=profile_id,
                    endpoint=endpoint,
                    params=params or None
                )

                endpoint_key = endpoint.replace("/", "_")
                self.result[network][profile_id][endpoint_key] = data

        return self.result