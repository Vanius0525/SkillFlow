"""Bounded local launch controller; never submits formal follow-ups before gate."""
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time

HERE = Path(__file__).resolve().parent
REMOTE = '/inspire/ssd/project/project-public/czxs253130660/state-completeness-20261022-v2'
STATE = HERE/'launch-state.json'


def call(args, timeout=180):
    r = subprocess.run(['/home/vanius/.local/bin/inspire', '--account', 'me']+args, capture_output=True,
                       text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError((r.stdout+r.stderr)[-1800:])
    return r.stdout


def inspect_gate():
    code = f'''from pathlib import Path
import json,hashlib,gzip
r=Path({REMOTE!r})/'outputs'
p=r/'gate-0-of-1.done.json'
f=r/'gate-0-of-1.failed.json'
if f.exists():
 print('GATE '+json.dumps({{'failed':json.loads(f.read_text())}}))
elif not p.exists():
 print('GATE '+json.dumps({{'ready':False}}))
else:
 d=json.loads(p.read_text()); raw=r/'gate-0-of-1.jsonl.gz'
 assert d['records']==14 and hashlib.sha256(raw.read_bytes()).hexdigest()==d['raw_sha256']
 rows=[json.loads(l) for l in gzip.decompress(raw.read_bytes()).decode().splitlines()]
 for iid in {{x['instance_id'] for x in rows}}:
  a={{x['arm']:x for x in rows if x['instance_id']==iid}}
  assert a['identity']['token_ids']==a['wrong']['token_ids']
  assert a['full_copy']['token_ids']==a['donor']['token_ids']
 print('GATE '+json.dumps({{'ready':True,'done':d}}))
'''
    command = 'python -c '+shlex.quote(code)
    result = call(['notebook','exec','wt-family-prep-1018','--workspace','CPU资源空间',
                   '--timeout','90',command], timeout=120)
    return json.loads(next(x[5:] for x in result.splitlines() if x.startswith('GATE ')))


def main():
    if (HERE/'TASK-COMPLETE').exists():
        print('TASK_ALREADY_COMPLETE_NO_SUBMISSION')
        return
    state = json.loads(STATE.read_text()) if STATE.exists() else {
        'submitted':['wt-state-repair-s0-1022-r3'], 'status':'awaiting_gate', 'started':time.time()}
    def save():
        state['checked_at'] = datetime.datetime.now().astimezone().isoformat()
        STATE.write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n')
    save()
    consecutive_errors = 0
    while time.time()-state['started'] < 20*3600:
        try:
            gate = inspect_gate()
            state['gate'] = gate
            if 'failed' in gate:
                state['status'] = 'gate_failed_no_followups'
                save()
                return
            if gate['ready']:
                state['status'] = 'submitting_followups'
                save()
                break
            state['status'] = 'awaiting_gate_repair_only'
            consecutive_errors = 0
            save()
        except Exception as exc:
            consecutive_errors += 1
            state['last_error'] = str(exc)
            save()
            if consecutive_errors >= 3:
                state['status'] = 'observer_error_no_followups'
                save()
                return
        time.sleep(60)
    else:
        state['status'] = 'gate_wait_expired_no_followups'
        save()
        return
    jobs = json.loads((HERE/'jobs.json').read_text())['jobs']
    for job in jobs[1:]:
        if job['name'] in state['submitted']:
            continue
        args = ['job','create','--name',job['name']]
        for key in ('workspace','project','group','quota','image','priority','shm_size','max_time','command'):
            args += ['--'+key.replace('_','-'),str(job[key])]
        for key,value in job['env'].items():
            args += ['--env',f'{key}={value}']
        # Persist the in-flight name; ambiguous submission errors require manual check.
        state['in_flight_submission'] = job['name']
        save()
        try:
            output = call(args)
        except Exception as exc:
            state.update(status='submission_error_check_platform_before_retry', last_error=str(exc))
            save()
            raise
        state['submitted'].append(job['name'])
        state['last_create_output'] = output.strip()
        state.pop('in_flight_submission',None)
        save()
    state['status'] = 'all_planned_repair_jobs_submitted_not_completion'
    save()


if __name__ == '__main__':
    main()
