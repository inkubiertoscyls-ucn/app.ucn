-- 006: Fecha de presentación del artista en dim_evento.
--
-- Cada evento representa una visita de un artista al local (artista + fecha +
-- costo). La rentabilidad por artista toma las ventas de FUDO de esa fecha
-- (hecho_venta_fudo.fecha_venta) y las compara con un día normal sin evento.
--
-- La columna es opcional: los eventos existentes quedan sin fecha hasta que se
-- completen desde la pantalla "Artistas y eventos".
-- Ejecutar manualmente en Supabase > SQL Editor.

ALTER TABLE dim_evento
ADD COLUMN IF NOT EXISTS fecha_evento DATE;

COMMENT ON COLUMN dim_evento.fecha_evento IS
    'Fecha en que el artista se presenta en el local (para rentabilidad por artista)';

CREATE INDEX IF NOT EXISTS idx_dim_evento_fecha_evento
    ON dim_evento (fecha_evento);

-- Verificación
SELECT id_evento, nombre_evento, nombre_artista, fecha_evento
FROM dim_evento
ORDER BY fecha_evento NULLS LAST, id_evento;
