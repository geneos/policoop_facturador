#-*- coding: utf-8 -*-
from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
import logging
import itertools
logger = logging.getLogger('sale')
REQUERIDO = True
from creador_ventas import CreadorVentas
from creador_ventas_viejo import CreadorVentasViejo
from trytond.transaction import Transaction
import datetime
from trytond.pyson import Eval, And, Bool, Equal, Not, Or

class CrearFacturasStart(ModelView):
    'Crear Facturas Start'
    __name__ = 'policoop_facturador.crear_facturas.start'

    tipofac = fields.Selection([
        ('masivo','Masivo'),
        ('individual', 'Individual')
        ], 'Tipo de Facturacion', required=REQUERIDO)

    plan_salud = fields.Many2One('gnuhealth.insurance.plan', 'Tipo de plan de salud')
    fecha_emision_factura = fields.Date('Fecha emision factura', required=REQUERIDO)
    #Obligatorio solo si Individual
    insurance = fields.Many2One('gnuhealth.insurance', 'Asociado')


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
                ('member_exp', '<=', datetime.date.today()),
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
                Transaction().cursor.commit()

        return 'end'
