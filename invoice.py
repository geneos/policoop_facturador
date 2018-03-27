from trytond.model import Workflow, ModelView, ModelSQL
from trytond.pool import Pool

__all__ = ['Invoice']

class Invoice(Workflow, ModelSQL, ModelView):
    'Invoice'
    __name__ = 'account.invoice'

    insurance = fields.Many2One('gnuhealth.insurance', 'Asociado')

