# SkillVector 论文交接

## 2026-10-17 Web / Agent Skills / WWW格式修订（完成；后续只维护投稿版）

- 用户最新偏好：**只维护一个投稿版，不再维护/编译/交付扩展版**。已移除main.tex扩展切换和C–H加载；旧扩展源和PDF保留归档、未改写。build.sh默认且仅支持submission，只复制实际依赖。主图style默认仅更新投稿图；table style仅更新可达表与A/B，历史扩展诊断不再生成。旧实验完成标记、停用的timer继续保持；没有新增推理或资源操作。
- 本轮完成：摘要/引言先讲Agent Skills与Web agents；skill明确采用Anthropic SKILL.md＋指令/脚本/资源范式，方法分析载入的instruction body。最近邻准确介绍context masking/patching、mediator interaction和skill-cache composition，再强调depth gap→SC repair→reader recut贡献链，保留有力度主张。删除AI Use Statement。AWM引用更正ICML2025，新增Anthropic原文作者与日期；7项关键一手源复核，全部37项实际引用/58 bib/14 TeX无缺键重复标签。
- 图表完成美化：主折线蓝橙真点、白底浅区间、轻网格无交叉箭头；teaser/热图同色系、热图白格线；主表分组线与关键行高亮。全部16份数值JSON逐字节不变；数值审计132731检查/489源文件通过，含8438机制检查。没有平滑、插值或改样本。
- WWW2027官方live规则：正文<=8页，**不含参考文献/可选附录**；全部<=12页，前8页自洽；推荐sigconf,anonymous,review/acmart。最终默认投稿版**8/12页**，主图在1/5/6/6页，首页明确Web-agent skill相关性，字体全部嵌入；0error/undefined/overfull。无正文页边距/字号/行距修改。已去未分配DOI/ISBN与ACM reference strip、保留匿名。格式审计audit/WWW2027-FORMAT-20261017.json；精确ZIP独立编译stage build-overleaf.15db_4zy。
- **请用桌面 /mnt/c/Users/12970/Desktop/StillNeeded-WWW2027-Submission-20261017/**：20文件、143187字节Overleaf ZIP；唯一投稿PDF StillNeeded-review.pdf；project/必要源码；阅读说明.md。ZIP SHA256 effbf13fbd25da637c0abbd587c7b3c95c398e1e76f13760d55d51b200cc6848。项目逐项等于ZIP，ZIP依赖等于workspace，workspace PDF等于独立ZIP预览。无扩展版开关/附录/图片/脚本/缓存。先前所有审阅快照保留；WebSkills目录是本轮较早中间快照，以Submission目录为准。
- 交付审计audit/DESKTOP-SUBMISSION-20261017.json；中文说明reports/Web-AgentSkills修订说明_20261017.md；引用/格式/数值未改动证据分别在audit/CITATIONS-WEB-REVISION-20261017.json、WWW2027-FORMAT-20261017.json、STYLE-NUMBERS-UNCHANGED-20261017.json。全部完成后仅本任务文件commit/push master；不提交用户howskill/data/cells.json.tmp。

## 2026-10-17 一天内完成论文：当前执行入口

- **14:21论文与交付已完成验证；本段为最终提交入口，覆盖下方运行中记录**：四卡结果全部填入真实Fig4（正文第6页），无待填机制面板；正文重排为setup→有效可复用探针→主现象与稳健性→机制。标题Still Needed, Hard to Transfer: Using and Reusing Contextual Skills。新增推理仅Qwen3-8B/MedCalc，未追加实验、下载权重或删除数据。
- 最终独立审计：check_main_data.py **132731检查/489源文件**通过；audit_mechanism.py **8438检查、48精确自身控制**通过；4项instrument测试通过；旧whitebox audit全部通过；git diff --check通过。正式图两panel同114题/14组，原始2356+1488+100条齐、完整hash追踪。推理中的反常与截断不利赋值界已写正文及附录B。
- 最终两版：投稿正文7页/全文12页（主图均正文，机制图第6页），扩展38页；两版0编译error、0undefined、0overfull hbox，扩展0vbox，投稿末页自动平衡有约1.97pt vbox警告，已目视确认无越界/重叠。构建bFxwDXEA/1L9LQycU；无需为无可见影响的末页平衡警告重复实验或改数值。
- **请使用桌面 /mnt/c/Users/12970/Desktop/StillNeeded-Overleaf-20261017-Final-v2/**：51文件干净Overleaf ZIP（381KB量级），独立编译StillNeeded-review.pdf、38页StillNeeded-extended.pdf、project/源码和中文阅读说明。精确ZIP已独立编译；项目51项逐字节等于ZIP，ZIP与workspace依赖一致，预览每页文字等于workspace投稿PDF。ZIP SHA256 e9e37aa1f80ce9e725402b6cdba27669258342a323c13941e9cb3728cdeb6826。旧01:25审阅快照及第一次Final导出都保留；第一次Final的图曾浮到第8页，以Final-v2为准。audit/DESKTOP-FINAL-20261017.json记录完整。
- 资源已收尾：原4090 Notebook wt-mechanism-4090-1017 STOPPED；三个GPU Job成功终态；临时CPU wt-paper-fetch-1017 STOPPED；原本既有wt-dev-cpu保持原状。旧串行pipeline不重启。本条随任务最终commit推master；**push成功后**写experiments/mechanism_20261016/PAPER-TASK-COMPLETE，并停止paper-progress-01a1456c.timer及milestone服务。未推送成功不得将任务标为全部完成。

- **14:10正式结果已完整取回并独立审计，覆盖旧等待记录**：临时CPU Notebook wt-paper-fetch-1017（CPU资源空间/CPU资源-2，4CPU16GiB，cpu-nat-207，2h自动停止）成功恢复SSH；42文件归档2,478,098字节，SHA256 5d1dac695984df93daa37c202100608946aa95aeb20ec7427e52349369bcf500，仅下载一次并安全解包。原空闲4090 Notebook已停止；三个Job均终态，无新推理。全部repair2356、edges1488、identity100记录齐；48自身写回token精确一致。新增tools/audit_mechanism.py独立8438项检查通过，repair与edges所有372条基线token完全相同。
- **真实机制发现**：124固定题中116 donor/receiver有效，114严格rescued，14组；两panel同114题。L16 S4/114=3.5%、C8/114=7.0%、SC48/114=42.1%、SCrecut8/114=7.0%。预定SC−S +38.6pp，按skill bootstrap95%CI[26.6,46.5]；SC加性交互31.6pp[14.1,41.6]；SC−recut35.1pp[23.2,43.0]。96基线未截断子集SC−S38.5pp；截断最坏重赋值仍35.1pp，无需为主结论补长生成。
- **路径发现及异常同步记录**：L24 reader cut保留29/114=25.4%，self cut110/114=96.5%，both同reader；L8/16两路径均损害。L24 SC25.4%、recut27.2%，没有额外recut损失，且recut截断28/114，不能把L16结论泛化全层；C18.4%，SC−C不确定区间跨0。reader-cut21截断全部算对仍最多50/114，仍低于self110/114，关键路径差不被截断解释。结果不证明reader-state因果来源，不追加R/SR作为交稿前提。
- **正文已填实并重排**：按用户建议，4.2合并内容/跨题控制，4.3合并跨模型任务复现/共同样本/重复注入，4.4机制解释；共4节（含setup）。fig-mechanism-results替换全部预留图；摘要/引言第三贡献/结论同步真实42.1/3.5/7.0结果，附录B新增protocol、分母、clusterCI与截断；正在两版构建与最终审计。新Overleaf导出脚本支持--final，禁止pending，尚未导出最终桌面或commit/push。下一步检查build-skillvector.XA3V17gA页数，再全版、审计、ZIP独立编译/新桌面导出、完成后提交推送停timer。

- **本轮补实验决策（用户问是否能填完整）**：现有正文预留的repair与edges两面板均有本次固定124题实验覆盖，不以追加实验作为交稿前提。先审计完整数据。唯一可能优先补的机制实验是receiver question/reader-state R/SR修复：仅在SC不能解释晚层失败、且希望正文主张receiver-state机制时需要；当前结果不能预先支持该因果归因。若关键对比被1536-token截断主导，再做固定受影响条件的更长生成敏感性，不按效果挑题。新模型/benchmark、完整phase网格、更多层号均后置。正式结果尚未完整取回，不能承诺任何机制方向。
- 文件入口诊断：已重启的原4090 Notebook RUNNING（仅取文件，不运行推理）；CPU原生SSH失败banner exchange timeout；CPU/GPU connection refresh均遇xterm surface not ready。正在尝试已运行Notebook连接刷新，命令会话94298及先前exec66641；未删除缓存、未重复启动实验。取回产物后停止这张为取文件重启的空闲GPU。

- **13:55恢复执行，覆盖旧进度**：live三个GPU Job均job_succeeded；watch最后06:56:45已记录repair_ready=true、done=true，并向当前thread投递repair_ready和done通知。但图表/正文尚未实际更新，不能把通知成功当作论文闭环完成。用户刚明确实验/论文/Inspire操作全部直接执行无需确认。原Notebook现STOPPED，结果在共享盘，已只为取回数据启动原Notebook（post-start none，无推理）；当前排队，同时恢复已有CPU文件通道。先取回全部12组原始JSONL/done/manifest→核验各卡身份控制→repair+edges分析→真实图与正文全量更新→验证ZIP/导出新桌面目录→master commit/push→完成标记停检查。禁止重跑已完成实验。

- 自动闭环核验（本轮）：四小时timer active、下次约04:10；五分钟监视器active/running，最新01:57读取成功、四分片均repair、repair_ready=false、无failure。bridge14通知已实际触发本对话并完成下载/审计/附录更新。已补强两条续接指令：全分片与控制审计→真实图替换占位→同步方法/样本/结果/图注/摘要/引言贡献/结论/附录→两版编译与审计→桌面新干净版本与ZIP→整项完成commit/push及完成标记。新增推理仍只做Qwen3-8B+MedCalc。监视器重载后PID以systemctl为准。

- 四卡正式进度（本轮live回读）：shard0/1/2/3分别18/128/100/130条，共376/2356，全部stage=repair、均无done（不是缺失故障）。四张卡均已通过首题身份控制并进入正式修复。各分片当前平均8.10/16.52/20.53/16.78秒；按当前均值粗估核心还需约3小时，长尾与capture额外耗时未精确计入，完成时间待更新。edges自动随后运行，不重复启动。

- 本轮验证完成：check_main_data.py通过132720检查/477源文件（新增14组桥接独立检查）；两版重建投稿7/11页、扩展38页，0error/undefined/overfull，构建B0G7IGRp/qEsGPG1l；workspace Overleaf ZIP已更新50文件0.37MB，桌面01:25审阅快照未覆盖。正式机制结果尚未齐，继续等待repair_ready/失败里程碑或4小时检查。
- **01:35桥接里程碑已核验**：bridge14于01:27完成，210条/14题/14组完整取回（JSONL、done、manifest），84次自身写回token完全一致，源码与ID哈希及hook/cache计数通过。新split协议13题donor/receiver有效，S@8修复12题；严格rescued12题，全部基线未截断10题。完整/分段各1道donor、1道receiver评分翻转；共同有效12题中S@8 full12/split11，S@16 full3/split2。只作协议/正控制诊断，不作为124题机制结果。
- 210条中10条截断（包括6条重复identity），累计3614.12秒、平均17.21秒。详细报告与summary/audit在experiments/mechanism_20261017和reports/机制协议桥接_20261017.md。附录A加入协议桥接和新基线说明，删除“SDPA/flash会静默忽略4D mask”的过强实现概括，改为实际采用eager+显式mask检查。
- 远端gate eligible13/positive12已通过，协调器已自动启动worker0；parallel-status为parallel-repair-and-edges，四worker状态文件齐。原串行流程没有重启。继续等待四份repair的done；只在四份齐、各卡身份控制通过后用analyze.py生成正式图。桌面01:25审阅版保留，当前workspace附录有新增桥接说明，最终结果版另行导出，不覆盖用户审阅快照。

- 平台入口澄清（本轮live核验）：三个wt-mech-s4-*均job_running，workspace确为可上网GPU资源、compute group 4090-2-cuda12.8。它们是GPU Job，网页入口在“分布式训练”列表 /jobs/distributedTraining，而非Notebook/开发实例列表；网页入口名不代表实际选择了分布式训练空间或正在训练模型。用户可在该页选公共科研项目并搜索wt-mech-s4。


- **01:26最新用户要求与交付阶段**：用户要求新实验全部只做Qwen3-8B+MedCalc，不扩其他模型/benchmark；旧跨模型结果保留。标题仅作参考、现有实验路径优先，现采用 Still Needed, Hard to Transfer: Using and Reusing Contextual Skills；不预先以Role of Receiver States作为已成立的机制结论。四卡均按原Qwen3-8B/MedCalc配置继续，没有追加新模型下载。
- 四卡具体分类与节点（01:18 live）：Notebook wt-mechanism-4090-1017 → qb-prod-4090-gpu030；GPU Job wt-mech-s4-1-1017 → gpu063，-2 → gpu056，-3 → gpu066（完整前缀qb-prod-4090-）；均可上网GPU资源、4090-2-cuda12.8、48GB4090+10CPU+100GiB，全部RUNNING/job_running。
- 已新增正文sec:mechanism，说明S/C/SC/SC后reader recut，以及reader/self/both路径切断；Fig4为两块明确RESULTS PENDING的无数值空白面板（tools/fig_mechanism_reserved.py→fig-mechanism-reserved.pdf）。原joint-failure段落/图移至扩展附录H，未删结果。新机制结果齐后替换图板、补真实结果和第三贡献；不要把空白图当完成实验。
- 当前投稿版正文7页/全文11页，扩展37页，均0error/undefined/overfull；构建W2i81dfh与xDC3MvTS。审计132627检查/476源文件通过。ZIP收敛为从main.tex递归可达的TeX/PDF/bib依赖（兼顾扩展开关），无缓存/实验日志/本机路径。tools/export_review.py已独立编译精确ZIP并成功输出桌面 /mnt/c/Users/12970/Desktop/StillNeeded-Overleaf-20261017（上传ZIP、独立编译PDF、project干净源码、阅读说明.md）。01:25:32导出完成，50文件、7/11页、0error/undefined/overfull，桌面ZIP与独立编译输入哈希相同，解压源码50项逐字节一致。该目录此前不存在，导出拒绝覆盖已有目录；审计记录audit/DESKTOP-REVIEW-20261017.json。
- 中文关键句与Intro/Experiment流程图、卡/实例分类在reports/桌面版本阅读说明_20261017.md；桌面说明由它复制。用户可先上传此审阅版，机制实验继续，整项任务仍未完成，不创建PAPER-TASK-COMPLETE、不提前commit/push。
- **01:12本轮已完成的本地更新**：按用户“措辞有力度、少防御”的追加要求完成摘要/引言/结论改写，删掉几处重复图注防御句；三条贡献见引言。Teaser首页目视通过，真实数据逐点校验已纳入check_main_data.py；最新审计132627 checks/476源文件，四个31题分片互不重叠覆盖124题、推理源码与两次已运行bridge manifest一致。投稿正文8页/全文11页，扩展37页，两版0error/undefined/overfull；构建bwU8aThW与bfoCD8aq。Overleaf已更新49文件0.36MB。任务仍含运行中实验及正式机制改稿，尚不commit/push。
- **实际进度（约01:08回读）**：bridge14已生成126/210条、9题已开始、平均18.73秒/生成、5条截断；三卡repair分别28/589、16/589、30/589条，平均15.47/21.40/16.31秒，均已通过每卡首题身份控制。按当前长尾粗估核心修复还需数小时，精简edges在各分片repair后继续。未据中途分数改样本。截断数量比2题探针更多，已记录；analyze.py额外输出“基线都未截断”敏感性子集，预定primary rescued不改变；同时保留各臂截断最坏/最好界。
- 只读watch服务已重载（PID8823），增加四卡worker状态及repair_ready里程碑：四份repair齐时即续接改稿，不必等edges结束。原4小时timer继续。新analyze_edges.py支持四份精简edges输入，同样强制done/manifest/ID/source哈希和完整覆盖；输出reader/self/both损伤热图及按skill bootstrap。命令 python3 experiments/mechanism_20261017/analyze_edges.py experiments/mechanism_20261017/edges-s4-0.jsonl experiments/mechanism_20261017/edges-s4-1.jsonl experiments/mechanism_20261017/edges-s4-2.jsonl experiments/mechanism_20261017/edges-s4-3.jsonl --ids experiments/mechanism_20261017/ids-repair124.json --out-prefix figures/fig-mechanism-edges。
- **00:55最新安排，覆盖下方旧串行计划**：用户要求更清晰的解释、可增加多卡、改为“上下文能力能否成为可独立复用内部技能”的叙事，并新增首页teaser；随后明确全文措辞更直接、少防御性说明。引言/摘要/结论已改，三条贡献为有效skill复用探针、沿深度的transfer/source-use分离、跨模型任务复现与竞争解释检验。没有提前声称新修复结果。
- **实际4张4090**：原Notebook wt-mechanism-4090-1017 + 三个Job wt-mech-s4-1-1017 / -2-1017 / -3-1017，均可上网GPU资源、4090-2-cuda12.8、1,10,100、同官方镜像；00:52 live三个Job均job_running。当前桥接仍在原卡，额外三卡跑各自身份控制后正式分片。
- 已安全停止旧串行调度父PID35692（核验/proc命令、断言尚无repair124-eager.jsonl），**保留bridge14正在运行的子进程**。停止前原始结果不变，serial-superseded.json记录。新协调PID241223，parallel_orchestrator.py，等待14题桥接gate通过后在原卡启动shard0，最后join四卡。不要再启动pipeline.py或旧单卡repair模板。
- 正式固定124题按ids[shard::4]分成4份各31题。每卡先用本分片首题验证L8/12/16/24自身写回，再跑repair（L8/12/16/24，S/C/SC/SC_recut），随后edges（L8/16/24，phases=both，reader/self/both）。推理run.py源码未改变；所有新输出在远端v1/parallel/。正式repair总2356生成；精简edges总1488生成。额外3卡允许并行采集，**正式解释/发布仍要求全体桥接与每卡身份控制通过**。没有按新效果选题。
- 新文件：worker.py、parallel_orchestrator.py、load_completed.py；analyze.py现支持4个输入，强制全分片完整、互不重叠、配置/哈希一致。下载 parallel/repair-s4-0..3 的jsonl/done/manifest；命令 python3 experiments/mechanism_20261017/analyze.py experiments/mechanism_20261017/repair-s4-0.jsonl experiments/mechanism_20261017/repair-s4-1.jsonl experiments/mechanism_20261017/repair-s4-2.jsonl experiments/mechanism_20261017/repair-s4-3.jsonl --ids experiments/mechanism_20261017/ids-repair124.json --out-prefix figures/fig-mechanism-repair。旧repair124-eager输出预期不存在。
- 完整prefill/decode细分、L28、R/SR读者状态替换、精确规则反事实和新家族下载暂后置。恢复了上述精简reader/self/both边对照，因它直接检验原knockout混合了读取与source内部更新；不是重新恢复整个耗时网格。
- **Teaser已生成并放首页**：tools/fig_teaser.py → figures/fig-teaser.pdf/svg/png；可编辑矢量。右图来自已审计的common 134题真实曲线，蓝线transfer，绿线1-retention，13–25橙色区间；无示意伪造数据。图值与源SHA在fig-teaser-values.json。投稿版编译通过：正文8页/全文11页、0error/undefined/overfull，首页已渲染目视检查，构建9iosPxVv。扩展PDF与Overleaf待本轮最终重建。
- 预定正文图序：Fig1 teaser→Fig2有效的source-span transfer（位置/内容对照）→Fig3六组transfer/source-attention深度曲线→Fig4机制repair+精简edges（未有正式结果）。现有joint-failure描述热图可移至附录腾版面；正式机制结果到齐再改实验章节，暂不填预期结论。中文叙事与实验说明另落盘reports/叙事与实验路线_20261017.md。

- 原始目标：读取桌面 HANDOFF-EXPERIMENTS-20261016，继续机制实验及论文；优先可上网GPU资源单卡4090、正文短实验；一天内完成；每4小时在当前对话检查。
- 已读取桌面完整交接，live确认旧3个机制Job均终态，无正式124题任务。保护已有改动及用户 cells.json.tmp。
- 已创建 wt-mechanism-4090-1017，Workspace 可上网GPU资源，Project 公共科研项目，group 4090-2-cuda12.8，quota 1,10,100，官方 ngc-pytorch:25.02-cuda12.8.0-py3，平台23小时停止上限（24小时参数被拒绝，没有创建重复实例）。SSH连接成功，实测显卡RTX4090 49140MiB。已启动新后台pipeline，详见下述记录。
- 计划：取回probe2原始输出→同硬件完整/分段及eager/SDPA桥接→优先固定层修复正文图；耗时边拆分后置，新增家族无大下载批准暂不下载。具体缩减在正式启动前预先记录，禁止按效果选题。
- 周期检查已创建并回读：systemd user timer paper-progress-01a1456c.timer，每4小时；首次2026-10-17 04:10:58 CST。执行 experiments/mechanism_20261016/check_thread.py，codex queue目标当前thread 01a1456c-2fe8-78c3-bb67-4a850cc990ac，24小时到期或PAPER-TASK-COMPLETE标记后停止。依赖本机运行；已测试投递且测试消息于00:29触发本对话续查，首次真正4小时检查仍约04:10。日志 thread-check-log.jsonl。
- 平台CLI需要沙箱外执行以写会话缓存，已走平台审批；旧CPU exec文件通道仍在诊断。
- 已取回并审计 experiments/mechanism_20261016/probe2-raw.jsonl：40条唯一记录，4次identity_SC token IDs完全相同；patch/cache/mask计数及token长度正确；仅SC@L16第二题截断900，见probe2-raw-audit.json。远端done=2题40条、exit=0。
- 当前后台：个人路径 /inspire/ssd/project/project-public/czxs253130660/mechanism-20261017-v1/pipeline.py，PID35692；2026-10-17约00:16启动。00:26已进入bridge14-eager；bridge2-eager与bridge2-sdpa均完成。PID仅作定位，禁止据旧PID直接kill。
- 独立新版本代码 experiments/mechanism_20261017/；本地源码包1258124字节，SHA256 d40aade846230c960847b69b422ae0898f3972dce788a49fa4cef896cb0316fa，远端解包前核验。只写新目录，没有覆盖v2。
- 启动前固定顺序：2题eager桥接→同2题SDPA桥接→每组首ID共14题eager桥接（L8/16）→控制通过后124题repair（L8/12/16/24，S/C/SC/SC_recut）。统一max_new1536，所有题补新no_skill；正式2356次生成。原L28和完整边拆分按用户一天优先要求后置，未按新效果选题。身份控制失败或14题无任何早层正控制时pipeline写failed并停止，不继续正式实验。详见README.md与pipeline.py。
- 定时续查已实际测试：00:15:56脚本codex queue退出0，确认向当前thread投递message 01a1457f-a8f9-7991-9cb1-a94fa865acec，日志已落盘。定时器首次约04:10；它依赖WSL/systemd/本地daemon活跃，不保证主机关机后运行。
- 实时异常（00:19）：4090/eager同硬件同backend首题medcalcbench_00987，split donor错、full donor对（均未截断），receiver两协议均错且tokens相同；截至当前的identity_S_full@8/16、identity_S_split@8均精确通过。旧H200此题split donor对，故新旧硬件与prefill漂移不能合并。该异常不是机制证据，继续固定14题估计影响范围。
- 00:25监视器成功只读回查：bridge2-eager已完成，正在bridge2-sdpa；无pipeline失败标记。新增systemd user service paper-milestones-01a1456c（MainPID6738），每300秒查完成标记，桥接14题/正式完成/失败各至多向本thread通知一次，最多24小时；连续3次读取失败则通知并退出。它不重启GPU，不与4小时检查冲突。状态watch-state.json，证据watch-observations.jsonl，脚本watch.py。
- 本轮本地验证完成：4项mask测试、全部新脚本py_compile、diff检查；数值审计132551检查/475源文件。重编译投稿正文7页/全文11页、扩展37页；两版0error/undefined/overfull，构建目录桌面WWW2027/build-skillvector.9dy0fPuO与FYvUpzUT。Overleaf ZIP已更新48文件0.33MB。正文遗漏的一处CI展示已移除，对应检查仅更新逐字断言，数值断言保留。
- 两题eager完整原始审计已落盘：bridge2-eager.jsonl/done/manifest与bridge2-eager-audit.json。30条唯一生成、12次identity精确通过、0截断、平均10.19秒/生成。四个完整/分段基线对比中2个正确性翻转：00987 donor split错/full对；00266 receiver split错/full对。此两题仅作诊断，比例不能外推。2题SDPA已完成，正在取回原始文件。14题eager于00:26:22开始；正式124题尚未启动。
- SDPA两题原始数据与done/manifest已取回，见bridge2-backends-audit.json与bridge2-backend-comparison.json：两种backend各30条，均12次identity精确通过、0截断；平均eager10.19秒、SDPA7.94秒。相同条件28/30生成token序列不同（含重复identity，非30个独立样本），5条评分不同。关键00266的S_full@8：eager错、SDPA对，与旧SDPA正控制方向一致；尚不能从2题外推其他样本。固定backend的新修复仍使用预定eager，不为更好结果切backend。
- 00:30测试消息触发的续查（并非已过去4h）：live确认14组桥接仍运行，GPU70%、17633MiB，无失败标记；未新建实例或重复推理。补强analyze.py为强制核验done/manifest、源码SHA、ID SHA、层号/全样本配置和精确覆盖；audit_bridge.py增加完成标记与完整arm/layer验证，两个完成的2题数据复验通过。下一次有意义的续接由14组完成/失败里程碑或04:10周期检查触发。
- 下一条动作：读取远端pipeline-status.json、bridge2-eager.log及pipeline.failed/done；核验2题两backend桥接，再取回14题完整结果。正式repair完成后下载repair124-eager.jsonl、.done.json、.manifest.json；命令 python3 experiments/mechanism_20261017/analyze.py experiments/mechanism_20261017/repair124-eager.jsonl --ids experiments/mechanism_20261017/ids-repair124.json --out-prefix figures/fig-mechanism-repair。正式结果用新analyze.py（新no-skill eligibility、完整共同分母、skill-cluster bootstrap、截断计数）分析后再写正文。

## 最新续接入口：机制实验状态（2026-10-16 23:49核查）

先读 **[实验交接快照](HANDOFF-EXPERIMENTS-20261016.md)**。2题/40条探针已于11:27成功结束；124题正式实验尚未启动，目前没有机制任务运行。完整/分段prefill存在输出差异，且一题旧/新S@L8正确性不同，下一步先做协议桥接。后台监控13:17因连续3次API失败退出。正式E1/E2粗估约20 GPU小时，4卡约6–10小时，尚未开始计时。新家族按用户要求后置，大下载批准仍待答。

本轮启动说明、代码、论文改写和PDF在工作区，尚未commit/push（整体实验任务未完成）。完整输出JSONL仍在远端；本地已保存平台日志与耗时summary。用户原有howskill/data/cells.json.tmp不动。

## 新对话入口（2026-10-16）

先读 **[当前完整快照](HANDOFF-20261016.md)**。它汇总截至已推送提交 `9a3c4ae` 的结果、贡献边界、正文取舍、热力图、关键mask混杂与未运行实验。下方同日多轮记录是历史，不应覆盖快照中的最终状态。2026-10-16本轮仅整理交接，未恢复学校资源或启动实验。


## 2026-10-15 贡献审查、正文收束与机制方案（本地部分完成，新增GPU实验明日续接）

- 用户进一步要求客观评价贡献、将不紧密的小实验移出正文、提出橙区机制判别实验及几个热力图设计。学校资源与新增GPU实验仍按用户明确指示留到明天。
- 已将合成presence/content分解、答案格式与末位置阶梯、详细位置budget、rank/SVD及其主复现表列移出正文，原文件与结果保留扩展附录；主体仍为六节固定结构。
- 已用现有原始结果增加正文 `fig-joint-failure.pdf`：按skill ID排序，层号×skillgroup，格子为同题transfer失败且knockout失败的比例。严格两协议donor baseline都对、transfer receiver错且knockout无skill错。样本MedCalc124/84/43，TheoremQA61/123/64。独立重算检查已加入check_main_data.py。
- 反事实当场记录：Qwen3-0.6B/TheoremQA的92个严格eligible skillgroups中23个在总体橙区L11–19没有joint failure，不能声称每个skill必经三阶段。正文与报告已明确。
- 机制识别问题：`wb_knockout.py:99` 屏蔽所有query行的skill keys，包括skill→skill。正文方法已说明同时干预source内部更新与读取。明天先做reader→skill-only vs skill→skill-only拆分，再做receiver-state 2×2；其次先救回再切断、prefill/decode分离与内容反事实。
- 详细评价/预期结果/4种热力图方案：`reports/贡献评估与橙区机制实验_20261015.md`。新颖性核查：`audit/NOVELTY-TRANSFER-ATTENTION-20261015.md`。资源续接：`audit/EXTRA-FAMILY-RESUME-20261015.md`。
- 最终验证：数值审计 **132,551** 检查/475源文件通过；历史audit通过；无重复label/bibkey，diff检查通过。投稿版正文 **7页/全文11页**，扩展 **36页**；两版均无undefined或overfull。已移位附录方法与相关结果以消除初次末页vbox，检查主图与末页，PDF/zip更新。本地任务完成后提交推送。无远端任务/下载/周期轮询。


## 2026-10-15 层数横轴、单点展示、新颖性核查（完成）；新家族实验暂缓

- 用户原始目标：Figure 2 横轴用实际层号；所有图表只留单点、移除 CI；增加色块和橙区冲突强调；reading blocked 改为准确含 attention 的措辞；调研橙区现象先例，并在启智扩 Llama/Gemma/DeepSeek。
- 已修改主绘图脚本：实际层号、`Skill-attention knockout`、橙区 `Weak transfer; source still needed` 标注，移除主/附录绘图脚本误差条及置信带。已新增 `tools/point_estimates.py`，展示层移除 CI 列，原始统计数据保留。
- 实时新发现：EMNLP 2025 `Internal Chain-of-Thought`（2025.emnlp-main.1147）同时做 layer-from context masking 和 cross-task patching；不能声称两种方法联用首次。已核查全文 §4.1/4.2、Eq 7、Table 2/5：其 transfer 强度取 best-layer，未见与 source dependence 配对的逐深度失效区间；需写成范围受限的新颖性判断。
- 启智当前受阻：`notebook list --workspace all --all` 所有 Workspace unavailable；`account check` TLS 建连前断开；`curl -I https://qz.sii.edu.cn` SSL unexpected EOF；已有 CPU SSH banner 超时。没有启动新实验，没有下载权重，没有创建新资源。CLI 7.1.8，可更新到7.1.12，未擅自更新。
- 用户已明确暂缓：先不用学校资源，明天再继续额外实验。已停止平台诊断；没有运行中远端任务或周期检查。继续本地文献、图表和编译。
- 今天图表、文献、正文取舍与交付已完成，最终结果见上节。明天：按 `audit/EXTRA-FAMILY-RESUME-20261015.md` 恢复平台、先查缓存权重、baseline 与 identity/masking probe，再全层实验；累计 >1GiB 新下载须先报告并确认。


## 2026-10-15 skill 主线、跨模型深度验证与全篇图表改版（完成）

- 原 Figure 2(a) 仅 Qwen3-8B / MedCalc；已复用六组完整逐层结果，新增共同 eligible item 分析，六组 T/R 不变，组 bootstrap 的边界差 95% CI 均 >0。共同 n 为 MedCalc 134/90/46、TheoremQA 63/125/65。
- `python3 paper/tools/depth_crossmodel.py` 可重现，源哈希写 `audit/DEPTH-CROSSMODEL-20261015.json`。没有新增模型推理或启智任务，因此无定期远端检查事项。
- 正在更新 abstract 为用户指定的 background→gap→approach→findings 结构，intro 同时覆盖 Web skill 注入/分享与 skill-bearing 文档；六节主结构保留。新增 AWM、WebXSkill、等预算负面结果引用。
- Figure 1 取消轴外长标签和层/样本小字；Figure 2 六组全层图；Figure 3 只保留内容/位置，完整预算图与谱诊断留扩展附录；全部表格统一配色与层级。
- 分析、调研、故事线和识别边界见 `audit/REVISION-SKILLS-20261015.md`。仍不能将操作性三段理解成单调的内部算法阶段（Qwen3-8B / MedCalc 的 q 在 L26 recross）。
- 验证：数值审计 **124,560** 检查通过、475 个源文件哈希；历史 `whitebox/analysis/audit.py` 通过；无重复 label/bibkey；`git diff --check` 通过。两版 PDF 均无未定义引用或 overfull，投稿版正文 **8 页 / 全文 12 页**，扩展版 **36 页**。已检查主图、首页及两版末页，PDF 与 Overleaf 包已更新。本轮仅提交 paper/，保留用户未跟踪 `howskill/data/cells.json.tmp`。


## 2026-10-15 用户指定五段引言与主线重排（完成，10-14 开始）

- 当前任务：围绕 transfer/reading 间隙重排 Introduction、Related Work、Problem Formulation、Experiments、Conclusion，重绘四张主图，统一证据表，生成投稿版与扩展版 PDF。
- 引言按“Web 文档保留问题 → 转移失效的 paradox → 互补干预 → 深度分离 discovery → 进一步验证与三项贡献”重写；关键深度实验提前到有效 span probe 之后。readout 次要诊断移到扩展附录 H。
- **新查出的文字错误**：`values/main-evidence-values.json` 中 L14 转移恢复为 0.16129，L15 起才不超过 0.07（两位小数）；旧正文“from 14 onward”已改为 15。knockout 首次在 L25 过半，L26 再低于一半，L27 后恢复；不能写成 L25 以后始终过半，已修正。两项均不改变首次 crossing 的 13/25 边界。
- 表格显式展示六组 transfer/knockout 样本数，避免同组筛选被误读成严格同题配对。四图从已有 audited JSON 重绘，不修改数值。
- 最终标题：*When Skill Transfer Fails but Reading Continues*。正文顺序：setup → 有效内容 probe → early span recovery → transfer/reading 间隙 → 位置/跨题/rank 控制 → 六组复现 → conclusion。详细中文说明见 `reports/论文主线与改写说明_20261014.md`。
- 新增 `tools/style_main_figures.py` 与 `tools/style_main_tables.py`：从 audited JSON 统一重绘四图及两张主证据表，不改数值；纳入 refresh 流程。rank 曲线改为三模型并排小图；主深度图明确区分 ρ 与 q；复现表显示 n_T/n_R。
- 验证：`MPLCONFIGDIR=/tmp/skillvector-mpl python3 tools/check_main_data.py` 共 **70,204** 检查通过、439 个源文件哈希；本轮历史 `whitebox/analysis/audit.py` 亦通过。无重复 label、无缺失 bibkey、所有图表环境匹配，`git diff --check` 通过。
- 最终 MiKTeX 编译：投稿版正文 **8 页 / 全文 12 页**；扩展版 **34 页**；两版均无未定义引用、无 overfull。已目视检查投稿首页、主深度图、结尾页及扩展末页，PDF 与 Overleaf 包已更新。构建记录见 `audit/BUILD-REWRITE-20261015.json`。
- 构建过程：10-14 使用临时 Tectonic 0.15.0；恢复会话后 `/tmp` 清空，10-15 改用可正常调用的 Windows MiKTeX，在新建系统临时目录编译，未覆盖已有桌面 staging。首次 PDF 生成时曾因重绘与编译同时访问 PDF 导致读取失败，最终使用不可变副本构建。首次版式有少量结论越到第 9 页，通过移出 rank 预测细节与压缩重复叙述解决，未改字号或页边距。
- 本轮仅提交 paper/ 下改动；用户原有 `howskill/data/cells.json.tmp` 保持未跟踪且未修改。完成后按约定提交并推送 master。
- 未运行模型实验；本轮 scope 核查仍以 WWW 2027 官方 research-track-papers 页面为依据，第一页 Web 动机不能保证满足 scope。下一步若补强实证，优先做六组共同 item 的边界复核与 receiver 状态交互实验；本轮不将这些未做实验写成已有证据。


## 2026-10-14 正文按 transfer/reading 间隙重构（完成，文件沿用 20261012 标识）

- 用户授权重排正文逻辑，要求不新增实验；后续只考虑 Figure 4 中间区间的多模型/多任务扩展。Web 联系限定于引言，不扩展 Web 实验。
- 主线已改为：外部程序表示何时能替代源文档 → 建立内容敏感的 transfer probe → 检查位置、跨题共享和秩 → transfer 失效但仍依赖 reading 的中间区间 → 排除简单解释 → 上下文压缩/复用的评价启示。重写 abstract、intro、related work、方法开头与 reading 定义、实验衔接及讨论；保留四张主图、数值与标签。
- 三阶段只作为两个干预阈值所定义的操作性区间，不命名为独立内部执行算法。接收态相容性仍是未识别机制，不把未做实验写成结果。
- 次要诊断与原有详细 rank 说明转入扩展附录 H；投稿附录 A 删除重复的 recovery 公式及旧叙事，原文也留在 H。
- 新增 [WWW 引言先例调研](audit/WWW-INTRO-PRECEDENTS-20261012.md)：AIM 是强的“在线服务引入、通用任务验证”先例；postEdit 的 WWW 首页可核实但完整投稿 PDF 下载失败；SheetAgent 有具体表格应用；DoT 含 WebShop，不是纯 intro 先例。新增 HtmlRAG 引用仅支撑 Web 文档交付动机。当前不能保证仅靠引言通过 2027 scope 审查。
- 新增 [Figure 4 扩展方案](audit/FIGURE4-EXTENSION-PLAN-20261012.md)：六组边界已有结果，先复用全层文件并核验共同 item，再扩 Mistral 的重复晚层注入；没有启动模型或平台任务。
- **当场核对的分母问题**：replication-values 中 transfer/knockout n 分别为 135/134、99/63、362/90、132/125、92/46、115/65。相同 screened groups 不等于同题严格配对。方法和 Table 4 caption 已明确独立 baseline 的 rescued 子集；后续 P0 需做 item 交集复核。当前未运行该新增分析，不报告其结果。
- 验证过程：本 worktree 不含 gitignored 原始结果；在 /tmp staging 复制本轮 paper，用只读软链接访问主工作区的 howskill/whitebox 结果，重写 staging JSON 中的旧绝对路径后运行 check_main_data.py，70,201 检查通过、439 个源文件哈希。历史 audit.py 在拥有结果的主工作区运行通过。最初直接在 worktree 跑历史审计因缺结果失败，不是数据不一致。
- 更新 check_main_data.py 的文字定位：迁入附录的数值仍检查，所有数值断言保留；同时修复上一轮改写遗留的四个逐字措辞断言，未改变预期数值。编译使用 /tmp Tectonic 缓存，不调用会覆盖 Windows 目录的 build.sh。
- 最终投稿版正文 8 页、全文 12 页，无未定义引用或 overfull；扩展版 34 页，无未定义引用，保留一条 1.15pt 竖向 overfull 警告，末页目视无裁切。两份 PDF 和 Overleaf 包已更新。详见 [构建记录](audit/BUILD-CHECK-RESTRUCTURE-20261012.json)。
- 下一步：先阅读新正文决定研究定位；若继续 Figure 4，按方案 P0 处理同题分母与阈值稳定性，再决定是否需要 P1 新实验。

### Open Ideas / 值得深挖的问题

- 2026-10-12：将“仍被读取但不能转移”的区间作为表示复用的压力测试。观察：Qwen3-8B/MedCalc 为 L13 vs L25，其他五组也有边界间隙，但干预分母有明显差异。价值：把可转移性与实际源依赖分开。最小验证：共同 item 复核及跨家族重复晚层注入。机制来源尚未识别；延续旧接收态假说，不声称本轮发现独立新机制。


## 2026-10-12 正文近邻定位、语言修订与 WWW 故事线

- 用户要求保留原文逻辑，直接润色已有工作定位并增加引用，同时给出 A 类论文故事线和具体 Web 关系。补充偏好：少用分号、破折号，减少过度防御表达，按正常学术写作陈述发现。
- 标题改为 `Transferring and Reading Skills in Language Model Contexts`。保持六个正文文件的章节顺序、标签和实验数值。新增 Davidson 指令 FV、Bigoulaeva ACL 2026 IV 的 BibTeX；在正文显式使用已有 JIT 条目，细化 Sia/Pola 和 Dong 的关系。
- 纠正位置预算段：不同块数选取不同内容，平均能量接近但非逐题匹配。使用 calculator-bootstrap 区间，说明 procedure 覆盖不同。错位描述明确为 content difference 的错位。
- last-token 段以一次性 prefill 协议解释结果，区分输出形式和纯长度效应。深度段明确两种干预背景，将接收态交互作为下一问题。附录相关工作中两处把 JIT 等同读取敲除的说法也同步修正。
- [故事线与 Web 方案](audit/STORYLINE-WWW-20261012.md)：主线是可转移性与读取依赖的关系，Web 优先程序文档检索/交付，再考虑多步工作流的规程保留。未启动新模型实验或部署 Web 环境。
- 2026-10-12 官网复核：WWW 摘要 10 月 18 日、全文 10 月 25 日 AoE；首页须明确 Web 科学问题。主文件会议日期/地点同步为 2027-05-10 至 14、Dublin。
- 静态检查：引用键全部存在，章节和标签保留，`git diff --check` 通过；正文分号由 41 减为 13，多数保留在图注并列项。
- 编译环境：原 Windows MiKTeX 在本会话报 `Exec format error`，未产生新 PDF；已用独立 Windows 临时目录避免覆盖既有构建目录。转用 /tmp 中的官方 Tectonic 0.17.0，首次编译需要下载 TeX bundle。最终验证结果见下方补记。
- 图文一致性：位置预算图仍含 `budget and energy fixed` 旧标签，已修改 `whitebox/analysis/posbudget_report.py` 的显示文字并用现有 JSON 重绘 PDF，未改曲线数值。
- 附录同步：压缩并纠正 A 节过时 provenance 清单，保留故障描述和当前主文修复状态；B 节提前声明双栏表，避免末尾浮动表独占第 13 页。B 节末的接收态机制解释改为待检验问题。
- 扩展版验证：正文 8 页、总计 34 页，无未定义引用或 overfull。更新 `skillvector.pdf`。首次仅缓存编译缺数学字体，联网补齐后通过。
- 最终投稿版验证：Tectonic 0.17.0 编译为正文 8 页、总计 12 页，无未定义引用、无 overfull。同引擎编译未修改 HEAD 也是 8/12 页。PDF 更新至 `skillvector-www2027.pdf`；详细验证见 [BUILD-CHECK-20261012.json](audit/BUILD-CHECK-20261012.json)。


## 2026-10-03 研究定位简报 PDF（完成）

- 用户要求先给 A 类会议竞争力判断，再概述最近邻核心实验，并将此前 last-token / RSI 问题一起整理成桌面 PDF。
- 结论：有继续投入和形成 A 类论文的基础，但当前证据尚不足以判断已达到较有把握中稿的程度；优先主打 transfer 与 reading 分离，补接收态交互和语义覆盖控制。WWW 另有 Web 范围要求。
- 交付：[7 页 PDF](reports/研究定位与相关工作_20261003.pdf)、[可编辑源稿](reports/研究定位与相关工作_20261003.md)、[构建脚本](reports/build_research_brief.py)。包含八篇最近邻的对象/实验/贡献、last-token 设计、RSI 两阶段候选和 14 条可点击一手出处。
- 桌面副本：`/mnt/c/Users/12970/Desktop/SkillFlow_论文竞争力与相关研究_20261003.pdf`。
- 验证：`python paper/reports/build_research_brief.py`；PyMuPDF 检查 7 页、文本可提取且无空字符；目视检查首页、近邻页与参考文献页。初版 Droid fallback 缺 Latin 字形，已改用 Windows Microsoft YaHei 内嵌字体并重新验证。脚本依赖 ReportLab 及本机字体路径。
- 未运行新模型实验、未修改 LaTeX。详细文献审查及待补实验仍以同日 audit 记录为准。用户既有 `howskill/data/cells.json.tmp` 未动。

## 2026-10-03 正文创新定位与 context/prompt、last-token、RSI 调研（完成）

- 用户范围：以当前 `sections/*.tex` 正文为准，评估相关研究、last-token 注入先例、WWW 适配和 Recursive Self-Improvement 的研究连接；本轮不启动模型实验、不修改论文正文。
- 已核实近邻：Hendel et al. 2023 的 task vectors、Todd et al. ICLR 2024 的 function vectors 均有末位置注入；Li et al. arXiv:2509.04466 已研究可转移表示的时间/语义局部性及长输出衰减；Sia et al. NeurIPS 2024 使用从某层起累计 context masking；Pola & Balasubramanian arXiv:2511.10694 同时 patch 指令关键词与最终 context token。因此这些单项不能笼统声称首创。
- **即时记录：正文 §4.4 的“constant budget and energy”与实现不符。** `howskill/howskill/wb_posbudget.py:215–229` 为每个块数重新选取原位位置，`:395–410` 记录 `sum(dnorm2[src])/tot` 后直接注入，没有能量归一化或逐项能量匹配。`whitebox/analysis/out/posbudget.md` 中 c1x256…c32x256 的平均能量四舍五入均为 0.29，但这不等于每项能量固定；half 档均值已有 0.49/0.50 差别。块数变化还改变了语义覆盖。连续块恢复更好的观察可保留，但“连续性是独立原因”的断言应收窄并补控制。本轮仅记录，未擅改正文/代码。
- 官方 WWW 2027 CFP 当前明确要求首页说明 Web 科学问题；仅使用 Web 数据/API 不满足范围。现稿无工具的 MedCalc/TheoremQA 机制研究存在范围风险。来源：https://www2027.thewebconf.org/research-track-papers/ （2026-10-03 核查）。
- 完整报告：[RESEARCH-context-lasttoken-rsi-20261003.md](audit/RESEARCH-context-lasttoken-rsi-20261003.md)。包含一手出处、阅读深度、方法比较、WWW 判断、判别实验、RSI 近邻与独立研究设计。
- 新补近邻：Davidson et al. arXiv:2505.12075v3 已从自然语言指令提取 FV；Bigoulaeva et al. ACL 2026 / arXiv:2602.07930v2 把 query 前指令末 token 移植到 filler，研究多层非加性交互；不能只对比最早的 few-shot task-vector 论文。
- JIT 后续核对到 v3（2025-12-01），明确某些长输出仍能被单 TV 支持，且增加 Qwen 复现；最终报告不采用 v1 的过宽概括。
- RSI 直接近邻：Coalition-Aware Skill Reliability（arXiv:2608.22610）已做技能组合与跨域效用审计；HyperAgents（2603.19461）有固定 meta-agent 对照；AIDE²（2609.26457）作者仍承认在 outer-loop 改进角色上无法决定性区分强基线。不能把 task 提升直接写成递归改进效率提升。
- 当前问题告一段落：没有新模型实验、没有修改 LaTeX。下一步优先在现稿做晚层 span/query 交互判别和连续性语义覆盖控制；RSI 独立先做 meta-skill 的后代质量行为筛选。


最新一轮：**2026-09-28，改投 WWW 2027 版式 + 整个 paper/ 目录重构**。
更早的记录（ICLR 单栏时期的重写、润色、图表样式回退）从「2026-09-18 图表样式」一节起原样保留。

---

## 2026-09-28  改成 WWW 2027（ACM acmart/sigconf）+ 目录重构

### 做了什么

1. **版式**：ICLR 单栏 `article + iclr2027_conference.sty` → **`\documentclass[sigconf, anonymous, review]{acmart}`**，
   即 WWW 2027 research track 指定的设置（<https://www2027.thewebconf.org/research-track-papers/>）。
2. **正文内容一个字没改**（用 `sed` 按行切片，切完 md5 与原文逐字节一致）。改动只有排版性的：
   图全部升为 `figure*`、23 张表升为 `table*`（两栏下单栏宽 241pt，表的自然宽度 234–498pt，
   实测见下），`[h]` → `[tbp]`，以及 7 处指向附录的 `\ref` 换成了下面说的 `\extref`。
3. **单文件 → 分章文件**：`skillvector.tex`（2873 行）拆成 `sections/`（6 个）+ `appendix/`（8 个），
   生成物进 `tables/`、`figures/`，脚本进 `tools/`，数值记录进 `values/`，审计日志进 `audit/`。
4. **附录去重与去过时**（见下「删了什么」）。
5. **两个构建目标**，靠 `main.tex` 里一个开关切换，**什么都没删**：

   | 目标 | 开关 | 页数 | 用途 |
   |---|---|---|---|
   | 投稿版 | `\extendedappendixfalse`（**默认**） | **正文 8 页 / 全文 12 页** | WWW 2027（上限 12 页含参考文献与附录） |
   | 技术报告 | `\extendedappendixtrue` | 正文 8 页 / 全文 34 页 | arXiv / 审稿人索要 / 自己查 |

   仓库里 `main.tex` 默认是**投稿版**，所以 Overleaf 上传后直接编译就是 12 页。
   `build.sh` 会在 staging 副本里按目标显式设置这一行，不依赖仓库里留成哪一边。

   ```bash
   ./build.sh              # 34 页 → skillvector.pdf
   ./build.sh submission   # 12 页 → skillvector-www2027.pdf
   ```

### 为什么必须有两个目标

WWW 2027 长文是 **8 页正文 + 参考文献 + 可选附录，总共不超过 12 页**，且前 8 页要自足。
正文（不改内容）在两栏下正好 8 页，参考文献约 1 页，**留给附录的只有约 3 页**，
而附录在两栏下是 **约 25 页**。实测各节页数（完整版）：

| 附录 | 内容 | 页数 |
|---|---|---|
| A | Setup, in full + Experimental detail + Evaluation scope | 2 |
| B | The full-dataset rerun（`tab:fullscale`、逐层深度、哪些 head 读 span） | 1.5 |
| C | Control documents + 三个 measurement traps + MC 格式 | 3 |
| D | 末位置几何 + 分解 + 答案长度阶梯 + 合成层全量 | 3 |
| E | span battery + 向量由什么构成 + 深度 + belongs | 11 |
| F | 秩截断 + model ladder + 跨任务复现 | 3 |
| G | Related work, at length | 1.5 |
| H | Additional tables | 4 |

投稿版保留 **A + B**（复现所需 + 全量重跑那张表），其余六节只是不 `\input`，
文件仍在仓库里、仍能编译。

### `\extref`：让两个版本的交叉引用都成立

正文有 7 处、核心附录有 4 处 `\ref` 指向被排除的附录。新宏：

```latex
\newcommand{\extref}[3]{\ifextendedappendix#1~\ref{#2}\else#3\fi}
```

- 完整版渲染成**和改之前逐字相同**的 `Appendix~\ref{...}`；
- 投稿版渲染成 "the extended version"，不出 `??`。

例：`\extref{Appendix}{app:onepos}{the extended version}` →
完整版 "Appendix D.1"，投稿版 "the extended version"。

### 图 1 改成并排（2026-09-28 晚）

`fig_channels_full.py` 原来是 `subplots(2, 1)`，两个面板上下叠、figsize (4.9, 3.0)、
用 `height_ratios` 让两边的条一样粗。改成 `subplots(1, 2)`、figsize (7.1, 2.15)，
长宽比从 1.84 变成 **3.49**，在两栏页面上只占一条横带。

两处为窄面板做的调整，改回去会出问题：

- 两个面板臂数不同（3 与 5）。等高的轴下直接画会让左边的条变粗，所以把条**居中放进一个
  共享的 5 槽坐标**（`off = (span - len(items)) / 2`），两边条的物理粗细相同。
- 两条基线标注原来同一行，面板宽度减半后 `wrong-skill receiver (0.00)` 和
  `correct skill (0.92)` 会叠在一起，改成上下各一行（y = −0.62 / −1.12，ylim 下界放到 −1.55）。

正文 caption 里 "Top:" / "Bottom:" 相应改成 "Left:" / "Right:"，图宽从 `0.92\textwidth`
改成 `\textwidth`（图变矮了，占不了多少高度）。`check_main_data.py` 会检查
`135 / 0.81 / 0.03 / 0.06` 四个数在 PDF 里渲染得出来，改完仍然通过。

### 删了什么（两个版本都删，理由是重复或已被取代）

| 删除项 | 理由 |
|---|---|
| `app:decomp` 开头「几何与行为相反」整段（15 行） | 与 `app:geometry` 一节几乎逐字重复，改成一句指针 |
| 第二处 "Which control you subtract chooses what you measure"（7 行） | 同一段在 `app:onepos` 已有带数字的完整版 |
| 「shuffle 打乱行序代价很小」那句的第二次出现 | 同一文件内两小节各说了一遍 |
| `app:depth` 里 **pre-fix 的 window 表**（n=27，7 个 calculator） | 紧接着的段落自己写着 "those estimates are superseded" |
| `tab:ladder` 的前两行 | 与 `tab:format` 上半块逐数字相同，改成指针 |
| `tab-prdiag-06/-17/-dl.tex`、`tab-skilltask.tex` | 生成了但全文没有 `\input` |
| `fig-decode-medcalc`、`fig-depth-medcalc`、`fig-dose-tierA`（pdf+png） | 全文没有 `\includegraphics`；decode 那张是 09-14 删掉的 skill 识别实验的遗物 |

**没有删**（想删但证据不足，留给你判断）：
- `tab:windows`（三通道表，n=39）：前两行被 `tab:windows2` 完全覆盖，第三行（末位置整集
  0.436–0.487 / 接收方 0.231）是 `tab:windows2` 没有的量，所以没动。
- `app:replication` 里 LogicBench 那条否定结果（5 行）：不承担任何正文结论，但删负结果要你点头。
- 所有其余 pre-fix 数字：文中都明确标注了 pre-fix 且给了 post-fix 对照，属于诚实记录。

### 目录结构

```
paper/
  main.tex                 前言 + ACM 元数据 + \input 骨架 + \extendedappendix 开关
  README.md                怎么编、怎么上 Overleaf、怎么重算数字
  sections/                00-abstract … 05-conclusion（6 个文件）
  appendix/                a-setup … h-additional-tables（8 个文件）
  tables/                  18 个由 tools/ 生成的 tabular 片段
  figures/                 10 个 pdf（+ png 副本，不进 Overleaf 包）
  skillvector.bib
  build.sh                 两个目标都从这里编
  tools/                   生成器 + 数据核对（原来散在 paper/ 根目录的 14 个 .py）
    _paths.py              新增：PAPER/TABLES/FIGURES/VALUES 与 main_text()
    make_overleaf_zip.py   打 Overleaf 包（这台 WSL 没有 zip(1)，用 Python 写）
  values/                  *-values.json、posbudget.json、DATA-CONSISTENCY
  audit/                   历次审计日志
  legacy/                  ICLR 的 .sty/.bst、旧 skillvector.tex、旧 .bak、旧预览图 —— **可以整个删掉**
```

### 流水线改了哪些路径（都已验证）

`tools/_paths.py` 统一给出 `PAPER / TABLES / FIGURES / VALUES / AUDIT`，以及 `main_text()`
——因为 `check_main_data.py` 原本是 `skillvector.tex.split('\label{endmain}')[0]` 拿正文做
prose 检查，拆文件后改成按 `main.tex` 的 `\input` 顺序拼 `sections/*.tex`。

```bash
cd paper
MPLCONFIGDIR=/tmp/skillvector-mpl python3 tools/refresh_main_data.py   # 8 个阶段全 PASS
python3 tools/check_main_data.py     # PASS: 70201 checks（和改之前同一个数）
python3 ../whitebox/analysis/audit.py  # ALL CHECKS PASSED
```

`refresh_main_data.py` 仍然不覆盖 `controls_table.py` / `decomp_tables.py` / `figs.py`，
改了对应数据要手动跑，命令在 `README.md`。

### 验收（2026-09-28）

| 项 | 投稿版 | 完整版 |
|---|---|---|
| LaTeX error | 0 | 0 |
| 未定义引用 | 0 | 0 |
| Overfull hbox | 0 | 0 |
| Overfull vbox | 0 | 1（1.6pt，分页产物，不是跑出版心） |
| 正文页数 | 8（上限 8） | 8 |
| 全文页数 | **12**（上限 12） | 34 |
| `check_main_data.py` | 70201 checks PASS | 同 |
| `whitebox/analysis/audit.py` | ALL CHECKS PASSED | 同 |

### 投稿前还必须做的三件事（`main.tex` 里都标了 TODO）

1. `\acmConference` / `\acmDOI` / `\acmISBN` 现在是占位符，要换成 ACM rights form 发来的那一段。
2. CCS concepts 现在是我按标准 CCS 树填的
   （`10010147.10010178.10010179` = Computing methodologies → NLP，
   `…10010187` = Knowledge representation and reasoning），**投稿前用
   <https://dl.acm.org/ccs> 重新生成一遍**。
3. `\author{Anonymous Author(s)}` 那一块，去匿名时换成真实作者。

另：正文 8 页是**踩着上限**的。任何正文改动都可能顶到 9 页，改完必须重跑 `./build.sh submission` 看页数。

### Overleaf

`paper/overleaf-skillvector.zip`（45 个文件 / 0.25 MB，`tools/make_overleaf_zip.sh` 生成）：
只含 `main.tex`、`README.md`、`.bib`、`sections/`、`appendix/`、`tables/`、`figures/*.pdf`。
不含 Python、PNG、审计日志、legacy。Overleaf 自己有 `acmart`，编译器选 pdfLaTeX。
包里默认就是投稿版（12 页）；要读完整版就在 Overleaf 里把 `\extendedappendixfalse` 改成 `true`。

---

## 2026-09-18 及更早：ICLR 单栏时期的记录

更新日期：2026-09-18（图表样式回退为当日第二轮）。

## 2026-09-18 图表样式与分页回退到旧版布局

- 用户任务：正文逻辑、表达和数据不改，把图表样式和分页改回桌面 `ICLR_2027__SkillVector/paper_` 那一版的风格和布局；数据继续用本仓库的新结果；图 2 的几条曲线要画在同一个坐标系里。
- 图 2（`fig_rank_full.py`）：三个面板合并为一个坐标系，沿用旧版 `figs.fig_rank` 的样式（标记 o/^/D、1.0 处绿色虚线、0 处接收者线、12 处的宽度比例预测标注、图例放在图下方两列），tex 里的宽度恢复为 `0.64\textwidth`。bottom-k 对照按各模型颜色画空心方块虚线，与旧版一样不画误差条；图例写入 n 和 k*。为避免三条曲线在同一 k 上重叠，加了约 ±5% 的对数轴横向错位（dodge）。标题从 “before its own handover” 改为 “at an early layer”，和新图注一致（0.6B 在 MedCalc 上没有测 handover）。
- 图 1（`fig_channels_full.py`）：改用旧版 `figs.fig_channels` 的样式：每个面板第一根柱子用深色，标题里写 n，每个面板在最低柱下方标出自己的基线（wrong-skill receiver / correct skill），x 轴标签也用旧版的。上面板的 y 轴标签缩短成 `last $\leq$256 prompt positions`，否则坐标轴被挤窄，两条基线标签会重叠。
- 表 2（`main_evidence.span_battery`）：改为旧版排版：表头小写、`CI$_{95}$`、区间写成 `[a,\,b]`、recovery 带符号，三条参照行（correct skill / identity / unpatched）用斜体；保留新增的 n 列（same-family 只有 41 项）。`check_main_data.py` 里对应的 TeX 格式断言也同步改了。表 1、3、4 的样式新旧版本本来就一样。
- 分页：把 `tab:replication` 的 table 环境（内容不变）从 §4.7 开头移到图 3 之后，得到和旧版相同的分页：p5 表1+图1，p6 表2+表3，p7 图2，p8 图3+表4，p9 正文与结论。正文仍是 9 页，全文 42 页，0 error、0 未定义引用、0 overfull。
- 验证：图 1、图 2 生成器重跑后，`fig-channels-values.json` 和 `fig-rank-values.json` 与改动前逐字节一致；`battery-values.json` 没有变化；`check_main_data.py` 27207 项全部通过（manifest 哈希已更新）；和 HEAD 比较，tex 的行集合只有 includegraphics 宽度那一行不同。
- 遗留：图 2 按旧版宽度 0.64\textwidth 缩放后，图例字号实际约 4pt，偏小（旧版也是这样），审稿时可能被提意见；如果要放大，需要从别处省出大约 3 行，否则会超 9 页。`overleaf-skillvector.zip` 仍然没有更新（原因同下一节）。

## 2026-09-18 正文逐段润色

- 用户任务：逐段润色 `skillvector.tex` 正文，提高可读性、术语引入和逻辑衔接，保留整体结构。本轮已处理摘要、Introduction、Related Work、Problem Formulation、Experiment、Conclusion、三项贡献与七处图表说明。
- 保留五个顶级章节、七个实验子节、17 个 paragraph 标题位置、3 图 4 表、全部公式、label、引用键及图表输入文件；`\\label{endmain}` 后内容与本轮修改前逐字一致。未改实验脚本或原始结果，未提交/推送。
- 同步正文中已被本地记录证实的旧数字：主 span 恢复 0.89、rank32 0.12、bottom64 0.03、rank knee 47；全文统一筛选后 135 题/14 calculators 的适用范围。使用 `python3 whitebox/analysis/full_rerun_report.py battery rank` 核验；按 `paper/replication.py` 的分组筛选和 kstar 定义、2000 次 calculator bootstrap 独立计算得 47.2909 [43.3021, 54.7581]，故正文统一为 47 [43,55]，替换另一处旧区间 [43,72]。
- 将“整个 drop 都发生在一层”收窄为“最大下降发生在 12–13 层”；后续层最大值按本地附录曲线改为 0.07。连续概率读出支持存在较陡下降，但其阈值并不等同于 accuracy 的 0.5 crossing。删除从 quarter 结果推出其他部分必须组合贡献的推断；prompt-order 比较明确不是同一样本的配对估计。
- 检查：`python3 paper/checks.py paper/skillvector.tex` 无重复标签，36 对全篇图表环境匹配；源码对比确认结构/公式/引用不丢失。`bash paper/build.sh` 最终正文 9 页、全文 42 页，0 LaTeX error、0 未定义引用、0 overfull，已更新 PDF。第一次编译正文 10 页，压缩重复表述后恢复 9 页；未改字号/页边距或缩图来压页。
- 改前源码备份：`.snapshots/skillvector-20260918-before-polish.tex`。修改说明与待核对项：`POLISH-AUDIT-20260918.md`。
- **仍存在的投稿前问题（非润色能解决）**：现有图 1 PDF 底部写 n=20、accuracy=0.95，与图注开发子集 n=16/1.00 不一致；图 2 PDF 只有两条 Qwen 曲线，没有正文/图注所述 Mistral，且其版本与当前 135 题结果不同。此次不重生成图或改变实验范围，图表资产与正文的一致性仍未通过。
- 主表 `tab-big40.tex` 的同 family 条目只覆盖 n=41；当前表用总体 donor 分母报 0.13，而匹配该 arm 样本的计算为 0.12。正文保留已核验的完整子集控制，不再笼统声称所有同/异类控制相同；表内口径待专门修正。附录也残留旧样本说明与不成立的“所有 control 不超过 0.12”等表述，按本轮正文范围未修改。
- 下一步：同步图表生成器与其实际样本、逐 arm 分母及图注，清理附录旧数值/旧说明，再作投稿前完整数据审计；pre-fix synthetic/final-position 结果仍需修复后验证。本轮未更新 Overleaf ZIP，避免将未完成数据一致性检查的包视为投稿定稿。

## 当前任务

按用户要求重写 `skillvector.tex` 正文，结构为 Introduction、Related Work、Problem Formulation、Experiment、Conclusion。引言依次讲问题、paradox、关键实验、核心发现、进一步验证，并归纳 3–4 项贡献。保留实验结果和分析结论，优先使用 skill，检查数据与引用，不保留 Limitations 部分。

## 已验证事实

- 修改前正文有 11 个顶级章节，Introduction 有 6 项贡献；独立 Limitations 在正文与附录各一处。
- 已保存原始 tex、bib、pdf 到 `.snapshots/*-20260917-before-rewrite.*`。
- 当前仓库已有大量其他未提交工作；本次仅在 paper 目录修改，不提交或推送。
- 旧 build.sh 使用 Windows MiKTeX 并写入 `/mnt/c/...`，需另查可用的本地编译路径。
- 2026-09-17 图表样本审计：当前正文 MedCalc 因果图表仍引用从 55 个计算器中按 rescued 数最多选出的 40 个、每组 4 个，共 160/470 rescued item；再按 receiver 全错筛到 15 组/60 item。此“top 40”选取规则未见于正文采样段落。参见 `../whitebox/full-rerun.sh` 的 WHY 注释及 `skillvector.tex` 实验设置。
- 本地 `../howskill/results/p8-wb/fetched/by-host/*/full-*.jsonl` 已有全量重跑文件；`python ../whitebox/analysis/full_rerun_report.py battery rank depth quarters knockout dose doclast window` 显示主要 span 注入在组筛选下为 0.89（旧 0.87）、rank128 为 0.77（旧 0.77）、formula quarter 为 0.56（旧 0.56）、depth L12/L13 为 0.74/0.16；但 skill-last L16 own 恢复率从旧 0.85 变为 0.49，同组他例从 0.48 变 0.29，需改写相关论断。多数 full span 输出只有 467 item/48 calculators，knockout 有 469/49；缺的两项是 calculator 28 的 `medcalcbench_00937`、`medcalcbench_00925`，必须查明。正文尚未吸收这些结果。

## 完成状态

- 已完成五节结构重写；用户后续要求将贡献压缩为三项、正文采用 3 图 4 表，均已落实。
- 三个贡献：可转移 skill 表示的因果定位；恢复所需表示 rank；skill 转移与继续读取的深度分离。
- 主图：最后位置 vs skill span、rank 曲线、替换/累计注意力敲除/层窗口三面板。主表：答案格式、span controls、skill 内容与题目依赖、跨模型与任务复现。
- 注意力敲除位于正文 §4.6 及图 3(b)；第三个贡献显式提及 cumulative attention knockout。
- 新增 `main_evidence.py`，从原始记录生成新增主图及两张表。无需新增模型实验；旧附录深度图仍保持其原来的历史定位，不混入修复后主图。
- `python3 ../whitebox/analysis/audit.py`：309 项通过；日志 `DATA-AUDIT-20260917.txt`。
- 原有所有 label 保留，35 对图表环境匹配；五节、3 图、4 表、3 项贡献的结构断言通过。
- Windows MiKTeX 编译通过：正文 9 页，全文 41 页，0 error / 0 未定义引用 / 0 overfull；已查看主要页面排版。日志 `BUILD-CHECK-20260917.txt`。
- 已更新 `skillvector.pdf` 和 `overleaf-skillvector.zip`；ZIP 已做依赖和 CRC 检查，内容与当前主 tex 一致。
- 原有 48 条引用均核对一手页面；更正见 `CITATION-AUDIT-20260917.md`。完整改写说明见 `REWRITE-AUDIT-20260917.md`。

## 已发现并处理的口径问题

- 原稿 battery accuracy CI 实际为逐题正态近似，rank 图误差条实际为逐题 bootstrap；本次保留所有区间数值，纠正图注与方法说明。生成器 `tables.load()` 的 calculator_id 键切片问题尚未修改，避免擅自改变用户要求保留的统计结果。
- battery 和 depth 都写 n=60，但分别为 15 和 20 个 calculator，已明确。
- TheoremQA 实际按 skill 分组筛选，singleton 才等于逐题筛选，已明确。
- 答案格式的 MC/numeric 各 120 题，CoT 为其中 80 题子集；新表同时列 evaluated 与 rescued，避免“完全相同样本”表述。
- k 指中心化方向数，保留均值后完整注入 rank 至多 k+1；k* 是有限网格的半幅 knee，不是完全恢复所需的最小 rank。

## 尚待用户补充

- 已通过异步问题询问历史 AI 使用范围，尚未回复。当前 AI Use Statement 仅陈述本轮已确认用途，不声称已完整核实此前的代码/实验设计/结果分析历史。官方要求与截止日期已记录在核查报告。
- 无提交/推送/投稿系统上传操作。
- 2026-09-17 正文审阅：现有五节主线完整，编译 PDF 的结论落在第 9 页，符合 ICLR 2027 正文不超过 9 页的页数要求。科学审稿风险集中在：主结果仅对 40 个计算器中筛出的 15 个组/60 个 item 成立；仪器修复前的 synthetic、final-position 与部分机制结果仍承担核心叙事；rank knee 是网格上的半高点而非最小充分秩；跨任务和模型的对照并不齐全。下一步优先在修复后重跑支撑主张的诊断、报告未筛选总体及每组效果，并收窄 abstract/conclusion 的外推。

## 失败尝试及原因

- 首次沙箱内调用 Windows MiKTeX 因 WSL socket 权限失败，经工具请求授权后正常编译。
- 图标签改名时暂将内部筛选键 needs_document 一并改名，数值一致性检查立即识别出 n=40 与原 n=16 的不一致；已修复内部键并重生成，最终图的全部数字标签与原稿一致，错误中间图未作为最终结果交付。

## Open Ideas / 值得深挖的问题

- **2026-10-03：meta-skill 的内部表示能否因果影响下一代改进效率？** 触发：现稿 span transfer 与 continued reading 分离；近期 HyperAgents/AIDE² 研究改进过程本身，Coalition-Aware 已覆盖技能库效用。最小验证：旧/新 meta-skill 的双向 patch 后生成 candidate skill，在全新固定 executor 与隐藏新任务评测后代质量；比较固定 improver 与更新 improver 的独立演化链。价值在连接内部因果中介与下一代可继承增益，不是又做技能移除审计。假说未验证，详细设计与失败判据见 `../IDEAS.md` 的 I8 及本轮调研报告 §6.2。

- **2026-09-17：skill span 的位置预算与任务映射复杂度是否共同决定单向量失效？** 触发：现稿单位置与完整 span（约 415–1,630 token）干预的效果差很大，但同时改变了干预容量；Dong et al., arXiv:2506.09048 的双射任务使 task vector 在原任务/逆任务较好、组合双射接近随机。值得做：把“答案长所以单向量失败”与“技能映射本身需要分布式表示”分开。最小实验：同一模型、同一 skill 与答案格式下，在独立 held-out 题上比较 1/4/16/64/全 span 的保序位置预算、相同预算的语义区域和随机/错位控制；另构造低/高映射复杂度的技能，在各预算下画恢复曲线。若高复杂度任务在等长答案下需要更多位置，且不是单纯 token 数或扰动能量造成，可能形成独立机制结果；若所有曲线只由答案长度或扰动总量解释，则该想法失败。
  - 现有部分位置证据：40-calculator 修复后 quarter ablation 已覆盖四个独立四分之一及完整 span（$0.12/0.56/0.12/0.12$ 对 $0.87$）；共享前缀有 $0.73$ 对完整 span $0.87$。因此新实验是填补同一 skill span 内连续、等预算、跨长度的位置剂量曲线，不是首次做局部 span 干预。

## 相关论文记录

- Dong et al., *Understanding Task Vectors in In-Context Learning: Emergence, Functionality, and Limitations*, arXiv:2506.09048：线性 Transformer 分析预测单 task vector 在双射映射上的表达限制，并用原任务/逆任务/组合双射的对照表及多向量注入验证；与本稿相关的是对“一个位置何时够用”的正面反例设计，但其映射秩不同于本稿 span 矩阵截断秩。

## 2026-10-16 reading/transfer 机制与新热力图设计

- 本轮仅研究设计，未启动GPU任务或修改论文结果。报告：`reports/橙区机制判别与因果热力图设计_20261016.md`。
- 新代码证据：span patch只在prefill的block输出生效；层≤L的source KV已由receiver计算，随后decode仍读取它。缓存覆盖不足是待检验解释，不能称已发现机制。
- 优先级：reader/source-self边拆分 → source residual×source历史KV四臂 → reader状态修复及同次执行再次切断 → 精确规则反事实。正文新图推荐修复条件×实际层号的准确率热力图。
- 新近邻：arXiv:2606.17107已研究字段刷新失败与下游缓存旧结论；不能宣称一般缓存历史解释首次。文献、协议、对照与失败判据已落报告。
- 验证：核对wb_patch.py patch_hook与wb_spanpatch.py decode_ids；文档diff检查。没有新数值结果，下一步是小样本仪器验证，不自动恢复远端任务。

### Open Ideas / 值得深挖的问题（2026-10-16增补）

- 候选：完整执行状态是否决定skill transfer？观察为单层patch未覆盖旧source KV、reader历史，而transfer与来源依赖边界分离。最小验证S/C四臂；强结果需修复后仍有内容特异的来源依赖。已有缓存笔记和中介交互近邻，先判别后评估独立立项价值。详见本轮报告§6。

## 2026-10-16 实验恢复与论文改写（进行中）

- 用户已授权实际启动启智实验、周期检查、生成真实热力图并继续改写。启动前说明已放Windows桌面：`/mnt/c/Users/12970/Desktop/WWW论文实验启动说明与整体脉络_20261016.md`，仓库副本在reports/。
- 平台live列表恢复正常；CPU文件入口wt-dev-cpu已请求start，仍在拉取自动保存镜像，尚未运行GPU实验。未下载新模型。
- 新专用脚本`experiments/mechanism_20261016/run.py`实现边类型/phase拆分、S/C四臂、R可选、SC后下一层recut；缓存于最终提示token重算前替换，不把旧首token当作干预结果。样本固定124题/14组，顺序按组ID交错。
- 本地`test_instruments.py`四项测试通过；py_compile通过。需要远端模型identity与split/full验证才能启动正式批量。
- 论文暂只修正已知方法边界：source-attention dependence同时包括内部更新；单层残差替换不追溯更新低层KV。不写未经测量的机制结果。
- 下一步：读取CPU启动事件，建立文件连接；核实共享盘已有模型和venv；上传唯一run目录，短GPU probe后再批量。

### 2026-10-16 11:20附近：探针与追加任务状态

- 用户追加新家族主实验（Llama/DeepSeek、4090可部署规模），随后明确优先新机制实验，成功后再跑新家族旧双曲线。已更新桌面说明。新权重>1GiB下载批准问题待答，不开始下载。
- GPU环境探针`wt-mechanism-env-1016`成功，Qwen3-8B/0.6B/Mistral等已缓存，torch2.7.0a0、transformers4.57.6、CUDA正常。
- CPU wt-dev-cpu已RUNNING，但7.1.8/临时7.1.12均建立SSH失败，xterm surface not ready。未删除缓存、未重复密码登录。新版CLI只安装于/tmp/inspire-cli-7.1.12，未替换全局。
- 首次大命令被API拒绝（未创建）；缩小后的`wt-mechanism-probe-1016`因远端wb_spanpatch源码与本地不符在模型前中止，未产生数值。
- 现任务`wt-mechanism-probe2-1016`已提交，1×H200，最长2h，独立路径`/inspire/ssd/project/project-public/czxs253130660/mechanism-20261016-v2`。使用本地最小Scorer/Engine+提示/评分依赖源码快照，数据复制前校验SHA256。2题、L8/16、900token、三类边和S/C四臂。
- 远端run.py、probe.jsonl、probe.manifest.json、probe.exit.json、probe.done.json均在该v2目录，只有完成后才有done。当前尚待仪器验证成功。
- 新增有限监控脚本monitor.py（只读，不自动重启），待正式任务启动后运行；当前本会话手动检查。论文已改方法/相关工作/引言/结论，删重复防御性措辞，构建脚本用新暂存目录避免删除旧构建。
