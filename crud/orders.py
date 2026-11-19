
from typing import List, Optional
from helpers.db_supabase import supabase


def upsertOrder(order:dict):
    """Insert/update, debe incluir al key (id) """ 
    data, count = supabase.table('orders').upsert(order).execute()

    return data[1]

#data.extend(data1)
def upsertOrderDocRelations(order_doc_relations:dict):
    """Insert/update, debe incluir al key (id) """ 
    data, count = supabase.table('orders_doc_relations').upsert(order_doc_relations).execute()

    return data[1]

def upsertItemOrder(item:dict):
    
    if item:
     data, count = supabase.table('ordersItems').upsert(item).execute()
     return data[1]
    return []

def deleteItemsOrder(order_id:int):
    
    data, count = data, count = supabase.table('ordersItems').delete().eq('order_id', order_id).execute()

    return data[1]

def fetchOrdersbyStatus(status:Optional[List[str]], since:Optional[str]=None, batch_size:int=1000):
    """
    Pedidos filtrados por estado (None = cualquier estado) y fecha >= since (YYYY-MM-DD).
    Pagina porque Supabase devuelve máximo 1000 filas por consulta.
    Ordenados del más reciente al más antiguo.
    """
    all_rows = []
    offset = 0
    while True:
        q = supabase.table('orders').select('id')
        if status:
            q = q.in_('status', status)
        if since:
            q = q.gte('date', since)
        rows = q.order('date', desc=True).order('id', desc=True).range(offset, offset + batch_size - 1).execute().data or []
        all_rows.extend(rows)
        if len(rows) < batch_size:
            break
        offset += batch_size
    return all_rows