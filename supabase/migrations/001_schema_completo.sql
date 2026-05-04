-- =============================================================================
-- LudusAcademia — Esquema completo PostgreSQL (Supabase)
-- Migración 001: tablas base + bancos de preguntas dinámicos
-- =============================================================================

-- =============================================================================
-- PARTE 1 — EXTENSIONES
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- =============================================================================
-- PARTE 2 — USUARIOS Y AVATARES
-- =============================================================================

CREATE TABLE avatares (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre          VARCHAR(100)  NOT NULL,
    imagen_url      TEXT          NOT NULL,
    costo_puntos    INTEGER       DEFAULT 0,
    categoria       VARCHAR(50),                  -- "cabeza", "cuerpo", "accesorio"
    disponible      BOOLEAN       DEFAULT true
);

CREATE TABLE usuarios (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email            VARCHAR(255) UNIQUE NOT NULL,
    password_hash    VARCHAR(255) NOT NULL,        -- bcrypt hash via pgcrypto
    nombre_completo  VARCHAR(200) NOT NULL,
    tipo_usuario     VARCHAR(20)  NOT NULL
                         CHECK (tipo_usuario IN ('alumno', 'docente', 'padre')),
    grado            INTEGER      CHECK (grado BETWEEN 1 AND 6),  -- solo alumnos
    grupo            VARCHAR(10),                  -- "1-A"
    avatar_id        UUID         REFERENCES avatares(id) ON DELETE SET NULL,
    nivel_actual     INTEGER      DEFAULT 1,
    puntos_totales   INTEGER      DEFAULT 0,
    fecha_registro   TIMESTAMP    DEFAULT NOW(),
    ultima_sesion    TIMESTAMP,
    activo           BOOLEAN      DEFAULT true
);


-- =============================================================================
-- PARTE 3 — MAPA (CÓDICE / LUMINIÁ)
-- =============================================================================

CREATE TABLE nodos (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo             VARCHAR(50)  UNIQUE NOT NULL,   -- "nodo_01"
    nombre             VARCHAR(100) NOT NULL,
    descripcion        TEXT,
    posicion_x         FLOAT        NOT NULL,
    posicion_y         FLOAT        NOT NULL,
    tipo_nodo          VARCHAR(50)  NOT NULL,           -- "desafio", "historia", "recompensa"
    materia            VARCHAR(50),                    -- "Matemáticas", "Español", "Mixto"
    dificultad         INTEGER      CHECK (dificultad BETWEEN 1 AND 5),
    nodos_requeridos   JSONB,                          -- array de UUIDs de nodos prerequisito
    recompensa_puntos  INTEGER      DEFAULT 0,
    icono_url          TEXT,
    orden_secuencia    INTEGER,
    activo             BOOLEAN      DEFAULT true
);

CREATE TABLE progreso_mapa (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id            UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nodo_id               UUID        NOT NULL REFERENCES nodos(id)    ON DELETE CASCADE,
    estado                VARCHAR(20) DEFAULT 'bloqueado'
                              CHECK (estado IN ('bloqueado', 'disponible', 'en_progreso', 'completado')),
    intentos_realizados   INTEGER     DEFAULT 0,
    mejor_puntuacion      INTEGER     DEFAULT 0,
    fecha_completado      TIMESTAMP,
    fecha_ultimo_intento  TIMESTAMP,
    UNIQUE (usuario_id, nodo_id)
);


-- =============================================================================
-- PARTE 4 — BANCOS DE PREGUNTAS (NUEVO)
-- =============================================================================

CREATE TABLE bancos_preguntas (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nombre              VARCHAR(100) NOT NULL,
    descripcion         TEXT,
    materia             VARCHAR(50)  NOT NULL,
    nivel_grado         INTEGER      CHECK (nivel_grado BETWEEN 1 AND 6),
    activo              BOOLEAN      DEFAULT true,
    version             INTEGER      DEFAULT 1,
    fecha_creacion      TIMESTAMP    DEFAULT NOW(),
    fecha_actualizacion TIMESTAMP    DEFAULT NOW(),
    creado_por          UUID         REFERENCES usuarios(id) ON DELETE SET NULL,
    es_oficial          BOOLEAN      DEFAULT false   -- true = banco precargado oficial
);

CREATE TABLE preguntas (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    texto_pregunta   TEXT         NOT NULL,
    tipo_pregunta    VARCHAR(50)  NOT NULL
                         CHECK (tipo_pregunta IN ('opcion_multiple', 'ordenamiento', 'emparejamiento', 'completar')),
    materia          VARCHAR(50)  NOT NULL,
    dificultad       INTEGER      CHECK (dificultad BETWEEN 1 AND 5),
    pista_texto      TEXT,
    explicacion      TEXT,        -- feedback educativo después de responder
    media_url        TEXT,        -- URL a imagen/audio de apoyo
    nodo_asociado    UUID         REFERENCES nodos(id) ON DELETE SET NULL,
    activo           BOOLEAN      DEFAULT true,
    fecha_creacion   TIMESTAMP    DEFAULT NOW(),
    creado_por       UUID         REFERENCES usuarios(id) ON DELETE SET NULL
);

CREATE TABLE opciones_respuesta (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pregunta_id         UUID    NOT NULL REFERENCES preguntas(id) ON DELETE CASCADE,
    texto_opcion        TEXT    NOT NULL,
    es_correcta         BOOLEAN DEFAULT false,
    orden               INTEGER,
    feedback_especifico TEXT    -- "Recuerda que..."
);

CREATE TABLE banco_pregunta_asignacion (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    banco_id      UUID    NOT NULL REFERENCES bancos_preguntas(id) ON DELETE CASCADE,
    pregunta_id   UUID    NOT NULL REFERENCES preguntas(id)        ON DELETE CASCADE,
    orden_en_banco INTEGER,
    UNIQUE (banco_id, pregunta_id)
);


-- =============================================================================
-- PARTE 5 — INTENTOS Y PROGRESO
-- =============================================================================

CREATE TABLE intentos_desafios (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id               UUID     NOT NULL REFERENCES usuarios(id)            ON DELETE CASCADE,
    nodo_id                  UUID              REFERENCES nodos(id)               ON DELETE SET NULL,
    pregunta_id              UUID              REFERENCES preguntas(id)            ON DELETE SET NULL,
    opcion_seleccionada_id   UUID              REFERENCES opciones_respuesta(id)  ON DELETE SET NULL,
    es_correcta              BOOLEAN  NOT NULL,
    tiempo_respuesta         INTEGER,           -- segundos
    puntos_obtenidos         INTEGER  DEFAULT 0,
    fecha_intento            TIMESTAMP DEFAULT NOW(),
    sincronizado             BOOLEAN  DEFAULT false
);


-- =============================================================================
-- PARTE 6 — COLECCIONABLES (CROMOS)
-- =============================================================================

CREATE TABLE cromos (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    codigo        VARCHAR(50) UNIQUE NOT NULL,   -- "cromo_01"
    nombre        VARCHAR(100) NOT NULL,
    descripcion   TEXT,
    imagen_url    TEXT         NOT NULL,
    categoria     VARCHAR(50),                   -- "leyenda", "lugar", "tradición"
    rareza        VARCHAR(20)
                      CHECK (rareza IN ('común', 'raro', 'épico', 'legendario')),
    costo_puntos  INTEGER NOT NULL,
    activo        BOOLEAN DEFAULT true
);

CREATE TABLE coleccion_usuario (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id       UUID      NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    cromo_id         UUID      NOT NULL REFERENCES cromos(id)   ON DELETE CASCADE,
    fecha_obtencion  TIMESTAMP DEFAULT NOW(),
    veces_visto      INTEGER   DEFAULT 0,
    UNIQUE (usuario_id, cromo_id)
);


-- =============================================================================
-- PARTE 7 — SINCRONIZACIÓN OFFLINE
-- =============================================================================

CREATE TABLE log_sincronizacion (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id            UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo_entidad          VARCHAR(50) NOT NULL,   -- "intento", "progreso", "coleccion"
    entidad_id            UUID        NOT NULL,
    accion                VARCHAR(20) NOT NULL
                              CHECK (accion IN ('insert', 'update', 'delete')),
    datos_json            JSONB,
    sincronizado          BOOLEAN     DEFAULT false,
    fecha_creacion        TIMESTAMP   DEFAULT NOW(),
    fecha_sincronizacion  TIMESTAMP
);


-- =============================================================================
-- PARTE 8 — ÍNDICES
-- =============================================================================

CREATE INDEX idx_usuarios_email         ON usuarios                  (email);
CREATE INDEX idx_usuarios_tipo          ON usuarios                  (tipo_usuario);
CREATE INDEX idx_progreso_usuario       ON progreso_mapa             (usuario_id);
CREATE INDEX idx_progreso_nodo          ON progreso_mapa             (nodo_id);
CREATE INDEX idx_preguntas_materia      ON preguntas                 (materia);
CREATE INDEX idx_preguntas_dificultad   ON preguntas                 (dificultad);
CREATE INDEX idx_banco_asig_banco       ON banco_pregunta_asignacion (banco_id);
CREATE INDEX idx_banco_asig_pregunta    ON banco_pregunta_asignacion (pregunta_id);
CREATE INDEX idx_intentos_usuario       ON intentos_desafios         (usuario_id);
CREATE INDEX idx_intentos_sincronizado  ON intentos_desafios         (sincronizado);
CREATE INDEX idx_sync_pendiente         ON log_sincronizacion        (sincronizado)
    WHERE sincronizado = false;


-- =============================================================================
-- PARTE 9 — FUNCIONES Y TRIGGERS
-- =============================================================================

-- Actualiza fecha_actualizacion en bancos_preguntas
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fecha_actualizacion = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_bancos_updated_at
    BEFORE UPDATE ON bancos_preguntas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- Acumula puntos al usuario cuando un intento es correcto
CREATE OR REPLACE FUNCTION incrementar_puntos_usuario()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.es_correcta = true THEN
        UPDATE usuarios
        SET puntos_totales = puntos_totales + NEW.puntos_obtenidos
        WHERE id = NEW.usuario_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_incrementar_puntos
    AFTER INSERT ON intentos_desafios
    FOR EACH ROW
    WHEN (NEW.es_correcta = true)
    EXECUTE FUNCTION incrementar_puntos_usuario();


-- =============================================================================
-- PARTE 10 — CONSTRAINTS ADICIONALES
-- =============================================================================

-- Cada pregunta debe tener al menos una opción marcada como correcta.
-- Se valida con una función para evitar el problema de que CHECK no puede
-- hacer subqueries correlacionadas de forma fiable en todas las versiones.
CREATE OR REPLACE FUNCTION check_tiene_opcion_correcta(p_pregunta_id UUID)
RETURNS BOOLEAN AS $$
    SELECT EXISTS (
        SELECT 1 FROM opciones_respuesta
        WHERE pregunta_id = p_pregunta_id
          AND es_correcta = true
    );
$$ LANGUAGE sql STABLE;

ALTER TABLE opciones_respuesta
    ADD CONSTRAINT check_al_menos_una_correcta
    CHECK (check_tiene_opcion_correcta(pregunta_id));
