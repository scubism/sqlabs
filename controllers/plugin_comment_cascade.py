# -*- coding: utf-8 -*-
from plugin_comment_cascade import CommentCascade
from gluon.tools import Auth
import unittest
from gluon.contrib.populate import populate
import datetime

if request.function == 'test':
    db = DAL('sqlite:memory:')
    
### setup core objects #########################################################
auth = Auth(db)
comment_cascade = CommentCascade(db)
comment_cascade.settings.table_comment_name = 'plugin_comment_cascade_comment'
comment_cascade.settings.extra_fields = {
    'plugin_comment_cascade_comment': 
        [Field('created_on', 'datetime', default=request.now)],
}

### define tables ##############################################################

auth.define_tables()
table_user = auth.settings.table_user

table_target = db.define_table('plugin_comment_cascade_target', 
                    Field('created_on', 'datetime', default=request.now))

comment_cascade.define_tables(str(table_target), str(table_user))

table_comment = comment_cascade.settings.table_comment  

comment_cascade.settings.select_fields = [table_user.ALL, table_comment.ALL]
comment_cascade.settings.select_attributes = dict(
    left=table_user.on(table_user.id==table_comment.user))
comment_cascade.settings.content = lambda r: DIV(
    A(r[table_user].email[:5], _href='#'), 
    XML('<br/>'.join([SPAN(c).xml() for c in r[table_comment].body_text.split('\n')])),
    DIV(TAG['ABBR'](r[table_comment].created_on), _class='comment_actions'),
) 

### populate records ###########################################################
num_users = 3
user_ids = {}
for user_no in range(1, num_users+1):   
    email = 'user%s@test.com' % user_no
    user = db(table_user.email==email).select().first()
    user_ids[user_no] = user and user.id or table_user.insert(email=email)

if db(table_target.created_on<request.now-datetime.timedelta(minutes=30)).count():
    table_target.truncate()
    table_comment.truncate()
    session.flash = 'the database has been refreshed'
    redirect(URL('index'))
for i in range(3-db(table_target.id>0).count()):
    table_target.insert()
    
### demo functions #############################################################
def index():
    user_no = int(request.args(0) or 1)
    user_id = user_ids[user_no]
    comment_cascade_form = comment_cascade.process()
    
    user_chooser = []
    for i in range(1, num_users+1):
        if i == user_no:
            user_chooser.append(SPAN('user%s' % user_no))
        else:
            user_chooser.append(A('user%s' % i, _href=URL('index', args=i)))
    user_chooser = DIV(XML(' '.join([r.xml() for r in user_chooser])), _style='font-weight:bold')
    
    targets = db(table_target.id>0).select()
    _targets = {}
    for target in targets:
        _targets[target.id] = DIV(
            DIV('', _class='comment_bubble'),
            comment_cascade.render_comment_box(user_id, target.id))
        
    style = STYLE("""
.plugin_comment_cascade {word-break:break-all;width:300px;line-height: 1.1em;}
.plugin_comment_cascade ul {list-style-type: none; margin: 0; padding: 0;}
.plugin_comment_cascade li {display: list-item; text-align: -webkit-match-parent;
background-color: #EDEFF4; border-bottom: 1px solid #E5EAF1; margin-top: 2px; padding: 5px 5px 4px;}
.plugin_comment_cascade a {color: #3B5998; text-decoration: none;}
.plugin_comment_cascade_comment a {font-weight: bold; color: #3B5998;text-decoration: none; margin-right:5px;}
.plugin_comment_cascade textarea {margin: 0px 0px -3px 2px; resize: none; border: 1px solid #BDC7D8; overflow: hidden;}
.comment_actions {padding-top: 2px; color: gray; font-size: 11px;}
.comment_bubble {border: solid 7px transparent; border-bottom-color: #E5EAF1; 
   border-top: 0; width: 0; height: 0; overflow: hidden; margin-left: 20px; margin-bottom: -2px;}   

   """)
    return dict(current_user=DIV(user_chooser, DIV(comment_cascade_form, style)),
                targets=_targets,
                unit_tests=[A('basic test', _href=URL('test'))],
                )
                
### unit tests #################################################################
class TestCommentCascade(unittest.TestCase):

    def setUp(self):
        table_comment.truncate()
        
    def test_crud(self):
        for target_id in range(1, 3):
            user_id = 1
            comment_cascade.add_comment(user_id, target_id, 'body_text_1')
            self.assertEqual(comment_cascade.comments_from_target(target_id).select().first().body_text, 'body_text_1')
            
            comment_cascade.add_comment(user_id, target_id, 'body_text_2')
            self.assertEqual(comment_cascade.comments_from_target(target_id).count(), 2)
            
            user_id = 2
            comment_cascade.add_comment(user_id, target_id, 'body_text_3')
            
            comments = comment_cascade.comments_from_target(target_id).select()
            self.assertEqual(len(comments), 3)
            
            comment_cascade.remove_comment(user_id, comments[2])
            self.assertEqual(comment_cascade.comments_from_target(target_id).count(), 2)
            
            self.assertRaises(ValueError, comment_cascade.remove_comment, user_id, comments[1])
            self.assertEqual(comment_cascade.comments_from_target(target_id).count(), 2)
        
def run_test(TestCase):
    import cStringIO
    stream = cStringIO.StringIO()
    suite = unittest.TestLoader().loadTestsFromTestCase(TestCase)
    unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return stream.getvalue()
    
def test():
    return dict(back=A('back', _href=URL('index')),
                output=CODE(run_test(TestCommentCascade)))