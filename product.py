# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, Check, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.product.product import STATES, DEPENDS

__all__ = ['Package', 'Template']


class Package(ModelSQL, ModelView):
    'Product Package'
    __name__ = 'product.package'

    product = fields.Many2One('product.template', 'Product', required=True,
        ondelete='CASCADE')
    name = fields.Char('Name', required=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Float('Quantity', required=True,
        domain=[('quantity', '>', 0)], digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])

    @classmethod
    def __setup__(cls):
        super(Package, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('quantity_greater_than_zero', Check(t, t.quantity > 0),
                'Quantity per package must be greater than zero.'),
            ]

    @fields.depends('product')
    def on_change_with_unit_digits(self, name=None):
        if self.product:
            return self.product.default_uom.digits
        return 2

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def default_unit_digits():
        pool = Pool()
        Uom = pool.get('product.uom')
        uom_id = Transaction().context.get('default_uom')
        if uom_id:
            uom = Uom(uom_id)
            return uom.digits
        return 1


class Template:
    __metaclass__ = PoolMeta
    __name__ = 'product.template'

    packages = fields.One2Many('product.package', 'product', 'Packages',
        states=STATES, depends=DEPENDS + ['default_uom'], context={
            'default_uom': Eval('default_uom', 0),
            },)
