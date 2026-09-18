#!/usr/bin/env python3
"""Generate main-text displays from the original, audited experiment records.
Run from paper/: MPLCONFIGDIR=/tmp/skillvector-mpl python3 main_evidence.py
No model inference and no changes to experimental outcomes.
"""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import replication as rep

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
plt.rcParams.update({'font.size':8, 'axes.titlesize':9, 'axes.labelsize':8,
                     'xtick.labelsize':7, 'ytick.labelsize':7, 'pdf.fonttype':42})

def span_battery():
    tags = ['full-battery-a', 'full-battery-b']
    groups = rep.restricted(rep.load(tags))
    # Typeset as the earlier tab-big40: lower-case labels, reference rows
    # (the correct skill, the identity arm, the unpatched receiver) in italics,
    # CI_95 and a signed recovery column.
    arms = [(r'\emph{correct skill in context}', 'gold_in_context'),
            (r'$h_{\text{recv}}+\dvec$ \ (full span)', 'real_L8'),
            ('correct content, shared prefix', 'realm_L8'),
            (r'half dose ($\alpha=0.5$)', 'a0.5_L8'),
            ('another skill (individual donor)', 'dcross_L8'),
            ('mean from another skill family', 'dfar_L8'),
            ('mean from the same skill family', 'dnear_L8'),
            ('positions permuted', 'dshuf_L8'),
            ('norm-matched Gaussian noise', 'drand_L8'),
            (r'\emph{identity intervention}', 'self_L8'),
            (r'\emph{wrong skill, unpatched}', 'receiver')]
    out = [r'\begin{tabular}{@{}lrccc@{}}', r'\toprule',
           r'intervention & $n$ & accuracy & CI$_{95}$ & recovery $\rho$ \\', r'\midrule']
    data = {'sources': tags, 'groups': len(groups), 'arms': {}}
    for label, arm in arms:
        key = 'ok_' + arm
        mean, lo, hi, n, ng = rep.accuracy(groups, key)
        value = rep.rho(groups, key)
        data['arms'][arm] = dict(n=n, groups=ng, accuracy=mean, ci=[lo,hi], rho=value)
        out.append(f'{label} & ${n}$ & ${mean:.3f}$ & $[{lo:.3f},\\,{hi:.3f}]$ & ${value:+.2f}$ '+r'\\')
    out += [r'\bottomrule', r'\end{tabular}']
    (HERE/'tab-big40.tex').write_text('\n'.join(out)+'\n')
    (HERE/'battery-values.json').write_text(json.dumps(data,indent=2)+'\n')

def behaviour():
    import collections
    import random
    base = ROOT/'howskill/results/p8-step'
    runs = {key: {r['instance_id']: r for r in
            [json.loads(line) for line in (base/f'p8-{key}.jsonl').read_text().splitlines() if line.strip()]}
            for key in ['gold_no_tool','no_skill','ctrl_neutral_no_tool']}
    assert all(set(rows)==set(runs['no_skill']) for rows in runs.values())
    groups = collections.defaultdict(list)
    for iid, row in runs['no_skill'].items():
        groups[row['calculator_id']].append(int(runs['ctrl_neutral_no_tool'][iid]['correct'])-int(row['correct']))
    # All groups contain 20 items; bootstrapping their means is equivalent
    # to resampling calculators with all of their paired item differences.
    assert {len(rows) for rows in groups.values()} == {20}
    means = [sum(rows)/len(rows) for rows in groups.values()]
    rng = random.Random(0)
    values = sorted(sum(rng.choices(means,k=len(means)))/len(means) for _ in range(10000))
    summary = {'accuracy':{key:sum(r['correct'] for r in rows.values())/len(rows) for key,rows in runs.items()},
               'n':len(runs['no_skill']), 'groups':len(groups),
               'wrong_minus_none_ci_pp':[100*values[250],100*values[9750]],
               'bootstrap':{'unit':'calculator','draws':10000,'seed':0,'paired':True}}
    (HERE/'behaviour-values.json').write_text(json.dumps(summary,indent=2)+'\n')

def answer_format():
    base=ROOT/'whitebox/results/fetched/agent-harness-hsw2/whitebox/results'
    specs=[('Multiple choice','1','20260910-e14/e14-tierA-mc-8B'),
           ('Numeric answer','2--4','20260910-e14/e14-tierA-num-8B'),
           ('Chain of thought','Hundreds','20260911-cot/e14-tierA-cot-8B-k1')]
    out=[r'\begin{tabular}{@{}lrrrr@{}}',r'\toprule',
         r'Answer format & Tokens & Evaluated & Rescued & Best recovery \\',r'\midrule']
    ids=[]; values={}
    for name,tokens,tag in specs:
        curves=[]; item_ids=None; rescued=None
        for p in sorted((base/tag).glob('layer_*.jsonl')):
            rows=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
            rr=[r for r in rows if r['cell']=='R']
            key='gok_replace_real' if 'gok_replace_real' in rr[0] else 'ok_replace_real'
            curves.append(sum(bool(r[key]) for r in rr)/len(rr))
            current={r['id'] for r in rows}
            assert item_ids is None or item_ids==current
            item_ids=current;rescued=len(rr)
        assert curves,tag
        ids.append(item_ids)
        values[name] = dict(n=len(item_ids), rescued=rescued, best=max(curves), source=str(base/tag))
        out.append(f'{name} & {tokens} & {len(item_ids)} & {rescued} & ${max(curves):.3f}$ '+r'\\')
    assert ids[0]==ids[1] and ids[2]<=ids[0]
    out.extend([r'\bottomrule',r'\end{tabular}'])
    (HERE/'tab-answer-format.tex').write_text('\n'.join(out)+'\n')
    (HERE/'answer-format-values.json').write_text(json.dumps({'status':'pre-fix, latest complete local comparison','formats':values},indent=2)+'\n')

def answer_format_full(root=ROOT/'whitebox/results/fetched/tA'):
    """Table 1 from the post-fix full reruns (CAMPAIGN-2026-09-18 §2.2).

    Same model and 358 items for all three formats, the same 36-layer grid,
    capture and decode through the same attention-mask kernel, and an identity
    arm that must reproduce the unpatched answer on every item and layer.
    Returns False (and leaves the pre-fix table alone) until every shard is in.
    """
    specs=[('Multiple choice','1',['tA-mc']),
           ('Numeric answer','1--5',['tA-num-a','tA-num-b']),
           ('Chain of thought','Hundreds',['tA-cot-1','tA-cot-2','tA-cot-3','tA-cot-4'])]
    def layers_of(tags):
        out={}
        for t in tags:
            for p in sorted((root/t).glob('layer_*.jsonl')):
                out[int(p.stem.split('_')[1])]=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        return out
    rows_out=[]; vals={}
    for name,tokens,tags in specs:
        L=layers_of(tags)
        if sorted(L)!=list(range(36)):
            print(f'answer_format_full: {name} has layers {sorted(L)}; keeping the pre-fix table')
            return False
        ids=None; curve={}
        for layer,rows in L.items():
            cur={r['id'] for r in rows}
            assert ids is None or ids==cur, f'{name}: item set differs at layer {layer}'
            if len(cur) != 358:
                print(f'answer_format_full: incomplete {name} layer {layer}: {len(cur)}/358')
                return False
            ids=cur
            rr=[r for r in rows if r['cell']=='R']
            curve[layer]=sum(bool(r['ok_replace_real']) for r in rr)/len(rr)
        best=max(curve,key=curve.get)
        vals[name]={'n':len(ids),'rescued':len(rr),'best':curve[best],'best_layer':best,'curve':curve,
                    'sources':[str(root/t) for t in tags]}
        rows_out.append(f'{name} & {tokens} & {len(ids)} & {len(rr)} & ${curve[best]:.3f}$ '+r'\\')
    # identity: every item, every layer that ran it
    ident=[]
    for tags in (['tA-mc'],['tA-num-a','tA-num-b'],['tA-cot-self']):
        for rows in layers_of(tags).values():
            ident+= [r['ok_replace_self']==r['ok_no'] for r in rows if 'ok_replace_self' in r]
    vals['identity']=[sum(ident),len(ident)]
    assert ident and all(ident), f'identity arm is not exact: {sum(ident)}/{len(ident)}'
    out=[r'\begin{tabular}{@{}lrrrr@{}}',r'\toprule',
         r'Answer format & Tokens & Evaluated & Rescued & Best recovery \\',r'\midrule']+rows_out+[r'\bottomrule',r'\end{tabular}']
    (HERE/'tab-answer-format.tex').write_text('\n'.join(out)+'\n')
    ident_n=vals.pop('identity')
    (HERE/'answer-format-values.json').write_text(json.dumps(
        {'status':'post-fix, 358 items, layers 0-35 for every format','identity':ident_n,
         'formats':vals},indent=1)+'\n')
    vals['identity']=ident_n
    print(json.dumps({k:(v if k=='identity' else {kk:vv for kk,vv in v.items() if kk!='curve'}) for k,v in vals.items()}))
    return True

def skill_content():
    # full-dataset rerun: every rescued item of every calculator with at least
    # two. The forty-calculator shards it replaces were fixmask-big40 and
    # fixmask-quarters40-q*, and fixmask-dl for the doc-last half.
    groups=rep.restricted(rep.load(['full-battery-a','full-quarters']))
    assert len(groups)==14 and sum(map(len,groups.values()))==135
    out=[r'\begin{tabular}{@{}lcc@{}}',r'\toprule',
         r'\multicolumn{3}{@{}l}{\textit{Skill quarters, layer 8, skill before question} ($n=135$)} \\',
         r'Injected content & \multicolumn{2}{c}{Recovery $\rho$} \\',r'\midrule']
    for name,key in [('Prose description','q0'),('Formulas','q1'),('Tool signatures','q2'),('Worked example','q3'),('Full span','real')]:
        v=rep.rho(groups,f'ok_{key}_L8')
        out.append(f'{name} & \\multicolumn{{2}}{{c}}{{${v:.2f}$}} '+r'\\')
    dl=rep.restricted(rep.load(['full-dl-a','full-dl-b']))
    assert len(dl)==17 and sum(map(len,dl.values()))==151
    out.extend([r'\midrule',r'\multicolumn{3}{@{}l}{\textit{Question dependence, skill after question} ($n=151$)} \\',
                r'Injected content & Layer 8 & Layer 16 \\',r'\midrule'])
    for name,key in [('This instance','real'),('Other instances of the same skill','dother'),('Instance-specific remainder','dperp')]:
        a,b=(rep.rho(dl,f'ok_{key}_L{l}') for l in [8,16])
        out.append(f'{name} & ${a:.2f}$ & ${b:.2f}$ '+r'\\')
    out.extend([r'\bottomrule',r'\end{tabular}'])
    (HERE/'tab-skill-content.tex').write_text('\n'.join(out)+'\n')

def depth():
    # full-dataset rerun at one-layer resolution through the handover: the
    # subset sweep (big40-depth) measured 0,4,8,12,14,15,16,20 and could not
    # localise the drop, which falls entirely between layers 12 and 13.
    dep=rep.restricted(rep.load(['full-depth-a','full-depth-b',
                                 'full-depth-c13','full-depth-d',
                                 'full-battery-a']))
    assert len(dep)==14 and sum(map(len,dep.values()))==135
    layers=sorted({int(k.split('_L')[-1]) for rs in dep.values() for r in rs for k in r if k.startswith('ok_real_L')})
    vals=[rep.rho(dep,f'ok_real_L{l}') for l in layers]
    ko=[r for r in rep.load(['full-ko']) if r['ok_with'] and not r['ok_without']]
    assert len(ko)==466
    kl=ko[0]['layers']; kv=[sum(bool(r['ok_block_from'][i]) for r in ko)/len(ko) for i in range(len(kl))]
    # Windows: the 2026-09-18 rerun builds the receiver exactly as the battery
    # does (wb_spanpatch --filler fixedskill); full-window used the control
    # prompt's tokens and was normalised by the battery's baselines anyway
    # (CAMPAIGN-2026-09-18 §2.3). It also adds the every-layer window 0:35.
    rows_in=lambda t: len(rep.load([t]))
    if rows_in('x8-win-a')>=467 and rows_in('x8-win-b')>=467:
        win=rep.restricted(rep.load(['x8-win-a','x8-win-b','full-battery-a']))
        assert sum(map(len,win.values()))==135
        wk=['L16','w8_11','w12_15','w14_19','w16_35','w0_35']
    else:
        # This earlier complete run has a different receiver. Its own
        # baselines are mandatory; importing the battery baseline was invalid.
        win=rep.restricted(rep.load(['full-window']))
        assert sum(map(len,win.values()))==222
        wk=['L16','w8_11','w12_15','w14_19','w16_35']
    wv=[rep.rho(win,f'ok_real_{k}') for k in wk]
    fig,axes=plt.subplots(1,3,figsize=(7.2,2.25),gridspec_kw={'width_ratios':[1,1,1.25]},layout='constrained')
    a,b,c=axes
    a.plot(layers,vals,'o-',color='#0072B2',ms=3,lw=1.5)
    a.axvspan(12,13,color='#0072B2',alpha=.12)
    a.set(title='(a) Span replacement',xlabel='Injection layer',ylabel=r'Recovery $\rho$')
    b.plot(kl,kv,'s-',color='#D55E00',ms=3,lw=1.5)
    b.set(title='(b) Attention knockout',xlabel='Block from layer L onward',ylabel='Fraction of rescued items retained')
    for ax in [a,b]:
        ax.axhline(.5,ls=':',lw=.8,color='#777777')
        ax.set_xticks([0,8,16,24,32]);ax.set_xlim(-1,35)
    c.bar(range(len(wv)),wv,color=['#999999','#0072B2','#56B4E9','#CC79A7','#D55E00','#009E73'][:len(wv)],width=.65)
    c.set_xticks(range(len(wv)),['16','8–11','12–15','14–19','16–35','0–35'][:len(wv)],rotation=35,ha='right')
    c.set(title='(c) Layer windows',xlabel='Layers receiving span states',ylabel=r'Recovery $\rho$')
    for i,v in enumerate(wv):c.text(i,v+.025,f'{v:.2f}',ha='center',va='bottom',fontsize=7)
    for ax,n in zip(axes,[135,466,sum(map(len,win.values()))]):
        ax.set_ylim(0,1.15);ax.spines[['top','right']].set_visible(False)
        ax.text(.98,.98,f'n = {n}',transform=ax.transAxes,ha='right',va='top',fontsize=7)
    fig.savefig(HERE/'fig-transfer-reading.pdf',bbox_inches='tight')
    fig.savefig(HERE/'fig-transfer-reading.png',bbox_inches='tight',dpi=160)
    plt.close(fig)
    data={'sufficiency':list(zip(layers,vals)),'necessity':list(zip(kl,kv)),
          'windows':dict(zip(wk,wv)), 'window_n':sum(map(len,win.values())),
          'window_groups':len(win), 'window_sources':(['x8-win-a','x8-win-b','full-battery-a']
              if 'w0_35' in wk else ['full-window'])}
    (HERE/'main-evidence-values.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))

def depth_v2(out_dir=HERE, force=False):
    """Figure 3 on one layer axis, every layer measured (2026-09-19).

    The earlier figure plotted (a) against an axis running to 35 with data to
    20, (b) against "block from L onward" at stride 4, and (c) as unordered
    categorical bars (16, 8-11, 12-15, ...). Here both panels share the layer
    axis 0-35 and every point is measured:
      (a) span states written at layer L; attention to the skill blocked from
          L onward; the last prompt position written at L -- all on the same
          screened items (the knockout on their rescued subset), so the two
          boundaries are read on the same items;
      (b) every window drawn across the layers it writes, at its recovery.
    Returns False (drawing nothing) until every curve is complete, unless
    `force` (layout checks only).
    """
    row = next(r for r in rep.resolved_rows() if r[0] == 'MedCalc' and r[1] == 'Qwen3-8B')
    dep_tags, ko_tags = row[5], row[7]
    dep = rep.restricted(rep.load(dep_tags))
    groups = set(dep)
    span = {L: rep.rho(dep, f'ok_real_L{L}') for L in range(36)}
    kc, kn = rep.ko_curve(ko_tags, groups=groups)
    tq = rep.restricted(rep.load(['full-battery-a', 'pb-tq', 'fp-a', 'fp-b', 'fp-c',
                                  'fp1-a', 'fp1-b', 'fp1-c', 'fp1-d']))
    last = {L: rep.rho(tq, f'ok_tq1_L{L}') for L in range(36)}
    wins = rep.restricted(rep.load(['full-battery-a', 'x8-win-a', 'x8-win-b', 'win1-a', 'win1-b']))
    wdef = [(0, 3), (4, 7), (8, 11), (12, 15), (16, 19), (20, 23), (24, 27), (28, 31), (32, 35),
            (14, 19), (16, 35), (0, 35)]
    wv = {w: rep.rho(wins, f'ok_real_w{w[0]}_{w[1]}') for w in wdef}
    ready = (all(v is not None for v in span.values()) and len(kc) == 36
             and all(v is not None for v in last.values()) and all(v is not None for v in wv.values()))
    if not ready and not force:
        return False
    n = sum(map(len, dep.values()))
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 2.55), layout='constrained',
                               gridspec_kw={'width_ratios': [1.25, 1]})
    xs = [L for L in range(36) if span[L] is not None]
    a.plot(xs, [span[L] for L in xs], 'o-', color='#0072B2', ms=2.8, lw=1.5,
           label='span states written at layer $L$')
    ks = sorted(kc)
    a.plot(ks, [kc[L] for L in ks], 's-', color='#D55E00', ms=2.6, lw=1.5,
           label='attention to the skill blocked from $L$ on')
    lx = [L for L in range(36) if last[L] is not None]
    a.plot(lx, [last[L] for L in lx], '^--', color='#777777', ms=2.6, lw=1.0,
           label='last prompt position written at $L$')
    tb = next((L for L in xs if span[L] < .5), None)
    rb = next((L for L in ks if kc[L] >= .5), None)
    if tb is not None and rb is not None:
        a.axvspan(tb - .5, rb - .5, color='#E69F00', alpha=.12, lw=0)
        a.text((tb + rb) / 2 - .5, .62, 'still read,\nno longer\ntransferable', ha='center',
               va='center', fontsize=6.3, color='#8a5a00')
        for x in (tb - .5, rb - .5):
            a.axvline(x, color='#555555', lw=.7, ls=':')
    a.axhline(.5, color='#999999', lw=.6, ls=':')
    a.set(xlabel='layer $L$', ylabel="fraction of the skill's gain", xlim=(-1, 36), ylim=(-.03, 1.08))
    a.set_title('(a) transfer ends before reading does', loc='left', fontsize=8.5)
    a.legend(loc='center left', fontsize=6.2, frameon=False, handlelength=1.8,
             bbox_to_anchor=(0.0, 0.40))
    # (b) windows as spans on the same axis
    b.plot(xs, [span[L] for L in xs], '-', color='#0072B2', lw=.9, alpha=.35,
           label='one layer at a time, from (a)')
    import matplotlib.patches as mp
    for (lo, hi) in wdef:
        v = wv[(lo, hi)]
        if v is None:
            continue
        long = hi - lo > 5
        col = '#009E73' if (lo, hi) == (0, 35) else ('#CC79A7' if long else '#0072B2')
        b.add_patch(mp.Rectangle((lo - .45, v - .018), hi - lo + .9, .036, color=col,
                                 alpha=.55 if long else .9, lw=0))
        if long or (lo, hi) in ((8, 11), (12, 15)):
            b.text(hi + .6 if (lo, hi) != (0, 35) else 17.5, v + (.04 if (lo, hi) != (16, 35) else -.07),
                   f'{lo}–{hi}: {v:.2f}', fontsize=6, color='#333333',
                   ha='left' if (lo, hi) != (0, 35) else 'center')
    b.axhline(.5, color='#999999', lw=.6, ls=':')
    b.set(xlabel='layers written (each bar spans its window)', xlim=(-1, 36), ylim=(-.03, 1.08))
    b.set_title('(b) writing more layers at once', loc='left', fontsize=8.5)
    b.legend(loc='center right', fontsize=6.2, frameon=False, bbox_to_anchor=(1.0, 0.5))
    for ax in (a, b):
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_xticks([0, 4, 8, 12, 16, 20, 24, 28, 32, 35])
    fig.savefig(out_dir/'fig-transfer-reading.pdf', bbox_inches='tight')
    fig.savefig(out_dir/'fig-transfer-reading.png', bbox_inches='tight', dpi=180)
    plt.close(fig)
    data = {'sufficiency': [(L, span[L]) for L in xs], 'necessity': [(L, kc[L]) for L in ks],
            'last_position': [(L, last[L]) for L in lx], 'n': n, 'groups': len(dep), 'ko_n': kn,
            'windows': {f'w{lo}_{hi}': v for (lo, hi), v in wv.items()},
            'window_n': sum(map(len, wins.values())), 'transfer_boundary': tb, 'reading_boundary': rb,
            'sources': {'depth': dep_tags, 'knockout': ko_tags,
                        'last': ['full-battery-a', 'pb-tq', 'fp-a', 'fp-b', 'fp-c', 'fp1-a', 'fp1-b', 'fp1-c', 'fp1-d'],
                        'windows': ['full-battery-a', 'x8-win-a', 'x8-win-b', 'win1-a', 'win1-b']},
            'version': 2}
    if out_dir == HERE:
        (HERE/'main-evidence-values.json').write_text(json.dumps(data, indent=2)+'\n')
    return True

if __name__=='__main__':
    answer_format_full() or answer_format();span_battery();skill_content()
    depth_v2() or depth()
    behaviour()
