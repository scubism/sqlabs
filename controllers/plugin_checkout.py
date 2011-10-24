# -*- coding: utf-8 -*-
from plugin_checkout import Checkout
from plugin_catalog import Catalog
import unittest
from gluon.contrib.populate import populate

if request.function == 'test':
    db = DAL('sqlite:memory:')
    
### setup core objects #########################################################

checkout = Checkout(db)
checkout.settings.table_purchase_order_name = 'plugin_checkout_purchase_order'
checkout.settings.table_line_item = 'plugin_checkout_line_item'
checkout.settings.extra_fields = {
    'plugin_checkout_purchase_order': 
        [Field('billing_address', 'text'),
         Field('shipping_address', 'text'),
         Field('ordered_on', 'datetime', label=T('Ordered on')),
         Field('created_on', 'datetime', default=request.now)],
}

catalog = Catalog(db)
catalog.settings.table_product_name = 'plugin_checkout_product'
catalog.settings.table_variant_name = 'plugin_checkout_variant'
catalog.settings.table_option_group_name = 'plugin_checkout_option_group'
catalog.settings.table_option_name = 'plugin_checkout_option'

### define tables ##############################################################

checkout.define_tables()
table_purchase_order = checkout.settings.table_purchase_order
table_line_item = checkout.settings.table_line_item

catalog.define_tables()
table_product = catalog.settings.table_product
table_variant = catalog.settings.table_variant
table_option_group = catalog.settings.table_option_group
table_option = catalog.settings.table_option

### populate records ###########################################################
import datetime
if db(table_purchase_order.created_on<request.now-datetime.timedelta(minutes=60)).count():
    for table in (table_purchase_order, table_line_item, 
                  table_product, table_variant, table_option_group, table_option):
        table.truncate()
    session.forget(resposne)
    session.flash = 'the database has been refreshed'
    redirect(URL('index'))
    
if not db(table_product.id>0).count():
    option_ids = {}
    id = table_option_group.insert(name='size')
    for option_name in ('small', 'large'):
        _option_id = table_option.insert(option_group=id, name=option_name)
        option_ids[option_name] = _option_id
            
    catalog.add_product(dict(name='product_1', available=True),
                        [dict(sku='product_1_master', price=100, quantity=10,
                              options=[])])
    catalog.add_product(dict(name='product_2', available=True),
                        [dict(sku='product_2_small', price=1000, quantity=3, 
                              options=[option_ids['small']]),
                         dict(sku='product_2_large', price=2000, quantity=1, 
                              options=[option_ids['large']])])
                  
### demo functions #############################################################
def index():
    if not request.args(0):
        products = catalog.get_products_by_query(table_product.id>0)
        products_inner = []
        for product in products:
            fields = [Field('quantity', 'integer', label=T('Quantity'), default=1,
                            requires=IS_INT_IN_RANGE(1, 100))]
            hidden = {}
            if product.option_groups:
                fields.insert(0, 
                      Field('variant', label=':'.join([og.name for og in product.option_groups]),
                      requires=IS_IN_SET([(v.id, ':'.join([o.name for o in v.options]) + (' ($%s)' % v.price))
                                            for v in product.variants],
                                         zero='--- %s ---' % T('Please Select'))))
                 
                price = [v.price for v in product.variants]
                price = '$%s - $%s' % (min(price), max(price))
            else:
                if not product.variants:
                    continue # It won't happen, but is for safe.
                hidden['variant'] = product.variants[0].id
                price = '$%s' % product.variants[0].price
               
            form = SQLFORM.factory(submit_button=T('Add to Cart'),
                                   formname='product_%s' % product.id,
                                   hidden=hidden, *fields)
            if form.accepts(request.vars, formname='product_%s' % product.id):
                variant_id = int(request.post_vars.variant)
                variant = catalog.get_variant(variant_id, load_product=False)
                checkout.add_to_cart(variant_id, variant.price, form.vars.quantity)
                session.flash = T('Added to Cart')
                redirect(URL(args='cart'))
                
            products_inner.append(DIV(H4(product.name), 
                                     H6(T('Sale price'), ' : ', price), 
                                     form))
        products = DIV(*products_inner) 
        
        line_items, total_price = checkout.get_cart()
        cart = dict(total_items=sum(line_items.values() or [0]),
                    total_price='$%s' % total_price,
                    view=A(T('View'), _href=URL(args='cart')))
        
        return dict(cart=cart,
                    products=products,
                    xxx=LOAD('plugin_checkout','hoge',ajax=True),
                    unit_tests=[A('basic test', _href=URL('test'))])
               
    elif request.args(0) == 'cart':
        line_items, _total_price = checkout.get_cart()
        variants = dict((variant_id, catalog.get_variant(variant_id)) 
                            for variant_id in line_items.keys())
        fields = []
        for variant_id, quantity in line_items.items():
            fields.append(Field('quantity_%s' % variant_id, 'ineger',
                    default=quantity, requires=IS_INT_IN_RANGE(1, 100)))
        form = SQLFORM.factory(submit_button=T('Update Cart'),
                               *fields)
        if form.accepts(request.vars, session):
            new_line_items = {}
            new_total_price = 0
            for field_name, quantity in form.vars.items():
                if field_name.startswith('quantity_'):
                    variant_id = int(field_name.split('_')[-1])
                    variant = variants[variant_id]
                    new_line_items[variant_id] = quantity
                    new_total_price += variant.price * quantity
            checkout.update_cart(new_line_items, new_total_price)
            session.flash = T('Updated')
            redirect(URL(args=request.args))
        print line_items
        items_inner = [form.custom.begin]
        sub_total_price = 0
        for variant_id, quantity in line_items.items():
            variant = variants[variant_id]
            sub_total_price += variant.price * quantity
            if variant.product.option_groups:
                option_set = ' :' + ', '.join([og.name + ':' + o.name for og, o 
                    in zip(variant.product.option_groups, variant.options)])
            else:
                option_set = ''
            items_inner.append(DIV(H4(variant.product.name + option_set), 
                  DIV(T('Unit Price'), ' : $%s' % variant.price),
                  DIV(T('Quantity'), form.custom.widget['quantity_%s' % variant_id])))
        items_inner.append(form.custom.submit)
        items_inner.append(form.custom.end)
        
        line_items = DIV(*items_inner) 
        return dict(back=A('back', _href=URL('index')),
                    line_items=line_items,
                    total_price='$%s' % sub_total_price)
          
### unit tests #################################################################
class TestCheckout(unittest.TestCase):

    def setUp(self):
        table_product.truncate()
        
    def test_basic(self):
        # TODO
        raise NotImplementedError
        
def run_test(TestCase):
    import cStringIO
    stream = cStringIO.StringIO()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCase)
    unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return stream.getvalue()
    
def test():
    return dict(back=A('back', _href=URL('index')),
                output=CODE(run_test(TestCheckout)))
        