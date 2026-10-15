"""Asynchronous memory action and a small result surface using the shared theme."""
from PySide6.QtCore import QObject,QThread,Signal,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFrame,QLabel,QPushButton
from .memory_cleaner import run_cleanup,readable_bytes
from .theme import stylesheet

class MemoryWorker(QThread):
    def run(self):
        try:self.result=run_cleanup()
        except Exception as error:self.result={'error':str(error)}

class MemoryResultDialog(QDialog):
    def __init__(self,parent,result):
        super().__init__(parent);self.setWindowTitle('内存清理');self.setWindowFlags(Qt.Dialog|Qt.FramelessWindowHint);self.setAttribute(Qt.WA_TranslucentBackground);self.setModal(True);self.setMinimumWidth(340)
        outer=QVBoxLayout(self);outer.setContentsMargins(0,0,0,0);frame=QFrame();frame.setObjectName('root');outer.addWidget(frame);box=QVBoxLayout(frame);box.setContentsMargins(20,18,20,16);box.setSpacing(12)
        title=QLabel('内存清理未完成' if result.get('error') or result.get('status')=='failed' else ('内存部分清理完成' if result.get('status')=='partial' else '内存清理完成'));title.setObjectName('settingsTitle');box.addWidget(title)
        if result.get('error'):
            message=QLabel(result['error']);message.setWordWrap(True);box.addWidget(message)
        else:
            row=QHBoxLayout();box.addLayout(row)
            for label,value in [('可用内存净增',readable_bytes(result['released']) if result['completed'] else '未完成'),('当前可用',readable_bytes(result['after']['available']))]:
                card=QFrame();card.setObjectName('settingsCard');column=QVBoxLayout(card);column.setSpacing(7);caption=QLabel(label);caption.setObjectName('hint');column.addWidget(caption);number=QLabel(value);number.setObjectName('settingsTitle');column.addWidget(number);row.addWidget(card)
            detail=QLabel(f"清理前可用 {readable_bytes(result['before']['available'])} · 总内存 {readable_bytes(result['after']['total'])}");detail.setWordWrap(True);detail.setObjectName('hint');box.addWidget(detail)
            note='按系统可用内存前后差值统计，其他程序活动会影响结果。'
            if result['delta']<=0:note='本次未测得可用内存净增加。'+note
            if result['failures']:note+='\n未完成：'+'、'.join(item['operation'] for item in result['failures'])+'。'
            hint=QLabel(note);hint.setObjectName('hint');hint.setWordWrap(True);box.addWidget(hint)
        close=QPushButton('完成');close.setObjectName('primary');close.clicked.connect(self.accept);box.addWidget(close)
        cfg=parent.cfg;self.setStyleSheet(stylesheet(cfg.get('alpha',220) if cfg.get('theme')=='透明模式' else 255));self.resize(380,self.sizeHint().height())
        self.setAttribute(Qt.WA_DeleteOnClose)

class MemoryController(QObject):
    busy_changed=Signal(bool);idle=Signal()
    def __init__(self,owner):super().__init__(owner);self.owner=owner;self.worker=None;self.dialog=None
    @property
    def busy(self):return self.worker is not None
    def start(self):
        if self.busy:return False
        self.worker=MemoryWorker(self);self.worker.finished.connect(self.complete);self.busy_changed.emit(True);self.worker.start();return True
    def complete(self):
        worker=self.worker;result=worker.result;self.worker=None;worker.deleteLater();self.busy_changed.emit(False)
        if not getattr(self.owner,'_wait_memory_quit',False):
            self.dialog=MemoryResultDialog(self.owner,result);self.dialog.show();self.dialog.raise_();self.dialog.activateWindow()
        self.idle.emit()
