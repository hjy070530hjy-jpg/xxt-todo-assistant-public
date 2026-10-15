"""Compact utility icon with a theme-matched, passive hover description."""
from PySide6.QtCore import Qt,QEvent,QPoint,Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QFrame,QVBoxLayout,QLabel,QToolButton,QGraphicsDropShadowEffect
from .theme import stylesheet

class ToolIcon(QToolButton):
    def __init__(self,title,description,settings,parent=None):
        super().__init__(parent);self.title=title;self.description=description;self.settings=settings
        self.setObjectName('toolIcon');self.setFixedSize(64,64);self.setToolButtonStyle(Qt.ToolButtonIconOnly);self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(title);self.setAccessibleDescription(description);self.setToolTip(title)
        self.info=QWidget(self,Qt.ToolTip|Qt.FramelessWindowHint);self.info.setAttribute(Qt.WA_TranslucentBackground);self.info.setAttribute(Qt.WA_ShowWithoutActivating);self.info.setAttribute(Qt.WA_TransparentForMouseEvents)
        outer=QVBoxLayout(self.info);outer.setContentsMargins(8,8,8,8);frame=QFrame();frame.setObjectName('root');outer.addWidget(frame)
        shadow=QGraphicsDropShadowEffect(frame);shadow.setBlurRadius(14);shadow.setOffset(0,3);shadow.setColor(QColor(32,65,47,28));frame.setGraphicsEffect(shadow)
        box=QVBoxLayout(frame);box.setContentsMargins(14,12,14,12);box.setSpacing(7)
        heading=QLabel(title);heading.setObjectName('sectionTitle');box.addWidget(heading)
        body=QLabel(description);body.setWordWrap(True);box.addWidget(body)
        self.note=QLabel('点击图标打开');self.note.setObjectName('hint');box.addWidget(self.note);self.info.setFixedWidth(260)
        self.clicked.connect(self.info.hide)
    def show_info(self):
        cfg=self.settings();self.info.setStyleSheet(stylesheet(cfg.get('alpha',220) if cfg.get('theme')=='透明模式' else 255));self.info.ensurePolished();self.info.layout().activate();self.info.adjustSize()
        height=self.info.layout().totalHeightForWidth(self.info.width())
        if height>0:self.info.resize(self.info.width(),height)
        point=self.mapToGlobal(QPoint(-8,self.height()+2));screen=self.screen().availableGeometry()
        x=max(screen.left(),min(point.x(),screen.right()-self.info.width()+1))
        y=point.y() if point.y()+self.info.height()<=screen.bottom()+1 else self.mapToGlobal(QPoint(0,0)).y()-self.info.height()-2
        self.info.move(x,max(screen.top(),min(y,screen.bottom()-self.info.height()+1)));self.info.show()
    def event(self,event):
        if event.type()==QEvent.ToolTip:self.show_info();event.accept();return True
        return super().event(event)
    def leaveEvent(self,event):self.info.hide();super().leaveEvent(event)
    def hideEvent(self,event):self.info.hide();super().hideEvent(event)

class DoubleClickToolIcon(ToolIcon):
    activated=Signal()
    def mouseDoubleClickEvent(self,event):
        if event.button()==Qt.LeftButton:self.info.hide();self.activated.emit();event.accept()
        else:super().mouseDoubleClickEvent(event)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return,Qt.Key_Enter,Qt.Key_Space):
            if not event.isAutoRepeat():self.info.hide();self.activated.emit()
            event.accept()
        else:super().keyPressEvent(event)
