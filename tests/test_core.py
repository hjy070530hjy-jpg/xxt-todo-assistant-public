import unittest,tempfile
from pathlib import Path
from datetime import timedelta
from assistant.domain import *
from assistant.api import Client,QueryError,sync,NOTICE,WORK
from assistant.storage import Store
class DomainTests(unittest.TestCase):
    def test_submitted_not_pending(self):
        for v in ['待批閱','待批阅','已提交','已完成','待互评']:
            self.assertFalse(pending({'status':state(v)}))
        self.assertTrue(pending({'status':state('未交')}))
        self.assertTrue(state('怪状态').startswith('状态未知'))
        self.assertTrue(state('未完成').startswith('状态未知'))
    def test_notice_independent(self):
        for v in [0,1,'0','1',True,False,None]:
            n=notice_state({'isread':v,'confirmed':True})
            self.assertIsNone(n['confirmed']);self.assertIsNone(n['requires_confirmation'])
        self.assertFalse(notice_state({'isread':'0'})['read'])
    def test_deadline_precision(self):
        self.assertEqual(deadline('2026-10-20')['kind'],'date')
        self.assertEqual(deadline('截止时间：2026-10-20 19:02')['kind'],'exact')
        self.assertEqual(deadline('10-20 19:02')['kind'],'unsupported')
        self.assertEqual(deadline('剩余7小时')['kind'],'unsupported')
        self.assertEqual(deadline('2026-02-30')['kind'],'failed')
        self.assertEqual(deadline('不限时')['kind'],'unset')
        self.assertIn('2026-10-20T19:02',deadline('2026-10-01 08:00 至 2026-10-20 19:02')['value'])
        self.assertEqual(datetime.fromisoformat(deadline('2026-10-20 19:02')['value']).utcoffset(),timedelta(hours=8))
    def test_reminder_dedup_and_changed_deadline(self):
        i={'id':'1','status':'未提交','deadline':{'kind':'exact','value':(now()+timedelta(hours=1)).isoformat()}}
        events=due_events([i],[24,2],set());self.assertEqual(len(events),1)
        self.assertEqual(due_events([i],[24,2],{events[0][0]}),[])
        i['deadline']['value']=(now()+timedelta(minutes=30)).isoformat()
        self.assertEqual(len(due_events([i],[24,2],{events[0][0]})),1)
        i['stale']=True;self.assertEqual(due_events([i],[24,2],set()),[])
    def test_dpapi_and_isolation(self):
        with tempfile.TemporaryDirectory(dir='.') as tmp:
            p=Path(tmp)/'cache.sqlite3';s=Store(p);s.put('cookies:A',{'secret':'cookie-test-secret'})
            self.assertEqual(s.get('cookies:A')['secret'],'cookie-test-secret');self.assertIsNone(s.get('cookies:B'))
            self.assertNotIn(b'cookie-test-secret',p.read_bytes());s.clear();self.assertIsNone(s.get('cookies:A'));s.db.close()
class Reply:
    def __init__(self,text='',data=None):self.text=text;self.data=data
    def json(self):return self.data
class Fake(Client):
    def __init__(self,pages):self.pages=pages;self.calls=[]
    def fetch_course_page(self,c):return '<input id="workEnc" value="signature">'
    def get(self,url,**kw):self.calls.append(kw['params']['pageNum']);return Reply(self.pages[kw['params']['pageNum']-1])
COURSE={'id':'c','courseid':'1','clazzid':'2','cpi':'3','title':'课程'}
def row(n):return f'<li data="https://mooc1.chaoxing.com/mooc-ans/mooc2/work/task?workId={n}"><p class="overHidden2">作业{n}</p><p class="status">未交</p><div class="time">2026-10-20 18:30</div></li>'
class NetworkParsingTests(unittest.TestCase):
    def test_pagination(self):
        c=Fake([row(1)+'<div id="page"><li>1</li><li>2</li></div>',row(2)])
        self.assertEqual(len(c.homework(COURSE)),2);self.assertEqual(c.calls,[1,2])
    def test_repeated_page_fails(self):
        p=row(1)+'<div id="page"><li>1</li><li>2</li></div>'
        with self.assertRaises(QueryError):Fake([p,p]).homework(COURSE)
    def test_unknown_empty_not_zero(self):
        with self.assertRaises(QueryError):Fake(['<html>新版结构</html>']).homework(COURSE)
    def test_partial_failure_preserves_cache(self):
        class Partial:
            def courses(self):return [dict(COURSE),dict(COURSE,id='c2',title='另一门')]
            def homework(self,c):
                if c['id']=='c':raise QueryError()
                return [{'id':'new','course_id':'c2','status':'未提交'}]
        out=sync(Partial(),{'homework':[{'id':'old','course_id':'c','status':'未提交'}]})
        self.assertFalse(out['homework_ok']);self.assertEqual(len(out['homework']),2);self.assertTrue(out['homework'][0]['stale'])
    def test_notice_cursor_loop_fails(self):
        class N(Client):
            def __init__(self):pass
            def request(self,*a,**k):return Reply(data={'status':True,'notices':{'list':[{'id':'1','isread':0}],'lastGetId':'same'}})
        with self.assertRaises(QueryError):N().notices()
if __name__=='__main__':unittest.main()
