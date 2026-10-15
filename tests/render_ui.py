import os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from assistant.ui import Window,configure_app
from assistant.settings import SettingsDialog
from tests.test_ui_and_details import MemoryStore
app=QApplication([]);configure_app(app);Path('artifacts/v3').mkdir(parents=True,exist_ok=True);w=Window(MemoryStore());w.load_demo();w.show()
for theme in ['纯白模式','透明模式']:
    w.cfg['theme']=theme;w.apply_settings();w.show()
    for size in [(480,270),(420,240)]:
        w.resize(*size)
        for tab in range(3):
            w.tabs.setCurrentRow(tab);app.processEvents();w.grab().save(f'artifacts/v3/{theme}-{size[0]}-{tab}.png')
    dialog=SettingsDialog(w);dialog.show()
    for tab in range(3):
        dialog.tabs.setCurrentIndex(tab);app.processEvents();dialog.grab().save(f'artifacts/v3/设置-{theme}-{tab}.png')
    dialog.reject()
w.tray.hide();print('v3 screenshots generated')
