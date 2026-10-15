"""Windows DPAPI；会话与缓存均按当前 Windows 用户加密。"""
import ctypes, json, sqlite3, os
from pathlib import Path
from ctypes import wintypes
class Blob(ctypes.Structure):
    _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
def crypt(data,decrypt=False):
    buf=ctypes.create_string_buffer(data); src=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte))); dst=Blob()
    api=ctypes.windll.crypt32
    api.CryptProtectData.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    api.CryptProtectData.restype=wintypes.BOOL
    api.CryptUnprotectData.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    api.CryptUnprotectData.restype=wintypes.BOOL
    if decrypt: ok=api.CryptUnprotectData(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst))
    else: ok=api.CryptProtectData(ctypes.byref(src),'XXT Assistant',None,None,None,1,ctypes.byref(dst))
    if not ok: raise ctypes.WinError()
    try: return ctypes.string_at(dst.data,dst.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes=[ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(dst.data)
class Store:
    def __init__(self,path=None):
        self.path=Path(path or Path(os.environ.get('LOCALAPPDATA','.'))/'XXTTodoAssistant'/'data.sqlite3')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA secure_delete=ON')
        self.db.execute('CREATE TABLE IF NOT EXISTS vault (key TEXT PRIMARY KEY, value BLOB NOT NULL)')
    def get(self,key,default=None):
        row=self.db.execute('SELECT value FROM vault WHERE key=?',(key,)).fetchone()
        if not row:return default
        return json.loads(crypt(row[0],True).decode())
    def put(self,key,value):
        self.db.execute('INSERT OR REPLACE INTO vault VALUES (?,?)',(key,crypt(json.dumps(value,ensure_ascii=False).encode())))
        self.db.commit()
    def delete(self,key):
        self.db.execute('DELETE FROM vault WHERE key=?',(key,));self.db.commit()
    def clear(self):
        self.db.execute('DELETE FROM vault');self.db.commit();self.db.execute('VACUUM')
