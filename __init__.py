#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from .wizard_facturador import CrearFacturasStart, CrearFacturas, CrearFacturasExito
from .invoice import Invoice
#from .resumen import ResumenCreacion
#from .autorizar_fe import AutorizarFeStart, AutorizarFe
#from .wizard_nc import notacreditoStart, notacreditoExito, notacredito



def register():
    Pool.register(
        CrearFacturasStart,
        CrearFacturasExito, 
        Invoice,        
        module='policoop_facturador', type_='model')

    Pool.register(
        CrearFacturas,
        #AutorizarFe,
        #notacredito,
        module='policoop_facturador', type_='wizard')
