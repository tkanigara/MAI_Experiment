from api import FanpageAPI
from endpoints import NETWORK_ENDPOINTS


class FanpageScraper:

    def __init__(self):
        self.api = FanpageAPI()
        self.result = {}

    def scrape(self):

        response = self.api.get_profiles()

        # Validasi response
        if "profiles" not in response:
            raise ValueError("Response tidak memiliki key 'profiles'")

        profiles = response["profiles"]

        for profile in profiles:

            network = profile["network"]
            profile_id = profile["profile_id"]
            profile_name = profile["profile_name"]

            # Buat kategori social media jika belum ada
            if network not in self.result:
                self.result[network] = {}

            # Gunakan profile_id sebagai key (lebih aman)
            self.result[network][profile_id] = {
                "profile_name": profile_name
            }

            endpoints = NETWORK_ENDPOINTS.get(network, [])

            for endpoint in endpoints:

                print(
                    f"[{network}] {profile_name} -> {endpoint}"
                )

                data = self.api.get_endpoint(
                    network=network,
                    profile_id=profile_id,
                    endpoint=endpoint
                )

                endpoint_key = endpoint.replace("/", "_")

                self.result[network][profile_id][endpoint_key] = data

        return self.result