# Adapted from DanMo661/Xuexitong-mcp, MIT, copyright Wu Jiale.
import base64, re, time
import html as html_mod
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
AES_KEY = AES_IV = b"u2oh6Vu^HWe4_AES"
URL_CHAPTER = "https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse"
def aes_encrypt(text: str) -> str:
    """学习通登录参数的 AES-128-CBC/PKCS7 加密 + base64（key=iv 固定值）。"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return base64.b64encode(cipher.encrypt(pad(text.encode("utf-8"), 16))).decode()

def hidden_value(page_html: str, input_id: str) -> str:
    """提取页面里 <input type="hidden" id="X" value="Y"> 的 value。"""
    m = re.search(r'id="%s"[^>]*value="([^"]*)"' % input_id, page_html) or \
        re.search(r'value="([^"]*)"[^>]*id="%s"' % input_id, page_html)
    return m.group(1) if m else ""

def parse_courses(html: str) -> list[dict]:
    """从 courselistdata 页面 HTML 解析课程列表。

    返回 [{name, teacher, courseid, clazzid, cpi}]，按出现顺序去重。
    """
    courses, seen = [], set()
    for m in re.finditer(r"stucoursemiddle\?courseid=(\d+)&clazzid=(\d+)&cpi=(\d+)", html):
        cid, clazz, cpi = m.groups()
        if (cid, clazz, cpi) in seen:
            continue
        seen.add((cid, clazz, cpi))
        seg = html[m.end():m.end() + 1600]
        nm = re.search(r'course-name[^>]*title="([^"]+)"', seg)
        teacher = ""
        for pm in re.finditer(r'<p class="overHidden2"[^>]*>([^<]{2,15})</p>', seg):
            txt = pm.group(1).strip()
            if txt and txt != (nm.group(1) if nm else ""):
                teacher = txt
                break
        courses.append({
            "name": html_mod.unescape(nm.group(1)) if nm else "?",
            "teacher": html_mod.unescape(teacher),
            "courseid": cid, "clazzid": clazz, "cpi": cpi,
        })
    return courses

def fetch_chapters(self, c: dict, with_nodes: bool = True) -> dict:
        """章节与任务点进度：{progress: (done,total)|None,
        nodes: [(level, text)]，level 0=一级章 1=二级小节}。
        with_nodes=False 只取总进度（全课程进度总览用，跳过节点解析）。"""
        page = self.fetch_course_page(c)
        page_enc = hidden_value(page, "enc")
        openc = hidden_value(page, "openc")
        r = self.get(URL_CHAPTER, params={
            "courseid": c["courseid"], "clazzid": c["clazzid"], "cpi": c["cpi"],
            "enc": page_enc, "openc": openc, "fromMiddle": 1, "ut": "s",
            "t": int(time.time() * 1000)})
        html = r.text
        if "没有此页面访问权限" in html:
            raise RuntimeError("章节页签名校验失败，请稍后重试")
        progress = None
        m_prog = re.search(r"已完成任务点\s*[:：]\s*<span[^>]*>\s*(\d+)\s*</span>\s*/\s*(\d+)", html)
        if m_prog:
            progress = (int(m_prog.group(1)), int(m_prog.group(2)))
        if not with_nodes:
            return {"progress": progress, "nodes": []}
        nodes: list[tuple[int, str]] = []
        # 一级章节（带序号的大章）
        chapter_titles = {}
        for m in re.finditer(
                r'<div class="catalog_num fl"><span><i><em[^>]*>(\d+)</em></i></span></div>\s*'
                r'<div class="catalog_name newCatalog_name"[^>]*>\s*<a class="clicktitle">\s*'
                r'<span title="([^"]*)"', html):
            chapter_titles[m.start()] = (m.group(1), html_mod.unescape(m.group(2)))
        # 二级小节（chapter_item，含任务点状态）
        sections = []
        for m in re.finditer(r'<div class="chapter_item"[^>]*title="([^"]*)"', html):
            seg = html[m.start():m.start() + 2200]
            end = seg.find("</li>")
            seg = seg[:end] if end > 0 else seg
            num = re.search(r'<span class="catalog_sbar">([\d.]+)</span>', seg)
            if not num:
                continue  # 一级章节自身的 chapter_item 外壳
            if "icon_yiwanc" in seg:
                status = "已完成"
            else:
                mp = re.search(r'<span class="catalog_points_yi">(\d+)</span>', seg)
                status = f"{mp.group(1)}个待完成" if mp else (
                    "未开放" if "暂未开放" in seg else "无任务点")
            sections.append((m.start(), num.group(1),
                             html_mod.unescape(m.group(1)), status))
        # 按文档顺序合并
        events = [(pos, 0, f"{num}. {title}") for pos, (num, title) in chapter_titles.items()]
        events += [(pos, 1, f"   {num} {title} | {status}")
                   for pos, num, title, status in sections]
        nodes = [(lvl, text) for _, lvl, text in sorted(events)]
        return {"progress": progress, "nodes": nodes}