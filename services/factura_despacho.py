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


def _split(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if v is not None]
    return [p.strip() for p in str(value or '').split(',') if p.strip()]


def fetch_facturas_zeus(pedidos, chunk=500):
    """Facturas (con fecha) de los pedidos dados, leídas de Zeus."""
    pedidos = sorted({int(p) for p in pedidos})
    rows = []
    conn = connectdb(settings.DB_INVENTARIO)
    try:
        for i in range(0, len(pedidos), chunk):
            part = pedidos[i:i + chunk]
            data = query(conn=conn, sql=SQL_FACTURAS.format(marks=','.join('?' * len(part))), params=tuple(part))
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
    """Una fila por orden con factura_nueva, dif_dias (factura - salida) y regla."""
    orders = df_report.drop_duplicates(subset='orden').copy()
    salida = pd.to_datetime(orders['hora_salida'], errors='coerce', format='mixed')
    orders['dispatch_ts'] = salida.fillna(pd.to_datetime(orders['fecha']))
    orders['dispatch_day'] = orders['dispatch_ts'].dt.date

    lp = orders[orders['estado'] != 'CANCELADA'][['orden', 'pedido', 'dispatch_ts', 'dispatch_day']].copy()
    lp['pedido'] = lp['pedido'].apply(_split)
    lp = lp.explode('pedido').dropna(subset=['pedido']).sort_values(['dispatch_ts', 'orden'])

    facts_by_ped = {p: list(g.sort_values('factura')[['factura', 'fecha_factura']].itertuples(index=False, name=None))
                    for p, g in df_fact.groupby('pedido')}
    pairs = []
    for ped, g in lp.groupby('pedido'):
        los = list(g[['orden', 'dispatch_day']].itertuples(index=False, name=None))
        pairs.extend(_assign_pedido(los, facts_by_ped.get(ped, [])))
    # Paso 3: una factura puede cubrir varios viajes. Orden sin factura -> la última factura
    # de su pedido emitida hasta el día de salida (o la primera posterior), aunque ya esté
    # en otro camión. Si el pedido tiene una sola factura, todas sus órdenes la llevan.
    con_factura = {p[0] for p in pairs}
    for orden, g in lp[~lp['orden'].isin(con_factura)].groupby('orden'):
        day = g['dispatch_day'].iloc[0]
        cands = [f for ped in g['pedido'] for f in facts_by_ped.get(ped, [])]
        antes = [f for f in cands if f[1] <= day]
        if antes:
            fac, fdate = max(antes, key=lambda f: (f[1], f[0]))
        elif cands:
            fac, fdate = min(cands, key=lambda f: (f[1], f[0]))
        else:
            continue
        pairs.append((orden, fac, (fdate - day).days))
    m = pd.DataFrame(pairs, columns=['orden', 'factura', 'dif'])

    def _regla(s):
        difs = sorted(set(s))
        if difs == [0]:
            return 'MISMO DIA'
        return 'DIA ' + ', '.join(f'{d:+d}' for d in difs)

    agg = m.groupby('orden').agg(
        factura_nueva=('factura', lambda s: ', '.join(sorted(set(s)))),
        n_facturas=('factura', 'nunique'),
        regla=('dif', _regla),
    ).reset_index() if not m.empty else pd.DataFrame(columns=['orden', 'factura_nueva', 'n_facturas', 'regla'])

    out = orders[['tipo', 'orden', 'fecha', 'placa', 'pedido', 'estado', 'hora_salida', 'factura']].rename(
        columns={'factura': 'factura_actual'})
    out = out.merge(agg, on='orden', how='left')
    out['regla'] = out['regla'].fillna(out['estado'].map(
        lambda e: 'CANCELADA' if e == 'CANCELADA' else f'SIN FACTURA (±{MAX_DIF_DIAS} dias)'))
    out['factura_nueva'] = out['factura_nueva'].fillna('')
    out['n_facturas'] = out['n_facturas'].fillna(0).astype(int)
    return out


def build_facturas(out_all: pd.DataFrame, df_fact: pd.DataFrame, d0, d1) -> pd.DataFrame:
    """Una fila por factura con el camión (orden/placa) en que salió.
    Incluye las facturas con fecha en el rango y las asignadas a órdenes del rango
    (la factura puede ser del día antes/después del despacho). Sin camión -> placa vacía."""
    # factura -> orden asignada (cada factura queda en una sola orden)
    asign = out_all[['orden', 'placa', 'hora_salida', 'fecha', 'pedido', 'factura_nueva']].copy()
    asign['factura'] = asign['factura_nueva'].apply(_split)
    asign['pedido'] = asign['pedido'].apply(_split)
    asign = asign.explode('factura').dropna(subset=['factura']).explode('pedido')
    asign = asign.drop(columns='factura_nueva').rename(columns={'fecha': 'fecha_orden', 'hora_salida': 'salida'})

    # Cruce por (pedido, factura): una factura puede cubrir varios pedidos del mismo camión
    fac = df_fact.drop_duplicates(subset=['pedido', 'factura']).merge(asign, on=['pedido', 'factura'], how='left')
    en_rango = pd.to_datetime(fac['fecha_factura']).dt.date.between(d0, d1)
    orden_en_rango = pd.to_datetime(fac['fecha_orden']).dt.date.between(d0, d1)
    fac = fac[en_rango | orden_en_rango].copy()

    # Si la factura quedó en un camión por un pedido, no repetirla "sin camión" por el otro pedido
    con_camion = set(fac.loc[fac['orden'].notna(), 'factura'])
    fac = fac[fac['orden'].notna() | ~fac['factura'].isin(con_camion)]

    fac['orden'] = fac['orden'].apply(lambda v: '' if pd.isna(v) else str(int(float(v))))
    fac = fac.fillna({'placa': '', 'salida': ''})
    fac = (fac.groupby(['factura', 'orden'], as_index=False)
              .agg(fecha_factura=('fecha_factura', 'first'),
                   placa=('placa', 'first'),
                   salida=('salida', 'first')))
    # Todos los pedidos que cubre la factura (según Zeus)
    pedidos_fac = df_fact.groupby('factura')['pedido'].agg(lambda s: ', '.join(sorted(set(s))))
    fac['pedido'] = fac['factura'].map(pedidos_fac)
    fac = fac.sort_values(['fecha_factura', 'factura', 'salida'])
    fac['salida'] = pd.to_datetime(fac['salida'], errors='coerce', format='mixed').dt.strftime('%d/%m/%Y %H:%M')
    fac['fecha_factura'] = pd.to_datetime(fac['fecha_factura']).dt.strftime('%d/%m/%Y')
    return fac[['factura', 'fecha_factura', 'pedido', 'orden', 'placa', 'salida']].fillna('').reset_index(drop=True)


def _clean_report(rows) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ['pedido', 'factura']:
        df[col] = df[col].apply(lambda v: ', '.join(_split(v)))
    return df
