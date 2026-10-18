"""Use the manuscript's Linux Libertine family in every maintained figure.

Install Linux Libertine or set PAPER_FONT_DIR to its OTF/TTF directory.
The existing local MiKTeX installation is also discovered on WSL.
"""
import os
from pathlib import Path
import matplotlib as mpl
from matplotlib import font_manager


def configure_fonts():
    roots=[]
    if os.environ.get('PAPER_FONT_DIR'):
        roots.append(Path(os.environ['PAPER_FONT_DIR']))
    roots.extend(Path('/mnt/c/Users').glob('*/AppData/Local/Programs/MiKTeX/fonts/opentype/public/libertine'))
    for root in roots:
        for stem in ('LinLibertine_R','LinLibertine_RB','LinLibertine_RI','LinLibertine_RBI'):
            for suffix in ('.otf','.ttf'):
                path=root/(stem+suffix)
                if path.is_file():font_manager.fontManager.addfont(str(path))
    family='Linux Libertine O'
    font_manager.findfont(family, fallback_to_default=False)
    mpl.rcParams.update({
        'font.family':family,
        'mathtext.fontset':'custom',
        'mathtext.rm':family,
        'mathtext.it':family+':italic',
        'mathtext.bf':family+':bold',
        'mathtext.sf':family,
        'mathtext.cal':family,
        'mathtext.tt':family,
        'mathtext.fallback':None,
        'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
    })
