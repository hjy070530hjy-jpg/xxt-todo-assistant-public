"""第三方网页内部查询接口；不调用学习、作答、提交、已读或确认接口。"""
import time, hashlib, re
from urllib.parse import urljoin,unquote,urlparse,parse_qs,urlencode
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from .upstream import hidden_value,fetch_chapters
from .domain import state,deadline,notice_state,now,deadline_label
BASE='https://i.chaoxing.com/base'
COURSES='https://mooc1-api.chaoxing.com/mycourse/backclazzdata'
MIDDLE='https://mooc1.chaoxing.com/visit/stucoursemiddle'
WORK='https://mooc1.chaoxing.com/mooc-ans/mooc2/work/list'
NOTICE='https://notice.chaoxing.com/pc/notice/getNoticeList'
class QueryError(Exception):pass
class LoginExpired(QueryError):pass
class Client:
    fetch_chapters=fetch_chapters
    def __init__(self,cookies,cancel=None):
        self.session=requests.Session(); self.cancel=cancel or (lambda:False)
        self.session.headers['User-Agent']='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36'
        for c in cookies:
            self.session.cookies.set(c['name'],c['value'],domain=c['domain'],path=c.get('path','/'),secure=c.get('secure',True))
        retry=Retry(total=2,backoff_factor=1,status_forcelist=[502,503,504],allowed_methods=['GET'])
        self.session.mount('https://',HTTPAdapter(max_retries=retry))
        self.last=0
    def request(self,method,url,**kwargs):
        if self.cancel():raise QueryError('同步已取消')
        parsed=urlparse(url)
        if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.chaoxing.com'):raise QueryError('拒绝非学习通 HTTPS 地址')
        time.sleep(max(0,.6-(time.monotonic()-self.last)));self.last=time.monotonic()
        r=self.session.request(method,url,timeout=(10,20),**kwargs);r.raise_for_status()
        if 'passport2.chaoxing.com' in r.url or '用户登录' in r.text or '请先登录' in r.text:raise LoginExpired('登录已过期，请重新网页登录')
        if '验证码' in r.text and ('验证后' in r.text or '访问异常' in r.text):raise QueryError('平台要求验证，请打开网页登录手动处理')
        return r
    def get(self,url,**kw):return self.request('GET',url,**kw)
    def fetch_course_page(self,c):return self.get(MIDDLE,params={k:c[k] for k in ('courseid','clazzid','cpi')}|{'ismooc2':1,'v':2}).text
    def courses(self):
        j=self.get(COURSES,params={'view':'json','rss':'1'}).json()
        if str(j.get('result'))!='1' or not isinstance(j.get('channelList'),list):raise QueryError('课程响应结构不受支持，无法确认列表完整性')
        result=[];seen=set()
        for channel in j['channelList']:
            c=channel.get('content',{})
            for v in c.get('course',{}).get('data',[]):
                if not all([v.get('id'),c.get('id'),c.get('cpi')]):continue
                key=f"{v['id']}:{c['id']}:{c['cpi']}"
                if key in seen:continue
                seen.add(key)
                args={'courseid':str(v['id']),'clazzid':str(c['id']),'cpi':str(c['cpi'])}
                result.append(args|{'id':key,'title':str(v.get('name') or '名称未知'),'teacher':str(v.get('teacherfactor') or '教师未知'),'history':c.get('isretire') in (-1,1,'-1','1'),'term':None,'course_end':deadline(str(c.get('endDate') or '')),'url':MIDDLE+'?'+urlencode(args),'deadline':{'kind':'unsupported'}})
        if j['channelList'] and not result:raise QueryError('课程结构已变化，未能可靠解析')
        return result
    def homework(self,c):
        page=self.fetch_course_page(c);enc=hidden_value(page,'workEnc')
        if not enc:raise QueryError('课程未提供作业查询签名')
        params={'courseId':c['courseid'],'classId':c['clazzid'],'cpi':c['cpi'],'enc':enc,'ut':'s','openc':hidden_value(page,'openc'),'stuenc':hidden_value(page,'enc'),'isdisplaytable':2}
        result=[];seen=set();fingerprints=set();pages=1;n=1
        while n<=pages:
            if n>100:raise QueryError('作业分页超过安全上限，列表不完整')
            soup=BeautifulSoup(self.get(WORK,params=params|{'pageNum':n}).text,'html.parser')
            if '没有此页面访问权限' in soup.get_text():raise QueryError('作业签名无效')
            rows=soup.select('li[data]');pagebox=soup.select_one('#page')
            if pagebox:
                nums=[int(x.get_text(strip=True)) for x in pagebox.select('li') if x.get_text(strip=True).isdigit()]
                if nums:pages=max(pages,max(nums))
            if not rows and not any(x in soup.get_text() for x in ('暂无作业','没有作业','暂无数据','共0','共 0')):raise QueryError('作业结构无法识别；不能据此判断没有作业')
            fingerprint=tuple(x.get('data') for x in rows)
            if rows and fingerprint in fingerprints:raise QueryError('分页重复返回同一页，作业可能不完整')
            fingerprints.add(fingerprint)
            for row in rows:
                title=row.select_one('.overHidden2');status=row.select_one('.status')
                if title is None or status is None:raise QueryError('作业字段发生变化')
                url=urljoin(WORK,unquote(row['data']));q=parse_qs(urlparse(url).query)
                ident=c['id']+':'+str((q.get('workId') or q.get('workid') or [url])[0])
                if ident in seen:continue
                seen.add(ident)
                # 只解析有明确截止标签的列表文本；不读取作答详情，避免附带动作。
                timebox=row.select_one('.time');raw=timebox.get_text(' ',strip=True) if timebox else ''
                d=deadline(raw)
                if d.get('kind')=='unsupported' and '剩余' in raw:d={'kind':'relative','raw':raw}
                result.append({'id':ident,'title':title.get_text(strip=True),'course':c['title'],'course_id':c['id'],'status':state(status.get_text(strip=True)),'raw_status':status.get_text(strip=True),'platform_time':raw,'deadline':d,'url':url,'updated':now().isoformat()})
            n+=1
        return result
    def homework_detail(self,item):
        url=item.get('url','')
        if not url:raise QueryError('平台未提供作业原页面')
        r=self.get(url)
        soup=BeautifulSoup(r.text,'html.parser')
        for node in soup(['script','style','input','textarea','select']):node.decompose()
        text=soup.get_text(' ',strip=True)
        m=re.search(r'(?:作答时间|作业时间|起止时间)[:：]\s*(.{1,120}?)\s*(?:一[.、．]|题量|智能分析|得分|满分|$)',text)
        # Actual platform header: 作答时间: MM-DD HH:mm 至 MM-DD HH:mm.
        times=re.search(r'(?:作答时间|作业时间|起止时间)[:：]\s*((?:20\d{2}[-/])?\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2})\s*至\s*((?:20\d{2}[-/])?\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2})',text)
        result={'detail_updated':now().isoformat(),'detail_text':text[:60000]}
        if times:
            raw=times.group(2);d=deadline(raw)
            if d['kind']=='unsupported':d={'kind':'partial','raw':raw}
            result.update(deadline=d,answer_period=times.group(1)+' 至 '+raw)
        else:
            end=re.search(r'(?:截止时间|结束时间)[:：]\s*((?:20\d{2}[-/年])?\d{1,2}[-/月]\d{1,2}日?(?:\s+\d{1,2}:\d{2})?)',text)
            if end:
                raw=end.group(1);d=deadline(raw)
                result['deadline']=d if d['kind']!='unsupported' else {'kind':'partial','raw':raw}
            elif any(x in text for x in ('无截止时间','未设置截止时间','不限时')):result['deadline']={'kind':'unset'}
        return result

    def notices(self):
        result=[];last='';seen=set()
        for _ in range(100):
            j=self.request('POST',NOTICE,data={'type':0,'notice_type':0,'lastValue':last,'sort':0,'folderUUID':'','kw':'','startTime':'','endTime':'','gKw':'','gName':'','year':'','tag':'','fidsCode':'','filterSenderPuids':'','filterTags':''}).json()
            if not j.get('status'):raise QueryError('通知查询失败')
            data=j.get('notices')
            # Verified on this account: after the last nonempty cursor page, status=true/notices=null.
            if data is None and last and result:return result
            if not isinstance(data,dict) or not isinstance(data.get('list'),list):raise QueryError('通知结构无法识别')
            for raw in data['list']:
                ident=str(raw.get('idCode') or raw.get('uuid') or raw.get('id') or hashlib.sha256(str(raw).encode()).hexdigest())
                if ident in seen:continue
                seen.add(ident)
                result.append({'id':ident,'title':raw.get('title') or '标题未知','content':BeautifulSoup(raw.get('content') or '', 'html.parser').get_text(' ',strip=True),'source':str(raw.get('createrName') or '来源不可获取'),'sent':deadline_label(deadline(str(raw.get('sendTime')))) if raw.get('sendTime') else str(raw.get('completeTime') or '发送时间不可获取'),'deadline':{'kind':'unsupported'},**notice_state(raw)})
            if not data['list'] or data.get('lastPage'):return result
            cursor=data.get('lastGetId')
            if not cursor or cursor==last:raise QueryError('通知分页游标未推进')
            last=cursor
        raise QueryError('通知超过100页，无法确认列表完整性')

def sync(client,old=None,advanced=False,progress=None):
    old=old or {};out={'courses':[],'homework':[],'notices':old.get('notices',[]),'errors':{},'updated':now().isoformat(),'notice_ok':False,'course_ok':False,'homework_ok':False,'progress_ok':False}
    courses=client.courses();out['course_ok']=True
    previous={c['id']:c for c in old.get('courses',[])}
    for n,c in enumerate(courses):
        if progress:progress(f'查询课程 {n+1}/{len(courses)}：{c["title"]}')
        try:
            items=client.homework(c)
            for item in items:
                # Query display-only pages for unresolved deadlines; never submit forms or run page scripts.
                if item.get('deadline',{}).get('kind') not in ('exact','date','unset') and item.get('status') in ('未提交','未开始') and hasattr(client,'homework_detail'):
                    try:item.update(client.homework_detail(item))
                    except LoginExpired:raise
                    except Exception:item['detail_error']='截止详情获取失败'
            out['homework'].extend(items)
        except LoginExpired:raise
        except Exception:
            out['errors']['作业/'+c['title']]='查询失败；请检查登录或稍后刷新'
            out['homework'].extend(dict(i,stale=True) for i in old.get('homework',[]) if i.get('course_id')==c['id'])
        result=None
        try:
            result=client.fetch_chapters(c);p=result['progress']
            if p is None or not (0<=p[0]<=p[1]):raise QueryError('未提供可靠进度')
            c['progress']=list(p);c['nodes']=result['nodes']
        except LoginExpired:raise
        except Exception:
            out['errors']['章节/'+c['title']]='进度查询失败或结构不受支持'
            c['progress']=previous.get(c['id'],{}).get('progress');c['nodes']=(result or {}).get('nodes') or previous.get(c['id'],{}).get('nodes',[]);c['stale']=True;c['progress_note']='平台未提供可靠汇总，章节仍可查看' if c['nodes'] else '进度获取失败，点详情重试'
        out['courses'].append(c)
    out['homework_ok']=not any(i.get('status','').startswith(('状态未知','已逾期（提交状态未知）')) for i in out['homework']) and not any(k.startswith('作业/') for k in out['errors'])
    out['progress_ok']=not any(k.startswith('章节/') for k in out['errors'])
    if advanced:
        try:out['notices']=client.notices();out['notice_ok']=True
        except LoginExpired:raise
        except Exception:out['errors']['通知']='查询失败；保留上次缓存'
    return out
