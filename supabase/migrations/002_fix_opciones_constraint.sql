-- =============================================================================
-- Migración 002: eliminar check_al_menos_una_correcta
--
-- El CHECK constraint que valida "al menos una opción correcta por pregunta"
-- no funciona en PostgreSQL cuando la función hace SELECT sobre la misma tabla:
-- la fila que se está insertando no es visible para la función STABLE, por lo
-- que el constraint falla incluso al insertar la opción correcta.
-- La validación se delega a la capa de aplicación (FastAPI).
-- =============================================================================

ALTER TABLE opciones_respuesta
    DROP CONSTRAINT IF EXISTS check_al_menos_una_correcta;

DROP FUNCTION IF EXISTS check_tiene_opcion_correcta(UUID);
