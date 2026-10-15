import sys,json
if '--memory-clean-helper' in sys.argv:
    from assistant.memory_cleaner import helper_main
    sys.exit(helper_main(sys.argv[sys.argv.index('--memory-clean-helper')+1:]))
from pathlib import Path
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtCore import QTimer,QLockFile
from assistant.ui import Window,LoginDialog,configure_app
from assistant.storage import Store

def main():
    app=QApplication(sys.argv);configure_app(app);app.setApplicationName('XXTTodoAssistant');app.setQuitOnLastWindowClosed(False)
    smoke='--smoke-test' in sys.argv
    if not smoke:
        lockdir=Path(__import__('os').environ.get('LOCALAPPDATA','.'))/'XXTTodoAssistant';lockdir.mkdir(parents=True,exist_ok=True)
        lock=QLockFile(str(lockdir/'application.lock'));lock.setStaleLockTime(0)
        if not lock.tryLock(100):
            QMessageBox.information(None,'程序已在运行','请通过系统托盘中的学习通待办助手图标显示窗口。');return 0
    try:w=Window(Store('artifacts/packaged-smoke.sqlite3') if smoke else None)
    except Exception:
        if smoke:raise
        QMessageBox.critical(None,'本地数据无法读取','加密数据无法读取。请使用原 Windows 用户打开；如需重置，请参阅使用说明。');return 1
    w.show()
    if smoke:
        w.load_demo();browser=LoginDialog(w);browser.show()
        report={'frozen':getattr(sys,'frozen',False),'window_size':[w.width(),w.height()],'browser_loaded':False,'browser_title':''}
        def loaded(ok):
            report['browser_loaded']=ok;report['browser_title']=browser.view.title()
            browser.page.runJavaScript("JSON.stringify({has_input:!!document.querySelector('input'),body_length:document.body.innerText.length})",lambda value:report.update(login_dom=value))
        browser.view.loadFinished.connect(loaded)
        def finish():
            w.store.put('test',{'value':'dpapi-smoke'});report['dpapi_roundtrip']=w.store.get('test')['value']=='dpapi-smoke'
            report['browser_off_record']=browser.profile.isOffTheRecord()
            w.grab().save('artifacts/packaged-main.png');browser.grab().save('artifacts/packaged-login.png')
            Path('artifacts/packaged-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            browser.view.close();browser.page.deleteLater();browser.close();w.tray.hide();w._quitting=True;app.quit()
        QTimer.singleShot(15000,finish)
    return app.exec()
if __name__=='__main__':sys.exit(main())
