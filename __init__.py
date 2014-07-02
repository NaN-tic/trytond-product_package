# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .product import *

def register():
    Pool.register(
        Package,
        Template,
        module='product_package', type_='model')
