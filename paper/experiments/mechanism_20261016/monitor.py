#!/usr/bin/env python3
"""Finite read-only monitoring. Does not launch/restart jobs or edit claims."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--jobs',required=True,help='JSON file containing a list of job names')
    p.add_argument('--out',required=True)
    p.add_argument('--interval',type=int,default=600)
    p.add_argument('--hours',type=float,default=24)
    a=p.parse_args()
    deadline=time.monotonic()+a.hours*3600
    terminal={'job_succeeded','job_failed','job_stopped','job_cancelled','succeeded','failed','stopped','cancelled'}
    failures=0
    while time.monotonic()<deadline:
        names=json.loads(Path(a.jobs).read_text())
        all_terminal=bool(names)
        for name in names:
            r=subprocess.run(['inspire','--json','job','status',name,'--workspace','分布式训练空间'],
                             capture_output=True,text=True,timeout=90)
            try:
                data=json.loads(r.stdout)
            except json.JSONDecodeError:
                data={'parse_error':True}
            def find_status(obj):
                if isinstance(obj,dict):
                    for k in ('status','state','phase'):
                        if isinstance(obj.get(k),str) and obj[k].lower().startswith('job_'):
                            return obj[k].lower()
                    for value in obj.values():
                        got=find_status(value)
                        if got:return got
                if isinstance(obj,list):
                    for value in obj:
                        got=find_status(value)
                        if got:return got
                return None
            status=find_status(data)
            all_terminal &= status in terminal
            # No raw API payload is persisted: it may include endpoint URLs.
            log=subprocess.run(['inspire','job','logs',name,'--workspace','分布式训练空间','--tail','6'],
                               capture_output=True,text=True,timeout=90)
            rec={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'job':name,'status':status,'status_returncode':r.returncode,
                 'log_returncode':log.returncode,'log_tail':log.stdout[-5000:]}
            with open(a.out,'a') as fh:fh.write(json.dumps(rec,ensure_ascii=False)+'\n')
            print(json.dumps({k:rec[k] for k in ['time','job','status','status_returncode']}),flush=True)
            failures=failures+1 if r.returncode else 0
        if all_terminal:
            print('MONITOR_DONE all jobs terminal',flush=True);return
        if failures>=3:
            print('MONITOR_STOP three consecutive API failures; inspect manually',flush=True);return
        time.sleep(min(a.interval,max(0,deadline-time.monotonic())))
    print('MONITOR_STOP time limit reached',flush=True)


if __name__=='__main__':main()
