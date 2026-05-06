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

    async def query(
        self,
        table: str,
        select: str = "*",
        filters: dict = None,
        in_filters: dict = None,
        order: str = None,
    ) -> list:
        url = f"{self.url}/rest/v1/{table}?select={select}"
        if filters:
            for k, v in filters.items():
                url += f"&{k}=eq.{v}"
        if in_filters:
            for k, vals in in_filters.items():
                url += f"&{k}=in.({','.join(str(v) for v in vals)})"
        if order:
            url += f"&order={order}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def get_one(self, table: str, pk_col: str, pk_val, select: str = "*") -> dict | None:
        rows = await self.query(table, select=select, filters={pk_col: pk_val})
        return rows[0] if rows else None

    async def get_by_match(self, table: str, match: dict, select: str = "*") -> list:
        url = f"{self.url}/rest/v1/{table}?select={select}"
        for k, v in match.items():
            url += f"&{k}=eq.{v}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def insert(self, table: str, data: dict) -> dict:
        url = f"{self.url}/rest/v1/{table}"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=data)
            if response.status_code >= 400:
                print(f"Supabase error {response.status_code} [{table}]: {response.text}", flush=True)
            response.raise_for_status()
            result = response.json()
            return result[0] if isinstance(result, list) else result

    async def update(self, table: str, data: dict, filters: dict) -> list:
        params = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
        url = f"{self.url}/rest/v1/{table}?{params}"
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()

    async def patch(self, table: str, filters: dict, payload: dict) -> list:
        params = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
        url = f"{self.url}/rest/v1/{table}?{params}"
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def delete(self, table: str, match: dict) -> None:
        params = "&".join(f"{k}=eq.{v}" for k, v in match.items())
        url = f"{self.url}/rest/v1/{table}?{params}"
        async with httpx.AsyncClient() as client:
            response = await client.delete(url, headers=self.headers)
            response.raise_for_status()


supabase_http = SupabaseDirectClient()


def get_supabase() -> SupabaseDirectClient:
    return supabase_http
