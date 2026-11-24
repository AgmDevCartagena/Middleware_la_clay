"""
Factura por despacho: asigna a cada orden de cargue las facturas (de Zeus) que salieron
en ese camión, en vez de todas las facturas del pedido.

Regla (por pedido; la factura puede salir el día antes o después del despacho):
  1. Emparejar 1:1 órdenes de cargue y facturas, primero las más cercanas en días
     (máx. MAX_DIF_DIAS) y respetando el orden: salida más temprana <-> factura menor.
  2. Facturas sobrantes -> a la orden más cercana del mismo pedido (mismo tope de días).
  3. Orden que quedó sin factura -> la última factura de su pedido emitida hasta su salida
     (o la primera posterior), aunque otro camión también la lleve: una factura puede
     cubrir varios viajes.
  Órdenes canceladas no reciben factura.

Las órdenes se deben consultar con MARGEN_DIAS extra a cada lado del rango para no
asignar facturas de despachos que quedan fuera del rango.
"""
import pandas as pd

from helpers.db import connectdb, query
from settings import settings

MAX_DIF_DIAS = 3
MARGEN_DIAS = 7

SQL_FACTURAS = """
    SELECT D.Exportador AS pedido, FDC.Documento AS factura, FDC.Fecha AS fecha_factura
    FROM DOCUMENTOSRELACIONADOS AS D
    INNER JOIN FacturaDeCliente AS FDC ON D.Importador = FDC.Consecutivo
    WHERE D.TipoImportador = 9 AND D.Exportador IN ({marks})
"""


# Remisiones del pedido con su fecha; se excluyen las revertidas y sus reversiones.
SQL_REMISIONES = """
    SELECT D.Exportador AS pedido, CAST(R.Consecutivo AS varchar) AS factura, R.Fecha AS fecha_factura
    FROM DOCUMENTOSRELACIONADOS AS D
    INNER JOIN Remision AS R ON D.Importador = R.Consecutivo
    WHERE D.TipoImportador = 20 AND D.Exportador IN ({marks})
      AND ISNULL(R.Estado, '') NOT IN ('Revertido', 'Reversion')
"""


def _split(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None]
    return [p.strip() for p in str(value or '').split(',') if p.strip()]


def fetch_remisiones_zeus(pedidos, chunk=500):
    """Remisiones (con fecha) de los pedidos dados, leídas de Zeus. Mismas columnas que
    fetch_facturas_zeus (la remisión va en 'factura') para reutilizar la misma regla."""
    return fetch_facturas_zeus(pedidos, chunk, sql=SQL_REMISIONES)


def fetch_facturas_zeus(pedidos, chunk=500, sql=SQL_FACTURAS):
    """Facturas (con fecha) de los pedidos dados, leídas de Zeus."""
    pedidos = sorted({int(p) for p in pedidos})
    rows = []
    conn = connectdb(settings.DB_INVENTARIO)
    try:
        for i in range(0, len(pedidos), chunk):
            part = pedidos[i:i + chunk]
            data = query(conn=conn, sql=sql.format(marks=','.join('?' * len(part))), params=tuple(part))
            if isinstance(data, dict):
                data = [data]
            rows.extend(data or [])
    finally:
        conn.close()
    df = pd.DataFrame(rows, columns=['pedido', 'factura', 'fecha_factura'])
    df['pedido'] = df['pedido'].astype(str)
    df['fecha_factura'] = pd.to_datetime(df['fecha_factura']).dt.date
    return df


def _assign_pedido(los: list, facts: list) -> list:
    """los: [(orden, dispatch_day)] ordenadas por salida; facts: [(factura, fecha)] ordenadas por número.
    Devuelve [(orden, factura, dif_dias)]."""
    cands = []
    for i, (orden, day) in enumerate(los):
        for j, (fac, fdate) in enumerate(facts):
            dif = (fdate - day).days
            if abs(dif) <= MAX_DIF_DIAS:
                cands.append((abs(dif), abs(i - j), i, j, dif))
    cands.sort()
    used_lo, used_f, out = set(), set(), []
    # Paso 1: 1:1 por cercanía
    for _, _, i, j, dif in cands:
        if i not in used_lo and j not in used_f:
            used_lo.add(i); used_f.add(j)
            out.append((los[i][0], facts[j][0], dif))
    # Paso 2: sobrantes a la orden más cercana
    for _, _, i, j, dif in cands:
        if j not in used_f:
            used_f.add(j)
            out.append((los[i][0], facts[j][0], dif))
    return out


def match_facturas(df_report: pd.DataFrame, df_fact: pd.DataFrame) -> pd.DataFrame:
    """Una fila por orden con:
    - factura_nueva: facturas del camión ("f1, f2")
    - pedido_factura: cada factura con el pedido por el que se asignó ("ped1: f1 | ped2: f2")
    - pares: lista [(pedido, factura)] para armar la hoja Facturas
    - n_facturas y regla (diferencia en días factura - salida)."""
    orders = df_report.drop_duplicates(subset='orden').copy()
    salida = pd.to_datetime(orders['hora_salida'], errors='coerce', format='mixed')
    orders['dispatch_ts'] = salida.fillna(pd.to_datetime(orders['fecha']))
    orders['dispatch_day'] = orders['dispatch_ts'].dt.date

    lp = orders[orders['estado'] != 'CANCELADA'][['orden', 'pedido', 'dispatch_ts', 'dispatch_day']].copy()
    lp['pedido'] = lp['pedido'].apply(_split)
    lp = lp.explode('pedido').dropna(subset=['pedido']).sort_values(['dispatch_ts', 'orden'])

    facts_by_ped = {p: list(g.sort_values('factura')[['factura', 'fecha_factura']].itertuples(index=False, name=None))
                    for p, g in df_fact.groupby('pedido')}
    pairs = []  # (orden, pedido, factura, dif)
    for ped, g in lp.groupby('pedido'):
        los = list(g[['orden', 'dispatch_day']].itertuples(index=False, name=None))
        pairs.extend((o, ped, f, d) for o, f, d in _assign_pedido(los, facts_by_ped.get(ped, [])))
    # Paso 3: una factura puede cubrir varios viajes. Orden sin factura -> la última factura
    # de su pedido emitida hasta el día de salida (o la primera posterior), aunque ya esté
    # en otro camión. Si el pedido tiene una sola factura, todas sus órdenes la llevan.
    con_factura = {p[0] for p in pairs}
    for orden, g in lp[~lp['orden'].isin(con_factura)].groupby('orden'):
        day = g['dispatch_day'].iloc[0]
        cands = [(ped, f) for ped in g['pedido'] for f in facts_by_ped.get(ped, [])]
        antes = [c for c in cands if c[1][1] <= day]
        if antes:
            ped, (fac, fdate) = max(antes, key=lambda c: (c[1][1], c[1][0]))
        elif cands:
            ped, (fac, fdate) = min(cands, key=lambda c: (c[1][1], c[1][0]))
        else:
            continue
        pairs.append((orden, ped, fac, (fdate - day).days))
    m = pd.DataFrame(pairs, columns=['orden', 'pedido', 'factura', 'dif'])

    def _regla(s):
        difs = sorted(set(s))
        if difs == [0]:
            return 'MISMO DIA'
        return 'DIA ' + ', '.join(f'{d:+d}' for d in difs)

    def _por_pedido(g):
        return ' | '.join(f"{ped}: {', '.join(sorted(set(gp['factura'])))}"
                          for ped, gp in g.groupby('pedido', sort=True))

    if m.empty:
        agg = pd.DataFrame(columns=['orden', 'factura_nueva', 'pedido_factura', 'pares', 'n_facturas', 'regla'])
    else:
        rows = []
        for orden, g in m.groupby('orden'):
            rows.append({
                'orden': orden,
                'factura_nueva': ', '.join(sorted(set(g['factura']))),
                'pedido_factura': _por_pedido(g),
                'pares': sorted(set(zip(g['pedido'], g['factura']))),
                'n_facturas': g['factura'].nunique(),
                'regla': _regla(g['dif']),
            })
        agg = pd.DataFrame(rows)

    out = orders[['tipo', 'orden', 'fecha', 'placa', 'pedido', 'estado', 'hora_salida', 'factura']].rename(
        columns={'factura': 'factura_actual'})
    out = out.merge(agg, on='orden', how='left')
    out['regla'] = out['regla'].fillna(out['estado'].map(
        lambda e: 'CANCELADA' if e == 'CANCELADA' else f'SIN FACTURA (±{MAX_DIF_DIAS} dias)'))
    out['factura_nueva'] = out['factura_nueva'].fillna('')
    out['pedido_factura'] = out['pedido_factura'].fillna('')
    out['pares'] = out['pares'].apply(lambda v: v if isinstance(v, list) else [])
    out['n_facturas'] = out['n_facturas'].fillna(0).astype(int)
    return out


def build_facturas(out_all: pd.DataFrame, df_fact: pd.DataFrame, d0, d1) -> pd.DataFrame:
    """Una fila por (factura, pedido, camión): el pedido es el de la orden por el que se asignó.
    Incluye las facturas con fecha en el rango y las asignadas a órdenes del rango
    (la factura puede ser del día antes/después del despacho). Sin camión -> orden/placa vacías."""
    fechas = df_fact.drop_duplicates(subset=['pedido', 'factura'])

    asign = out_all[['orden', 'placa', 'hora_salida', 'fecha', 'pares']].explode('pares').dropna(subset=['pares'])
    asign['pedido'] = asign['pares'].str[0]
    asign['factura'] = asign['pares'].str[1]
    asign = asign.drop(columns='pares').merge(fechas, on=['pedido', 'factura'], how='left')

    orden_en_rango = pd.to_datetime(asign['fecha']).dt.date.between(d0, d1)
    fac_en_rango = pd.to_datetime(asign['fecha_factura']).dt.date.between(d0, d1)
    # Camiones del margen solo si la factura (del rango) no salió en ningún camión del rango
    con_camion_rango = set(asign.loc[orden_en_rango, 'factura'])
    asign = asign[orden_en_rango | (fac_en_rango & ~asign['factura'].isin(con_camion_rango))]

    # Facturas del rango que no salieron en ningún camión: una fila por pedido, sin camión
    sin_camion = fechas[pd.to_datetime(fechas['fecha_factura']).dt.date.between(d0, d1)
                        & ~fechas['factura'].isin(set(asign['factura']))]

    fac = pd.concat([
        asign.rename(columns={'hora_salida': 'salida'})[['factura', 'fecha_factura', 'pedido', 'orden', 'placa', 'salida']],
        sin_camion[['factura', 'fecha_factura', 'pedido']],
    ], ignore_index=True)
    fac['orden'] = fac['orden'].apply(lambda v: '' if pd.isna(v) or v == '' else str(int(float(v))))
    fac['salida'] = pd.to_datetime(fac['salida'], errors='coerce', format='mixed')
    fac = fac.sort_values(['fecha_factura', 'factura', 'pedido', 'salida'], na_position='last')
    fac['salida'] = fac['salida'].dt.strftime('%d/%m/%Y %H:%M')
    fac['fecha_factura'] = pd.to_datetime(fac['fecha_factura']).dt.strftime('%d/%m/%Y')
    return fac[['factura', 'fecha_factura', 'pedido', 'orden', 'placa', 'salida']].fillna('').reset_index(drop=True)


def _clean_report(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ['pedido', 'factura']:
        df[col] = df[col].apply(lambda v: ', '.join(_split(v)))
    return df
