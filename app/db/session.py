"""app/db/session.py"""
import httpx

from app.core.config import get_settings

settings = get_settings()


class SupabaseDirectClient:
    def __init__(self):
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_ANON_KEY
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    async def query(self, table: str, select: str = "*", filters: dict = None):
        async with httpx.AsyncClient() as client:
            endpoint = f"{self.url}/rest/v1/{table}?select={select}"
            if filters:
                for key, value in filters.items():
                    endpoint += f"&{key}=eq.{value}"
            response = await client.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()


supabase_http = SupabaseDirectClient()


def get_supabase():
    return supabase_http
