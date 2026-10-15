import os,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QPushButton,QTextBrowser,QDialog
from assistant.ui import Window,configure_app
from assistant.api import Client
from assistant.domain import deadline_label
class MemoryStore:
    def __init__(self):self.values={}
    def get(self,key,default=None):return self.values.get(key,default)
    def put(self,key,value):self.values[key]=value
    def delete(self,key):self.values.pop(key,None)
class WindowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);configure_app(cls.app)
    def setUp(self):self.window=Window(MemoryStore());self.window.load_demo();self.window.show();self.app.processEvents()
    def tearDown(self):self.window.tray.hide();self.window.hide();self.window.deleteLater();self.app.processEvents()
class UITests(WindowTestCase):
    def test_compact_sidebar_and_no_overview(self):
        self.assertEqual([self.window.tabs.item(i).text() for i in range(self.window.tabs.count())],['课程','作业','消息'])
        self.assertGreater(self.window.width(),self.window.height());self.assertLessEqual(self.window.width()*self.window.height(),420*580*.55)
    def open_detail(self,page,expected):
        self.window.tabs.setCurrentRow(page);self.app.processEvents();captured=[]
        def check():
            dialog=self.app.activeModalWidget()
            if isinstance(dialog,QDialog):
                text=dialog.findChild(QTextBrowser,'detailContent');captured.append(text.toPlainText() if text else '');dialog.accept()
        timer=QTimer();timer.setSingleShot(True);timer.timeout.connect(check);timer.start(50)
        buttons=[b for b in self.window.scroll.widget().findChildren(QPushButton) if b.text()=='查看详情']
        self.assertTrue(buttons);buttons[0].click();self.assertTrue(captured);self.assertIn(expected,captured[0])
    def test_course_detail_button_opens_full_content(self):self.open_detail(0,'状态：未完成')
    def test_homework_detail_button_opens_full_title(self):self.open_detail(1,'第二章课后练习')
class DetailParsingTests(unittest.TestCase):
    def test_actual_header_without_year_is_visible(self):
        class C(Client):
            def __init__(self):pass
            def get(self,url):return type('R',(),{'text':'<h1>作业详情</h1><p>作答时间: 09-30 10:40 至 10-31 23:55</p><script>ignored</script><input value="private-answer">'})()
        result=C().homework_detail({'url':'https://mooc1.chaoxing.com/mooc-ans/mooc2/work/task'})
        self.assertEqual(result['deadline']['kind'],'partial');self.assertIn('10-31 23:55',deadline_label(result['deadline']));self.assertIn('年份未提供',deadline_label(result['deadline']));self.assertNotIn('private-answer',result['detail_text']);self.assertNotIn('ignored',result['detail_text'])
    def test_complete_header_uses_real_end_date(self):
        class C(Client):
            def __init__(self):pass
            def get(self,url):return type('R',(),{'text':'<p>作答时间：2026-09-30 10:40 至 2026-10-31 23:55</p>'})()
        result=C().homework_detail({'url':'https://mooc1.chaoxing.com/mooc-ans/mooc2/work/task'})
        self.assertEqual(result['deadline']['kind'],'exact');self.assertIn('2026-10-31',result['deadline']['value'])

class NoticeTerminalTests(unittest.TestCase):
    def test_verified_null_after_nonempty_cursor_page(self):
        class C(Client):
            def __init__(self):self.n=0
            def request(self,*a,**kw):
                self.n+=1
                data={'status':True,'notices':{'list':[{'idCode':'stable','title':'测试通知','isread':0}],'lastGetId':'next','lastPage':0}} if self.n==1 else {'status':True,'notices':None}
                return type('R',(),{'json':lambda self:data})()
        result=C().notices();self.assertEqual(len(result),1);self.assertEqual(result[0]['id'],'stable')

class CourseStatusTests(unittest.TestCase):
    def test_complete_requires_positive_reliable_total(self):
        from assistant.domain import course_completion
        self.assertEqual(course_completion({'progress':[10,10]}),'已完成')
        self.assertEqual(course_completion({'progress':[4,10]}),'未完成')
        for course in [{'progress':[0,0]},{'progress':[10,10],'stale':True},{'progress':None}]:self.assertEqual(course_completion(course),'完成状态未知')

class DeletionTests(WindowTestCase):
    def test_context_menu_deletes_locally_survives_refresh_and_undoes(self):
        w=self.window;item=w.data['courses'][0];menu=w.item_menu('courses',item);menu.actions()[0].trigger()
        self.assertIn(item['id'],w.deleted_items('courses'));self.assertEqual(len(w.data['courses']),1)
        w.load_demo();self.assertIn(item['id'],w.deleted_items('courses'))
        self.assertFalse(any(f.property('recordId')==item['id'] for f in w.scroll.widget().findChildren(__import__('PySide6.QtWidgets',fromlist=['QFrame']).QFrame)))
        w.undo_button.click();self.assertNotIn(item['id'],w.deleted_items('courses'))
    def test_account_isolation_and_restore(self):
        w=self.window;w.account='A';w.delete_item('homework',w.data['homework'][0]);self.assertTrue(w.deleted_items('homework'))
        w.account='B';self.assertFalse(w.deleted_items('homework'))
        w.account='A';w.restore_deleted();self.assertFalse(w.deleted_items('homework'))
    def test_deleted_homework_does_not_remind(self):
        w=self.window;w.account='A';w.demo=False;item=w.data['homework'][0];w.delete_item('homework',item);messages=[];w.tray.showMessage=lambda *args:messages.append(args);w.remind();self.assertEqual(messages,[])
    def test_course_summary_omits_teacher_task_counts_and_percent(self):
        from PySide6.QtWidgets import QLabel
        texts=' '.join(label.text() for label in self.window.scroll.widget().findChildren(QLabel))
        self.assertNotIn('示例教师',texts);self.assertNotIn('任务点',texts);self.assertNotIn('60%',texts);self.assertIn('未完成',texts);self.assertIn('结束',texts)

class SettingsTests(WindowTestCase):
    def test_preview_and_save_use_shared_theme_and_preserve_options(self):
        from assistant.settings import SettingsDialog
        w=self.window;w.set_autostart=lambda enabled:None;dialog=SettingsDialog(w);dialog.show();self.app.processEvents()
        transparent=next(button for button in dialog.themes.buttons() if button.text()=='透明模式');transparent.click();dialog.alpha.setValue(190)
        self.assertEqual(w.cfg['theme'],'透明模式');self.assertEqual(w.store.get('settings')['alpha'],190)
        self.assertIn('rgba(255,255,255,190)',dialog.styleSheet());self.assertIn('rgba(255,255,255,190)',w.root.styleSheet())
        dialog.notify.setChecked(False);dialog.interval.setValue(45);dialog.finish()
        self.assertFalse(w.cfg['notify']);self.assertEqual(w.cfg['interval'],45);self.assertFalse(dialog.isVisible())

class FailedDisplayTests(WindowTestCase):
    def test_failed_records_hidden_without_removing_cache_and_return_when_recovered(self):
        from PySide6.QtWidgets import QLabel
        w=self.window;course=dict(w.data['courses'][0],id='failed-course',title='失败课程样本',stale=True)
        homework=dict(w.data['homework'][0],id='failed-work',title='失败作业样本',stale=True)
        w.data['courses'].append(course);w.data['homework'].append(homework)
        w.data['errors']={'章节/失败课程样本':'进度查询失败或结构不受支持','作业/失败课程样本':'查询失败'}
        def content():return ' '.join(label.text() for label in w.scroll.widget().findChildren(QLabel))
        w.render();self.assertIn('高等数学',content());self.assertNotIn('失败课程样本',content());self.assertNotIn('进度查询失败',content())
        w.tabs.setCurrentRow(1);self.assertIn('第二章课后练习',content());self.assertNotIn('失败作业样本',content());self.assertNotIn('结构不受支持',content())
        self.assertEqual(len(w.data['courses']),2);self.assertEqual(len(w.data['homework']),2)
        course['stale']=False;homework['stale']=False;w.data['errors']={};w.render();self.assertIn('失败作业样本',content())
        w.tabs.setCurrentRow(0);self.assertIn('失败课程样本',content())
