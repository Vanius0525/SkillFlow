#!/usr/bin/env python3
"""Write a self-contained Overleaf project containing reachable assets only."""
import re
import sys
import zipfile
import pathlib


def project_members(paper):
    paper=pathlib.Path(paper).resolve()
    found=set()
    def add_tex(path):
        path=path.resolve()
        if not path.is_relative_to(paper) or not path.is_file():
            raise ValueError(f'Missing or external TeX input: {path}')
        if path in found:return
        found.add(path)
        text=re.sub(r'(?<!\\)%[^\n]*','',path.read_text())
        for name in re.findall(r'\\(?:input|include)\{([^{}]+)\}',text):
            target=paper/name
            add_tex(target if target.suffix else target.with_suffix('.tex'))
        for name in re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}',text):
            target=pathlib.Path(name)
            if not target.suffix:target=target.with_suffix('.pdf')
            options=[paper/target,paper/'figures'/target]
            match=next((p.resolve() for p in options if p.is_file()),None)
            if match is None or not match.is_relative_to(paper):
                raise ValueError(f'Missing or external figure: {name}')
            found.add(match)
        for names in re.findall(r'\\bibliography\{([^{}]+)\}',text):
            for name in names.split(','):
                target=(paper/name).with_suffix('.bib')
                if not target.is_file():raise ValueError(f'Missing bibliography: {name}')
                found.add(target.resolve())
    add_tex(paper/'main.tex')
    return sorted(found)


def write_project_zip(paper,out):
    paper=pathlib.Path(paper).resolve()
    members=project_members(paper)
    pending=any(path.name=='fig-mechanism-reserved.pdf' for path in members)
    phase_note=('The mechanism section contains explicitly blank result panels.\n'
                'These are draft reservations for Qwen3-8B/MedCalc experiments,\n'
                'not measured results.\n\n' if pending else
                'The mechanism section includes measured Qwen3-8B/MedCalc results.\n\n')
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for path in members:z.write(path,path.relative_to(paper).as_posix())
        z.writestr('README.md',
            '# Overleaf review draft\n\n'
            'Main file: main.tex. Compiler: pdfLaTeX. Bibliography: BibTeX.\n\n'
            'Upload this ZIP directly as a new Overleaf project. The default\n'
            'build is the WWW manuscript. Change \\extendedappendixfalse to\n'
            '\\extendedappendixtrue for the extended technical report.\n\n'
            +phase_note+
            'This project contains only TeX inputs, referenced PDF figures,\n'
            'the bibliography and this README. No local absolute paths,\n'
            'experiment scripts, raw logs or build caches are needed.\n')
    return len(members)+1

if __name__=='__main__':
    paper=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else pathlib.Path(__file__).resolve().parents[1])
    out=paper/'overleaf-skillvector.zip'
    count=write_project_zip(paper,out)
    print(f'-> {out}  ({count} files, {out.stat().st_size/1e6:.2f} MB)')
