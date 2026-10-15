"""Settings surface shares the main window's theme and visual language."""
from PySide6.QtCore import Qt,QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QDialog,QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTabWidget,QScrollArea,QWidget,QFormLayout,QSpinBox,QLineEdit,QCheckBox,QSlider,QComboBox,QButtonGroup,QMessageBox,QSizeGrip,QFileDialog,QStyle)
from .theme import stylesheet

class SettingsDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setObjectName('settingsDialog');self.setWindowTitle('设置 · 学习通待办助手');self.setWindowFlags(Qt.Dialog|Qt.FramelessWindowHint);self.setAttribute(Qt.WA_TranslucentBackground);self.resize(520,430);self.setMinimumSize(480,360)
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);self.surface=QFrame();self.surface.setObjectName('root');outer.addWidget(self.surface)
        layout=QVBoxLayout(self.surface);layout.setContentsMargins(20,16,20,10);layout.setSpacing(12)
        header=QHBoxLayout();titles=QVBoxLayout();title=QLabel('偏好设置');title.setObjectName('settingsTitle');titles.addWidget(title);subtitle=QLabel('让桌面助手保持你的使用习惯');subtitle.setObjectName('hint');titles.addWidget(subtitle);header.addLayout(titles);header.addStretch();close=self.button(header,'×',self.finish);close.setFixedSize(28,28);layout.addLayout(header)
        self.tabs=QTabWidget();self.tabs.setObjectName('settingsTabs');layout.addWidget(self.tabs,1)
        appearance=self.page('外观');sync=self.page('同步与提醒');account=self.page('账户与数据');toolbox=self.page('百宝箱')
        self.appearance_page(appearance);self.sync_page(sync);self.account_page(account);self.toolbox_page(toolbox)
        footer=QHBoxLayout();note=QLabel('设置仅保存在本机');note.setObjectName('hint');footer.addWidget(note);footer.addStretch();done=self.button(footer,'完成',self.finish);done.setObjectName('primary');layout.addLayout(footer)
        grip=QSizeGrip(self);layout.addWidget(grip,0,Qt.AlignRight);self.update_theme()
    def button(self,layout,label,callback):
        button=QPushButton(label);button.clicked.connect(lambda checked=False:callback());layout.addWidget(button);return button
    def page(self,title):
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setFrameShape(QFrame.NoFrame);content=QWidget();box=QVBoxLayout(content);box.setContentsMargins(0,8,5,4);box.setSpacing(10);scroll.setWidget(content);self.tabs.addTab(scroll,title);return box
    def card(self,layout,title,subtitle=None):
        card=QFrame();card.setObjectName('settingsCard');box=QVBoxLayout(card);box.setContentsMargins(14,12,14,12);box.setSpacing(10);head=QLabel(title);head.setObjectName('sectionTitle');box.addWidget(head)
        if subtitle:
            hint=QLabel(subtitle);hint.setObjectName('hint');hint.setWordWrap(True);box.addWidget(hint)
        layout.addWidget(card);return box
    def appearance_page(self,page):
        cfg=self.owner.cfg;box=self.card(page,'界面主题','主题与主窗口同步，切换后立即生效。');row=QHBoxLayout();box.addLayout(row);self.themes=QButtonGroup(self)
        for label in ('纯白模式','透明模式'):
            button=QPushButton(label);button.setObjectName('themeChoice');button.setCheckable(True);button.setChecked(cfg.get('theme','纯白模式')==label);self.themes.addButton(button);row.addWidget(button);button.clicked.connect(lambda checked=False,label=label:self.change_theme(label))
        line=QHBoxLayout();line.addWidget(QLabel('背景强度'));line.addStretch();self.alpha_label=QLabel();self.alpha_label.setObjectName('hint');line.addWidget(self.alpha_label);box.addLayout(line)
        self.alpha=QSlider(Qt.Horizontal);self.alpha.setObjectName('backgroundStrength');self.alpha.setRange(150,255);self.alpha.setValue(cfg.get('alpha',220));self.alpha.valueChanged.connect(self.change_alpha);box.addWidget(self.alpha)
        behavior=self.card(page,'窗口行为');self.top=QCheckBox('窗口置顶');self.top.setChecked(cfg.get('top',False));behavior.addWidget(self.top)
        form=QFormLayout();form.setHorizontalSpacing(20);self.close_behavior=QComboBox();self.close_behavior.addItems(['询问','后台运行','退出程序']);self.close_behavior.setCurrentText(cfg.get('close','询问'));form.addRow('关闭窗口后',self.close_behavior);behavior.addLayout(form)
        self.autostart=QCheckBox('开机自启动');self.autostart.setChecked(cfg.get('autostart',False));behavior.addWidget(self.autostart);page.addStretch()
    def sync_page(self,page):
        cfg=self.owner.cfg;box=self.card(page,'自动同步','按设定频率更新课程、作业与消息。');form=QFormLayout();self.interval=QSpinBox();self.interval.setRange(5,1440);self.interval.setSuffix(' 分钟');self.interval.setValue(cfg.get('interval',30));form.addRow('同步间隔',self.interval);box.addLayout(form)
        reminders=self.card(page,'桌面提醒','只对有可靠完整截止日期的项目提醒。');self.notify=QCheckBox('启用桌面提醒');self.notify.setChecked(cfg.get('notify',True));reminders.addWidget(self.notify)
        form=QFormLayout();self.hours=QLineEdit(','.join(map(str,cfg.get('hours',[24,2]))));self.hours.setPlaceholderText('24, 2');form.addRow('提前小时',self.hours);reminders.addLayout(form)
        hint=QLabel('可填写多个时间，以逗号分隔，例如 24, 2。');hint.setObjectName('hint');hint.setWordWrap(True);reminders.addWidget(hint);page.addStretch()
    def account_page(self,page):
        owner=self.owner;box=self.card(page,'我的账户','已连接 · 会话由 Windows 系统加密保护' if owner.account else '尚未连接学习通账户');row=QHBoxLayout();box.addLayout(row)
        login=self.button(row,'网页登录 / 切换账户',self.login);login.setObjectName('primary');login.setEnabled(not(owner.worker and owner.worker.isRunning()));self.button(row,'退出登录',self.logout)
        trash=self.card(page,'本地删除记录','右键删除仅隐藏本应用中的条目，不影响学习通。');self.deleted_label=QLabel();self.deleted_label.setObjectName('hint');trash.addWidget(self.deleted_label);self.undo_button=self.button(trash,'撤销上一次删除',self.undo_delete);self.restore_button=self.button(trash,'恢复已删除的课程与作业',self.restore_deleted);self.refresh_deleted()
        storage=self.card(page,'数据管理','清除账户会话、缓存和本地标记，保留界面设置。');clear=self.button(storage,'清除本地数据',lambda:owner.clear_data(self));clear.setObjectName('danger');page.addStretch()
    def toolbox_page(self,page):
        from .tool_widgets import ToolIcon,DoubleClickToolIcon
        from .memory_ui import MemoryController
        row=QHBoxLayout();row.setContentsMargins(4,6,4,0);page.addLayout(row)
        self.geek_open_button=ToolIcon('Geek Uninstaller','卸载电脑中的应用，清理卸载后残留的文件与注册表项目。\n在独立窗口中使用。',lambda:self.owner.cfg,self)
        self.geek_open_button.setIconSize(QSize(32,32));self.geek_open_button.clicked.connect(self.launch_geek);row.addWidget(self.geek_open_button)
        self.memory_button=DoubleClickToolIcon('内存清理','回收工作集和待机缓存。完成后显示本次可用内存净增量，以及当前可用内存。\n部分缓存会在使用时重新载入。',lambda:self.owner.cfg,self);self.memory_button.setIconSize(QSize(32,32))
        from pathlib import Path
        import sys
        base=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1];self.memory_button.setIcon(QIcon(str(base/'assets'/'memory-clean.svg')));row.addWidget(self.memory_button);row.addStretch();row.setSpacing(12)
        if not hasattr(self.owner,'memory_controller'):self.owner.memory_controller=MemoryController(self.owner)
        controller=self.owner.memory_controller;self.memory_button.activated.connect(controller.start);controller.busy_changed.connect(self.memory_busy);self.memory_busy(controller.busy)
        self.refresh_geek();page.addStretch()
    def memory_busy(self,busy):
        self.memory_button.setEnabled(not busy);self.memory_button.note.setText('正在清理，请稍候…' if busy else '双击清理 · 可能需要管理员授权')
    def refresh_geek(self):
        from .toolbox import geek_path
        from pathlib import Path
        import sys
        path=geek_path(self.owner.cfg);ready=path.is_file() and path.suffix.lower()=='.exe'
        base=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
        icon=QIcon(str(base/'assets'/'geek-tool.png'))
        if icon.isNull():icon=self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.geek_open_button.setIcon(icon);self.geek_open_button.note.setText('点击图标打开' if ready else '点击图标选择 geek.exe')
    def choose_geek(self):
        path,_=QFileDialog.getOpenFileName(self,'选择 Geek 程序','','Windows 程序 (*.exe)')
        if not path:return False
        self.owner.cfg['geek_path']=path;self.owner.save_settings();self.refresh_geek();return True
    def launch_geek(self):
        from .toolbox import open_geek,geek_path
        if not geek_path(self.owner.cfg).is_file() and not self.choose_geek():return
        try:open_geek(self.owner.cfg)
        except OSError as error:
            self.refresh_geek()
            if getattr(error,'winerror',None)!=1223:QMessageBox.information(self,'无法打开 Geek','工具暂时无法启动，请检查文件是否可用。')
    def refresh_deleted(self):
        courses=len(self.owner.deleted_items('courses'));homework=len(self.owner.deleted_items('homework'));self.deleted_label.setText(f'课程 {courses} 项  ·  作业 {homework} 项');self.restore_button.setEnabled(bool(courses or homework));self.undo_button.setEnabled(any(entry[0]==self.owner.deletion_namespace() for entry in self.owner.undo_stack))
    def undo_delete(self):self.owner.undo_delete();self.refresh_deleted()
    def restore_deleted(self):self.owner.restore_deleted();self.refresh_deleted()
    def update_theme(self):
        cfg=self.owner.cfg;alpha=cfg.get('alpha',220) if cfg.get('theme','纯白模式')=='透明模式' else 255;self.setStyleSheet(stylesheet(alpha));self.alpha_label.setText(f'{round(cfg.get("alpha",220)/255*100)}%' if cfg.get('theme','纯白模式')=='透明模式' else '透明模式下可调');self.alpha.setEnabled(cfg.get('theme','纯白模式')=='透明模式')
    def change_theme(self,label):
        self.owner.cfg['theme']=label;self.owner.apply_settings();self.owner.save_settings();self.owner.show();self.update_theme()
    def change_alpha(self,value):
        self.owner.cfg['alpha']=value;self.owner.apply_settings();self.owner.save_settings();self.owner.show();self.update_theme()
    def finish(self):
        try:
            hours=sorted(set(float(x.strip()) for x in self.hours.text().replace('，',',').split(',')))
            if not hours or any(not 0<h<=8760 for h in hours):raise ValueError()
        except ValueError:QMessageBox.information(self,'提醒时间无效','请输入大于0且不超过8760的小时数，例如24,2。');self.tabs.setCurrentIndex(1);self.hours.setFocus();return
        try:self.owner.set_autostart(self.autostart.isChecked())
        except OSError:QMessageBox.information(self,'设置失败','无法写入 Windows 自启动项，请稍后重试。');return
        self.owner.cfg.update(interval=self.interval.value(),notify=self.notify.isChecked(),hours=hours,top=self.top.isChecked(),close=self.close_behavior.currentText(),autostart=self.autostart.isChecked());self.owner.apply_settings();self.owner.save_settings();self.owner.show();self.owner.render(preserve_scroll=True);self.accept()
    def login(self):self.accept();self.owner.login()
    def logout(self):
        if self.owner.logout():self.accept()
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and event.position().y()<70:self.windowHandle().startSystemMove()
    def closeEvent(self,event):
        event.ignore();self.finish()
