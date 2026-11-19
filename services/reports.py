import re
import pandas as pd
from settings import settings
from  services.gsheets import dataframe_to_google_sheets, dataframes_to_google_sheets
from services.excel_exporter import dataframe_to_excel_buffer, dataframes_to_excel_buffer
from services.sharepoint import sharepoint_service
from datetime import datetime,timedelta
from typing import List
from helpers.db_supabase import supabase

def fetch_trucks_control(date_ref,emails):
    try:
        # Suponiendo que 'get_trucks_control' es un Procedimiento Almacenado en Supabase
        data = supabase.rpc('get_trucks_control', {'fecha_ref': date_ref}).execute()
        
        # Convertir el resultado en una lista de diccionarios si se devuelve algún dato
        df = pd.DataFrame(data.data if data.data else [])
        
        # Verificar si el DataFrame está vacío
        if df.empty:
            raise ValueError("No se encontraron datos para la fecha proporcionada.")
        
        # Convertir la columna 'hora' a datetime y formatearla para mostrar solo horas y minutos
        df['hora'] = pd.to_datetime(df['hora']).dt.strftime('%H:%M')
        
        # Generar nombre de archivo con extensión .xlsx
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_date = re.sub(r'[^0-9A-Za-z]', '', str(date_ref))
        filename = f'Reporte_control_camiones_{clean_date}_{now}.xlsx'
        
        # Generar Excel en memoria y entregar (SharePoint o Local)
        buffer = dataframe_to_excel_buffer(df, sheet_name="Control Camiones")
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)
        
        return [result]
    
    except Exception as e:
        # Manejar cualquier excepción que pueda ocurrir durante el proceso
        print(f"Error al generar el reporte control vehicular: {e}")
        return [{"success": False, "error": str(e)}]


def fetch_vehicle_control(date_ref,emails):
    try:
        # Suponiendo que 'get_trucks_control' es un Procedimiento Almacenado en Supabase
        data = supabase.rpc('get_vehicle_control', {'fecha_ref': date_ref}).execute()
        
        # Convertir el resultado en una lista de diccionarios si se devuelve algún dato
        df = pd.DataFrame(data.data if data.data else [])
        
        # Verificar si el DataFrame está vacío
        if df.empty:
            raise ValueError("No se encontraron datos para la fecha proporcionada.")
        
        # Convertir la columna 'hora' a datetime y formatearla para mostrar solo horas y minutos
        df['hora'] = pd.to_datetime(df['hora']).dt.strftime('%H:%M')
        
        # Generar nombre de archivo con extensión .xlsx
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_date = re.sub(r'[^0-9A-Za-z]', '', str(date_ref))
        filename = f'Reporte_control_vehicular_{clean_date}_{now}.xlsx'
        
        # Generar Excel en memoria y entregar (SharePoint o Local)
        buffer = dataframe_to_excel_buffer(df, sheet_name="Control Vehicular")
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)
        
        return [result]
    
    except Exception as e:
        # Manejar cualquier excepción que pueda ocurrir durante el proceso
        print(f"Error al generar el reporte control vehicular: {e}")
        return [{"success": False, "error": str(e)}]



#get_order_information

def fetch_order_information(date_ref,emails):
    try:
        # Suponiendo que 'get_trucks_control' es un Procedimiento Almacenado en Supabase
        data = supabase.rpc('get_order_information', {'date_ref': date_ref}).execute()
        
        # Convertir el resultado en una lista de diccionarios si se devuelve algún dato
        df = pd.DataFrame(data.data if data.data else [])
        
        # Verificar si el DataFrame está vacío
        if df.empty:
            raise ValueError("No se encontraron datos para la fecha proporcionada.")
        
        #get_active_company_vehicles()
        vehicles = supabase.rpc('get_active_company_vehicles').execute()
        
        df_v = pd.DataFrame(vehicles.data if vehicles.data else [])
        print(df_v)
        print(df)
        # adicionar aca 
        # Asegurar que 'plate' existe en ambos DataFrames
        if 'placa' in df.columns and 'plate' in df_v.columns:
            # Filtrar los valores de 'plate' en df_v que no están en 'placa' de df
            unique_plates = df_v[~df_v['plate'].isin(df['placa'])]
            
            # Crear un DataFrame vacío con las mismas columnas que df
            new_rows = pd.DataFrame(columns=df.columns)
            
            # Asignar los valores únicos de 'plate' de df_v a la columna 'placa' en new_rows
            new_rows['placa'] = unique_plates['plate']
            
            # Concatenar new_rows al final de df
            df = pd.concat([df, new_rows], ignore_index=True)
        # Generar nombre de archivo con extensión .xlsx
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_date = re.sub(r'[^0-9A-Za-z]', '', str(date_ref))
        filename = f'Reporte_programacion_diaria_{clean_date}_{now}.xlsx'
        
        # Generar Excel en memoria y entregar (SharePoint o Local)
        buffer = dataframe_to_excel_buffer(df, sheet_name="Programacion Diaria")
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)
        
        return [result]
    
    except Exception as e:
        # Manejar cualquier excepción que pueda ocurrir durante el proceso
        print(f"Error al generar el informe de distribuidores : {e}")
        return [{"success": False, "error": str(e)}]


#get_order_information_interval

def fetch_rpc_paginated(function_name: str, params: dict, batch_size: int = 1000) -> list:
    """
    Llama un RPC de Supabase que recibe 'offset_val' y 'limit_val' y
    acumula todas las páginas hasta que no lleguen más filas.
    """
    offset = 0
    all_data = []
    while True:
        page_params = {**params, 'offset_val': offset, 'limit_val': batch_size}
        data = supabase.rpc(function_name, page_params).execute()
        rows = data.data or []
        all_data.extend(rows)
        if len(rows) < batch_size:
            break
        offset += batch_size
    return all_data


HOUR_COLUMNS = ['hora_entrega_orden', 'hora_entrada', 'hora_cargue', 'hora_conteo', 'hora_salida']

# Duraciones por etapa (minutos): nombre -> (hora_fin, hora_inicio)
# Mismas definiciones que el reporte de distribuidores.
STAGE_DURATIONS = {
    'tiempo_espera_min': ('hora_entrada', 'hora_entrega_orden'),
    'tiempo_cargue_min': ('hora_cargue', 'hora_entrada'),
    'tiempo_conteo_min': ('hora_conteo', 'hora_cargue'),
    'tiempo_salida_min': ('hora_salida', 'hora_conteo'),
    'tiempo_planta_min': ('hora_salida', 'hora_entrada'),
    'tiempo_total_min': ('hora_salida', 'hora_entrega_orden'),
}
DURATION_COLUMNS = list(STAGE_DURATIONS.keys())

ORDER_TIME_COLUMNS = HOUR_COLUMNS + DURATION_COLUMNS
ORDER_LEVEL_COLUMNS = [
    'orden', 'fecha_programacion', 'jornada', 'placa', 'conductor', 'descripcion', 'estado', 'estado_orden',
]


def _join_list(value):
    """Convierte una lista (array de Postgres) en texto separado por comas."""
    if isinstance(value, list):
        return ', '.join(str(v) for v in value if v is not None)
    return value if value is not None else ''


def _parse_hours(df: pd.DataFrame) -> pd.DataFrame:
    for col in HOUR_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df


def _format_hours(df: pd.DataFrame) -> pd.DataFrame:
    """Horas como texto legible: algunos visores muestran el número serial de Excel."""
    for col in HOUR_COLUMNS:
        if col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%d/%m/%Y %H:%M').fillna('')
    return df


def _add_stage_durations(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula duraciones en minutos; si falta alguna hora queda vacío (no 0)."""
    for name, (end_col, start_col) in STAGE_DURATIONS.items():
        if end_col in df.columns and start_col in df.columns:
            minutes = (df[end_col] - df[start_col]).dt.total_seconds() / 60
            df[name] = minutes.round().astype('Int64')
    return df


def _derive_estado(df: pd.DataFrame, status_col: str = 'estado_orden') -> pd.Series:
    """Estado operativo a partir de las horas (loading_order.status solo trae EN TRANSITO / CANCELADA)."""
    def _estado(row):
        if str(row.get(status_col) or '').upper() == 'CANCELADA':
            return 'CANCELADA'
        if pd.notnull(row.get('hora_salida')):
            return 'DESPACHADO'
        if pd.notnull(row.get('hora_conteo')):
            return 'CONTADO - PENDIENTE SALIDA'
        if pd.notnull(row.get('hora_cargue')):
            return 'CARGADO - EN CONTEO'
        if pd.notnull(row.get('hora_entrada')):
            return 'EN PLANTA - EN CARGUE'
        return 'SIN INGRESO'
    return df.apply(_estado, axis=1)


def fetch_order_information_interval(start_date: str, end_date: str, emails: List[str]):
    try:
        # Aceptar 'YYYY-MM-DD' o DateTime completo ('2026-11-17 16:16:47.000', '2026-11-17T16:16:47')
        start_date = str(start_date).strip()[:10]
        end_date = str(end_date).strip()[:10]

        # Validar formato de fechas (YYYY-MM-DD)
        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
        if start_obj > end_obj:
            raise ValueError("start_date no puede ser mayor que end_date.")

        rows = fetch_rpc_paginated('get_order_information_interval', {
            'start_date': start_date,
            'end_date': end_date,
        })
        df = pd.DataFrame(rows)

        if df.empty:
            raise ValueError("No se encontraron datos para el rango de fechas proporcionado.")

        # Arrays de Postgres -> texto legible en Excel
        for col in ['pedido', 'factura', 'remision']:
            if col in df.columns:
                df[col] = df[col].apply(_join_list)

        # Duraciones por etapa y estado operativo (el status del sistema queda como estado_orden)
        df = _parse_hours(df)
        df = _add_stage_durations(df)
        if 'estado' in df.columns:
            df = df.rename(columns={'estado': 'estado_orden'})
        df['estado'] = _derive_estado(df)

        # Hoja 1: Programación (una fila por producto, sin tiempos)
        df_prog = df.drop(columns=[c for c in ORDER_TIME_COLUMNS + ['estado_orden'] if c in df.columns])

        # Agregar vehículos activos sin programación en el rango
        vehicles = supabase.rpc('get_active_company_vehicles').execute()
        df_v = pd.DataFrame(vehicles.data or [])
        if 'placa' in df_prog.columns and 'plate' in df_v.columns:
            missing = df_v.loc[~df_v['plate'].isin(df_prog['placa']), 'plate']
            if not missing.empty:
                df_prog = pd.concat(
                    [df_prog, pd.DataFrame({'placa': missing.values})],
                    ignore_index=True,
                )

        # Hoja 2: Tiempos por orden (una fila por orden)
        order_cols = [c for c in ORDER_LEVEL_COLUMNS + ORDER_TIME_COLUMNS if c in df.columns]
        df_times = (
            df[order_cols]
            .drop_duplicates(subset='orden')
            .sort_values(['fecha_programacion', 'orden'])
            .reset_index(drop=True)
        )
        df_times = _format_hours(df_times)

        # Nombre de archivo y entrega
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_start = start_date.replace("-", "")
        clean_end = end_date.replace("-", "")
        filename = f'Reporte_programacion_diaria_{clean_start}_{clean_end}_{now}.xlsx'

        buffer = dataframes_to_excel_buffer(
            dfs=[df_prog, df_times],
            sheet_titles=["Programacion", "Tiempos por orden"],
        )
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)

        return [result]

    except Exception as e:
        print(f"Error al generar el reporte de programacion por rango de fechas: {e}")
        return [{"success": False, "error": str(e)}]


#get_consolidated_report_interval

CONSOLIDATED_COLUMNS = [
    'tipo', 'tipo_vehiculo', 'orden', 'fecha', 'cliente', 'placa', 'conductor', 'carroceria',
    'tipo_carga', 'cantidad', 'referencia', 'producto', 'pedido', 'factura', 'remision',
    'estado', 'estado_orden',
] + ORDER_TIME_COLUMNS


def _summary_by(df_orders: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Resumen por grupo: órdenes, vehículos, cantidades y promedio de cada tiempo (en minutos)."""
    grouped = df_orders.groupby(group_col, dropna=False)
    summary = pd.DataFrame({
        'ordenes': grouped['orden'].nunique(),
        'vehiculos': grouped['placa'].nunique(),
        'cantidad': grouped['cantidad_orden'].sum(),
        'despachadas': grouped['estado'].apply(lambda s: int((s == 'DESPACHADO').sum())),
        'con_factura': grouped['factura'].apply(lambda s: int((s.fillna('') != '').sum())),
        'con_remision': grouped['remision'].apply(lambda s: int((s.fillna('') != '').sum())),
    })
    for col in DURATION_COLUMNS:
        if col in df_orders.columns:
            summary[f'prom_{col}'] = grouped[col].apply(lambda s: s.astype('float').mean()).round(1)
    return summary.reset_index()


def fetch_consolidated_interval(start_date: str, end_date: str, emails: List[str]):
    """
    Reporte consolidado (distribuidores + vehículos propios + externos) por rango de fechas.
    Hojas: Consolidado (tabla plana con filtros), Resumen por tipo, Resumen por estado.
    """
    try:
        start_date = str(start_date).strip()[:10]
        end_date = str(end_date).strip()[:10]
        start_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_obj = datetime.strptime(end_date, '%Y-%m-%d')
        if start_obj > end_obj:
            raise ValueError("start_date no puede ser mayor que end_date.")

        rows = fetch_rpc_paginated('get_consolidated_report_interval', {
            'start_date': start_date,
            'end_date': end_date,
        })
        df = pd.DataFrame(rows)

        if df.empty:
            raise ValueError("No se encontraron datos para el rango de fechas proporcionado.")

        for col in ['cliente', 'pedido', 'factura', 'remision', 'conductor']:
            if col in df.columns:
                df[col] = df[col].apply(_join_list)

        # Duraciones se recalculan aquí (incluye tiempo_planta_min) para tener
        # una sola definición compartida con la programación diaria.
        df = _parse_hours(df)
        df = _add_stage_durations(df)
        df['cantidad'] = pd.to_numeric(df['cantidad'], errors='coerce').astype('Int64')

        # Nivel orden (una fila por orden) para los resúmenes
        df_orders = df.copy()
        df_orders['cantidad_orden'] = df_orders.groupby('orden')['cantidad'].transform('sum')
        df_orders = df_orders.drop_duplicates(subset='orden')

        df_tipo = _summary_by(df_orders, 'tipo')
        df_estado = df_orders.pivot_table(
            index='estado', columns='tipo', values='orden', aggfunc='nunique', fill_value=0,
        ).reset_index()
        df_estado.columns.name = None

        # Hoja plana (una fila por producto)
        df_flat = df[[c for c in CONSOLIDATED_COLUMNS if c in df.columns]].copy()
        df_flat = df_flat.sort_values(['fecha', 'tipo', 'orden']).reset_index(drop=True)
        df_flat = _format_hours(df_flat)

        now = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_start = start_date.replace("-", "")
        clean_end = end_date.replace("-", "")
        filename = f'Reporte_consolidado_{clean_start}_{clean_end}_{now}.xlsx'

        buffer = dataframes_to_excel_buffer(
            dfs=[df_flat, df_tipo, df_estado],
            sheet_titles=["Consolidado", "Resumen por tipo", "Resumen por estado"],
            filters=True,
        )
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)

        return [result]

    except Exception as e:
        print(f"Error al generar el reporte consolidado: {e}")
        return [{"success": False, "error": str(e)}]



#report_loading_distribution

def fetch_loading_distribution(date_ref,emails):
    try:
        # Suponiendo que 'get_trucks_control' es un Procedimiento Almacenado en Supabase
        data = supabase.rpc('report_loading_distribution', {'date_ref': date_ref}).execute()
        
        # Convertir el resultado en una lista de diccionarios si se devuelve algún dato
        df = pd.DataFrame(data.data if data.data else [])
        
        # Verificar si el DataFrame está vacío
        if df.empty:
            raise ValueError("No se encontraron datos para la fecha proporcionada.")
        # Verificar si hay valores NA antes de la conversión y llenar con un valor predeterminado o eliminar
        if df[['hora_entrada', 'hora_entrega_orden', 'hora_cargue', 'hora_conteo', 'hora_salida']].isnull().any().any():
            print("Hay valores nulos en las columnas de fecha/hora.")
            # Puedes optar por llenar los valores nulos con una fecha/hora específica o eliminar esas filas
            df.dropna(subset=['hora_entrada', 'hora_entrega_orden', 'hora_cargue', 'hora_conteo', 'hora_salida'], inplace=True)
            # O puedes llenar los valores NA con una fecha/hora que tenga sentido en tu contexto
            # df.fillna({'hora_entrada': fecha_hora_predeterminada, 'hora_entrega_orden': fecha_hora_predeterminada, ...}, inplace=True)

                # Convertir la columna 'hora' a datetime y formatearla para mostrar solo horas y minutos
        #print(df['tiempo_espera']) = df['hora_entrada']- df['hora_entrega_orden']
        df['hora_entrega_orden'] = pd.to_datetime(df['hora_entrega_orden'])
        df['hora_entrada'] = pd.to_datetime(df['hora_entrada'])
        df['hora_cargue'] = pd.to_datetime(df['hora_cargue'])
        df['hora_conteo'] = pd.to_datetime(df['hora_conteo'])
        df['hora_salida'] = pd.to_datetime(df['hora_salida'])
        
        
        df['tiempo_espera'] = ((df['hora_entrada'] - df['hora_entrega_orden']).dt.total_seconds() / 60).astype(int)
        df['tiempo_carque'] = ((df['hora_cargue'] - df['hora_entrada']).dt.total_seconds() / 60).astype(int)
        df['tiempo_conteo'] = ((df['hora_conteo'] - df['hora_cargue']).dt.total_seconds() / 60).astype(int)
        df['tiempo_salida'] = ((df['hora_salida'] - df['hora_conteo']).dt.total_seconds() / 60).astype(int)




        # Generar nombre de archivo con extensión .xlsx
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        clean_date = re.sub(r'[^0-9A-Za-z]', '', str(date_ref))
        filename = f'Informe_distribuidores_{clean_date}_{now}.xlsx'
        
        # Generar Excel en memoria y entregar (SharePoint o Local)
        buffer = dataframe_to_excel_buffer(df, sheet_name="Distribucion")
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)
        
        return [result]
    
    except Exception as e:
        # Manejar cualquier excepción que pueda ocurrir durante el proceso
        print(f"Error al generar el informe de distribuidores : {e}")
        return [{"success": False, "error": str(e)}]



# --- Asumo que estas funciones ya existen en tu código ---
# 1. La función de análisis que devuelve un diccionario de DataFrames
# def analyze_distribution_times(df_input: pd.DataFrame) -> dict:
#     ...
#     return {'by_body_type': pivot_body_type, 'by_load_type': pivot_load_type}
#
# 2. La nueva función para subir múltiples DataFrames
# def dataframes_to_google_sheets(dfs: list[pd.DataFrame], email_shares: list[str], sheet_title: str, credentials_json: str) -> str:
#     ...
#     return sheet_url
#
# --- Asumo que 'supabase' y 'settings' están configurados ---
# import supabase
# import settings
# ---

def fetch_loading_distribution_interval(start_date: str, end_date: str, emails: List[str], batch_size: int = 1000):
    try:
        # Convertir las fechas a objetos datetime y formatearlas
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
        start_date_formatted = start_date_obj.strftime('%d/%m/%Y')
        end_date_formatted = end_date_obj.strftime('%d/%m/%Y')

        offset = 0
        all_data = []

        while True:
            # Obtener datos usando un Procedimiento Almacenado en Supabase con el límite especificado
            data = supabase.rpc('report_loading_distribution_interval', {
                'start_date': start_date, 
                'end_date': end_date, 
                'offset_val': offset, 
                'limit_val': batch_size
            }).execute()

            # Verificar si hay datos
            if not data.data:
                break

            # Agregar los datos a la lista total
            all_data.extend(data.data)

            # Incrementar el offset para la siguiente página
            offset += batch_size

        # Convertir el resultado en un DataFrame
        df = pd.DataFrame(all_data if all_data else [])

        # Obtener la hora actual sin zona horaria y restarle 5 horas
        current_time = datetime.now().replace(tzinfo=None) - timedelta(hours=5)

        # Manejar valores nulos en las columnas de fecha/hora
        columns = ['hora_entrada', 'hora_entrega_orden', 'hora_cargue', 'hora_conteo', 'hora_salida']
        for column in columns:
            df[column] = pd.to_datetime(df[column], errors='coerce')

        # Calcular los tiempos en minutos, asignando 0 a los tiempos donde haya valores nulos
        df['tiempo_espera'] = df.apply(
            lambda row: (row['hora_entrada'] - row['hora_entrega_orden']).total_seconds() / 60 
            if pd.notnull(row['hora_entrada']) and pd.notnull(row['hora_entrega_orden']) else 0, axis=1).astype(int)
        df['tiempo_cargue'] = df.apply(
            lambda row: (row['hora_cargue'] - row['hora_entrada']).total_seconds() / 60 
            if pd.notnull(row['hora_cargue']) and pd.notnull(row['hora_entrada']) else 0, axis=1).astype(int)
        df['tiempo_conteo'] = df.apply(
            lambda row: (row['hora_conteo'] - row['hora_cargue']).total_seconds() / 60 
            if pd.notnull(row['hora_conteo']) and pd.notnull(row['hora_cargue']) else 0, axis=1).astype(int)
        df['tiempo_salida'] = df.apply(
            lambda row: (row['hora_salida'] - row['hora_conteo']).total_seconds() / 60 
            if pd.notnull(row['hora_salida']) and pd.notnull(row['hora_conteo']) else 0, axis=1).astype(int)

        # Calcular el tiempo de total como la suma de los otros tiempos
        df['tiempo_total'] = df['tiempo_espera'] + df['tiempo_cargue'] + df['tiempo_conteo']+df['tiempo_salida']

        # Generar el título de la hoja con la fecha y hora actual
        now = current_time.strftime("%Y%m%d %H:%M")
        sheet_title = f'Informe de distribuidores [ {start_date_formatted} - {end_date_formatted} ] - {now}'

        
        # 1. Realizar los análisis de tiempos
        df_res = analyze_distribution_times(df, 'tiempo_cargue')
        df_por_carroceria = df_res['by_body_type']
        df_por_tipo_carga = df_res['by_load_type']

        # 2. Crear la lista de DataFrames y títulos para las pestañas de Excel
        lista_dfs = [df, df_por_carroceria, df_por_tipo_carga]
        titulos_hojas = ["1. Datos Completos", "2. Resumen Carroceria", "3. Resumen Carga"]
        
        # 3. Generar nombre de archivo con extensión .xlsx
        clean_start = start_date.replace("-", "")
        clean_end = end_date.replace("-", "")
        now_clean = current_time.strftime("%Y%m%d_%H%M%S")
        filename = f'Informe_distribuidores_{clean_start}_{clean_end}_{now_clean}.xlsx'
        
        # 4. Generar Excel en memoria con múltiples pestañas y entregar (SharePoint o Local)
        buffer = dataframes_to_excel_buffer(dfs=lista_dfs, sheet_titles=titulos_hojas)
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)
        
        return [result]

    except Exception as e:
        print(f"Error al generar el informe de distribuidores por rango de fechas: {e}")
        return [{"success": False, "error": str(e)}]


def analyze_distribution_times(df_input: pd.DataFrame, time_column: str) -> dict:
    """
    Analiza un DataFrame de órdenes de carga para calcular tiempos promedio.

    Sigue esta lógica:
    1.  Filtra placas que comienzan con '*'.
    2.  Elimina filas con fechas nulas en columnas clave.
    3.  Convierte columnas de fecha/hora a objetos datetime.
    4.  Extrae el 'dia' (fecha) de 'hora_entrega_orden'.
    5.  Agrupa por 'orden' para consolidar datos, evitando duplicar tiempos.
    6.  Crea una tabla dinámica para el tiempo promedio por 'tipo_carroceria' y 'dia'.
    7.  Crea una tabla dinámica para el tiempo promedio por 'tipo_carga' y 'dia'.

    Parámetros:
    df_input (pd.DataFrame): El DataFrame original cargado del CSV.
    time_column (str): La columna de tiempo a promediar ('tiempo_total' o 'tiempo_cargue').

    Retorna:
    dict: Un diccionario que contiene dos DataFrames (tablas dinámicas):
          'por_carroceria' y 'por_tipo_carga'.
    """
    
    # 1. Copiar y Filtrar
    df = df_input.copy()

    # 1a. Filtrar placas que empiezan por "*"
    df = df[~df['placa'].astype(str).str.startswith('*', na=False)]

    # 1b. Excluir registros con fechas vacías/nulas en columnas clave
    columnas_fecha = [
        'hora_entrega_orden',
        'hora_entrada',
        'hora_salida',
        'hora_cargue',
        'hora_conteo'
    ]
    df = df.dropna(subset=columnas_fecha)

    # 1c. Excluir filas donde el tiempo a analizar es cero o nulo
    df = df[df[time_column].notna() & (df[time_column] > 0)]

    # 2. Conversión de Fechas y Extracción del Día
    for col in columnas_fecha:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    
    df['dia'] = df['hora_entrega_orden'].dt.date

    # 3. Consolidación por Orden
    agg_dict = {
        'dia': 'first',
        'tipo_carroceria': 'first',
        'tipo_carga': 'first',
        time_column: 'first'
    }
    df_agrupado = df.groupby('orden').agg(agg_dict).reset_index()

    # 4. Análisis 1: Tabla Dinámica por Tipo de Carrocería
    pivot_carroceria = df_agrupado.pivot_table(
        index='tipo_carroceria',
        columns='dia',
        values=time_column,
        aggfunc='mean'
    )

    # 5. Análisis 2: Tabla Dinámica por Tipo de Carga
    pivot_carga = df_agrupado.pivot_table(
        index='tipo_carga',
        columns='dia',
        values=time_column,
        aggfunc='mean'
    )

    # 6. Retornar resultados
    return {
        'by_body_type': pivot_carroceria,
        'by_load_type': pivot_carga
    }


#load_report_driver_by_month
#load_report_by_month_and_year
def fetch_load_report_driver_by_month(year:int, month:int,emails):
    try:
        # Suponiendo que 'load_report_by_month_and_year' es un Procedimiento Almacenado en Supabase
        data = supabase.rpc('load_report_by_month_and_year', {'year_ref': year,'month_ref':month}).execute()
        print(data)
        # Convertir el resultado en una lista de diccionarios si se devuelve algún dato
        df = pd.DataFrame(data.data if data.data else [])
        # Verificar si el DataFrame está vacío
        if df.empty:
            raise ValueError("No se encontraron datos para la fecha proporcionada.")
        
        # Suponiendo que 'load_report_by_month_and_year' es un Procedimiento Almacenado en Supabase
        data = supabase.rpc('load_report_driver_by_month', {'year_ref': year,'month_ref':month}).execute()
        print(data)
        # Convertir el resultado en una lista de diccionarios si se devuelve algún dato
        df2 = pd.DataFrame(data.data if data.data else [])
        # Verificar si el DataFrame está vacío
        if df2.empty:
            raise ValueError("No se encontraron datos para la fecha proporcionada.")
        
        dfs = []
        # Convertir la columna 'hora' a datetime y formatearla para mostrar solo horas y minutos
        #print(df['tiempo_espera']) = df['hora_entrada']- df['hora_entrega_orden']
        dfs.append(df2)
        dfs.append(df)


        # Generar nombre de archivo con extensión .xlsx
        now = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f'Informe_incentivos_conductores_{year}_{month}_{now}.xlsx'
        titulos_hojas = ["Incentivos Conductores", "Detalle Mensual"]
        
        # Generar Excel en memoria con múltiples pestañas y entregar (SharePoint o Local)
        buffer = dataframes_to_excel_buffer(dfs=dfs, sheet_titles=titulos_hojas)
        result = sharepoint_service.export_and_deliver(buffer, filename, emails)
        
        return [result]
    
    except Exception as e:
        # Manejar cualquier excepción que pueda ocurrir durante el proceso
        print(f"Error al generar el Informe incentivos conductores : {e}")
        return [{"success": False, "error": str(e)}]