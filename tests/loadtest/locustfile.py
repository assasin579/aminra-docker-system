"""
AMINRA Load Test
Usage: locust -f tests/loadtest/locustfile.py --host=http://localhost:8100
"""
from locust import HttpUser, task, between, tag


class AminraUser(HttpUser):
    wait_time = between(1, 3)

    @tag("health")
    @task(10)
    def health_check(self):
        self.client.get("/health")

    @tag("health")
    @task(5)
    def stats(self):
        self.client.get("/stats")

    @tag("chat")
    @task(3)
    def chat_simple(self):
        self.client.post("/chat", json={
            "question": "Halal la gi?",
            "top_k": 3
        })

    @tag("chat")
    @task(2)
    def chat_complex(self):
        self.client.post("/chat", json={
            "question": "Quy trinh xin chung nhan Halal cho doanh nghiep san xuat thuc pham gom nhung buoc nao?",
            "top_k": 5
        })

    @tag("auth")
    @task(2)
    def login(self):
        self.client.post("/auth/login", json={
            "email": "admin@aminra.com",
            "password": "admin123!"
        })

    @tag("topics")
    @task(3)
    def topics(self):
        self.client.get("/topics")
