import os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from assistant.ui import Window,configure_app
from assistant.settings import SettingsDialog
from tests.test_ui_and_details import MemoryStore
app=QApplication([])
# Qt's offscreen plugin needs explicit font registration on Windows.
for name in ['msyh.ttc','msyhbd.ttc']:
    font=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name
    if font.exists():QFontDatabase.addApplicationFont(str(font))
configure_app(app);Path('artifacts/v3').mkdir(parents=True,exist_ok=True);w=Window(MemoryStore());w.load_demo();w.show()
for theme in ['纯白模式','透明模式']:
    w.cfg['theme']=theme;w.apply_settings();w.show()
    for size in [(480,270),(420,240)]:
        w.resize(*size)
        for tab in range(3):
            w.tabs.setCurrentRow(tab);app.processEvents();w.grab().save(f'artifacts/v3/{theme}-{size[0]}-{tab}.png')
    dialog=SettingsDialog(w);dialog.show()
    for tab in range(dialog.tabs.count()):
        dialog.tabs.setCurrentIndex(tab);app.processEvents();dialog.grab().save(f'artifacts/v3/设置-{theme}-{tab}.png')
        if tab==3:
            dialog.geek_open_button.show_info();app.processEvents();dialog.geek_open_button.info.grab().save(f'artifacts/v3/工具介绍-{theme}.png');dialog.geek_open_button.info.hide()
            dialog.memory_button.show_info();app.processEvents();dialog.memory_button.info.grab().save(f'artifacts/v3/内存介绍-{theme}.png');dialog.memory_button.info.hide()
    dialog.reject()
    from assistant.memory_ui import MemoryResultDialog
    from assistant.memory_cleaner import summarize
    example=summarize({'total':32*1024**3,'available':8*1024**3},{'total':32*1024**3,'available':10*1024**3},['工作集','待机缓存'],[])
    result=MemoryResultDialog(w,example);result.show();app.processEvents();result.grab().save(f'artifacts/v3/内存结果-示例数据-{theme}.png');result.accept()
w.tray.hide();print('v3 screenshots generated')
