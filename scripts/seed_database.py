#!/usr/bin/env python3
"""
scripts/seed_database.py
Carga bancos de preguntas en Supabase usando la REST API (HTTPS port 443).
Funciona en GitHub Codespaces y cualquier entorno donde el puerto 5432 esté bloqueado.

Uso:
    python scripts/seed_database.py [ruta_json]

    Si no se especifica ruta_json se usa scripts/seed_preguntas_inicial.json.

Variables de entorno (o en archivo .env en la raíz del proyecto):
    SUPABASE_URL              — https://xyzxyz.supabase.co
    SUPABASE_SERVICE_ROLE_KEY — clave service_role (Project Settings → API)
"""
import json
import os
import sys

import httpx
from dotenv import load_dotenv

# ── Colores ANSI ──────────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_DIM    = "\033[2m"


def ok(msg: str)     -> None: print(f"  {_GREEN}✅{_RESET} {msg}")
def err(msg: str)    -> None: print(f"  {_RED}✗  {_RESET} {msg}", file=sys.stderr)
def info(msg: str)   -> None: print(f"{_CYAN}ℹ  {_RESET} {msg}")
def warn(msg: str)   -> None: print(f"{_YELLOW}⚠  {_RESET} {msg}")
def header(msg: str) -> None: print(f"\n{_BOLD}{_CYAN}{msg}{_RESET}")


# ── Credenciales ──────────────────────────────────────────────────────────────

_PROJECT_REF    = "bbyhevcprqxntsaknwul"
_SUPABASE_URL   = f"https://{_PROJECT_REF}.supabase.co"


def _get_credentials() -> tuple[str, str]:
    """Devuelve (supabase_url, service_role_key). Lee .env si existe."""
    load_dotenv()
    url = os.environ.get("SUPABASE_URL", _SUPABASE_URL)
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    return url, key


# ── Cliente HTTP ──────────────────────────────────────────────────────────────

def _make_client(url: str, key: str) -> httpx.Client:
    return httpx.Client(
        base_url=f"{url}/rest/v1",
        headers={
            "apikey":        key,
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
            "Prefer":        "return=representation",
        },
        timeout=30,
    )


def _insert_one(client: httpx.Client, table: str, payload: dict) -> dict:
    """Inserta una fila y devuelve el registro creado (con id generado por Supabase)."""
    resp = client.post(f"/{table}", json=payload)
    if resp.status_code not in (200, 201):
        raise RuntimeError(
            f"POST /{table} → {resp.status_code}\n{resp.text}"
        )
    rows = resp.json()
    return rows[0] if isinstance(rows, list) else rows


# ── Lógica principal ──────────────────────────────────────────────────────────

def seed_database(json_path: str) -> None:
    supabase_url, service_key = _get_credentials()

    if not service_key:
        err("No se encontró SUPABASE_SERVICE_ROLE_KEY.")
        err("Agrégala al archivo .env o como variable de entorno:")
        err("  SUPABASE_SERVICE_ROLE_KEY=eyJ...")
        err("  (Project Settings → API → service_role en supabase.com)")
        sys.exit(1)

    # ── Leer JSON ──────────────────────────────────────────────────────────────
    info(f"Leyendo {json_path} …")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    bancos = data.get("bancos", [])
    if not bancos:
        warn("El JSON no contiene ningún banco en la clave 'bancos'.")
        return

    info(f"Bancos encontrados en el JSON: {len(bancos)}")
    info(f"Conectando a {supabase_url} vía REST API …\n")

    bancos_ok    = 0
    preguntas_ok = 0
    opciones_ok  = 0
    fallidos     = 0

    with _make_client(supabase_url, service_key) as client:

        # Verificar conectividad antes de empezar
        try:
            probe = client.get("/bancos_preguntas?limit=0")
            if probe.status_code == 401:
                err("Error 401 — service_role_key inválida o incorrecta.")
                sys.exit(1)
            if probe.status_code not in (200, 206):
                err(f"Error al verificar conexión: {probe.status_code} {probe.text}")
                sys.exit(1)
        except httpx.ConnectError as exc:
            err(f"No se pudo conectar a {supabase_url}: {exc}")
            sys.exit(1)

        info("Conexión verificada ✓\n")

        for banco_data in bancos:
            nombre_banco  = banco_data.get("nombre", "(sin nombre)")
            materia_banco = banco_data.get("materia")
            header(f"Banco: {nombre_banco}")

            try:
                # ── 1. Insertar banco ──────────────────────────────────────────
                banco_row = _insert_one(client, "bancos_preguntas", {
                    "nombre":      banco_data.get("nombre"),
                    "descripcion": banco_data.get("descripcion"),
                    "materia":     materia_banco,
                    "nivel_grado": banco_data.get("nivel_grado"),
                    "es_oficial":  banco_data.get("es_oficial", False),
                })
                banco_id = banco_row["id"]
                ok(f"{_BOLD}Banco creado:{_RESET} {nombre_banco} {_DIM}({banco_id}){_RESET}")
                bancos_ok += 1

                # ── 2. Preguntas ───────────────────────────────────────────────
                for idx, p in enumerate(banco_data.get("preguntas", []), start=1):
                    pregunta_row = _insert_one(client, "preguntas", {
                        "texto_pregunta": p["texto_pregunta"],
                        "tipo_pregunta":  p["tipo_pregunta"],
                        "materia":        materia_banco,      # heredada del banco
                        "dificultad":     p.get("dificultad"),
                        "pista_texto":    p.get("pista_texto"),
                        "explicacion":    p.get("explicacion"),
                    })
                    pregunta_id = pregunta_row["id"]

                    # ── 3. Opciones ────────────────────────────────────────────
                    for opcion in p.get("opciones", []):
                        _insert_one(client, "opciones_respuesta", {
                            "pregunta_id":  pregunta_id,
                            "texto_opcion": opcion["texto_opcion"],
                            "es_correcta":  opcion.get("es_correcta", False),
                            "orden":        opcion.get("orden"),
                        })
                        opciones_ok += 1

                    # ── 4. Asignación banco ↔ pregunta ─────────────────────────
                    _insert_one(client, "banco_pregunta_asignacion", {
                        "banco_id":      banco_id,
                        "pregunta_id":   pregunta_id,
                        "orden_en_banco": idx,
                    })

                    texto_corto = p["texto_pregunta"][:60]
                    if len(p["texto_pregunta"]) > 60:
                        texto_corto += "…"
                    ok(f"  Pregunta {idx:>2}: {texto_corto}")
                    preguntas_ok += 1

            except Exception as exc:
                fallidos += 1
                err(f"Falló el banco '{nombre_banco}'.")
                err(f"Detalle: {exc}")

    # ── Resumen ────────────────────────────────────────────────────────────────
    print()
    if fallidos == 0:
        print(f"{_BOLD}{_GREEN}🎉 Seed completado exitosamente!{_RESET}")
    else:
        print(f"{_BOLD}{_YELLOW}⚠  Seed finalizado con {fallidos} banco(s) fallido(s).{_RESET}")

    print(f"\n{_BOLD}📊 Resumen:{_RESET}")
    print(f"   - Bancos insertados   : {bancos_ok}")
    print(f"   - Preguntas insertadas: {preguntas_ok}")
    print(f"   - Opciones insertadas : {opciones_ok}")
    if fallidos:
        print(f"   {_RED}- Bancos fallidos    : {fallidos}{_RESET}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    default_path = os.path.join(
        os.path.dirname(__file__), "seed_preguntas_inicial.json"
    )
    json_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    if not os.path.isfile(json_path):
        err(f"No se encontró el archivo JSON: {json_path}")
        print("Uso: python scripts/seed_database.py [ruta_json]", file=sys.stderr)
        sys.exit(1)

    seed_database(json_path)


if __name__ == "__main__":
    main()
