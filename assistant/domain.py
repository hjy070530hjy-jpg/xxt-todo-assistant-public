"""纯状态函数：不把缺失值当成已完成或无截止。"""
import re, hashlib
from datetime import datetime, timedelta, timezone
TZ = timezone(timedelta(hours=8))
def now(): return datetime.now(TZ)
def state(raw):
    s=raw.strip().translate(str.maketrans('閱評','阅评'))
    if s in ('未交','未提交'): return '未提交'
    if s in ('未开始','未开放'): return '未开始'
    if s in ('待批阅','待批改','已提交'): return '已提交待批阅'
    if s in ('已完成','已批改','已互评'): return '已完成'
    if s=='待互评': return '待互评'
    if s in ('已逾期','已过期'): return '已逾期（提交状态未知）'
    return '状态未知：'+(s or '未提供')
def pending(item): return item.get('status') in ('未提交','未开始')

def homework_overdue(item,clock=None):
    """Hide only work that the platform or a reliable deadline establishes as expired."""
    if any(str(item.get(key,'')).startswith(('已逾期','已过期','已截止')) for key in ('status','raw_status','platform_time')):return True
    d=item.get('deadline',{});kind=d.get('kind');clock=clock or now()
    if kind not in ('exact','date'):return False
    try:
        end=datetime.fromisoformat(d['value'])
        if end.tzinfo is None:return False
        return end<clock if kind=='exact' else end.astimezone(TZ).date()<clock.astimezone(TZ).date()
    except (KeyError,TypeError,ValueError):return False
def deadline(text):
    if '至' in text:text=text.rsplit('至',1)[1]
    if re.search(r'无截止时间|未设置截止|不限时',text): return {'kind':'unset'}
    # 仅接受含年份的绝对日期；相对倒计时不反推时刻。
    m=re.search(r'(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})日?(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?',text)
    if not m: return {'kind':'unsupported','raw':text[:160]}
    try:
        y,mo,d,h,mi,se=m.groups()
        value=datetime(int(y),int(mo),int(d),int(h or 0),int(mi or 0),int(se or 0),tzinfo=TZ)
        return {'kind':'exact' if h else 'date','value':value.isoformat()}
    except ValueError: return {'kind':'failed'}
def deadline_label(d):
    k=d.get('kind','unsupported')
    if k=='partial':return d.get('raw','')+'（年份未提供）'
    if k=='relative':return '平台仅提供相对截止时间'
    if k in ('exact','date'):
        dt=datetime.fromisoformat(d['value']).astimezone(TZ)
        return dt.strftime('%Y年%m月%d日 %H:%M') if k=='exact' else dt.strftime('%Y年%m月%d日')+'（具体截止时刻未知）'
    return {'unset':'未设置截止时间','unsupported':'截止时间不可获取','failed':'截止时间获取失败'}.get(k,'截止时间不可获取')
def remaining(d):
    if d.get('kind')=='relative':return d.get('raw','')+'（平台查询时显示）'
    if d.get('kind')!='exact': return ''
    dt=datetime.fromisoformat(d['value']); seconds=(dt-now()).total_seconds()
    if seconds<0: return '已逾期'
    prefix='今天截止 · ' if dt.astimezone(TZ).date()==now().date() else ('即将截止 · ' if seconds<=86400 else '')
    return prefix+f'剩余 {int(seconds//86400)}天 {int(seconds%86400//3600)}小时 {int(seconds%3600//60)}分'
def sort_key(i):
    return i.get('deadline',{}).get('value','9999')
def notice_state(raw):
    # 源码仅证明 isread 字段存在；不猜测其他字段的确认语义。
    v=raw.get('isread')
    read=True if v is True or v==1 or v=='1' else False if v is False or v==0 or v=='0' else None
    return {'read':read,'requires_confirmation':None,'confirmed':None}
def event_key(item,rule):
    return hashlib.sha256((item['id']+'|'+str(item.get('deadline'))+'|'+str(rule)).encode()).hexdigest()
def due_events(items,hours,seen,clock=None):
    clock=clock or now(); result=[]
    for item in items:
        if not pending(item) or item.get('stale') or item.get('deadline',{}).get('kind')!='exact': continue
        dt=datetime.fromisoformat(item['deadline']['value']); diff=(dt-clock).total_seconds()
        eligible=[h for h in hours if 0<diff<=h*3600]
        if diff<=0: eligible=['overdue']
        if not eligible: continue
        rule=min(eligible) if diff>0 else 'overdue'; key=event_key(item,rule)
        if key not in seen: result.append((key,item,rule))
    return result


def course_completion(course,cache_stale=False):
    """Only a reliable, positive task total can establish course completion."""
    p=course.get('progress')
    if cache_stale or course.get('stale') or not isinstance(p,(list,tuple)) or len(p)!=2:return '完成状态未知'
    done,total=p
    if not isinstance(done,(int,float)) or not isinstance(total,(int,float)) or total<=0 or not 0<=done<=total:return '完成状态未知'
    return '已完成' if done==total else '未完成'

def course_end_label(value):
    if value.get('kind') in ('exact','date','partial'):return deadline_label(value)
    return {'unset':'未设置结束时间','failed':'结束时间获取失败'}.get(value.get('kind'),'结束时间不可获取')
