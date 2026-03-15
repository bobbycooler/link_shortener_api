import random
from locust import HttpUser, task, between


class LinkShortenerUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        import uuid
        username = f"user_{uuid.uuid4()}@example.com"
        password = "string"

        self.created_links = []

        reg_payload = {
            "email": username,
            "password": password,
            "is_active": True,
            "is_superuser": False,
            "is_verified": False,
            "username": username
        }

        with self.client.post("/auth/register",
                              json=reg_payload,
                              name="Register",
                              catch_response=True) as reg_res:
            if reg_res.status_code != 201:
                reg_res.failure(f"Reg failed: {reg_res.text}")
                return

        login_payload = {
            "username": username,
            "password": password
        }

        with self.client.post("/auth/jwt/login",
                              data=login_payload,
                              name="Login",
                              catch_response=True) as response:
            if response.status_code == 200:
                token = response.json().get("access_token")
                self.client.headers.update(
                    {"Authorization": f"Bearer {token}"})
            else:
                response.failure(f"""Login failed:
                                 {response.status_code} - {response.text}""")

    @task(3)
    def shorten_url(self):
        long_url = f"https://example.com{random.randint(1, 10000)}"
        payload = {
            "long_url": long_url,
            "custom_alias": None,
            "expires_at": None
        }
        res = self.client.post("/links/shorten", json=payload, name="/shorten")
        if res.status_code == 201:
            short_url = res.json()["short_url"]
            self.created_links.append((short_url, long_url))

    @task(10)
    def redirect(self):
        if not self.created_links:
            return
        code = random.choice(self.created_links)[0]
        self.client.get(f"/links/{code}",
                        name="/[short_code] (Redirect)",
                        allow_redirects=False)

    @task(2)
    def get_my_links(self):
        self.client.get("/links/my?limit=10", name="/my")

    @task(1)
    def delete_some_link(self):
        if self.created_links:
            code = self.created_links.pop()[0]
            self.client.delete(f"/links/{code}", name="/[short_code] (Delete)")

    @task(5)
    def search_link_optimized(self):
        if not self.created_links:
            return

        _, target_long_url = random.choice(self.created_links)

        params = {"original_url": target_long_url}
        self.client.get("/links/search",
                        params=params,
                        name="/links/search (Found)")

    @task(1)
    def update_link_test(self):
        if self.created_links:
            old_short_code, long_url = self.created_links.pop()
            new_short_code = f"new_{random.randint(1, 99999)}"

            payload = {"new_short_code": new_short_code,
                       "long_url": long_url}
            with self.client.put(f"/links/{old_short_code}",
                                 json=payload,
                                 name="/[short_code] (Update)",
                                 catch_response=True) as res:
                if res.status_code == 200:
                    self.created_links.append((new_short_code, long_url))
