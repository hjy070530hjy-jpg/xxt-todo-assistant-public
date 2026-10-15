"""Launch user-provided desktop utilities without invoking a command shell."""
import os,sys
from pathlib import Path

def geek_path(settings):
    selected=settings.get('geek_path')
    if selected:return Path(selected)
    base=Path(sys._MEIPASS) if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
    return base/'extras'/'geek'/'geek.exe'

def open_geek(settings):
    path=geek_path(settings)
    if path.suffix.lower()!='.exe' or not path.is_file():
        raise FileNotFoundError('Geek 程序不存在，请重新选择 geek.exe。')
    os.startfile(str(path.resolve()))
