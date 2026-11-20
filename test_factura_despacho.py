"""
Prueba SOLO LECTURA de la regla "factura por despacho" para el reporte consolidado.

No escribe nada en Supabase ni en Zeus:
  1. Lee el reporte actual desde Supabase (RPC get_consolidated_report_interval, sin cambios),
     con MARGEN_DIAS extra a cada lado para no asignar facturas de despachos fuera del rango.
  2. Lee de Zeus las facturas de esos pedidos con su fecha (FacturaDeCliente.Fecha).
  3. Aplica la regla en pandas y genera un Excel local para comparar.

Regla (por pedido; la factura puede salir el día antes o después del despacho):
  1. Emparejar 1:1 órdenes de cargue y facturas, primero las más cercanas en días
     (máx. MAX_DIF_DIAS) y respetando el orden: salida más temprana <-> factura menor.
  2. Facturas sobrantes -> a la orden más cercana del mismo pedido (mismo tope de días).
  Órdenes canceladas no reciben factura.

Uso:
    # con acceso ODBC a Zeus
    python test_factura_despacho.py 2026-11-01 2026-11-17
    # sin acceso: exportar a Excel/CSV la consulta SQL_EXPORT (abajo) y pasar el archivo
    python test_factura_despacho.py 2026-11-01 2026-11-17 facturas_zeus.xlsx
"""
import sys
from datetime import datetime, timedelta

import pandas as pd

from services.reports import fetch_rpc_paginated
from services.factura_despacho import (
    MARGEN_DIAS, MAX_DIF_DIAS, _split, _clean_report, fetch_facturas_zeus, match_facturas, build_facturas,
)

# Consulta de SOLO LECTURA para correr a mano en Zeus (SSMS u otra herramienta) y
# exportar el resultado. Rango con margen de una semana a cada lado del reporte.
SQL_EXPORT = """
SELECT D.Exportador AS pedido, FDC.Documento AS factura,
       CONVERT(varchar(10), FDC.Fecha, 23) AS fecha_factura
FROM DOCUMENTOSRELACIONADOS AS D
INNER JOIN FacturaDeCliente AS FDC ON D.Importador = FDC.Consecutivo
WHERE D.TipoImportador = 9
  AND FDC.Fecha BETWEEN '2026-10-25' AND '2026-11-24'
ORDER BY D.Exportador, FDC.Fecha, FDC.Documento
"""

def load_facturas_file(path: str, pedidos) -> pd.DataFrame:
    """Facturas exportadas a mano desde Zeus (xlsx o csv) con columnas pedido, factura, fecha_factura."""
    if path.lower().endswith('.csv'):
        df = pd.read_csv(path, dtype=str, sep=None, engine='python')
    else:
        df = pd.read_excel(path, dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]
    df = df[['pedido', 'factura', 'fecha_factura']].dropna(subset=['pedido', 'factura'])
    df['pedido'] = df['pedido'].str.strip().str.split('.').str[0]
    # Documento en Zeus viene con ceros a la izquierda (0000064565); Excel suele quitarlos
    df['factura'] = df['factura'].str.strip().str.split('.').str[0].str.zfill(10)
    # ISO (2026-11-03, lo que da SQL_EXPORT) primero; si no, dd/mm/aaaa
    raw = df['fecha_factura'].str.strip().str[:10]
    fecha = pd.to_datetime(raw, format='%Y-%m-%d', errors='coerce')
    fecha = fecha.fillna(pd.to_datetime(raw, format='%d/%m/%Y', errors='coerce'))
    df['fecha_factura'] = fecha.dt.date
    sin_fecha = df['fecha_factura'].isna().sum()
    if sin_fecha:
        print(f"ADVERTENCIA: {sin_fecha} facturas con fecha no reconocida (se ignoran)")
    return df[df['pedido'].isin({str(p) for p in pedidos})]


def main(start_date: str, end_date: str, facturas_file: str = None):
    d0 = datetime.strptime(start_date, '%Y-%m-%d').date()
    d1 = datetime.strptime(end_date, '%Y-%m-%d').date()
    wide = fetch_rpc_paginated('get_consolidated_report_interval', {
        'start_date': str(d0 - timedelta(days=MARGEN_DIAS)),
        'end_date': str(d1 + timedelta(days=MARGEN_DIAS)),
    })
    df = _clean_report(wide)
    in_range = pd.to_datetime(df['fecha']).dt.date.between(d0, d1)
    print(f"Reporte actual: {df[in_range]['orden'].nunique()} órdenes en rango "
          f"({df['orden'].nunique()} con margen de {MARGEN_DIAS} días)")

    pedidos = {p for v in df['pedido'] for p in _split(v)}
    if facturas_file:
        df_fact = load_facturas_file(facturas_file, pedidos)
    else:
        df_fact = fetch_facturas_zeus(pedidos)
    print(f"Facturas en Zeus para {len(pedidos)} pedidos: {len(df_fact)}")

    out_all = match_facturas(df, df_fact)
    out = out_all[pd.to_datetime(out_all['fecha']).dt.date.between(d0, d1)].reset_index(drop=True)
    print(out['regla'].value_counts().to_string())

    facturas = build_facturas(out_all, df_fact, d0, d1)
    sin_placa = (facturas['placa'] == '').sum()
    print(f"Facturas: {len(facturas)} ({len(facturas) - sin_placa} con camión, {sin_placa} sin camión en ±{MAX_DIF_DIAS} días)")

    fname = f"prueba_factura_despacho_{start_date.replace('-', '')}_{end_date.replace('-', '')}_{datetime.now():%H%M%S}.xlsx"
    with pd.ExcelWriter(fname) as xw:
        facturas.to_excel(xw, sheet_name='Facturas', index=False)
        out.to_excel(xw, sheet_name='Resumen por orden', index=False)
    print(f"Generado: {fname}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
