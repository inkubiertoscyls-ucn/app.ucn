-- INKubiertos - Initial Schema Migration
-- NO EJECUTAR AUTOMÁTICAMENTE EN BD REMOTA
-- Revisar y ejecutar manualmente en Supabase SQL Editor

-- IMPORTANTES:
-- - dim_producto NO tiene area_habitual
-- - dim_usuario.rut_usuario es PK (sin id_usuario)
-- - dim_proveedor.rut_proveedor es PK (sin id_proveedor)
-- - hecho_inventario NO tiene costo_total
-- - hecho_venta_fudo es tabla independiente

-- dim_fecha
CREATE TABLE IF NOT EXISTS dim_fecha (
    id_fecha BIGSERIAL PRIMARY KEY,
    fecha DATE UNIQUE NOT NULL,
    dia INTEGER,
    mes INTEGER,
    anio INTEGER
);

-- dim_area
CREATE TABLE IF NOT EXISTS dim_area (
    id_area BIGSERIAL PRIMARY KEY,
    nombre_area VARCHAR(100) NOT NULL,
    descripcion_area TEXT,
    activo BOOLEAN DEFAULT TRUE
);

-- dim_usuario (PK: rut_usuario)
CREATE TABLE IF NOT EXISTS dim_usuario (
    rut_usuario VARCHAR(12) PRIMARY KEY,
    nombre_usuario VARCHAR(150) NOT NULL,
    rol VARCHAR(50) NOT NULL CHECK (rol IN ('Administrador', 'Operario')),
    area_asignada BIGINT REFERENCES dim_area(id_area),
    password_hash TEXT,
    activo BOOLEAN DEFAULT TRUE,
    fecha_creacion TIMESTAMP DEFAULT NOW()
);

-- dim_proveedor (PK: rut_proveedor)
CREATE TABLE IF NOT EXISTS dim_proveedor (
    rut_proveedor VARCHAR(12) PRIMARY KEY,
    nombre_proveedor VARCHAR(150) NOT NULL,
    contacto_proveedor VARCHAR(150),
    tipo_proveedor VARCHAR(100),
    activo BOOLEAN DEFAULT TRUE
);

-- dim_producto (SIN area_habitual)
CREATE TABLE IF NOT EXISTS dim_producto (
    id_producto BIGSERIAL PRIMARY KEY,
    nombre_producto VARCHAR(150) NOT NULL,
    categoria VARCHAR(100),
    unidad_medida VARCHAR(50) NOT NULL,
    costo_base NUMERIC(10,2) DEFAULT 0,
    stock_minimo INTEGER DEFAULT 0,
    stock_maximo INTEGER DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE
);

-- dim_tipo_movimiento
CREATE TABLE IF NOT EXISTS dim_tipo_movimiento (
    id_tipo_movimiento BIGSERIAL PRIMARY KEY,
    tipo_movimiento VARCHAR(50) NOT NULL,
    factor_stock INTEGER NOT NULL CHECK (factor_stock IN (1, -1)),
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE
);

-- dim_evento
CREATE TABLE IF NOT EXISTS dim_evento (
    id_evento BIGSERIAL PRIMARY KEY,
    nombre_evento VARCHAR(150),
    nombre_artista VARCHAR(150),
    tipo_evento VARCHAR(100),
    costo_artista NUMERIC(10,2) DEFAULT 0,
    activo BOOLEAN DEFAULT TRUE
);

-- hecho_inventario (SIN costo_total)
CREATE TABLE IF NOT EXISTS hecho_inventario (
    id_hecho_inventario BIGSERIAL PRIMARY KEY,
    id_fecha BIGINT REFERENCES dim_fecha(id_fecha),
    id_producto BIGINT NOT NULL REFERENCES dim_producto(id_producto),
    id_area BIGINT NOT NULL REFERENCES dim_area(id_area),
    id_tipo_movimiento BIGINT NOT NULL REFERENCES dim_tipo_movimiento(id_tipo_movimiento),
    rut_usuario VARCHAR(12) NOT NULL REFERENCES dim_usuario(rut_usuario),
    rut_proveedor VARCHAR(12) REFERENCES dim_proveedor(rut_proveedor),
    id_evento BIGINT REFERENCES dim_evento(id_evento),
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    costo_unitario NUMERIC(10,2),
    observacion TEXT,
    fecha_hora_registro TIMESTAMP DEFAULT NOW()
);

-- hecho_venta_fudo (independiente de hecho_inventario)
CREATE TABLE IF NOT EXISTS hecho_venta_fudo (
    id_venta_fudo BIGSERIAL PRIMARY KEY,
    fecha_venta DATE,
    id_evento BIGINT REFERENCES dim_evento(id_evento),
    origen_archivo VARCHAR(255),
    datos_raw JSONB,
    total_venta NUMERIC(12,2),
    cantidad_total NUMERIC(10,2),
    producto_identificado VARCHAR(150),
    id_producto_relacionado BIGINT REFERENCES dim_producto(id_producto),
    importado_por VARCHAR(12) REFERENCES dim_usuario(rut_usuario),
    fecha_importacion TIMESTAMP DEFAULT NOW(),
    hash_registro VARCHAR(64)
);
