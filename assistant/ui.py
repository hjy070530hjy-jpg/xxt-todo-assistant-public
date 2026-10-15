import os,sys,hashlib
from PySide6.QtCore import Qt,QUrl,Signal,QTimer,QThread,QRect
from PySide6.QtGui import QIcon,QColor,QPainter,QPixmap,QDesktopServices,QFont,QPalette
from PySide6.QtWidgets import *
from .storage import Store
from .domain import *
from .api import Client,sync,LoginExpired

def configure_app(app):
    app.setStyle('Fusion')
    palette=QPalette()
    for role,color in [(QPalette.Window,'#ffffff'),(QPalette.WindowText,'#243a32'),(QPalette.Base,'#ffffff'),(QPalette.AlternateBase,'#f0f4f1'),(QPalette.Text,'#243a32'),(QPalette.Button,'#edf3ef'),(QPalette.ButtonText,'#243a32'),(QPalette.Highlight,'#397461'),(QPalette.HighlightedText,'#ffffff')]:palette.setColor(role,QColor(color))
    app.setPalette(palette);app.setFont(QFont('Microsoft YaHei UI',10))

class Worker(QThread):
    done=Signal(object);failed=Signal(str);status=Signal(str)
    def __init__(self,cookies,old,advanced):
        super().__init__();self.cookies=cookies;self.old=old;self.advanced=advanced
    def run(self):
        try:self.done.emit(sync(Client(self.cookies,self.isInterruptionRequested),self.old,self.advanced,self.status.emit))
        except LoginExpired:self.failed.emit('登录已过期，请在设置中重新网页登录。')
        except Exception:self.failed.emit('同步失败：网络、平台验证或响应结构异常。旧数据已保留并标记过期。')
        finally:self.cookies=[]

class LoginDialog(QDialog):
    def __init__(self,parent):
        super().__init__(parent)
        from PySide6.QtWebEngineCore import QWebEngineProfile,QWebEnginePage
        from PySide6.QtWebEngineWidgets import QWebEngineView
        self.setWindowTitle('学习通官方网页登录');self.resize(800,660);self.cookies={}
        box=QVBoxLayout(self);label=QLabel('在此窗口扫码或输入账户密码。完成验证码后，点击下方“连接”。\n网页由学习通提供；浏览器使用内存会话，应用不保存密码。');label.setWordWrap(True);label.setMaximumHeight(64);box.addWidget(label)
        self.profile=QWebEngineProfile(self) # 无名称 = off-the-record，不落盘
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        self.view=QWebEngineView(self);self.page=QWebEnginePage(self.profile,self.view);self.view.setPage(self.page)
        self.profile.cookieStore().cookieAdded.connect(self.add_cookie)
        self.profile.cookieStore().cookieRemoved.connect(self.remove_cookie)
        self.view.setUrl(QUrl('https://passport2.chaoxing.com/login?refer=https%3A%2F%2Fi.chaoxing.com'))
        box.addWidget(self.view,1);buttons=QDialogButtonBox();connect=buttons.addButton('我已登录，连接账户',QDialogButtonBox.AcceptRole);buttons.addButton('取消',QDialogButtonBox.RejectRole)
        connect.clicked.connect(self.check);buttons.rejected.connect(self.reject);box.addWidget(buttons)
    def add_cookie(self,c):
        if c.domain().lstrip('.')!='chaoxing.com' and not c.domain().endswith('.chaoxing.com'):return
        key=(bytes(c.name()).decode(),c.domain(),c.path())
        self.cookies[key]={'name':key[0],'value':bytes(c.value()).decode(),'domain':key[1],'path':key[2],'secure':c.isSecure()}
    def remove_cookie(self,c):self.cookies.pop((bytes(c.name()).decode(),c.domain(),c.path()),None)
    def check(self):
        uids=[x['value'] for x in self.cookies.values() if x['name'] in ('_uid','UID','uid')]
        if not uids:QMessageBox.information(self,'尚未完成登录','尚未获取账户标识，请先完成网页登录及验证码。');return
        self.account=hashlib.sha256(uids[0].encode()).hexdigest();self.accept()

class DetailWorker(QThread):
    done=Signal(object);failed=Signal(str)
    def __init__(self,cookies,item,course=False):
        super().__init__();self.cookies=cookies;self.item=dict(item);self.course=course
    def run(self):
        try:
            client=Client(self.cookies,self.isInterruptionRequested)
            result=client.fetch_chapters(self.item) if self.course else client.homework_detail(self.item)
            if self.course and result.get('progress') is None and not result.get('nodes'):raise ValueError('没有可显示的章节字段')
            self.done.emit(result)
        except LoginExpired:self.failed.emit('登录已过期，请在设置中重新登录。')
        except Exception:self.failed.emit('详情查询失败，保留已缓存信息。可点击原页面核对。')
        finally:self.cookies=[]

class Window(QWidget):
    def __init__(self,store=None):
        super().__init__();self.store=store or Store();self.cfg=self.store.get('settings',{});self.account=self.store.get('active');self.data=self.store.get('cache:'+self.account,{}) if self.account else {};self.worker=None;self.detail_workers=set();self.notice_limit=30;self.undo_stack=[];self.demo=False;self.expired=False
        self.setWindowTitle('学习通待办助手');self.setWindowFlags(Qt.Window|Qt.FramelessWindowHint);self.setAttribute(Qt.WA_TranslucentBackground);self.setMinimumSize(420,240);self.resize(480,270)
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(0,0,0,0);self.root=QFrame();self.root.setObjectName('root');self.outer.addWidget(self.root);layout=QVBoxLayout(self.root);layout.setContentsMargins(8,7,8,4);layout.setSpacing(5)
        bar=QHBoxLayout();self.title=QLabel('学习通待办助手');self.title.setObjectName('title');bar.addWidget(self.title);bar.addStretch()
        for label,fn in [('−',self.showMinimized),('×',self.close)]:
            b=self.button(bar,label,fn);b.setFixedSize(25,25)
        layout.addLayout(bar)
        body=QHBoxLayout();body.setSpacing(7);layout.addLayout(body,1)
        sidebar=QVBoxLayout();self.tabs=QListWidget();self.tabs.setObjectName('navigation');self.tabs.setFixedWidth(49);self.tabs.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.tabs.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for label in ('课程','作业','消息'):
            item=QListWidgetItem(label);item.setSizeHint(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(47,40));item.setTextAlignment(Qt.AlignCenter);self.tabs.addItem(item)
        self.tabs.setCurrentRow(0);self.tabs.currentRowChanged.connect(self.change_page);sidebar.addWidget(self.tabs,1)
        settings=self.button(sidebar,'⚙',self.settings);settings.setToolTip('设置');settings.setFixedWidth(49);body.addLayout(sidebar)
        content=QVBoxLayout();content.setSpacing(5);body.addLayout(content,1)
        self.banner=QLabel();self.banner.setWordWrap(True);self.banner.setObjectName('banner');content.addWidget(self.banner)
        self.controls=QHBoxLayout();self.controls.setSpacing(4);self.filter=QComboBox();self.filter.addItems(['全部','仅未完成','今天截止','24小时内','已逾期']);self.filter.setMinimumWidth(0);self.filter.setMaximumWidth(108);self.filter.currentIndexChanged.connect(self.render);self.controls.addWidget(self.filter)
        self.hide_history=QCheckBox('隐藏历史');self.hide_history.setChecked(self.cfg.get('hide_history',True));self.hide_history.toggled.connect(self.render);self.controls.addWidget(self.hide_history);self.controls.addStretch();content.addLayout(self.controls)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);self.scroll.setFrameShape(QFrame.NoFrame);content.addWidget(self.scroll,1)
        foot=QHBoxLayout();self.stamp=QLabel('尚未同步');self.stamp.setWordWrap(True);foot.addWidget(self.stamp,1);self.refresh=self.button(foot,'刷新',self.start_sync);self.refresh.setToolTip('立即同步');content.addLayout(foot);grip=QSizeGrip(self);layout.addWidget(grip,0,Qt.AlignRight)
        pix=QPixmap(32,32);pix.fill(QColor('#397461'));p=QPainter(pix);p.setPen(Qt.white);p.setFont(QFont('Microsoft YaHei UI',18));p.drawText(pix.rect(),Qt.AlignCenter,'学');p.end();self.icon=QIcon(pix);self.setWindowIcon(self.icon)
        self.tray=QSystemTrayIcon(self.icon,self);self.tray.setToolTip('学习通待办助手');menu=QMenu();menu.addAction('显示窗口',self.reveal);menu.addAction('立即同步',self.start_sync);menu.addSeparator();menu.addAction('退出',self.quit_app);self.tray.setContextMenu(menu);self.tray.activated.connect(lambda r:self.reveal() if r==QSystemTrayIcon.Trigger else None);self.tray.show()
        self.timer=QTimer(self);self.timer.timeout.connect(self.start_sync);self.reminder_timer=QTimer(self);self.reminder_timer.timeout.connect(self.remind);self.reminder_timer.start(60000);self.last_tick=now()
        self.apply_settings();self.restore_geometry();self.render()
        if self.account:QTimer.singleShot(1000,self.start_sync)
    def change_page(self,row):
        self.filter.blockSignals(True);self.filter.clear();self.filter.addItems(['全部','仅未完成','今天截止','24小时内']+([] if row==1 else ['已逾期']));self.filter.setCurrentIndex(1 if row==1 else 0);self.filter.blockSignals(False);self.render()
    def button(self,box,text,fn):
        b=QPushButton(text);b.clicked.connect(lambda checked=False:fn());box.addWidget(b);return b
    def reveal(self):self.showNormal();self.raise_();self.activateWindow()
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton and e.position().y()<48:self.windowHandle().startSystemMove()
    def restore_geometry(self):
        g=self.cfg.get('geometry') if self.cfg.get('layout_version')==3 else None;area=QApplication.primaryScreen().availableGeometry()
        if g:
            rect=QRect(*g);screen=QApplication.screenAt(rect.center());area=(screen or QApplication.primaryScreen()).availableGeometry();w=min(max(420,rect.width()),area.width());h=min(max(240,rect.height()),area.height());self.setGeometry(max(area.left(),min(rect.x(),area.right()-w+1)),max(area.top(),min(rect.y(),area.bottom()-h+1)),w,h)
        else:self.move(area.right()-self.width()-24,area.top()+50)
    def save_settings(self):
        self.cfg['layout_version']=3;self.cfg['geometry']=[self.x(),self.y(),self.width(),self.height()];self.cfg['hide_history']=self.hide_history.isChecked();self.store.put('settings',self.cfg)
    def apply_settings(self):
        transparent=self.cfg.get('theme','纯白模式')=='透明模式';a=self.cfg.get('alpha',220) if transparent else 255
        from .theme import stylesheet
        self.root.setStyleSheet(stylesheet(a))
        self.setWindowFlag(Qt.WindowStaysOnTopHint,self.cfg.get('top',False));self.timer.start(self.cfg.get('interval',30)*60000)
    def card(self,parent,title,body,action=None,record=None):
        frame=QFrame();frame.setObjectName('card');box=QVBoxLayout(frame);box.setContentsMargins(10,9,10,9);box.setSpacing(5)
        head=QLabel(title if len(title)<48 else title[:47]+'…');head.setTextFormat(Qt.PlainText);head.setWordWrap(True);head.setStyleSheet('font-weight:600');box.addWidget(head)
        text=QLabel(body);text.setWordWrap(True);text.setTextFormat(Qt.PlainText);box.addWidget(text)
        if action:self.button(box,'查看详情',action)
        if record:
            kind,item=record;frame.setProperty('recordKind',kind);frame.setProperty('recordId',item['id'])
            targets=[frame]+frame.findChildren(QLabel)+frame.findChildren(QPushButton)
            for target in targets:
                target.setContextMenuPolicy(Qt.CustomContextMenu)
                target.customContextMenuRequested.connect(lambda pos,target=target,kind=kind,item=item:self.item_menu(kind,item,target).exec(target.mapToGlobal(pos)))
        parent.addWidget(frame)
    def deletion_namespace(self):return self.account or ('demo' if self.demo else 'local')
    def deletion_key(self,kind):return 'deleted:'+self.deletion_namespace()+':'+kind
    def deleted_items(self,kind):return self.store.get(self.deletion_key(kind),{})
    def item_menu(self,kind,item,parent=None):
        menu=QMenu(parent or self);menu.setObjectName('itemContextMenu')
        action=menu.addAction('删除（仅本地）');action.triggered.connect(lambda checked=False:self.delete_item(kind,item))
        return menu
    def delete_item(self,kind,item):
        key=self.deletion_key(kind);deleted=self.store.get(key,{});deleted[item['id']]=item['title'];self.store.put(key,deleted)
        self.undo_stack.append((self.deletion_namespace(),kind,item['id']));self.render(preserve_scroll=True)
    def undo_delete(self):
        namespace=self.deletion_namespace()
        for n in range(len(self.undo_stack)-1,-1,-1):
            owner,kind,ident=self.undo_stack[n]
            if owner!=namespace:continue
            self.undo_stack.pop(n);key=self.deletion_key(kind);deleted=self.store.get(key,{});deleted.pop(ident,None);self.store.put(key,deleted);self.render(preserve_scroll=True);return
    def restore_deleted(self):
        namespace=self.deletion_namespace()
        for kind in ('courses','homework'):self.store.delete(self.deletion_key(kind))
        self.undo_stack=[entry for entry in self.undo_stack if entry[0]!=namespace];self.render()
    def eligible(self,i):
        f=self.filter.currentIndex();d=i.get('deadline',{});r=remaining(d)
        if f==1:return pending(i)
        if f==2:return r.startswith('今天')
        if f==3:return bool(r) and r!='已逾期' and (datetime.fromisoformat(d['value'])-now()).total_seconds()<=86400
        if f==4:return r=='已逾期'
        return True
    def render(self,*args,preserve_scroll=False):
        if not hasattr(self,'scroll'):return
        scroll_position=self.scroll.verticalScrollBar().value() if preserve_scroll else None
        widget=QWidget();box=QVBoxLayout(widget);box.setContentsMargins(0,0,1,0);box.setSpacing(6);page=self.tabs.currentRow();d=self.data
        banner='未登录 · 点击左下角⚙连接账户'
        if self.demo:banner='示例数据 · 非真实账户'
        elif self.expired:banner='登录已过期，请重新登录'
        elif self.account:banner='正在同步…' if self.worker and self.worker.isRunning() else '只读查询 · 北京时间'
        if d.get('stale'):banner+=' · 缓存可能过期'
        if page==2 and '通知' in d.get('errors',{}):banner+=' · 消息查询失败'
        self.banner.setText(banner);self.hide_history.setVisible(page==0);self.filter.setVisible(page in (0,1))
        self.stamp.setText('同步 '+(datetime.fromisoformat(d['updated']).astimezone(TZ).strftime('%m-%d %H:%M') if d.get('updated') else '尚未完成'))
        courses=d.get('courses',[]);homework=d.get('homework',[]);shown=0
        deleted_courses=self.deleted_items('courses');deleted_homework=self.deleted_items('homework')
        if page==0:
            for c in courses:
                if c['id'] in deleted_courses or c.get('stale'):continue
                if self.hide_history.isChecked() and c.get('history'):continue
                p=c.get('progress');f=self.filter.currentIndex()
                if f==1 and course_completion(c,d.get('stale',False))=='已完成':continue
                if f>=2 and not self.eligible(c):continue
                body='状态：'+course_completion(c,d.get('stale',False))+'\n结束：'+course_end_label(c.get('course_end',{}))
                self.card(box,c['title'],body,lambda c=c:self.detail(c,True),record=('courses',c));shown+=1
            if not shown:self.card(box,'暂无可显示课程','可调整筛选或稍后刷新，查询成功后会重新显示。')
        elif page==1:
            for i in sorted(homework,key=sort_key):
                if i['id'] in deleted_homework or i.get('stale') or homework_overdue(i):continue
                if self.eligible(i):self.item_card(box,i);shown+=1
            if not shown:self.card(box,'暂无可显示作业','可调整筛选或稍后刷新，查询成功后会重新显示。')
        else:
            self.card(box,'消息状态','未读与未确认分别记录；当前确认字段不可获取。')
            for i in sorted(d.get('notices',[]),key=lambda i:i.get('read') is not False)[:self.notice_limit]:
                read={True:'已读',False:'未读',None:'已读状态未知'}[i.get('read')]
                local=' · 本地已处理' if self.store.get('handled:'+str(self.account)+':'+i['id']) else ''
                self.card(box,i['title'],read+local+'\n'+i.get('source','')+'\n'+i.get('sent','')+'\n'+i.get('content','')[:65],lambda i=i:self.notice_detail(i))
            if len(d.get('notices',[]))>self.notice_limit:self.button(box,f'加载更多（{self.notice_limit}/{len(d["notices"])}）',self.load_more_notices)
            if not d.get('notice_ok'):self.card(box,'消息尚未加载或查询失败','请刷新。不会自动确认收到或请求已读接口。')
        if page==2 and '通知' in d.get('errors',{}):self.card(box,'消息暂不可用',d['errors']['通知'])
        if not self.account:self.button(box,'查看示例',self.load_demo)
        box.addStretch();self.scroll.setWidget(widget)
        if scroll_position is not None:
            def restore_scroll():
                # Replacing the content resets QScrollArea. Restore after Qt has
                # laid out the new cards, and ignore a newer page/filter render.
                if self.scroll.widget() is widget:
                    bar=self.scroll.verticalScrollBar();bar.setValue(min(scroll_position,bar.maximum()))
            QTimer.singleShot(0,widget,restore_scroll)
    def load_more_notices(self):
        self.notice_limit+=30;self.render()
    def item_card(self,box,i):
        text=i.get('course','')+' · '+i.get('status','未知')+'\n'+deadline_label(i.get('deadline',{}))+'\n'+(remaining(i.get('deadline',{})) or (i.get('platform_time','')+'（同步时）' if i.get('platform_time') else ''))
        if i.get('stale') or self.data.get('stale'):text+='\n缓存可能过期'
        self.card(box,i['title'],text,lambda i=i:self.detail(i),record=('homework',i))
    def detail(self,i,course=False):
        dialog=QDialog(self);dialog.setWindowTitle('课程详情' if course else '作业详情');dialog.resize(370,450);b=QVBoxLayout(dialog);text=QTextBrowser();text.setObjectName('detailContent');b.addWidget(text,1);status=QLabel();status.setWordWrap(True);b.addWidget(status)
        def display():
            lines=[i['title']]
            if course:
                lines += ['状态：'+course_completion(i,self.data.get('stale',False)),'结束：'+course_end_label(i.get('course_end',{}))]
            else:
                lines += [i.get('course',''),i.get('status',''),'截止：'+deadline_label(i.get('deadline',{})),remaining(i.get('deadline',{})) or i.get('platform_time','')]
                if i.get('answer_period'):lines += ['平台作答时间：'+i['answer_period']]
                if i.get('deadline',{}).get('kind')=='partial':lines += ['平台没有提供年份，未据此生成绝对日期提醒。']
                lines += ['',i.get('detail_text','正在读取作业页面内容…')]
            text.setPlainText('\n'.join(lines))
        display()
        if i.get('url'):self.button(b,'打开学习通原页面',lambda:self.open_original(i['url']))
        note=QLabel('原页面需要浏览器登录；访问可能产生平台访问记录。此处仅读取内容，不填写或提交。');note.setWordWrap(True);b.addWidget(note)
        if self.account and not self.demo:
            status.setText('正在后台获取最新详情…');worker=DetailWorker(self.store.get('cookies:'+self.account,[]),i,course);self.detail_workers.add(worker);account=self.account
            def done(result):
                if self.account!=account:return
                if course:
                    p=result.get('progress');i.update(progress=list(p) if p is not None else None,nodes=result.get('nodes',[]),stale=False)
                else:i.update(result)
                if self.account:self.store.put('cache:'+self.account,self.data)
                self.render()
                if dialog.isVisible():display();status.setText('已获取平台最新详情')
            worker.done.connect(done);worker.failed.connect(lambda msg:status.setText(msg) if dialog.isVisible() else None);worker.finished.connect(lambda:self.detail_workers.discard(worker));worker.start()
        dialog.exec()
    def open_original(self,url):
        from urllib.parse import urlparse
        u=urlparse(url)
        if u.scheme=='https' and (u.hostname or '').endswith('.chaoxing.com'):QDesktopServices.openUrl(QUrl(url))
        else:QMessageBox.information(self,'页面不可打开','平台未提供受信任的 HTTPS 原页面地址。')
    def notice_detail(self,i):
        dialog=QDialog(self);dialog.setWindowTitle('通知缓存详情 · 不请求平台');dialog.resize(380,440);b=QVBoxLayout(dialog);text=QTextBrowser();text.setPlainText(i['title']+'\n'+i.get('content','')+'\n\n确认状态不可获取');b.addWidget(text)
        self.button(b,'仅在本应用标记/取消已处理',lambda:self.toggle_handled(i,dialog));dialog.exec()
    def toggle_handled(self,i,d):
        key='handled:'+str(self.account)+':'+i['id'];self.store.put(key,not self.store.get(key,False));d.accept();self.render()
    def login(self):
        if self.worker and self.worker.isRunning():return
        dlg=LoginDialog(self)
        if dlg.exec()==QDialog.Accepted:
            self.demo=False;self.expired=False;self.account=dlg.account;self.store.put('active',self.account);self.store.put('cookies:'+self.account,list(dlg.cookies.values()));self.data=self.store.get('cache:'+self.account,{});self.render();self.start_sync()
        dlg.view.setPage(None);dlg.page.deleteLater();dlg.deleteLater()
    def start_sync(self):
        if self.worker and self.worker.isRunning():return
        if self.demo:return
        if not self.account:self.settings();return
        cookies=self.store.get('cookies:'+self.account,[])
        if not cookies:self.expired=True;self.render();return
        self.refresh.setEnabled(False);self.banner.setText('同步中，请稍候…');self.worker=Worker(cookies,self.data,True);self.worker.done.connect(self.synced);self.worker.failed.connect(self.failed);self.worker.status.connect(self.banner.setText);self.worker.finished.connect(lambda:self.refresh.setEnabled(True));self.worker.start()
    def synced(self,data):
        old=self.data;self.data=data;self.expired=False;self.store.put('cache:'+self.account,data);self.render()
        if self.cfg.get('notify',True) and old.get('homework_ok') and data.get('homework_ok'):
            ids={i['id'] for i in old.get('homework',[])}
            deleted=self.deleted_items('homework');fresh=[i for i in data['homework'] if pending(i) and i['id'] not in ids and i['id'] not in deleted]
            seen=set(self.store.get('seen:'+self.account,[]));news=[i for i in fresh if 'new:'+i['id'] not in seen]
            if news:
                self.tray.showMessage('发现新作业',f'{len(news)} 份新作业，请查看作业页面。');seen.update('new:'+i['id'] for i in news);self.store.put('seen:'+self.account,list(seen))
        self.remind()
    def failed(self,message):
        self.data['stale']=True
        if '登录已过期' in message:self.expired=True
        if self.account:self.store.put('cache:'+self.account,self.data)
        self.render();self.banner.setText(message)
    def remind(self):
        tick=now();gap=(tick-self.last_tick).total_seconds();self.last_tick=tick
        if gap>100:
            if self.account and not self.demo:self.start_sync()
            return
        if not self.account or self.demo or self.expired or self.data.get('stale') or not self.data.get('homework_ok') or not self.cfg.get('notify',True):return
        seen=set(self.store.get('seen:'+self.account,[]));deleted=self.deleted_items('homework');events=due_events([i for i in self.data.get('homework',[]) if i['id'] not in deleted],self.cfg.get('hours',[24,2]),seen)
        if events:
            self.tray.showMessage('学习通截止提醒',f'{len(events)} 项待办接近或已过截止时间，请打开窗口查看。',QSystemTrayIcon.Information,10000)
            for key,item,rule in events:
                seen.add(key)
                if isinstance(rule,(int,float)):
                    for h in self.cfg.get('hours',[24,2]):
                        if h>=rule:seen.add(event_key(item,h))
            self.store.put('seen:'+self.account,list(seen))
    def logout(self):
        if self.worker and self.worker.isRunning():QMessageBox.information(self,'同步中','请等待当前同步结束后退出账户。');return False
        if self.account:self.store.delete('cookies:'+self.account)
        self.store.delete('active');self.account=None;self.demo=False;self.data={};self.expired=False;self.render();return True
    def settings(self):
        from .settings import SettingsDialog
        dialog=SettingsDialog(self);dialog.exec()
    def set_autostart(self,enabled):
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if enabled:
                if getattr(sys,'frozen',False):command='"'+sys.executable+'"'
                else:command='"'+sys.executable.replace('python.exe','pythonw.exe')+'" "'+os.path.abspath('main.py')+'"'
                winreg.SetValueEx(key,'XXTTodoAssistant',0,winreg.REG_SZ,command)
            else:
                try:winreg.DeleteValue(key,'XXTTodoAssistant')
                except FileNotFoundError:pass
    def clear_data(self,dialog):
        if self.worker and self.worker.isRunning():QMessageBox.information(dialog,'同步中','请等待同步结束后清除数据。');return
        if QMessageBox.question(dialog,'清除本地数据','将清除所有账户会话、缓存和本地处理标记，是否继续？')!=QMessageBox.Yes:return
        cfg=dict(self.cfg);self.store.clear();self.store.put('settings',cfg);self.account=None;self.data={};self.demo=False;self.expired=False;self.undo_stack=[];self.render();dialog.accept()
    def closeEvent(self,event):
        if getattr(self,'_quitting',False):event.accept();return
        self.save_settings();behavior=self.cfg.get('close','询问')
        if behavior=='询问':
            msg=QMessageBox(self);msg.setWindowTitle('关闭窗口');msg.setText('关闭后如何运行？');bg=msg.addButton('继续后台运行',QMessageBox.AcceptRole);quitbtn=msg.addButton('退出程序',QMessageBox.DestructiveRole);msg.addButton('取消',QMessageBox.RejectRole);msg.exec()
            if msg.clickedButton()==bg:behavior='后台运行'
            elif msg.clickedButton()==quitbtn:behavior='退出程序'
            else:event.ignore();return
        event.ignore()
        if behavior=='后台运行' and QSystemTrayIcon.isSystemTrayAvailable():self.hide()
        else:self.quit_app()
    def quit_app(self):
        if hasattr(self,'memory_controller') and self.memory_controller.busy:
            if not getattr(self,'_wait_memory_quit',False):self._wait_memory_quit=True;self.memory_controller.idle.connect(self.quit_app)
            self.banner.setText('等待内存清理完成后退出…');return
        running=[w for w in self.detail_workers if w.isRunning()]
        if running:
            for worker in running:worker.requestInterruption();worker.finished.connect(self.quit_app)
            self.banner.setText('正在停止详情查询…');return
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption();self.banner.setText('正在停止同步，完成当前网络请求后退出…');self.worker.finished.connect(self.quit_app);return
        self._quitting=True;self.save_settings();self.tray.hide();QApplication.instance().quit()
    def load_demo(self):
        self.demo=True;self.data={'updated':now().isoformat(),'course_ok':True,'homework_ok':True,'progress_ok':True,'courses':[{'id':'demo','title':'高等数学 · 示例课程','teacher':'示例教师','course_end':{'kind':'exact','value':(now()+timedelta(days=7)).replace(hour=23,minute=0,second=0,microsecond=0).isoformat()},'progress':[12,20],'nodes':[(1,'1.2 极限 · 2个待完成')],'deadline':{'kind':'unsupported'}}],'homework':[{'id':'demo-work','title':'第二章课后练习 · 示例作业','course':'高等数学（示例）','status':'未提交','deadline':{'kind':'exact','value':(now()+timedelta(hours=7)).replace(second=0,microsecond=0).isoformat()}}]};self.render()
