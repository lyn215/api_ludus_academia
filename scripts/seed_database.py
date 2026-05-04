#!/usr/bin/env python3
"""
scripts/seed_database.py
Carga bancos de preguntas desde un JSON a Supabase (PostgreSQL).

Uso:
    python scripts/seed_database.py [ruta_json]

    Si no se especifica ruta_json se usa /home/claude/seed_preguntas_inicial.json.

Variables de entorno (alternativa a hardcodear):
    DATABASE_URL  — connection string de PostgreSQL
"""
import asyncio
import json
import os
import sys
import traceback

import asyncpg

# ── Colores ANSI ───────────────────────────────────────────────────────────────

_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_DIM    = "\033[2m"


def ok(msg: str)    -> None: print(f"  {_GREEN}✅{_RESET} {msg}")
def err(msg: str)   -> None: print(f"  {_RED}✗  {_RESET} {msg}", file=sys.stderr)
def info(msg: str)  -> None: print(f"{_CYAN}ℹ  {_RESET} {msg}")
def warn(msg: str)  -> None: print(f"{_YELLOW}⚠  {_RESET} {msg}")
def header(msg: str)-> None: print(f"\n{_BOLD}{_CYAN}{msg}{_RESET}")


# ── Constante de conexión ─────────────────────────────────────────────────────

_DEFAULT_DATABASE_URL = (
    "postgresql://postgres:Dez6XRXwOiHFHo7A"
    "@db.bbyhevcprqxntsaknwul.supabase.co:5432/postgres"
)


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)


# ── Lógica principal ──────────────────────────────────────────────────────────

async def seed_database(json_path: str) -> None:
    database_url = get_database_url()

    # ── Leer JSON ──────────────────────────────────────────────────────────────
    info(f"Leyendo {json_path} …")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    bancos = data.get("bancos", [])
    if not bancos:
        warn("El JSON no contiene ningún banco en la clave 'bancos'. Nada que insertar.")
        return

    info(f"Bancos encontrados en el JSON: {len(bancos)}")

    # ── Conectar ───────────────────────────────────────────────────────────────
    info("Conectando a Supabase …")
    try:
        conn = await asyncpg.connect(database_url)
    except Exception as exc:
        err(f"No se pudo conectar a la base de datos: {exc}")
        sys.exit(1)

    info("Conexión establecida.\n")

    # ── Contadores globales ───────────────────────────────────────────────────
    bancos_ok       = 0
    preguntas_ok    = 0
    opciones_ok     = 0
    bancos_fallidos = 0

    try:
        for banco_data in bancos:
            nombre_banco = banco_data.get("nombre", "(sin nombre)")
            header(f"Banco: {nombre_banco}")

            try:
                async with conn.transaction():
                    # ── 1. Insertar banco ──────────────────────────────────────
                    banco_id = await conn.fetchval(
                        """
                        INSERT INTO bancos_preguntas
                            (nombre, descripcion, materia, nivel_grado, es_oficial)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING id
                        """,
                        banco_data.get("nombre"),
                        banco_data.get("descripcion"),
                        banco_data.get("materia"),
                        banco_data.get("nivel_grado"),
                        banco_data.get("es_oficial", False),
                    )

                    ok(f"{_BOLD}Banco creado:{_RESET} {nombre_banco} {_DIM}({banco_id}){_RESET}")
                    bancos_ok += 1

                    preguntas = banco_data.get("preguntas", [])
                    materia_banco = banco_data.get("materia")

                    for idx, pregunta_data in enumerate(preguntas, start=1):
                        # ── 2. Insertar pregunta ───────────────────────────────
                        pregunta_id = await conn.fetchval(
                            """
                            INSERT INTO preguntas
                                (texto_pregunta, tipo_pregunta, materia, dificultad,
                                 pista_texto, explicacion)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            RETURNING id
                            """,
                            pregunta_data["texto_pregunta"],
                            pregunta_data["tipo_pregunta"],
                            materia_banco,                       # heredada del banco
                            pregunta_data.get("dificultad"),
                            pregunta_data.get("pista_texto"),
                            pregunta_data.get("explicacion"),
                        )

                        # ── 3. Insertar opciones ───────────────────────────────
                        opciones = pregunta_data.get("opciones", [])
                        for opcion in opciones:
                            await conn.execute(
                                """
                                INSERT INTO opciones_respuesta
                                    (pregunta_id, texto_opcion, es_correcta, orden)
                                VALUES ($1, $2, $3, $4)
                                """,
                                pregunta_id,
                                opcion["texto_opcion"],
                                opcion.get("es_correcta", False),
                                opcion.get("orden"),
                            )
                            opciones_ok += 1

                        # ── 4. Asignar pregunta al banco ───────────────────────
                        await conn.execute(
                            """
                            INSERT INTO banco_pregunta_asignacion
                                (banco_id, pregunta_id, orden_en_banco)
                            VALUES ($1, $2, $3)
                            """,
                            banco_id,
                            pregunta_id,
                            idx,
                        )

                        texto_corto = pregunta_data["texto_pregunta"][:60]
                        if len(pregunta_data["texto_pregunta"]) > 60:
                            texto_corto += "…"
                        ok(f"  Pregunta {idx:>2}: {texto_corto}")
                        preguntas_ok += 1

            except Exception as exc:
                bancos_fallidos += 1
                err(f"Falló el banco '{nombre_banco}' — se hizo rollback.")
                err(f"Detalle: {exc}")
                if os.environ.get("SEED_VERBOSE"):
                    traceback.print_exc()

    finally:
        await conn.close()

    # ── Resumen ────────────────────────────────────────────────────────────────
    print()
    if bancos_fallidos == 0:
        print(f"{_BOLD}{_GREEN}🎉 Seed completado exitosamente!{_RESET}")
    else:
        print(f"{_BOLD}{_YELLOW}⚠  Seed finalizado con {bancos_fallidos} banco(s) fallido(s).{_RESET}")

    print(f"\n{_BOLD}📊 Resumen:{_RESET}")
    print(f"   - Bancos insertados  : {bancos_ok}")
    print(f"   - Preguntas insertadas: {preguntas_ok}")
    print(f"   - Opciones insertadas : {opciones_ok}")
    if bancos_fallidos:
        print(f"   {_RED}- Bancos fallidos    : {bancos_fallidos}{_RESET}")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    default_path = "/home/claude/seed_preguntas_inicial.json"
    json_path = sys.argv[1] if len(sys.argv) > 1 else default_path

    if not os.path.isfile(json_path):
        print(f"{_RED}Error: no se encontró el archivo JSON: {json_path}{_RESET}",
              file=sys.stderr)
        print("Uso: python scripts/seed_database.py [ruta_json]", file=sys.stderr)
        sys.exit(1)

    asyncio.run(seed_database(json_path))


if __name__ == "__main__":
    main()
