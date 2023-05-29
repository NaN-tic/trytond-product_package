# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import functools
from trytond.model import ModelView, ModelSQL, Check, fields, sequence_ordered
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
                    ['OR',
                        ('product.template', 'in', list(map(int, sub_records))),
                        ('product', 'in',list(map(int, sub_records)))],
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
            with Transaction().set_context(_check_access=False):
                templates = list(set([r.get('template') for r in vlist
                    if r.get('template')]))
                products = list(set([r.get('product') for r in vlist
                    if r.get('product')]))
                for model, msg in Package._create_package:
                    if (find_packages(cls, model, products) or
                            find_packages(cls, model, templates)):
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


class Package(sequence_ordered(), ModelSQL, ModelView):
    'Product Package'
    __name__ = 'product.package'

    template = fields.Many2One('product.template', "Template",
        ondelete='CASCADE')
    product = fields.Many2One('product.product', "Product", ondelete='CASCADE')
    name = fields.Char('Name', required=True)
    unit = fields.Function(fields.Many2One('product.uom', "Unit"),
        'on_change_with_unit')
    quantity = fields.Float('Quantity', required=True,
        domain=[('quantity', '>', 0)], digits='unit')
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

    @classmethod
    def __register__(cls, module_name):
        table_h = cls.__table_handler__(module_name)

        #Rename product to template
        if (table_h.column_exist('product') and not
                table_h.column_exist('template')):
            table_h.column_rename('product', 'template')
        super().__register__(module_name)

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def default_is_default():
        return True

    @fields.depends('product', '_parent_product.default_uom', )
    def on_change_with_unit(self, name=None):
        if self.product and self.product.default_uom:
            return self.product.default_uom.id

    @classmethod
    def validate(cls, packages):
        super(Package, cls).validate(packages)

        products, templates = [], []
        is_unique = True
        for package in packages:
            if package.is_default:
                if package.template:
                    for pack in package.template.packages:
                        if pack.is_default:
                            template_id = pack.template.id
                            if template_id in templates:
                                is_unique = False
                                break
                            templates.append(template_id)
                if package.product:
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

    packages = fields.One2Many('product.package', 'template', "Packages",
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

    @classmethod
    def copy(cls, templates, default=None):
        pool = Pool()
        Package = pool.get('product.package')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_packages = 'packages' not in default
        default.setdefault('packages', None)
        new_templates = super().copy(templates, default)
        if copy_packages:
            old2new = {}
            to_copy = []
            for template, new_template in zip(templates, new_templates):
                to_copy.extend(
                    package for package in template.packages if not package.product)
                old2new[template.id] = new_template.id
            if to_copy:
                Package.copy(to_copy, {
                        'template': lambda d: old2new[d['template']],
                        })
        return new_templates

    def package_used(self, **pattern):
        # Skip rules to test pattern on all records
        with Transaction().set_user(0):
            template = self.__class__(self)
        for package in template.packages:
            if package.match(pattern):
                yield package


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    packages = fields.One2Many('product.package', 'product', "Packages",
        states={
            'readonly': ~Eval('active', True) | ~Bool(Eval('default_uom')),
            }, depends=['active', 'default_uom'], context={
            'default_uom': Eval('default_uom', 0),
            },)
    default_package = fields.Function(fields.Many2One(
        'product.package', 'Default Package'), 'get_default_package')

    @classmethod
    def __setup__(cls):
        if not hasattr(cls, '_no_template_field'):
            cls._no_template_field = set()
        cls._no_template_field.update(['packages', 'default_package'])

        super(Product, cls).__setup__()

    def get_default_package(self, name=None):
        if self.packages:
            for package in self.packages:
                if package.is_default:
                    return package
            else:
                return self.packages[0]

    @classmethod
    def copy(cls, products, default=None):
        pool = Pool()
        Package = pool.get('product.package')
        if default is None:
            default = {}
        else:
            default = default.copy()

        copy_packages = 'packages' not in default
        if 'product' in default:
            default.setdefault('packages', None)
        new_products = super().copy(products, default)
        if 'product' in default and copy_packages:
            template2new = {}
            product2new = {}
            to_copy = []
            for product, new_product in zip(product, new_products):
                if product.packages:
                    to_copy.extend(product.packages)
                    template2new[product.template.id] = new_product.template.id
                    product2new[product.id] = new_product.id
            if to_copy:
                Package.copy(to_copy, {
                    'product': lambda d: product2new[d['product']],
                    'template': lambda d: template2new[d['template']],
                    })
        return new_products

    def package_used(self, **pattern):
        # Skip rules to test patern on all records
        with Transaction().set_user(0):
            product = self.__class__(self)
        for package in product.packages:
            if package.match(pattern):
                yield package
        pattern['product'] = None
        yield from self.template.package_used(**pattern)
