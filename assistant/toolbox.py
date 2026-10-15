"""Launch user-provided desktop utilities without invoking a command shell."""
import os,sys,hashlib,tempfile
from pathlib import Path

def geek_path(settings):
    selected=settings.get('geek_path')
    if selected:return Path(selected)
    base=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
    return base/'extras'/'geek'/'geek.exe'

def prepare_geek(settings):
    path=geek_path(settings)
    if path.suffix.lower()!='.exe' or not path.is_file():
        raise FileNotFoundError('Geek 程序不存在，请重新选择 geek.exe。')
    if not getattr(sys,'frozen',False) or settings.get('geek_path'):return path.resolve()
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
    folder=Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'XXTTodoAssistant'/'tools'/'geek'/digest[:16];folder.mkdir(parents=True,exist_ok=True);target=folder/'geek.exe'
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==digest:return target
    # Geek may remain open after the assistant exits. Keep its working copy
    # outside PyInstaller's temporary runtime directory and verify every launch.
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=folder,suffix='.tmp',delete=False) as stream:temporary=Path(stream.name);stream.write(data)
        os.replace(temporary,target)
    finally:
        if temporary and temporary.exists():temporary.unlink()
    return target

def open_geek(settings):os.startfile(str(prepare_geek(settings)))
