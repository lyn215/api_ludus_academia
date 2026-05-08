-- =============================================================================
-- Migración 003: tabla grupos vinculada a usuarios (docentes)
-- =============================================================================

CREATE TABLE IF NOT EXISTS grupos (
    id             UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
    nombre_grupo   TEXT         NOT NULL,
    docente_id     UUID         NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    codigo_acceso  TEXT         UNIQUE,
    activo         BOOLEAN      DEFAULT true,
    created_at     TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_grupos_docente_id ON grupos(docente_id);
