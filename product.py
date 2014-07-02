# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, ModelSQL, fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.product.product import STATES, DEPENDS

__all__ = ['Package', 'Template']
__metaclass__ = PoolMeta



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
        cls._sql_constraints += [
            ('quantity_greater_than_zero', 'CHECK(quantity > 0)',
                'Quantity per package must be greater than zero.'),
            ]

    @fields.depends('product')
    def on_change_with_unit_digits(self, name=None):
        if self.product:
            return self.product.default_uom.digits
        return 2


class Template:
    __name__ = 'product.template'

    packages = fields.One2Many('product.package', 'product', 'Packages',
        states=STATES, depends=DEPENDS)
