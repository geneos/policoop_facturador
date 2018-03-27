#-*- coding: utf-8 -*-
from trytond.pool import Pool
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
import datetime
from decimal import Decimal


class AutorizarFeStart(ModelView):
    'Autorizar Fe Start'
    __name__ = 'policoop_facturador.autorizarfe.start'
    fecha_emision = fields.Date('Fecha Emision')
    pos = fields.Many2One('account.pos', 'Punto de Venta',
        required=True, domain=([('pos_type', '=', 'electronic')]))

 

class AutorizarFe(Wizard):
    'Autorizar Fe'
    __name__ = 'policoop_facturador.autorizarfe'

    start = StateView('policoop_facturador.autorizarfe.start',
        'policoop_facturador.autorizarfe_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Autorizar Comprobantes', 'autorizar', 'tryton-ok', default=True),
            ])
 
    autorizar = StateTransition()


    def transition_autorizar(self):
        self.solictarcae()
        return 'end'


    def confirmarfac(self, factura):
        pool = Pool()
        Invoices = pool.get('account.invoice')
        invoice = Invoices.search([('id','=', factura)])[0]

        invoice.post([invoice])

        Transaction().cursor.commit()



    def solictarcae(self):      

        query = '''SELECT id from account_invoice
                    where state in ('draft','validated')
                    and type in ('out_invoice', 'out_credit_note')
                '''

 
        query += '''and pos = \'%s\' ''' % (self.start.pos.id)

        if self.start.fecha_emision:
            query += '''and invoice_date = \'%s\' ''' % (self.start.fecha_emision)
     
        cursor = Transaction().cursor
        cursor.execute(query)
        invoices = cursor.fetchall()
 

        for item in invoices:
            try:
                self.confirmarfac(item[0])
            except Exception as e:
                self.raise_user_error('Error autorizando factura id: ' + str(item[0]))

            