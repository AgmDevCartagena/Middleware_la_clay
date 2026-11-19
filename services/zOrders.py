from helpers.db import connect,query, connectdb
from settings import settings

def  getOrdersAll(CURRENT_ORDER_SYNC:int=0):
    
    conn=connectdb(settings.DB_INVENTARIO)
    if CURRENT_ORDER_SYNC==0:
        sql = """Select  D.Consecutivo as id,D.Estado
                From PedidoDeCliente As D 
                where D.Fecha >= '2023-05-31'
                order by D.Consecutivo ASC """
        data = query(conn=conn, sql=sql)

    else:
        sql = """Select  D.Consecutivo as id,D.Estado
                From PedidoDeCliente As D 
                where  D.Consecutivo >= ? AND YEAR(D.Fecha) >= 2022
                order by D.Consecutivo ASC """
        data = query(conn=conn, sql=sql,params=(CURRENT_ORDER_SYNC,))
        
    if isinstance(data, dict):
        data = [data]
    
    
    return data

def getOrdersChangedSince(since: str):
    """
    Pedidos que tuvieron movimiento en Zeus desde `since` (YYYY-MM-DD), sin importar
    cuándo se crearon:
      - pedidos creados desde esa fecha, o
      - pedidos con una factura (TipoImportador=9) o remisión (TipoImportador=20)
        emitida desde esa fecha.
    """
    sql = """
        SELECT P.Consecutivo AS id
        FROM PedidoDeCliente AS P
        WHERE P.Fecha >= ?
        UNION
        SELECT D.Exportador AS id
        FROM DOCUMENTOSRELACIONADOS AS D
        INNER JOIN PedidoDeCliente AS P ON D.Exportador = P.Consecutivo
        INNER JOIN FacturaDeCliente AS F ON D.Importador = F.Consecutivo
        WHERE D.TipoImportador = 9 AND F.Fecha >= ?
        UNION
        SELECT D.Exportador AS id
        FROM DOCUMENTOSRELACIONADOS AS D
        INNER JOIN PedidoDeCliente AS P ON D.Exportador = P.Consecutivo
        INNER JOIN Remision AS R ON D.Importador = R.Consecutivo
        WHERE D.TipoImportador = 20 AND R.Fecha >= ?
        ORDER BY id DESC
    """
    conn = connectdb(settings.DB_INVENTARIO)
    try:
        data = query(conn=conn, sql=sql, params=(since, since, since))
    finally:
        conn.close()
    if isinstance(data, dict):
        data = [data]
    return data or []

def  getOrderById(id:int):
    
    conn=connectdb(settings.DB_INVENTARIO)
    
    sql = """Select  D.Consecutivo as id,D.Estado
                From PedidoDeCliente As D 
                where D.consecutivo=?
                """
    data = query(conn=conn, sql=sql,params=(id,))

        
    if isinstance(data, dict):
        data = [data]
    
    
    return data

def  getOrder(order_id:int):
    
    sql = """Select  D.Consecutivo as id,D.Fecha,D.FechaEntrega,D.Detalle,D.Estado,D.Cliente,CL.IDTercero,
		CL.RazonCial ,CL.Direccion,CL.Ciudad,CL.Telefono,D.Vendedor,V.NOMBVENDE, D.DespachoDireccion, D.DespachoCliente, D.DespachoCiudad
        From	PedidoDeCliente As D 
		LEFT OUTER JOIN Clientes As CL ON D.Cliente=CL.IDCliente 
		LEFT OUTER JOIN MAEVENDE AS V ON D.Vendedor=V.IDVende
        where D.consecutivo =? 
	     """
    
    conn=connectdb(settings.DB_INVENTARIO)
    data = query(conn=conn, sql=sql,params=(order_id,))
    
    return data


def  getOrderItems(order_id:int):
      
    sql = """
      Select  DI.iden as id,DI.Codigo,D.Consecutivo,
                A.Codigo,A.Nombre As 'NombreArt',A.Presentacion,DI.PorcentajeDcto,DI.PorcentajeIVA,
                Abs(DI.Cantidad) As 'Cantidad',
                 Abs(DI.Aprobado) As 'Aprobado',
                Valorunidad = dbo.fnNuevaValorUnidad(0, DI.ValorUnidad, DI.ValorUnidad2),
        DI.PrecioUnidad as preciounidad,
        (DI.Cantidad-DI.faltantes) as faltantes
    From        PedidoDeCliente As D
                LEFT OUTER JOIN DocumentoItems As DI
                ON D.Consecutivo=DI.Documento And DI.TipoDocumento=7
                LEFT OUTER JOIN Items As I ON DI.Item=I.Codigo
                LEFT OUTER JOIN Articulo As A ON I.Articulo=A.IDArticulo
       Where d.consecutivo = ? """
   
    conn=connectdb(settings.DB_INVENTARIO)
    data = query(conn=conn, sql=sql,params=(order_id,))
     # Verificar si data es un dict y convertirlo a lista si es necesario
    if isinstance(data, dict):
        data = [data]
    return data