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
        """Consulta filtrando por múltiples parámetros con coincidencia exacta (eq.)"""
        url = f"{self.url}/rest/v1/{table}?select={select}"
        for k, v in match.items():
            url += f"&{k}=eq.{v}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def insert(self, table: str, data: dict):
        async with httpx.AsyncClient() as client:
            endpoint = f"{self.url}/rest/v1/{table}"
            # 'return=minimal' evita que Supabase devuelva todo el objeto insertado, ahorrando ancho de banda
            headers = {**self.headers, "Prefer": "return=minimal"}
            response = await client.post(endpoint, headers=headers, json=data)
            response.raise_for_status()
            return True

    async def delete(self, table: str, match: dict):
        async with httpx.AsyncClient() as client:
            # PostgREST usa la sintaxis ?columna=eq.valor para filtrar
            query_params = "&".join([f"{k}=eq.{v}" for k, v in match.items()])
            endpoint = f"{self.url}/rest/v1/{table}?{query_params}"
            response = await client.delete(endpoint, headers=self.headers)
            response.raise_for_status()
            return True

    async def update(self, table: str, data: dict, filters: dict) -> list:
        params = "&".join(f"{k}=eq.{v}" for k, v in filters.items())
        url = f"{self.url}/rest/v1/{table}?{params}"
        async with httpx.AsyncClient() as client:
            response = await client.patch(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()


supabase_http = SupabaseDirectClient()


def get_supabase() -> SupabaseDirectClient:
    return supabase_http
