import typer
from services.zOrders import getOrdersAll, getOrderItems, getOrder
from commands.sync import sync_orders
#import debugpy
# Habilita la depuración en el puerto 5679
#debugpy.listen(('0.0.0.0', 5678))


app = typer.Typer()

@app.command()
def orders(id: int = 0,
           all: bool = False,
           new: bool = False,
           status: bool = False,
           days: int = None,
           since: str = None
           ):
    """Cargar lista pedidos, pedidos o items de un pedido.

    --status            TODOS los pedidos Pendiente/Parcialmente Satisfecho (sin limite de fecha)
    --status --days N   opcional: solo los de los ultimos N dias
    --since D           pedidos con movimiento en Zeus desde D (creados, facturados o remitidos),
                        sin importar su fecha de creacion: relleno de lo desincronizado
    """
    response=[]

    if(status):
        response = sync_orders(type='Status', days=days, since=since)
    elif(since):
        response = sync_orders(type='Since', since=since)
    
    if(all):
        response = sync_orders(type='All')
    
    if(new):
        response = sync_orders(type='New')
    if(id):
        response = sync_orders(type='One',id=id)  
    
    print(response) 




if __name__ == "__main__":
    app()