import io
import os
import re
from typing import List, Union
import pandas as pd
from openpyxl.utils import get_column_letter

def sanitize_sheet_name(name: str) -> str:
    """
    Limpia caracteres no permitidos por Excel y limita a 31 caracteres.
    Excel prohíbe: [ ] : * ? / \\
    """
    cleaned = re.sub(r'[\\/*?:\[\]]', '_', str(name))
    cleaned = cleaned.strip()
    return cleaned[:31] if cleaned else "Hoja"

def autofit_columns(writer: pd.ExcelWriter, sheet_name: str, df: pd.DataFrame):
    """
    Ajusta automáticamente el ancho de cada columna en función del contenido
    para asegurar una apertura legible del documento.
    """
    try:
        worksheet = writer.sheets[sheet_name]
        for col_idx, col in enumerate(df.columns, start=1):
            # Obtener longitud máxima entre el nombre de columna y los datos
            if not df.empty:
                max_val_len = df[col].astype(str).map(len).max()
            else:
                max_val_len = 0
            header_len = len(str(col))
            max_len = max(max_val_len, header_len) + 4
            
            # Limitar ancho entre 10 y 60 caracteres
            col_width = max(10, min(max_len, 60))
            col_letter = get_column_letter(col_idx)
            worksheet.column_dimensions[col_letter].width = col_width
    except Exception as e:
        # Si falla el autoajuste visual, no debe interrumpir la exportación de datos
        print(f"Aviso al autoajustar columnas en {sheet_name}: {e}")

def dataframe_to_excel_buffer(df: pd.DataFrame, sheet_name: str = "Datos") -> io.BytesIO:
    """
    Convierte un DataFrame de pandas en un buffer en memoria io.BytesIO
    en formato Excel (.xlsx).
    """
    buffer = io.BytesIO()
    clean_sheet_name = sanitize_sheet_name(sheet_name)
    
    # Preparar datos (resetear index si es relevante)
    df_to_write = df.reset_index() if (isinstance(df.index, pd.MultiIndex) or df.index.name) else df
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_to_write.to_excel(writer, sheet_name=clean_sheet_name, index=False)
        autofit_columns(writer, clean_sheet_name, df_to_write)
        
    buffer.seek(0)
    return buffer

def dataframes_to_excel_buffer(dfs: List[pd.DataFrame], sheet_titles: List[str]) -> io.BytesIO:
    """
    Convierte una lista de DataFrames en un libro de Excel con múltiples hojas.
    """
    if len(dfs) != len(sheet_titles):
        raise ValueError(
            f"El número de DataFrames ({len(dfs)}) no coincide con el número de títulos ({len(sheet_titles)})."
        )
        
    buffer = io.BytesIO()
    used_names = set()
    
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        for idx, (df, raw_title) in enumerate(zip(dfs, sheet_titles)):
            base_title = sanitize_sheet_name(raw_title)
            # Evitar colisión de nombres duplicados en pestañas
            sheet_title = base_title
            counter = 1
            while sheet_title.lower() in used_names:
                suffix = f"_{counter}"
                sheet_title = f"{base_title[:31-len(suffix)]}{suffix}"
                counter += 1
            used_names.add(sheet_title.lower())
            
            # Preparar DataFrame (resetear index para que no se pierdan headers en pivots)
            if isinstance(df.index, pd.MultiIndex) or df.index.name:
                df_to_write = df.reset_index()
            else:
                df_to_write = df
                
            df_to_write.to_excel(writer, sheet_name=sheet_title, index=False)
            autofit_columns(writer, sheet_title, df_to_write)
            
    buffer.seek(0)
    return buffer

def save_excel_to_disk(excel_buffer: io.BytesIO, file_path: str) -> str:
    """
    Guarda el buffer de Excel en una ruta de disco local.
    """
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(excel_buffer.getbuffer())
    return file_path
