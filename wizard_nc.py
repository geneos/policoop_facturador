#-*- coding: utf-8 -*-
from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval, And, Bool, Equal, Not, Or
import datetime
from decimal import Decimal


class notacreditoStart(ModelView):
    'notacredito Start'
    __name__ = 'sigcoop_wizard_ventas.notacredito.start'
    tipoemi = fields.Selection([
        ('otro','Otro'),
        ('porid','Por numero de ID'),
        ('portarifa', 'Por Tarifa')
        ], 'Tipo de Emision', required=True)

    desdeid = fields.Integer('Desde ID',
        states={'required': Equal(Eval('tipoemi'),'porid')})
 
    hastaid = fields.Integer('Hasta ID',
        states={'required': Equal(Eval('tipoemi'),'porid')})

    servicio = fields.Many2One('product.category', 'Tipo de servicio', required=True,
        on_change=['servicio', 'mismocesp'])
    servicio_char = fields.Char('servicio_char')

    periodo = fields.Many2One('sigcoop_periodo.periodo', 'Periodo',
        states={'required': Equal(Eval('tipoemi'),'portarifa')},
        domain=[ ('category', '=', Eval('servicio'))])

    lista_precios = fields.Many2One('product.price_list', 'Tarifa',
                states={'required': Equal(Eval('tipoemi'),'portarifa')},
                domain = [
                    ('servicio', '=', Eval('servicio')),
                    ('tarifa_oculta', '=', False )])

    consumo_cero = fields.Boolean('NC de Facturas con consumo cero', select=False,
                    states={'readonly': Not(Equal(Eval('servicio_char'),'Energia') |
                            Equal(Eval('servicio_char'),'Agua'))
                    })

    mismocesp = fields.Boolean('Usar CESP y Fecha de la factura', select=False,
        states={'readonly': Not(Equal(Eval('servicio_char'),'Energia') |
                            Equal(Eval('servicio_char'),'Agua'))
    })
    numerocesp = fields.Many2One('account.cesp', 'C.E.S.P.',
        states={'required': Equal(Eval('servicio_char'),'Energia') |
                            Equal(Eval('servicio_char'),'Agua'),
                'readonly': Or(Bool(Eval('mismocesp')), Not(Equal(Eval('servicio_char'),'Energia') |
                            Equal(Eval('servicio_char'),'Agua'))),
    })

    fecha_nc = fields.Date('Fecha de Nota de Credito',
        states={'required': Equal(Eval('servicio_char'),'Energia') |
                            Equal(Eval('servicio_char'),'Agua'),
                'readonly': Bool(Eval('mismocesp')),
    })


    def on_change_servicio(self):
        serv=''
        ret={}
        if (self.servicio and self.servicio.name):
            serv=self.servicio.name
        if (self.servicio.name!='Energia') or (self.servicio.name!='Agua'):
            ret['mismocesp']=False

        ret['servicio_char']=serv
 
        return ret
 


class notacreditoExito(ModelView):
    'notacredito Exito'
    __name__ = 'sigcoop_wizard_ventas.notacredito.exito'
    resumen = fields.Text('Resumen', readonly=True)



class notacredito(Wizard):
    'notacredito'
    __name__ = 'sigcoop_wizard_ventas.notacredito'

    start = StateView('sigcoop_wizard_ventas.notacredito.start',
        'sigcoop_wizard_ventas.notacredito_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Generar', 'crear', 'tryton-ok', default=True),
            ])

    confirmar = StateView('sigcoop_wizard_ventas.notacredito.exito',
        'sigcoop_wizard_ventas.notacredito_resumen_view_form', [
            Button('Ok', 'end', 'tryton-ok', default=True),
            ])

    exito = StateView('sigcoop_wizard_ventas.notacredito.exito',
        'sigcoop_wizard_ventas.notacredito_resumen_view_form', [
            Button('Volver', 'start', 'tryton-ok', default=True),
            Button('Ok', 'generar', 'tryton-ok'),
            ])
 
    crear = StateTransition()
    generar = StateTransition()


    def default_exito(self, fields):
        texto = self.exito.resumen
        self.exito.resumen = False

        return {
                'resumen': texto,
                }


    def transition_crear(self):
        self.ejecutar_nc()
        return 'exito'

    def transition_generar(self):
        self.generar_notas_de_creditos()
        return 'end'
 


    def ejecutar_nc(self):
        if self.start.tipoemi=='porid':
            query = '''SELECT ac.id, ac.number  from account_invoice ac
                        left join sigcoop_suministro_suministro ss on ss.id=ac.suministro
                        where ac.state in ('posted') and ac.type = 'out_invoice'
                        and ac.id between \'%s\' and \'%s\'
                        and ss.servicio = \'%s\'
                        order by ac.id ''' % (self.start.desdeid, self.start.hastaid, self.start.servicio.id)
        elif self.start.consumo_cero:
            #genero NC para las facturas con cero consumo
            query = '''SELECT ac.id, ac.number  from account_invoice ac
                        left join sigcoop_suministro_suministro ss on ss.id=ac.suministro
                        join sigcoop_consumos_consumo c on c.invoice = ac.id
                        where ac.state in ('posted') and ac.type = 'out_invoice'
                        and c.consumo_neto = 0
                        and ss.servicio = \'%s\'
                        and ac.periodo = \'%s\'
                        order by ac.id  ''' % (self.start.servicio.id, self.start.periodo.id)
        else:
            query = '''SELECT ac.id, ac.number  from account_invoice ac
                        left join sigcoop_suministro_suministro ss on ss.id=ac.suministro
                        where ac.state in ('posted') and ac.type = 'out_invoice'
                        and ss.servicio = \'%s\'
                        and ss.lista_precios = \'%s\'
                        and ac.periodo = \'%s\'
                        order by ac.id ''' % (self.start.servicio.id, self.start.lista_precios.id, self.start.periodo.id)

        cursor = Transaction().cursor
        cursor.execute(query)
        facturas = cursor.fetchall()

        self.exito.resumen = "Se van a generar notas de creditos para las siguientes facturas: %s" % map(lambda x: str(x[1]), facturas)
        return 'exito'

 
    def generar_notas_de_creditos(self):
        if self.start.tipoemi=='porid':
            query = '''SELECT ac.id  from account_invoice ac
                        left join sigcoop_suministro_suministro ss on ss.id=ac.suministro
                        where ac.state in ('posted') and ac.type = 'out_invoice'
                        and ac.id between \'%s\' and \'%s\'
                        and ss.servicio = \'%s\'
                        order by ac.id ''' % (self.start.desdeid, self.start.hastaid, self.start.servicio.id)
 
        elif self.start.consumo_cero:
            #genero NC para las facturas con cero consumo
            query = '''SELECT ac.id  from account_invoice ac
                        left join sigcoop_suministro_suministro ss on ss.id=ac.suministro
                        join sigcoop_consumos_consumo c on c.invoice = ac.id
                        where ac.state in ('posted') and ac.type = 'out_invoice'
                        and c.consumo_neto = 0
                        and ss.servicio = \'%s\'
                        and ac.periodo = \'%s\'
                        order by ac.id  ''' % (self.start.servicio.id, self.start.periodo.id)
        else:
            query = '''SELECT ac.id  from account_invoice ac
                        left join sigcoop_suministro_suministro ss on ss.id=ac.suministro
                        where ac.state in ('posted') and ac.type = 'out_invoice'
                        and ss.servicio = \'%s\'
                        and ss.lista_precios = \'%s\'
                        and ac.periodo = \'%s\'
                        order by ac.id ''' % (self.start.servicio.id, self.start.lista_precios.id, self.start.periodo.id)


        cursor = Transaction().cursor
        cursor.execute(query)
        facturas = cursor.fetchall()
 
        pool = Pool()
        Invoices = pool.get('account.invoice')

        for fac in facturas:

            invoices = Invoices.search([
                ('id', '=', fac)
            ])

            for invoice in invoices:
                if invoice.payment_lines:
                    self.raise_user_error('refund_with_payement',
                        (invoice.rec_name,))
                if invoice.type in ('in_invoice', 'in_credit_note'):
                    self.raise_user_error('refund_supplier', invoice.rec_name)

            print "Creando nota de credito para la factura", invoice.number

 
            if self.start.servicio.name=='Energia' or self.start.servicio.name=='Agua':
                if not self.start.mismocesp:
                    credit_invoices = Invoices.credit(invoices, refund=True,
                        cesp=self.start.numerocesp, fecha_nc=self.start.fecha_nc)
                #elif (not self.start.mismocesp) and (self.start.fecha_nc):
                #    credit_invoices = Invoices.credit(invoices, refund=True,
                #        cesp=None, fecha_nc=self.start.fecha_nc)
                else:
                    credit_invoices = Invoices.credit(invoices, refund=True,
                        cesp=None, fecha_nc=None)
            else:
                credit_invoices = Invoices.credit(invoices, refund=True,
                        cesp=None, fecha_nc=self.start.fecha_nc)
 
