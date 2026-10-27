"""
FUDO Import Service - Flexible importer for FUDO sales exports.
Excel/CSV, configurable column mapping, preview, validation, duplicates.
Saves to hecho_venta_fudo (independent from hecho_inventario).
"""
import logging
import hashlib
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

from db.supabase_client import get_supabase_client
from core.exceptions import ValidationError
from repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class FudoImportService:
    def __init__(self):
        self.client = get_supabase_client()
        self.ventas_repo = BaseRepository("hecho_venta_fudo")
        self.productos_repo = BaseRepository("dim_producto")
        self.eventos_repo = BaseRepository("dim_evento")
    
    def leer_archivo(self, file_path: str) -> Tuple[pd.DataFrame, str]:
        """
        Read Excel or CSV file.
        Returns (DataFrame, sheet_name_or_type)
        """
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
                return df, 'csv'
            elif file_path.endswith(('.xlsx', '.xls')):
                # Read all sheets
                excel_file = pd.ExcelFile(file_path)
                # Return first sheet by default, but can inspect
                df = pd.read_excel(file_path, sheet_name=excel_file.sheet_names[0])
                return df, excel_file.sheet_names[0]
            else:
                raise ValidationError("Formato no soportado. Use CSV o Excel (.xlsx, .xls)")
        except Exception as e:
            raise ValidationError(f"Error al leer archivo: {e}")
    
    def inspeccionar_archivo(self, file_path: str) -> Dict:
        """Inspect file structure - sheets and columns."""
        try:
            result = {
                "tipo": None,
                "hojas": [],
                "columnas_por_hoja": {},
                "preview": {}
            }
            if file_path.endswith('.csv'):
                result["tipo"] = "csv"
                df = pd.read_csv(file_path)
                result["columnas_por_hoja"] = {"csv": list(df.columns)}
                result["preview"]["csv"] = df.head(10).to_dict('records')
            elif file_path.endswith(('.xlsx', '.xls')):
                result["tipo"] = "excel"
                excel_file = pd.ExcelFile(file_path)
                result["hojas"] = excel_file.sheet_names
                for sheet in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    result["columnas_por_hoja"][sheet] = list(df.columns)
                    result["preview"][sheet] = df.head(10).to_dict('records')
            return result
        except Exception as e:
            raise ValidationError(f"Error al inspeccionar archivo: {e}")
    
    def crear_mapeo_columnas(self, columnas_origen: List[str], 
                            mapeo_config: Dict[str, str]) -> Dict:
        """
        Create column mapping from source to destination.
        mapeo_config: {columna_origen: campo_destino}
        campos_destino: fecha_venta, total_venta, cantidad_total, producto_identificado, etc.
        """
        mapeo = {}
        for origen, destino in mapeo_config.items():
            if origen in columnas_origen:
                mapeo[origen] = destino
        return mapeo
    
    def previsualizar_importacion(self, file_path: str, sheet_name: str = None,
                                 mapeo_columnas: Dict = None) -> Dict:
        """Preview data before import with mapping."""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name) if sheet_name else pd.read_excel(file_path)
            
            if mapeo_columnas:
                df_mapeado = df.rename(columns=mapeo_columnas)
            else:
                df_mapeado = df.copy()
            
            preview = {
                "total_filas": len(df),
                "columnas_origen": list(df.columns),
                "columnas_mapeadas": list(df_mapeado.columns) if mapeo_columnas else list(df.columns),
                "datos_preview": df_mapeado.head(20).to_dict('records'),
                "validacion_preliminar": self._validar_preliminar(df_mapeado)
            }
            return preview
        except Exception as e:
            raise ValidationError(f"Error en previsualización: {e}")
    
    def _validar_preliminar(self, df: pd.DataFrame) -> Dict:
        """Preliminary validation."""
        issues = []
        warnings = []
        
        # Check for date
        if 'fecha_venta' not in df.columns and 'fecha' not in df.columns:
            warnings.append("No se detectó columna de fecha")
        
        # Check for amounts/quantities
        if 'total_venta' not in df.columns and 'total' not in df.columns and 'monto' not in df.columns:
            warnings.append("No se detectó columna de total/monto")
        
        return {
            "errores": issues,
            "advertencias": warnings,
            "filas_con_datos": len(df.dropna(how='all'))
        }
    
    def detectar_duplicados(self, df: pd.DataFrame) -> Dict:
        """Detect duplicates based on available info."""
        try:
            # Create hash based on key fields
            df_copy = df.copy()
            df_copy['hash_temp'] = df_copy.apply(lambda row: self._crear_hash_registro(row), axis=1)
            duplicados = df_copy[df_copy.duplicated(subset=['hash_temp'], keep=False)]
            return {
                "hay_duplicados": len(duplicados) > 0,
                "cantidad_duplicados": len(duplicados),
                "indices_duplicados": duplicados.index.tolist()
            }
        except Exception as e:
            return {"hay_duplicados": False, "error": str(e)}
    
    def _crear_hash_registro(self, row) -> str:
        """Create hash for duplicate detection."""
        # Use available fields
        campos = []
        for key in ['fecha_venta', 'fecha', 'total_venta', 'total', 'producto_identificado', 'producto']:
            if key in row and pd.notna(row[key]):
                campos.append(str(row[key]))
        contenido = '|'.join(campos)
        return hashlib.sha256(contenido.encode()).hexdigest()
    
    def importar_ventas(self, file_path: str, sheet_name: str = None,
                       mapeo_columnas: Dict = None, 
                       importado_por: str = None,
                       origen_archivo: str = None) -> Dict:
        """
        Import sales to hecho_venta_fudo.
        Does NOT mix with hecho_inventario.
        Does NOT auto-associate all sales to artist if not identifiable.
        Distinguishes consolidated vs detailed.
        """
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path, sheet_name=sheet_name) if sheet_name else pd.read_excel(file_path)
            
            if mapeo_columnas:
                df = df.rename(columns=mapeo_columnas)
            
            if origen_archivo is None:
                origen_archivo = file_path.split('/')[-1].split('\\')[-1]
            
            resultados = {
                "importados": 0,
                "rechazados": 0,
                "duplicados_detectados": 0,
                "errores": [],
                "detalles": []
            }
            
            # Check duplicates
            dup_info = self.detectar_duplicados(df)
            if dup_info.get("hay_duplicados"):
                resultados["duplicados_detectados"] = dup_info.get("cantidad_duplicados", 0)
            
            for idx, row in df.iterrows():
                try:
                    registro = self._procesar_fila(row, origen_archivo, importado_por)
                    if registro is None:
                        resultados["rechazados"] += 1
                        resultados["errores"].append(f"Fila {idx+1}: Datos inválidos o incompletos")
                        continue
                    
                    # Check if duplicate exists in DB
                    if registro.get('hash_registro'):
                        existente = self.client.table('hecho_venta_fudo').select('*').eq(
                            'hash_registro', registro['hash_registro']
                        ).execute()
                        if existente.data:
                            resultados["duplicados_detectados"] += 1
                            continue
                    
                    self.ventas_repo.create(registro)
                    resultados["importados"] += 1
                except Exception as e:
                    resultados["rechazados"] += 1
                    resultados["errores"].append(f"Fila {idx+1}: {str(e)}")
            
            return resultados
        except Exception as e:
            raise ValidationError(f"Error en importación: {e}")
    
    def _procesar_fila(self, row, origen_archivo: str, importado_por: str = None) -> Optional[Dict]:
        """Process individual row."""
        try:
            registro = {
                "origen_archivo": origen_archivo,
                "datos_raw": json.loads(json.dumps(row.to_dict(), default=str)),
                "fecha_importacion": datetime.now().isoformat()
            }
            
            if importado_por:
                registro["importado_por"] = importado_por
            
            # Date
            fecha_val = None
            for key in ['fecha_venta', 'fecha', 'Fecha']:
                if key in row and pd.notna(row[key]):
                    fecha_val = row[key]
                    break
            if fecha_val:
                try:
                    if isinstance(fecha_val, str):
                        registro["fecha_venta"] = pd.to_datetime(fecha_val).date().isoformat()
                    else:
                        registro["fecha_venta"] = pd.to_datetime(fecha_val).date().isoformat()
                except:
                    pass
            
            # Amounts
            for key in ['total_venta', 'total', 'monto', 'Total', 'Monto']:
                if key in row and pd.notna(row[key]):
                    try:
                        registro["total_venta"] = float(row[key])
                        break
                    except:
                        pass
            
            for key in ['cantidad_total', 'cantidad', 'Cantidad']:
                if key in row and pd.notna(row[key]):
                    try:
                        registro["cantidad_total"] = float(row[key])
                        break
                    except:
                        pass
            
            # Product
            for key in ['producto_identificado', 'producto', 'Producto', 'item']:
                if key in row and pd.notna(row[key]):
                    registro["producto_identificado"] = str(row[key])
                    break
            
            # Try to relate to product if possible
            if registro.get('producto_identificado'):
                try:
                    prod = self.client.table('dim_producto').select('id_producto').ilike(
                        'nombre_producto', f"%{registro['producto_identificado']}%"
                    ).limit(1).execute()
                    if prod.data:
                        registro["id_producto_relacionado"] = prod.data[0]['id_producto']
                except:
                    pass
            
            # Hash for duplicate detection
            registro["hash_registro"] = self._crear_hash_registro(row)
            
            # Validate required fields
            if not registro.get('fecha_venta') and not registro.get('total_venta'):
                return None
            
            return registro
        except Exception:
            return None
    
    def listar_importaciones(self, limit: int = 50) -> List[Dict]:
        """List recent imports."""
        try:
            response = self.client.table('hecho_venta_fudo').select('*').order(
                'fecha_importacion', desc=True
            ).limit(limit).execute()
            return response.data or []
        except Exception:
            return []
