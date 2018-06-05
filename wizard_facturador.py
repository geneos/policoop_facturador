#-*- coding: utf-8 -*-
from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
import logging
import itertools
logger = logging.getLogger('sale')
REQUERIDO = True     
from trytond.transaction import Transaction
import datetime
from trytond.pyson import Eval, And, Bool, Equal, Not, Or
import sys
import os
from decimal import Decimal, ROUND_DOWN, ROUND_UP, ROUND_HALF_UP
import math

INVOICE_TYPE_AFIP_CODE = {
        ('out', 'A'): ('1', u'01-Factura A'),
        ('out', 'B'): ('6', u'06-Factura B'),
        ('out', 'C'): ('11', u'11-Factura C'),
        ('out', 'E'): ('19', u'19-Factura E'),
        }

class CrearFacturasStart(ModelView):
    'Crear Facturas Start'
    __name__ = 'policoop_facturador.crear_facturas.start'

    tipofac = fields.Selection([
        ('masivo','Masivo'),
        ('individual', 'Individual')
        ], 'Tipo de Facturacion', required=REQUERIDO)

    #Obligatorio solo si Masivo
    plan_salud = fields.Many2One('gnuhealth.insurance.plan', 'Tipo de plan de salud',        
       states={           
           'required': Eval('tipofac') == 'masivo',
            })     


    fecha_emision_factura = fields.Date('Fecha emision factura', required=REQUERIDO)
    #Obligatorio solo si Individual
    insurance = fields.Many2One('gnuhealth.insurance', 'Asociado',        
        states={           
           'required': Eval('tipofac') == 'individual',
            })     



class CrearFacturasExito(ModelView):
    'Crear Facturas Exito'
    __name__ = 'policoop_facturador.crear_facturas.exito'
    resumen = fields.Text('Resumen', readonly=True)

class CrearFacturas(Wizard):
    'Crear Facturas'
    __name__ = 'policoop_facturador.crear_facturas'

    start = StateView('policoop_facturador.crear_facturas.start',
        'policoop_facturador.crear_facturas_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Crear Facturas', 'crear', 'tryton-ok', default=True),
            ])

    exito = StateView('policoop_facturador.crear_facturas.exito',
        'policoop_facturador.crear_facturas_exito_view_form', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    crear = StateTransition()


    def transition_crear(self):
        self.crear_venta_padre()
        return 'exito'

    ''''''''''''''''''''''''''''''''''''''''''
    '''   FUNCIONES VARIAS                 '''
    ''''''''''''''''''''''''''''''''''''''''''


    def default_exito(self, fields):
        """
        Esto lo copiamos de ir/translation.py
        """
        #texto = self.exito.resumen
        #self.exito.resumen = False
        #return {
        #        'resumen': texto,
        #        }
        return {}


    ''''''''''''''''''''''''''''''''''''''''''
    '''   FUNCIONES DE CREACION DE VENTAS  '''
    ''''''''''''''''''''''''''''''''''''''''''

    def crear_venta_padre(self):
        #datos de la empresa
        Company = Pool().get('company.company')
        cuit_policoop = Company(Transaction().context.get('company')).party.vat_number

    
        Insurances = Pool().get('gnuhealth.insurance')
        if self.start.plan_salud:
            filtro_insurance = [
                ('member_exp', '>=', datetime.date.today()),
                ('plan_id', '=', self.start.plan_salud),
            ]
        else:
            filtro_insurance = [
                ('member_exp', '<=', datetime.date.today()),
            ]

        if self.start.tipofac=='individual':
            if self.start.insurance:
                filtro_insurance.append(('id', '=', self.start.insurance.id))

        insurances = Insurances.search(filtro_insurance,
            order=[('id','ASC')])

        if insurances:
            for item in insurances:
                creadorfacturas = CreadorFacturas(self.start.fecha_emision_factura)
                creadorfacturas.crear_venta_padre(item.id)
                #Transaction().cursor.commit()

        return 'end'


class CreadorFacturas(object):
    def __init__(self, fecha_emision_factura):
        self.cantidad_facturas_creadas = 0
        self.fecha_emision_factura = fecha_emision_factura      
    ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
    '''FUNCIONES GENERALES '''
    ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
    def calcular_unit_price(self, quantity, product, price_list, customer, dias_lectura=None):
        return product.get_sale_price([product], quantity)[product.id]
    
    def buscar(self, modelo, atributo, valor):
        search = modelo.search([atributo, '=', valor])
        if search:
            return search[0]
        else:
            return None

    def get_subtotal_cargos(self, sale, tipo, servicio):
        """
        Retornamos el subtotal de los cargos
        """
        subtotal_cargos = 0
        if sale.lines:
            for line in sale.lines:
                if line.servicio == servicio:
                    if line.type == 'line' and line.product.tipo_producto == tipo:
                        if not line.product.sin_subsidio and not line.product.ocultar_en_impresion:
                            subtotal_cargos += Decimal(line.amount).quantize(Decimal(".01"), rounding=ROUND_DOWN)
                            
        return subtotal_cargos

    
    def buscar_pos(self):
        """
        Buscamos el punto de venta que vamos a usar para las facturas.
        Este punto de venta deberia tener un PosSequence para cada tipo de factura (ver INVOICE_TYPE_AFIP_CODE
        en account_invoice_ar/invoice.py).
        """
        Pos = Pool().get('account.pos')
        pos = Pos.search([('pos_type', '=', 'electronic'), ('number', '=', 1)]) 
        return pos[0]
        
        
    ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
    '''FUNCIONES QUE CREAN LINEAS'''
    ''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
    
    #Todas las otras funciones crean con esta funcion
    #Creo la columna servicio, para usar despues en el reporte
    def crear_sale_line(self, amount, product, unit_price, sequence):
        """
        Creamos una linea de ventas de acuerdo a los parametros que recibimos.
        """
        
        SaleLine = Pool().get('sale.line')
        
        #new_line = SaleLine(
        #        product=product,
        #        quantity=Decimal(round(amount,2)),
        #        description=product.name,
        #        unit=product.default_uom,
        #        unit_price = Decimal(unit_price),
        #        sequence = sequence,                
        #        )

        new_line = SaleLine()
        new_line.product = product
        new_line.on_change_product()
        new_line.quantity = Decimal(round(amount,2))
        new_line.on_change_quantity()
        new_line.description = product.name
        new_line.unit = product.default_uom
        new_line.on_change_unit()
        new_line.unit_price = Decimal(unit_price)
        new_line.sequence = sequence

        return new_line

    
    def crear_sale_lines_independientes_consumo(self, party, product_name):
        ret = []
        #Obtenemos los productos que son cargos fijos, de la lista de precios que recibimos como parametro        
        productos = Pool().get('product.product').search([('name','=',product_name)])
        #Chequeo que no haya factura de ese asegurado, posteada, con esa fecha
        for producto in productos:                  
            #Le agrego la sequence = 1 para cargos fijos
            up = producto.list_price
            ret.append(
                self.crear_sale_line(1, producto, up, 1)
            )
        return ret
        

    
    ''''''''''''''''''''''''''''''''''''''
    '''FUNCION MADRE QUE CREA LA VENTA'''
    ''''''''''''''''''''''''''''''''''''''

    def crear_venta_padre(self, insurance_id):
        insurance = Pool().get('gnuhealth.insurance')(insurance_id)             
        Invoice = Pool().get('account.invoice')     
        #Chequeo que no haya factura de ese asegurado, posteada, con esa fecha
        invoice_facturada = Invoice.search([('invoice_date','=', self.fecha_emision_factura), ('insurance','=',insurance_id), ('state','=','posted')])
        
        if not invoice_facturada:
                        
            #VENTA
            Sale = Pool().get('sale.sale')
            party = insurance.name
            pos = self.buscar_pos()
                
            with Transaction().set_context({"customer": party}):
                #Creamos la venta a la que le vamos a asociar las lineas de venta
                descripcion = str(insurance.name.name.encode('utf-8')) + " - " + str(insurance.plan_id.name.name.encode('utf-8'))
                sale = Sale(
                        party = insurance.name,                     
                        description = descripcion,
                        pos = pos
                )
                #Creamos las lineas para los distintos tipos de productos
                sale_lines = []

                #1 Cargos Fijos             
                #Las lineas que no dependen del consumo, solo se crean una vez por venta
                sale_lines.extend(self.crear_sale_lines_independientes_consumo(party, insurance.plan_id.name.name))
                sale.lines = sale_lines
                sale.save()
                sale_lines = []                                                         
                                        
                Tax = Pool().get('account.tax')
               
                for i in sale.lines:                 
                                            
                    tax_browse_records = Tax.search([('name','=', 'IVA 21% Ventas')])
                    #tax_browse_records = Tax.browse([2]) or []                                            
                    i.taxes = tax_browse_records
                    i.save()

                #Controlo que no sea menor a cero el total
                if sale.total_amount >= Decimal('0'):
                
                    #Avanzamos a presupuesto
                    sale.invoice_address = sale.party.address_get(type='invoice')
                    sale.shipment_address = sale.party.address_get(type='delivery')
                    sale.quote([sale])
                    #Avanzamos a confirmado
                    sale.confirm([sale])
                    #Avanzamos a procesado. En este estado se crea la factura
                    #de la venta.                                           
                    sale.process([sale])
                    #Luego de ejecutar el workflow de la venta, la guardamos.
                    sale.save()                         
                    #Seteamos las fechas de creacion, vencimiento de la factura y recargo por vencimiento.
                    #Tambien seteamos el suministro.
                    hoy = datetime.date.today()
                    if sale.invoices:
                        if party.iva_condition == 'responsable_inscripto':
                            kind = 'A'                            
                        else: 
                            kind = 'B'
                                                    
                        sale.invoices[0].invoice_date = self.fecha_emision_factura                      
                        sale.invoices[0].pos = pos                                              
                        
                        sale.invoices[0].save()


                        PosSequence = Pool().get('account.pos.sequence')
                        invoice_type, invoice_type_desc = INVOICE_TYPE_AFIP_CODE[
                                ('out', kind)
                            ]
                        
                        sequences = PosSequence.search([
                            ('pos', '=', pos.id),
                            ('invoice_type', '=', invoice_type)
                        ])

                        sale.invoices[0].invoice_type = sequences[0].id
                        sale.invoices[0].pyafipws_concept = 2 # 2 es servicios

                        original = datetime.datetime.strptime(self.fecha_emision_factura , "%Y/%m/%d")
                        desde = original + datetime.timedelta(days=1)
                        hasta = original + datetime.timedelta(days=31)

                        #sale.invoices[0].pyafipws_billing_start_date = self.fecha_emision_factura
                        #sale.invoices[0].pyafipws_billing_end_date = self.fecha_emision_factura
                        sale.invoices[0].pyafipws_billing_start_date = desde
                        sale.invoices[0].pyafipws_billing_end_date = hasta
                                                                    
                        sale.invoices[0].save()
                        
                        #QUEDA EN BORRADOR
                                                                                    
                        #Transaction().cursor.commit()               

                #self.actualizar_resumen_importacion(sale)

        return True