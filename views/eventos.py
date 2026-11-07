"""Administración de artistas y eventos de INKubiertos.

El artista es un campo del evento (`nombre_artista`): no se crea una entidad
separada. Las fechas que se muestran se derivan de ventas y movimientos ya
vinculados; esta pantalla no crea ni modifica esas relaciones.
"""
from __future__ import annotations

import unicodedata
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from core.exceptions import AuthorizationError
from data.errors import ErrorDatos
from data.eventos import (
    actividad_eventos_admin,
    cambiar_estado_evento,
    listar_eventos_admin,
    modificar_evento,
    registrar_evento,
)
from data.permisos import ADMINISTRADOR
from ui.feedback import boton_reintentar, cargando, mostrar_error, mostrar_vacio
from ui.format import fmt_clp, fmt_fecha
from ui.layout import metric_grid, page_header, status_badge
from ui.state import flash, render_flash

TODOS = "Todos"
SIN_TIPO = "Sin tipo"
SIN_ARTISTA = "Sin artista"
ESTADOS = [TODOS, "Activos", "Inactivos"]
TIPOS_SUGERIDOS = ("Concierto", "Festival", "Privado")
OTRO_TIPO = "Otro tipo…"


def _normalizar(texto: Any) -> str:
    """Minúsculas, sin tildes y sin espacios sobrantes."""
    valor = unicodedata.normalize("NFKD", str(texto or ""))
    return "".join(
        caracter for caracter in valor if not unicodedata.combining(caracter)
    ).strip().casefold()


def _tipo(fila: Dict[str, Any]) -> str:
    return str(fila.get("tipo_evento") or "").strip() or SIN_TIPO


def _artista(fila: Dict[str, Any]) -> str:
    return str(fila.get("nombre_artista") or "").strip() or SIN_ARTISTA


def _orden(fila: Dict[str, Any]) -> tuple:
    return (
        0 if fila.get("activo") else 1,
        str(fila.get("nombre_evento") or "").casefold(),
    )


def _tipos(eventos: List[Dict[str, Any]]) -> List[str]:
    return sorted(
        {_tipo(fila) for fila in eventos},
        key=lambda valor: (valor.casefold(), valor),
    )


def _numero(valor: Any) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def _duplicados(
    nombre: str,
    eventos: List[Dict[str, Any]],
    *,
    exclude_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Devuelve eventos con el mismo nombre normalizado, sin bloquear."""
    objetivo = _normalizar(nombre)
    if not objetivo:
        return []

    encontrados = []
    for fila in eventos:
        if _normalizar(fila.get("nombre_evento")) != objetivo:
            continue
        try:
            identificador = int(fila.get("id_evento"))
        except (TypeError, ValueError):
            identificador = None
        if exclude_id is not None and identificador == int(exclude_id):
            continue
        encontrados.append(fila)
    return encontrados


def filtrar_eventos(
    eventos: List[Dict[str, Any]],
    *,
    texto: str = "",
    tipo: str = TODOS,
    estado: str = TODOS,
) -> List[Dict[str, Any]]:
    """Aplica búsqueda por evento/artista/tipo y filtros de catálogo."""
    termino = _normalizar(texto)
    tipo_normalizado = _normalizar(tipo)
    resultado = []

    for fila in eventos:
        if tipo != TODOS and _normalizar(_tipo(fila)) != tipo_normalizado:
            continue
        if estado == "Activos" and not fila.get("activo"):
            continue
        if estado == "Inactivos" and fila.get("activo"):
            continue
        if termino:
            campos = (
                _normalizar(fila.get("nombre_evento")),
                _normalizar(_artista(fila)),
                _normalizar(_tipo(fila)),
            )
            if not any(termino in campo for campo in campos):
                continue
        resultado.append(fila)

    return sorted(resultado, key=_orden)


def agrupar_artistas(eventos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Agrupa los eventos por `nombre_artista` para la vista derivada."""
    grupos: Dict[str, Dict[str, Any]] = {}
    for fila in eventos:
        artista = _artista(fila)
        grupo = grupos.setdefault(
            artista,
            {
                "artista": artista,
                "eventos": 0,
                "activos": 0,
                "costo_total": 0.0,
                "tipos": set(),
            },
        )
        grupo["eventos"] += 1
        if fila.get("activo"):
            grupo["activos"] += 1
        grupo["costo_total"] += _numero(fila.get("costo_artista"))
        if _tipo(fila) != SIN_TIPO:
            grupo["tipos"].add(_tipo(fila))

    resultado = []
    for grupo in grupos.values():
        resultado.append(
            {
                **grupo,
                "tipos": len(grupo["tipos"]),
            }
        )

    return sorted(
        resultado,
        key=lambda grupo: (
            1 if grupo["artista"] == SIN_ARTISTA else 0,
            grupo["artista"].casefold(),
        ),
    )


def filtrar_artistas(
    artistas: List[Dict[str, Any]], *, texto: str = ""
) -> List[Dict[str, Any]]:
    """Filtra la vista derivada de artistas por nombre."""
    termino = _normalizar(texto)
    if not termino:
        return artistas
    return [
        grupo
        for grupo in artistas
        if termino in _normalizar(grupo.get("artista"))
    ]


def _rango_actividad(
    actividad: Dict[int, Dict[str, str]], id_evento: Any
) -> str:
    try:
        identificador = int(id_evento)
    except (TypeError, ValueError):
        return "—"

    registro = actividad.get(identificador) or {}
    primera = registro.get("primera")
    ultima = registro.get("ultima")
    if not primera and not ultima:
        return "Sin actividad vinculada"
    if primera and ultima and primera != ultima:
        return f"{fmt_fecha(primera)} – {fmt_fecha(ultima)}"
    return fmt_fecha(primera or ultima)


def _metricas(eventos: List[Dict[str, Any]]) -> None:
    total = len(eventos)
    activos = sum(1 for fila in eventos if fila.get("activo"))
    inactivos = total - activos
    artistas = len({_artista(fila) for fila in eventos} - {SIN_ARTISTA})

    metric_grid(
        [
            {
                "label": "Eventos",
                "value": total,
                "hint": "Registros del catálogo, activos e inactivos.",
                "tone": "default",
            },
            {
                "label": "Activos",
                "value": activos,
                "hint": "Disponibles en los selectores de la aplicación.",
                "tone": "green",
            },
            {
                "label": "Inactivos",
                "value": inactivos,
                "hint": "Conservan su nombre en el historial de ventas.",
                "tone": "amber",
            },
            {
                "label": "Artistas",
                "value": artistas,
                "hint": "Nombres de artista distintos en los eventos.",
                "tone": "wine",
            },
        ]
    )


def _tabla_eventos(
    eventos: List[Dict[str, Any]],
    actividad: Dict[int, Dict[str, str]],
) -> str:
    cuerpo = []
    for fila in eventos:
        activo = bool(fila.get("activo"))
        estado = status_badge(
            "Activo" if activo else "Inactivo", "green" if activo else "muted"
        )
        costo = fila.get("costo_artista")
        costo_texto = "—" if costo is None else fmt_clp(costo)
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(fila.get("nombre_evento") or "Sin nombre"))}</span></td>'
            f"<td>{escape(_artista(fila))}</td>"
            f"<td>{escape(_tipo(fila))}</td>"
            f'<td class="is-num">{escape(costo_texto)}</td>'
            f'<td class="is-date">{escape(_rango_actividad(actividad, fila.get("id_evento")))}</td>'
            f"<td>{estado}</td>"
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th>Evento</th><th>Artista</th><th>Tipo</th>"
        "<th class='is-num'>Costo artista</th>"
        "<th>Actividad vinculada</th><th>Estado</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _tabla_artistas(artistas: List[Dict[str, Any]]) -> str:
    cuerpo = []
    for grupo in artistas:
        activos = int(grupo.get("activos") or 0)
        eventos = int(grupo.get("eventos") or 0)
        if grupo.get("artista") == SIN_ARTISTA:
            estado = status_badge("Sin asignar", "muted")
        else:
            estado = status_badge(
                "Con eventos activos" if activos else "Solo historial",
                "green" if activos else "muted",
            )
        cuerpo.append(
            "<tr>"
            f'<td><span class="ink-product-name">'
            f'{escape(str(grupo.get("artista") or SIN_ARTISTA))}</span></td>'
            f'<td class="is-num">{escape(str(eventos))}</td>'
            f'<td class="is-num">{escape(str(activos))}</td>'
            f'<td class="is-num">{escape(str(grupo.get("tipos") or 0))}</td>'
            f'<td class="is-num">{escape(fmt_clp(grupo.get("costo_total")))}</td>'
            f"<td>{estado}</td>"
            "</tr>"
        )

    return (
        '<div class="ink-table-wrap">'
        '<table class="ink-table">'
        "<thead><tr>"
        "<th>Artista</th><th class='is-num'>Eventos</th>"
        "<th class='is-num'>Activos</th><th class='is-num'>Tipos</th>"
        "<th class='is-num'>Costo registrado</th><th>Estado</th>"
        "</tr></thead>"
        f'<tbody>{"".join(cuerpo)}</tbody>'
        "</table>"
        "</div>"
    )


def _formulario_evento(
    evento: Optional[Dict[str, Any]],
    eventos: List[Dict[str, Any]],
    usuario: Dict[str, Any],
    *,
    editar: bool,
) -> None:
    identificador = int(evento["id_evento"]) if evento else "nuevo"
    clave = f"eve_form_{'editar' if editar else 'nuevo'}_{identificador}"

    with st.form(key=clave, clear_on_submit=not editar):
        col_izquierda, col_derecha = st.columns(2, gap="large")
        with col_izquierda:
            nombre = st.text_input(
                "Nombre del evento",
                value=str(evento.get("nombre_evento") or "") if evento else "",
                max_chars=150,
                key=f"{clave}_nombre",
                help=(
                    "Obligatorio, entre 2 y 150 caracteres. Si ya existe otro "
                    "evento con el mismo nombre se advierte, pero no se bloquea."
                ),
            )
            artista = st.text_input(
                "Artista",
                value=str(evento.get("nombre_artista") or "") if evento else "",
                max_chars=150,
                key=f"{clave}_artista",
                help="Opcional. El artista se guarda como parte del evento.",
            )
        with col_derecha:
            tipo_actual = (
                str(evento.get("tipo_evento") or "").strip() if evento else ""
            )
            opciones_tipo = list(TIPOS_SUGERIDOS)
            if tipo_actual and tipo_actual not in opciones_tipo:
                opciones_tipo.append(tipo_actual)
            opciones_tipo.append(OTRO_TIPO)
            indice_tipo = (
                opciones_tipo.index(tipo_actual)
                if tipo_actual in opciones_tipo
                else None
            )
            tipo_elegido = st.selectbox(
                "Tipo de evento",
                opciones_tipo,
                index=indice_tipo,
                placeholder="Selecciona un tipo",
                key=f"{clave}_tipo",
                help=(
                    "Obligatorio. Opciones sugeridas: Concierto, Festival o "
                    "Privado. Si el evento es de otro tipo, elige «Otro tipo…» "
                    "y escríbelo (máximo 50 caracteres)."
                ),
            )
            if tipo_elegido == OTRO_TIPO:
                tipo = st.text_input(
                    "Especifica el tipo de evento",
                    value=(
                        tipo_actual
                        if tipo_actual and tipo_actual not in TIPOS_SUGERIDOS
                        else ""
                    ),
                    max_chars=50,
                    key=f"{clave}_tipo_libre",
                    help="Obligatorio, máximo 50 caracteres.",
                )
            else:
                tipo = str(tipo_elegido or "").strip()

            costo = st.number_input(
                "Costo del artista (CLP)",
                min_value=0.0,
                step=1000.0,
                format="%.2f",
                value=_numero(evento.get("costo_artista")) if evento else 0.0,
                key=f"{clave}_costo",
                help="Costo acordado con el artista. No modifica ventas históricas.",
            )

        if editar:
            st.caption(
                "El evento no tiene campo de fecha propio. Las fechas visibles "
                "se derivan de ventas y movimientos ya vinculados."
            )

        enviado = st.form_submit_button(
            "Guardar cambios" if editar else "Registrar evento",
            type="primary",
            use_container_width=True,
        )

    if not enviado:
        return

    datos = {
        "nombre_evento": nombre,
        "nombre_artista": artista,
        "tipo_evento": tipo,
        "costo_artista": costo,
    }

    excluir = int(evento["id_evento"]) if editar and evento else None
    duplicados = _duplicados(nombre, eventos, exclude_id=excluir)

    try:
        with cargando("Guardando evento…"):
            if editar and evento:
                modificar_evento(
                    int(evento["id_evento"]), datos, usuario=usuario
                )
                accion = "quedó actualizado"
            else:
                registrar_evento(datos, usuario=usuario)
                accion = "quedó registrado"
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudo guardar el evento.")
        return
    except Exception:
        st.error("No se pudo guardar el evento. Intenta nuevamente.")
        return

    if duplicados:
        nombres = ", ".join(
            f"«{fila.get('nombre_evento') or 'Sin nombre'}»" for fila in duplicados[:3]
        )
        flash(
            "warning",
            f"El evento «{nombre.strip()}» {accion}, pero ya existen otros "
            f"registros con el mismo nombre: {nombres}. No se bloqueó el guardado.",
        )
    else:
        flash("success", f"El evento «{nombre.strip()}» {accion}.")
    st.rerun()


def _panel_edicion(
    eventos: List[Dict[str, Any]], usuario: Dict[str, Any]
) -> None:
    seleccionado = st.selectbox(
        "Evento a editar",
        eventos,
        format_func=lambda fila: (
            f"{fila.get('nombre_evento') or 'Sin nombre'} · "
            f"{_artista(fila)} · "
            f"{'Activo' if fila.get('activo') else 'Inactivo'}"
        ),
        key="eve_editar_evento",
    )
    if not seleccionado:
        return
    _formulario_evento(seleccionado, eventos, usuario, editar=True)


def _panel_estado(
    eventos: List[Dict[str, Any]], usuario: Dict[str, Any]
) -> None:
    st.caption(
        "Desactivar un evento no borra su nombre ni su historial. Las ventas y "
        "movimientos que ya lo referencian conservan la etiqueta histórica."
    )
    seleccionado = st.selectbox(
        "Evento",
        eventos,
        format_func=lambda fila: (
            f"{fila.get('nombre_evento') or 'Sin nombre'} · "
            f"{'Activo' if fila.get('activo') else 'Inactivo'}"
        ),
        key="eve_estado_evento",
    )
    if not seleccionado:
        return

    identificador = int(seleccionado["id_evento"])
    nombre = str(seleccionado.get("nombre_evento") or "el evento")
    activo = bool(seleccionado.get("activo"))
    accion = "desactivar" if activo else "activar"

    confirmar = st.checkbox(
        f"Confirmo que quiero {accion} «{nombre}».",
        key=f"eve_confirmar_{accion}_{identificador}",
    )
    if st.button(
        "Desactivar evento" if activo else "Activar evento",
        key=f"eve_boton_{accion}_{identificador}",
        type="primary",
        disabled=not confirmar,
        use_container_width=True,
    ):
        try:
            with cargando(f"Procesando «{nombre}»…"):
                cambiar_estado_evento(
                    identificador, not activo, usuario=usuario
                )
        except (ErrorDatos, AuthorizationError) as exc:
            mostrar_error(exc, prefijo=f"No se pudo {accion} el evento.")
            return
        except Exception:
            st.error(f"No se pudo {accion} el evento. Intenta nuevamente.")
            return

        flash(
            "success",
            f"El evento «{nombre}» quedó {'activo' if not activo else 'inactivo'}.",
        )
        st.rerun()


def _vista_artistas(eventos: List[Dict[str, Any]]) -> None:
    artistas = agrupar_artistas(eventos)
    con_nombre = [grupo for grupo in artistas if grupo["artista"] != SIN_ARTISTA]
    con_activos = sum(1 for grupo in con_nombre if grupo["activos"])

    metric_grid(
        [
            {
                "label": "Artistas",
                "value": len(con_nombre),
                "hint": "Nombres distintos registrados en los eventos.",
                "tone": "wine",
            },
            {
                "label": "Con eventos activos",
                "value": con_activos,
                "hint": "Artistas con al menos un evento activo.",
                "tone": "green",
            },
            {
                "label": "Eventos con artista",
                "value": sum(
                    1
                    for fila in eventos
                    if _artista(fila) != SIN_ARTISTA
                ),
                "hint": "Eventos que tienen un artista asignado.",
                "tone": "default",
            },
        ]
    )

    st.caption(
        "Vista derivada de `nombre_artista`. No existe una tabla separada de "
        "artistas: agrupar aquí no modifica el catálogo. La fila «Sin artista» "
        "agrupa los eventos que no tienen un nombre asignado."
    )

    if not artistas:
        mostrar_vacio(
            "Aún no hay artistas para mostrar. Registra un evento con el campo "
            "Artista para que aparezca en esta vista."
        )
        return

    texto = st.text_input(
        "Buscar artista",
        placeholder="Nombre del artista",
        key="eve_buscar_artista",
    )
    filtrados = filtrar_artistas(artistas, texto=texto)

    st.markdown(
        '<div class="ink-table-meta">'
        f"<span>{len(filtrados)} de {len(artistas)} artistas</span>"
        "<span>Agrupación derivada de los eventos</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    if filtrados:
        st.markdown(_tabla_artistas(filtrados), unsafe_allow_html=True)
    else:
        mostrar_vacio(
            "No hay artistas que coincidan con la búsqueda. Prueba con otro "
            "término."
        )


def render_eventos() -> None:
    """Renderiza la administración de artistas y eventos para un administrador."""
    usuario = st.session_state.get("user") or {}
    if usuario.get("rol") != ADMINISTRADOR:
        st.error("No tienes permisos para acceder a esta sección.")
        st.stop()

    page_header("Artistas y eventos", "Administración del catálogo de eventos")
    render_flash()
    st.markdown(
        '<div class="ink-scope">Administración · eventos y artistas</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "El evento no tiene una fecha propia: las fechas de actividad se derivan "
        "de ventas y movimientos ya vinculados. El artista es un campo del evento."
    )

    try:
        with cargando("Cargando eventos…"):
            eventos = listar_eventos_admin(usuario=usuario)
    except (ErrorDatos, AuthorizationError) as exc:
        mostrar_error(exc, prefijo="No se pudieron cargar los eventos.")
        boton_reintentar("eventos")
        return

    actividad: Dict[int, Dict[str, str]] = {}
    actividad_disponible = True
    try:
        with cargando("Cargando actividad vinculada…"):
            actividad = actividad_eventos_admin(usuario=usuario)
    except (ErrorDatos, AuthorizationError):
        actividad_disponible = False

    eventos = sorted(eventos, key=_orden)
    artistas = agrupar_artistas(eventos)

    pestana_eventos, pestana_artistas = st.tabs(["Eventos", "Artistas"])

    with pestana_eventos:
        if not actividad_disponible:
            st.caption(
                "Las fechas de actividad vinculada no están disponibles en este "
                "momento. El resto del catálogo sigue operativo."
            )

        if eventos:
            _metricas(eventos)

            col_buscar, col_tipo, col_estado = st.columns(
                [2.2, 1.3, 1.2], gap="medium"
            )
            with col_buscar:
                texto = st.text_input(
                    "Buscar evento",
                    placeholder="Evento, artista o tipo",
                    key="eve_buscar",
                )
            with col_tipo:
                tipo = st.selectbox(
                    "Tipo de evento",
                    [TODOS] + _tipos(eventos),
                    key="eve_tipo",
                )
            with col_estado:
                estado = st.selectbox("Estado", ESTADOS, key="eve_estado")

            filtrados = filtrar_eventos(
                eventos,
                texto=texto,
                tipo=tipo,
                estado=estado,
            )

            st.markdown(
                '<div class="ink-table-meta">'
                f"<span>{len(filtrados)} de {len(eventos)} eventos</span>"
                "<span>Las fechas se derivan de ventas y movimientos</span>"
                "</div>",
                unsafe_allow_html=True,
            )

            if filtrados:
                st.markdown(
                    _tabla_eventos(filtrados, actividad),
                    unsafe_allow_html=True,
                )
            else:
                mostrar_vacio(
                    "No hay eventos que coincidan con la búsqueda o los filtros "
                    "seleccionados. Prueba con otro término o restablece los filtros."
                )
                if st.button("Limpiar filtros", key="eve_limpiar", type="secondary"):
                    for clave in ("eve_buscar", "eve_tipo", "eve_estado"):
                        st.session_state.pop(clave, None)
                    st.rerun()
        else:
            mostrar_vacio(
                "Aún no hay eventos registrados. Crea el primero con el "
                "formulario de abajo; el artista se guarda dentro del evento."
            )

        st.markdown("---")
        st.markdown("**Registrar evento**")
        with st.expander(
            "Datos del nuevo evento",
            expanded=not eventos,
        ):
            _formulario_evento(None, eventos, usuario, editar=False)

        if eventos:
            st.markdown("**Editar evento**")
            with st.expander(
                "Selecciona un evento y actualiza sus datos", expanded=False
            ):
                _panel_edicion(eventos, usuario)

            st.markdown("**Activar o desactivar evento**")
            with st.expander("Cambiar el estado del evento", expanded=False):
                _panel_estado(eventos, usuario)

    with pestana_artistas:
        _vista_artistas(eventos)
