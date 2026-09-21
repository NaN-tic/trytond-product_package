import unittest

from proteus import Model
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):
        activate_modules('product_package')

        ProductUom = Model.get('product.uom')
        ProductTemplate = Model.get('product.template')
        unit, = ProductUom.find([('name', '=', 'Unit')])

        template = ProductTemplate()
        template.name = 'Product'
        template.default_uom = unit
        template.type = 'goods'
        package = template.packages.new()
        package.quantity = 6
        template.save()
        template.reload()
        package, = template.packages
        self.assertEqual(package.rec_name, 'Package of 6 u')

        decimal_package = Model.get('product.package')(quantity=6.5)
        decimal_package.save()
        self.assertEqual(decimal_package.rec_name, 'Package of 6.5')

        package.name = 'Box'
        package.save()
        self.assertEqual(package.rec_name, 'Box')
