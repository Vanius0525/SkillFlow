#!/usr/bin/env python3
"""Figure 4 (fig-posbudget) and its numbers, written into paper/.

    cd paper && MPLCONFIGDIR=/tmp/skillvector-mpl python3 fig_posbudget.py

A thin wrapper: the experiment's report lives in
whitebox/analysis/posbudget_report.py, which recomputes every arm from the
run files, runs the instrument checks (the identity arm must reproduce the
receiver and the untruncated transplant must reproduce the battery, on every
item) and draws the four panels. Here it is pointed at the manuscript
directory so refresh_main_data.py regenerates the figure with everything else.
"""
import pathlib
import runpy
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.argv = [sys.argv[0], "--out", str(HERE), "--B", "4000"]
runpy.run_path(str(HERE.parent / "whitebox/analysis/posbudget_report.py"),
               run_name="__main__")
