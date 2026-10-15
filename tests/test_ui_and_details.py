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
    def populate_scrollable_page(self,kind,page):
        w=self.window;sample=w.data[kind][0]
        w.data[kind]=[dict(sample,id=f'scroll-{n}',title=f'滚动测试 {n:02d}') for n in range(30)]
        w.tabs.setCurrentRow(page);w.render();self.app.processEvents()
        bar=w.scroll.verticalScrollBar();self.assertGreater(bar.maximum(),1000)
        return bar
    def test_delete_and_undo_keep_scroll_position_on_both_pages(self):
        for kind,page in [('courses',0),('homework',1)]:
            with self.subTest(kind=kind):
                bar=self.populate_scrollable_page(kind,page);position=bar.maximum()//2;bar.setValue(position)
                self.window.item_menu(kind,self.window.data[kind][15]).actions()[0].trigger();self.app.processEvents()
                self.assertEqual(bar.value(),position)
                self.window.undo_delete();self.app.processEvents();self.assertEqual(bar.value(),position)
    def test_delete_last_item_clamps_to_new_bottom(self):
        bar=self.populate_scrollable_page('courses',0);old_max=bar.maximum();bar.setValue(old_max)
        self.window.delete_item('courses',self.window.data['courses'][-1]);self.app.processEvents()
        self.assertLess(bar.maximum(),old_max);self.assertGreater(bar.value(),0);self.assertEqual(bar.value(),bar.maximum())
    def test_switching_page_before_restore_does_not_reuse_old_position(self):
        bar=self.populate_scrollable_page('courses',0);bar.setValue(bar.maximum()//2)
        self.window.delete_item('courses',self.window.data['courses'][15]);self.window.tabs.setCurrentRow(1);self.app.processEvents()
        self.assertEqual(bar.value(),0)
    def test_context_menu_deletes_locally_survives_refresh_and_undoes(self):
        w=self.window;item=w.data['courses'][0];menu=w.item_menu('courses',item);menu.actions()[0].trigger()
        self.assertIn(item['id'],w.deleted_items('courses'));self.assertEqual(len(w.data['courses']),1)
        w.load_demo();self.assertIn(item['id'],w.deleted_items('courses'))
        self.assertFalse(any(f.property('recordId')==item['id'] for f in w.scroll.widget().findChildren(__import__('PySide6.QtWidgets',fromlist=['QFrame']).QFrame)))
        from assistant.settings import SettingsDialog
        dialog=SettingsDialog(w);dialog.undo_button.click();self.assertNotIn(item['id'],w.deleted_items('courses'));self.assertFalse(dialog.undo_button.isEnabled());dialog.deleteLater()
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
    def test_memory_icon_requires_double_click_and_blocks_duplicates(self):
        import threading
        from unittest.mock import patch
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        from assistant.settings import SettingsDialog
        from assistant.memory_cleaner import summarize
        w=self.window;dialog=SettingsDialog(w);dialog.tabs.setCurrentIndex(3);dialog.show();self.app.processEvents();release=threading.Event()
        result=summarize({'total':1024**3,'available':100},{'total':1024**3,'available':500},['工作集'],[])
        def cleanup():release.wait(5);return result
        with patch('assistant.memory_ui.run_cleanup',side_effect=cleanup) as clean:
            QTest.mouseClick(dialog.memory_button,Qt.LeftButton);self.assertFalse(w.memory_controller.busy);clean.assert_not_called()
            QTest.mouseDClick(dialog.memory_button,Qt.LeftButton);self.assertTrue(w.memory_controller.busy);self.assertFalse(dialog.memory_button.isEnabled());self.assertFalse(w.memory_controller.start())
            release.set()
            for _ in range(100):
                self.app.processEvents();QTest.qWait(5)
                if not w.memory_controller.busy:break
            self.assertFalse(w.memory_controller.busy);clean.assert_called_once();self.assertTrue(dialog.memory_button.isEnabled());self.assertTrue(w.memory_controller.dialog.isVisible());w.memory_controller.dialog.accept()
        dialog.reject();dialog.deleteLater()
    def test_toolbox_is_icon_only_with_themed_hover_info(self):
        from PySide6.QtCore import QEvent,QPoint,Qt
        from PySide6.QtGui import QHelpEvent
        from assistant.settings import SettingsDialog
        dialog=SettingsDialog(self.window);dialog.tabs.setCurrentIndex(3);dialog.show();self.app.processEvents();button=dialog.geek_open_button
        self.assertEqual(button.text(),'');self.assertEqual(button.toolButtonStyle(),Qt.ToolButtonIconOnly);self.assertFalse(button.info.isVisible())
        self.assertFalse(any(b.text() in ['打开 Geek','选择程序…'] for b in dialog.findChildren(QPushButton)))
        event=QHelpEvent(QEvent.ToolTip,QPoint(20,20),button.mapToGlobal(QPoint(20,20)));self.app.sendEvent(button,event);self.app.processEvents()
        self.assertTrue(button.info.isVisible());self.assertIn('rgba(255,255,255,255)',button.info.styleSheet());self.assertTrue(button.screen().availableGeometry().contains(button.info.geometry()))
        self.app.sendEvent(button,QEvent(QEvent.Leave));self.assertFalse(button.info.isVisible())
        self.window.cfg.update(theme='透明模式',alpha=190);button.show_info();self.assertIn('rgba(255,255,255,190)',button.info.styleSheet())
        button.info.hide();dialog.memory_button.show_info();self.app.processEvents()
        from PySide6.QtWidgets import QLabel
        for label in dialog.memory_button.info.findChildren(QLabel):self.assertGreaterEqual(label.height(),label.heightForWidth(label.width()))
        dialog.hide();self.app.processEvents();self.assertFalse(button.info.isVisible());dialog.deleteLater()
    def test_toolbox_selects_persists_and_opens_utility(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from assistant.settings import SettingsDialog
        w=self.window
        with tempfile.TemporaryDirectory(dir='.') as folder:
            executable=Path(folder).resolve()/'geek.exe';executable.write_bytes(b'test fixture')
            w.cfg['geek_path']=str(executable.parent/'missing.exe');dialog=SettingsDialog(w)
            self.assertIn('百宝箱',[dialog.tabs.tabText(n) for n in range(dialog.tabs.count())]);self.assertTrue(dialog.geek_open_button.isEnabled())
            with patch('assistant.settings.QFileDialog.getOpenFileName',return_value=(str(executable),'Windows 程序 (*.exe)')):dialog.choose_geek()
            self.assertTrue(dialog.geek_open_button.isEnabled());self.assertEqual(w.store.get('settings')['geek_path'],str(executable))
            with patch('assistant.toolbox.os.startfile') as start:
                dialog.geek_open_button.click();start.assert_called_once_with(str(executable))
            with patch('assistant.toolbox.os.startfile',side_effect=OSError('Unavailable')),patch('assistant.settings.QMessageBox.information') as message:
                dialog.geek_open_button.click();message.assert_called_once();self.assertTrue(dialog.geek_open_button.isEnabled())
            dialog.deleteLater()
    def test_toolbox_finds_tool_inside_portable_bundle(self):
        import tempfile,sys
        from pathlib import Path
        from unittest.mock import patch
        from assistant.toolbox import geek_path,open_geek
        with tempfile.TemporaryDirectory(dir='.') as folder:
            bundle=Path(folder).resolve();executable=bundle/'extras'/'geek'/'geek.exe'
            with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS',str(bundle),create=True):
                self.assertEqual(geek_path({}),executable)
                with self.assertRaises(FileNotFoundError):open_geek({})
                executable.parent.mkdir(parents=True);executable.write_bytes(b'test fixture')
                with patch.dict(os.environ,{'LOCALAPPDATA':str(bundle/'local')}),patch('assistant.toolbox.os.startfile') as start:
                    open_geek({});cached=Path(start.call_args.args[0]);self.assertNotEqual(cached,executable);self.assertEqual(cached.read_bytes(),executable.read_bytes())
                    # An existing modified working copy must be repaired from
                    # the embedded resource before it can be executed again.
                    cached.write_bytes(b'changed');open_geek({});self.assertEqual(cached.read_bytes(),executable.read_bytes())
    def test_undo_only_in_settings_and_isolates_accounts(self):
        from assistant.settings import SettingsDialog
        w=self.window;w.account='A';item=w.data['courses'][0];w.delete_item('courses',item)
        self.assertFalse(any('撤销' in b.text() for b in w.findChildren(QPushButton)))
        w.account='B';dialog=SettingsDialog(w);self.assertFalse(dialog.undo_button.isEnabled());dialog.deleteLater()
        w.account='A';dialog=SettingsDialog(w);self.assertTrue(dialog.undo_button.isEnabled());dialog.undo_button.click()
        self.assertFalse(w.deleted_items('courses'));self.assertFalse(dialog.undo_button.isEnabled());self.assertFalse(dialog.restore_button.isEnabled());dialog.deleteLater()
    def test_preview_and_save_use_shared_theme_and_preserve_options(self):
        from assistant.settings import SettingsDialog
        w=self.window;w.set_autostart=lambda enabled:None;dialog=SettingsDialog(w);dialog.show();self.app.processEvents()
        transparent=next(button for button in dialog.themes.buttons() if button.text()=='透明模式');transparent.click();dialog.alpha.setValue(190)
        self.assertEqual(w.cfg['theme'],'透明模式');self.assertEqual(w.store.get('settings')['alpha'],190)
        self.assertIn('rgba(255,255,255,190)',dialog.styleSheet());self.assertIn('rgba(255,255,255,190)',w.root.styleSheet())
        dialog.notify.setChecked(False);dialog.interval.setValue(45);dialog.finish()
        self.assertFalse(w.cfg['notify']);self.assertEqual(w.cfg['interval'],45);self.assertFalse(dialog.isVisible())

class FailedDisplayTests(WindowTestCase):
    def test_overdue_homework_hidden_in_all_filters_and_returns_if_extended(self):
        from PySide6.QtWidgets import QLabel
        from assistant.domain import now,timedelta
        w=self.window;sample=w.data['homework'][0]
        expired=dict(sample,id='expired',title='过期样本',deadline={'kind':'exact','value':(now()-timedelta(hours=1)).isoformat()})
        platform=dict(sample,id='platform-expired',title='平台过期样本',status='已逾期（提交状态未知）',deadline={'kind':'unsupported'})
        unknown=dict(sample,id='unknown',title='日期未知样本',deadline={'kind':'partial','raw':'01-01 12:00'})
        w.data['homework'] += [expired,platform,unknown];w.tabs.setCurrentRow(1)
        def content():return ' '.join(label.text() for label in w.scroll.widget().findChildren(QLabel))
        self.assertNotIn('已逾期',[w.filter.itemText(n) for n in range(w.filter.count())])
        for index in range(w.filter.count()):
            w.filter.setCurrentIndex(index);self.assertNotIn('过期样本',content())
        w.filter.setCurrentIndex(0);self.assertIn('日期未知样本',content());self.assertEqual(len(w.data['homework']),4)
        expired['deadline']['value']=(now()+timedelta(hours=1)).isoformat();w.render();self.assertIn('过期样本',content());self.assertNotIn('平台过期样本',content())
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
