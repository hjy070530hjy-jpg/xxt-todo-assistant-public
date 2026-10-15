"""Windows memory reclamation; independent implementation, see docs/内存清理研究.md."""
import ctypes,json,os,secrets,subprocess,sys,tempfile,time
from contextlib import contextmanager
from pathlib import Path
from ctypes import wintypes as w

class MemoryStatus(ctypes.Structure):
    _fields_=[('length',w.DWORD),('load',w.DWORD)]+[(name,ctypes.c_ulonglong) for name in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]

def memory_status():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes=[ctypes.POINTER(MemoryStatus)];kernel.GlobalMemoryStatusEx.restype=w.BOOL
    value=MemoryStatus();value.length=ctypes.sizeof(value)
    if not kernel.GlobalMemoryStatusEx(ctypes.byref(value)):raise ctypes.WinError(ctypes.get_last_error())
    return {'total':int(value.total),'available':int(value.available)}

def summarize(before,after,completed,failures):
    delta=after['available']-before['available']
    return {'before':before,'after':after,'delta':delta,'released':max(0,delta),'completed':completed,'failures':failures,'status':('partial' if failures else 'success') if completed else 'failed'}

def readable_bytes(value):
    return f'{value/1024**3:.2f} GB' if value>=1024**3 else f'{value/1024**2:.1f} MB'

class Luid(ctypes.Structure):_fields_=[('low',w.DWORD),('high',w.LONG)]
class LuidAttributes(ctypes.Structure):_fields_=[('luid',Luid),('attributes',w.DWORD)]
class TokenPrivileges(ctypes.Structure):_fields_=[('count',w.DWORD),('entry',LuidAttributes)]

@contextmanager
def memory_privilege():
    adv=ctypes.WinDLL('advapi32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    adv.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)];adv.OpenProcessToken.restype=w.BOOL
    adv.LookupPrivilegeValueW.argtypes=[w.LPCWSTR,w.LPCWSTR,ctypes.POINTER(Luid)];adv.LookupPrivilegeValueW.restype=w.BOOL
    adv.AdjustTokenPrivileges.argtypes=[w.HANDLE,w.BOOL,ctypes.POINTER(TokenPrivileges),w.DWORD,ctypes.POINTER(TokenPrivileges),ctypes.POINTER(w.DWORD)];adv.AdjustTokenPrivileges.restype=w.BOOL
    kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
    token=w.HANDLE();previous=TokenPrivileges();changed=False
    if not adv.OpenProcessToken(w.HANDLE(-1),0x28,ctypes.byref(token)):raise ctypes.WinError(ctypes.get_last_error())
    try:
        requested=TokenPrivileges();requested.count=1;requested.entry.attributes=2
        if not adv.LookupPrivilegeValueW(None,'SeProfileSingleProcessPrivilege',ctypes.byref(requested.entry.luid)):raise ctypes.WinError(ctypes.get_last_error())
        length=w.DWORD();ctypes.set_last_error(0)
        ok=adv.AdjustTokenPrivileges(token,False,ctypes.byref(requested),ctypes.sizeof(previous),ctypes.byref(previous),ctypes.byref(length));code=ctypes.get_last_error()
        changed=bool(ok and previous.count)
        if not ok or code:raise PermissionError('无法取得内存清理权限，请允许管理员授权。')
        yield
    finally:
        if changed:adv.AdjustTokenPrivileges(token,False,ctypes.byref(previous),0,None,None)
        kernel.CloseHandle(token)

class WindowsMemory:
    status=staticmethod(memory_status)
    privilege=staticmethod(memory_privilege)
    def operation(self,command):
        nt=ctypes.WinDLL('ntdll',use_last_error=True)
        nt.NtSetSystemInformation.argtypes=[w.ULONG,ctypes.c_void_p,w.ULONG];nt.NtSetSystemInformation.restype=ctypes.c_int32
        value=w.ULONG(command);status=nt.NtSetSystemInformation(80,ctypes.byref(value),ctypes.sizeof(value))
        if status!=0:raise OSError(f'NTSTATUS 0x{status & 0xffffffff:08X}')

def clean_memory(backend=None,pause=time.sleep):
    backend=backend or WindowsMemory();completed=[];failures=[]
    with backend.privilege():
        before=backend.status()
        for label,command in [('工作集',2),('待机缓存',4)]:
            try:backend.operation(command);completed.append(label)
            except OSError as error:failures.append({'operation':label,'reason':str(error)})
        pause(.35);after=backend.status()
    return summarize(before,after,completed,failures)

class ShellExecuteInfo(ctypes.Structure):
    _fields_=[('cbSize',w.DWORD),('fMask',w.ULONG),('hwnd',w.HWND),('lpVerb',w.LPCWSTR),('lpFile',w.LPCWSTR),('lpParameters',w.LPCWSTR),('lpDirectory',w.LPCWSTR),('nShow',ctypes.c_int),('hInstApp',w.HINSTANCE),('lpIDList',ctypes.c_void_p),('lpClass',w.LPCWSTR),('hkeyClass',w.HKEY),('dwHotKey',w.DWORD),('hIcon',w.HANDLE),('hProcess',w.HANDLE)]

def is_admin():return bool(ctypes.WinDLL('shell32').IsUserAnAdmin())

def run_cleanup():
    if is_admin():return clean_memory()
    with tempfile.TemporaryDirectory(prefix='xxt-memory-') as folder:
        nonce=secrets.token_hex(16);arguments=['--memory-clean-helper',folder,nonce]
        if not getattr(sys,'frozen',False):arguments.insert(0,str(Path(__file__).resolve().parents[1]/'main.py'))
        executable=sys.executable
        if not getattr(sys,'frozen',False) and Path(executable).with_name('pythonw.exe').exists():executable=str(Path(executable).with_name('pythonw.exe'))
        shell=ctypes.WinDLL('shell32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        shell.ShellExecuteExW.argtypes=[ctypes.POINTER(ShellExecuteInfo)];shell.ShellExecuteExW.restype=w.BOOL
        kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];kernel.WaitForSingleObject.restype=w.DWORD
        kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
        info=ShellExecuteInfo();info.cbSize=ctypes.sizeof(info);info.fMask=0x140;info.lpVerb='runas';info.lpFile=executable;info.lpParameters=subprocess.list2cmdline(arguments);info.nShow=0
        if not shell.ShellExecuteExW(ctypes.byref(info)):
            if ctypes.get_last_error()==1223:raise PermissionError('已取消管理员授权，未执行内存清理。')
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            wait=kernel.WaitForSingleObject(info.hProcess,120000)
            if wait==258:raise TimeoutError('内存清理等待超时，暂时无法确认结果。')
            if wait!=0:raise ctypes.WinError(ctypes.get_last_error())
        finally:kernel.CloseHandle(info.hProcess)
        path=Path(folder)/'result.json'
        if not path.exists():raise RuntimeError('未收到清理结果，未将本次操作显示为成功。')
        payload=json.loads(path.read_text(encoding='utf-8'))
        if payload.get('nonce')!=nonce:raise RuntimeError('内存清理结果校验失败。')
        if payload.get('error'):raise RuntimeError(payload['error'])
        return payload['result']

def helper_main(arguments):
    if len(arguments)!=2:return 2
    folder=Path(arguments[0]).resolve();nonce=arguments[1]
    if folder.parent!=Path(tempfile.gettempdir()).resolve() or not folder.name.startswith('xxt-memory-') or not folder.is_dir() or len(nonce)!=32 or any(c not in '0123456789abcdef' for c in nonce):return 2
    try:payload={'nonce':nonce,'result':clean_memory()}
    except Exception as error:payload={'nonce':nonce,'error':str(error)}
    temporary=folder/'result.tmp';temporary.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8');os.replace(temporary,folder/'result.json')
    return 1 if 'error' in payload else 0
