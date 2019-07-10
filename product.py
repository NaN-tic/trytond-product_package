# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import functools
from trytond.model import ModelView, ModelSQL, Check, fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.model.exceptions import AccessError
from trytond.tools import grouped_slice


__all__ = ['Package', 'Template']

def check_new_package(func):

    def find_packages(cls, model, products):
        Model = Pool().get(model)
        for sub_records in grouped_slice(products):
            rows = Model.search([
                    ('product', 'in', list(map(int, sub_records))),
                    ('product_package', '=', None),
                    ],
                limit=1, order=[])
            if rows:
                return rows
        return False

    @functools.wraps(func)
    def decorator(cls, vlist):
        Package =  Pool().get('product.package')

        transaction = Transaction()
        if (transaction.user != 0 and transaction.context.get('_check_access')):
            products = list(set([r.get('product') for r in vlist]))
            for model, msg in Package._create_package:
                if find_packages(cls, model, products):
                    raise AccessError(gettext(msg))
        return func(cls, vlist)
    return decorator

def check_no_package(func):

    @functools.wraps(func)
    def decorator(cls, *args):
        Package =  Pool().get('product.package')

        transaction = Transaction()
        if (transaction.user != 0 and transaction.context.get('_check_access')):
            actions = iter(args)
            for records, values in zip(actions, actions):
                for field, msg in Package._modify_no_package:
                    if field in values:
                        if Package.find_packages(records):
                            raise AccessError(gettext(msg))
                        # No packages for those records
                        break
        func(cls, *args)
    return decorator


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
    is_default = fields.Boolean('Default')

    @classmethod
    def __setup__(cls):
        super(Package, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('quantity_greater_than_zero', Check(t, t.quantity > 0),
                'product_package.msg_quantity_greater_than_zero'),
            ]
        cls._modify_no_package = [
            ('quantity', 'product_package.msg_product_package_qty'),
            ]
        cls._create_package = []

    @staticmethod
    def default_unit_digits():
        pool = Pool()
        Uom = pool.get('product.uom')
        uom_id = Transaction().context.get('default_uom')
        if uom_id:
            uom = Uom(uom_id)
            return uom.digits
        return 1

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def default_is_default():
        return True

    @fields.depends('product')
    def on_change_with_unit_digits(self, name=None):
        if self.product and self.product.default_uom:
            return self.product.default_uom.digits
        return 2

    @classmethod
    def validate(cls, packages):
        super(Package, cls).validate(packages)

        products = []
        is_unique = True
        for package in packages:
            if package.is_default:
                for pack in package.product.packages:
                    if pack.is_default:
                        product_id = pack.product.id
                        if product_id in products:
                            is_unique = False
                            break
                        products.append(product_id)

        if not is_unique:
            raise UserError(gettext(
                'product_package.msg_is_default_unique'))

    @classmethod
    @check_new_package
    def create(cls, vlist):
        return super(Package, cls).create(vlist)

    @classmethod
    @check_no_package
    def write(cls, *args):
        super(Package, cls).write(*args)

    @classmethod
    def find_packages(cls, records):
        return False


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    packages = fields.One2Many('product.package', 'product', 'Packages',
        states={
            'readonly': ~Eval('active', True) | ~Bool(Eval('default_uom')),
            }, depends=['active', 'default_uom'], context={
            'default_uom': Eval('default_uom', 0),
            },)
    default_package = fields.Function(fields.Many2One(
        'product.package', 'Default Package'), 'get_default_package')

    def get_default_package(self, name=None):
        if self.packages:
            for package in self.packages:
                if package.is_default:
                    return package
            else:
                return self.packages[0]
