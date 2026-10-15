"""Presentation-only removal of confidence columns; raw estimates stay intact."""
import re
NUM=r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)'
CI=re.compile(r'\s*\$\[\s*'+NUM+r'\s*,(?:\\,)?\s*'+NUM+r'\s*\]\$')

def point_tables(text):
    def table(m):
        block=m.group(0)
        lines=block.splitlines()
        ci_index=None
        for line in lines:
            if '&' in line:
                cells=line.split('&')
                for i,c in enumerate(cells):
                    if re.search(r'CI|confidence',c) and not c.strip().startswith('$\\rho$') and not c.strip().startswith('$\\Delta$'):
                        ci_index=i
        if ci_index is not None:
            # Existing tables with standalone CI columns use simple l/r/c specs.
            match=re.search(r'\\begin\{tabular\}\{([lrc]+)\}',block)
            if match is None:
                match=re.search(r'\\begin\{tabular\}\{@\{\}([lrc]+)@\{\}\}',block)
            if match is None:raise ValueError('Unsupported CI column specification')
            spec=match.group(1);new=spec[:ci_index]+spec[ci_index+1:]
            block=block[:match.start(1)]+new+block[match.end(1):]
            lines=block.splitlines()
            for j,line in enumerate(lines):
                cells=line.split('&')
                if len(cells)==len(spec):
                    removed=cells.pop(ci_index)
                    if ci_index==len(spec)-1 and r'\\' in removed: cells[-1]+=r' \\'
                    lines[j]=' & '.join(c.strip() for c in cells)
                elif '\\multicolumn' in line:
                    lines[j]=re.sub(r'\\multicolumn\{'+str(len(spec))+r'\}',lambda _: '\\multicolumn{'+str(len(spec)-1)+'}',line)
            block='\n'.join(lines)
        block=CI.sub('',block)
        block=block.replace('[95\\% CI]','').replace('[95% CI]','')
        return block
    return re.sub(r'\\begin\{tabular\}.*?\\end\{tabular\}',table,text,flags=re.S)

if __name__=='__main__':
    from _paths import PAPER,TABLES
    for p in list(TABLES.glob('*.tex'))+list((PAPER/'appendix').glob('*.tex')):
        p.write_text(point_tables(p.read_text()))
