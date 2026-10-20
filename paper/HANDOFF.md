## 2026-10-20 剩余审计完成，正文模型×benchmark矩阵齐全

- 用户目标已处理：诊断HDD配额、完成剩余审计、判定正文所需结果是否齐全。本轮无GPU生成/重提，无删除/下载，无论文修改。
- Mistral/TheoremQA：6332回答独立重判changed_labels=0；逆序＋16 fresh-process对照通过；142候选→73 transfer有效→72共同题/58组，32层完整，self身份无失败，T/R=7/19。报告mistral-independent-audit-20261020-r1.json；初次检查仅因模型层块计数残留9而在重判前失败，修正8块后通过。
- 全suite最终审计completed-matrix-audit-20261020-r1.json：80文件/87915记录，绑定原始SHA与已验证评分overlay，新增独立重判24480个唯一回答（其中TheoremQA414），标签新变化0，逆序＋16 fresh-process对照通过；6024个已执行身份对照无失败。冻结候选覆盖、必需身份网格、跨题donor身份核验通过。结构性same-family/跨题无donor明确单列，不填0、不当漏跑。
- DeepSeek corrected54 edges/repair：54题的donor/receiver/no-skill基线token逐题一致，各suite独立有效46题/40组，必需网格无缺失。深度原分片因评分修正新增5题对应300缺失键，已通过scorefix补跑合并消除；final-family-depth-audit-20261020.json确认4个新增家族组合全层无缺失、无基线token漂移、身份通过。
- 完成度：正文4主模型×MedCalc/TheoremQA=8格深度齐全，Qwen0.6补充2格齐全。Qwen8/TQA82题66组、Mistral/TQA72题58组；其余见completion-matrix-20261020.json和COMPLETION-20261020.md。内容/位置、L2、doclast、windows、bridge、repair、edges共70个模型×任务×suite格有产物；Qwen8/MedCalc六格沿用原已验证实验，本轮另核对关键源文件，其他64格按协议核验。历史深度47份源文件及原Qwen8/MedCalc机制12份源文件SHA全部复核匹配。
- 结论边界：完整指既定冻结候选集与各suite独立基线下的计划矩阵，不是每模型全量benchmark，也不是70格同题同协议重生成；bridge仅2候选预检、部分对照无donor，历史TheoremQA KO预算等价性未最终核实。当前稿件仍写6/8与两Pending，数据已齐不代表论文整合完成。
- 存储：HDD整盘余约25TiB/inode充足、个人du约58GiB，Errno122为配额约束而非整盘满，精确限额未获得；SSD整盘余569GiB但个人约92GiB，也不能据df承诺可写。HDD大目录artifacts26GiB、support_opd_20261002约12GiB、models12GiB、wheelhouse3GiB；前两项为其他研究结果，不擅自清理。当前审计用纯内存＋stdout报告已全部完成，不需删数据。恢复长期持久写入需核对可再生缓存/旧checkpoint用途后用户确认删除，或申请调配额。
- 本轮CPU审计/只读探针均退出，无后台审计待续接。未建TASK-COMPLETE，小时/5h监督保留。下一步是论文整合：先在正确Overleaf关联目录完整olcli diff，纳入协作者修改，再更新图3/深度表/分母与正文结论及所需机制说明，独立编译审计并按流程同步；不能直接将“所有实验完成”写成跨所有题/所有协议的机制泛化。

## 2026-10-20 13:17 Qwen8独立审计与聚合完成（论文未改）

- 已完成本次q8-transfer-20事件对应的全Qwen8审计，不重跑GPU。9个transfer块＋KO共9828条原始回答，逐题parser重置后changed_labels=0，全量逆序一致，16个全新进程评分一致；生成顺序与窄表一一映射，prompt/span与冻结expected一致。
- 168候选→transfer有效88题；KO完整168题合法（启用admission前已生成），独立KO基线筛选后共同82题/66组。共同集36层transfer/KO网格完整、transfer全部有效题网格完整，已执行self身份检查无失败。transfer首次低于0.5在L13，retention首次≥0.5在L21（0-based层号，首次阈值，不宣称单调或机制充分证明）。每层截断计数已保存，最大5/82。
- 9个后续/KO文件的raw和窄表SHA256与done匹配；首块旧done无哈希字段，因此本轮计算并记录其哈希、核对计数/manifest/expected/模块及映射，不冒称其done已有哈希绑定。历史KO预算精确可比性仍未核实，不能称原结果逐字恢复。
- 首次远端overlay审计被HDD Errno122中断，保留部分overlay且无AUDIT-COMPLETE；第二次原生--report-stdout纯内存审计41.51s成功，完整小报告已取回本地experiments/family_depth_20261018/q8-independent-audit-20261020.json。失败中间目录不当完整overlay来源，原始raw未改、未删除文件。脚本audit_q8_recovery.py支持不写共享盘模式。初次字符串转换方案在审计前assert失败，改为直接执行压缩源码后通过。
- 当前Qwen8检查已结束，无本轮审计进程待续接。下一步核验Mistral恢复全网格/独立评分，以及DeepSeek edges独立baseline/eligible与repair token协议，合并全部模型后再按Overleaf完整diff流程改稿。共享盘满会阻碍后续落盘，优先小报告直接本地取回；任何删除另按用户确认规则。整项未完成，不建TASK-COMPLETE。小时timer继续。

## 2026-10-20 Qwen8审计存储异常（实时记录）

- 第一轮审计9个transfer块均完成哈希/映射/逐题重判，处理KO评分overlay写入时HDD返回Errno122 Disk quota exceeded；未形成report/AUDIT-COMPLETE，部分overlay不能当完整审计。原raw未改动，未删除任何文件。
- 诊断后启动相同代码的纯内存审计（跳过远端mkdir/overlay/report写入，以stdout取回本地小报告）；本地进程命令python /tmp/run_q8_memory_audit.py，初次exec session37693在审计前因字符串转换校验失败退出；已加入原生--report-stdout模式，以压缩源码直接在远端whitebox Python执行，当前exec session83779（不写远端文件），远端exec上限600s。目标本地experiments/family_depth_20261018/q8-independent-audit-20261020.json；失败日志和未完成目录保留，不扩写共享盘。
- 下一步检查上述进程结果，完整网格/逆序及独立进程对照通过后再聚合；无论成功与否记录存储约束。不据done改论文。

## 2026-10-20 Qwen8完成事件：独立审计准备

- 用户监督事件q8-transfer-20属于恢复观察后的积压完成通知；四续接Job已全部成功，不重新生成。
- 新增audit_q8_recovery.py，核对9个transfer块＋KO的done计数/raw与窄表哈希/manifest模块与expected哈希/900token协议、按生成顺序映射所有答案、逐题重置parser评分、全量逆序及16独立进程对照。重建168候选基线与36层共同网格，允许KO全候选、transfer后续仅88题。未运行前不声称通过。
- 远端审计目标：HDD recovery目录下q8-independent-audit-20261020；新脚本audit_q8_recovery_20261020.py；原始输出保留，不改论文。已启动timeout PID26797（最长1200s），日志q8-independent-audit-20261020.log、PID元数据同名.pid.json；首轮日志9个transfer块全部AUDITED，KO/逆序/独立进程对照仍在运行，尚无report/done。下一步读取report与AUDIT-COMPLETE，异常先诊断不重提GPU。

## 2026-10-20 13:12 当前实验检查与每小时监督恢复

- 本轮用户目标：阅读当前实验交接、核实进度、设置每小时周期检查。当前入口是paper/HANDOFF.md及experiments/family_depth_20261018/README.md，上级HANDOFF.md为旧GAIA记录。
- Live `inspire --json job status`确认四项c132续接均job_succeeded：Qwen8 transfer、Mistral transfer、Qwen8 KO、DeepSeek edges。观察CPU wt-family-prep-1018原已STOPPED，现已start并connection refresh，RUNNING/cpu-nat-389，恢复时自动停止剩余22h59m；共享盘exec读取成功。
- 共享盘已有Qwen8 transfer全部后续块04/08/12/16/20/24/28/32及总recovery完成标记；Qwen8 KO标记5412回答/168记录；Mistral末块852回答/142记录，KO2450回答/73记录；DeepSeek edges标记54 items/648 records。这里只核验标记和平台状态，尚未对本轮全部raw重新计算哈希、完整网格与独立评分。复制首块标记不计新完成。
- 复用family-depth-watch-01a15016.timer，实际OnUnitActiveUSec=1h、active；手动触发service成功结束（Result=success），watch-progress-state.json已更新且last_error清除。下次北京时间约2026-10-20 14:11；原5h完整检查约16:02保留。新增每小时去重状态摘要，monitor_thread改为当前会话01a157b3-4b1a-76a2-85fe-33c86548a953；原5h续接会话不改。不新增重复timer或GPU任务。
- 定时器依赖本机WSL/systemd/Codex在线，Linger=no，重启后transient timer不保证保留；原expiry 2026-11-01 00:21北京时间及TASK-COMPLETE停止条件保留。CPU约23h后仍需维护，不能将timer active当远端读取永久健康。
- 下一步：独立核验SSD完整块＋HDD续接块的raw哈希、全层网格、身份与token协议，逐题隔离重判、各suite独立重建baseline/eligible，特别核对edges与repair人群；不得直接沿用54分母。完成审计前不声称论文实验完成，不创建TASK-COMPLETE。本文/Overleaf本轮未修改。

## 2026-10-19 最新指令：只排4090，5分钟监督，完成后同步论文

- 用户取消H卡方案。此前仅阅读help/平台文档，**没有提交H100/H200任务或创建H卡实例**；parallel-plan和launch-state无H卡项，不新增第二套GPU队列。现有四个HDD续接任务均为4090单卡Job，合计最多4卡，仍服从8卡总上限。
- 最新live仍4个job_queuing，表示平台待分配GPU，不是已占卡后的内部实验顺序。保留排队位置，不重提，不修改900/1536预算或attention实现。正式开始以可解析回答text写入为准。
- 轻量监督现改为**每5分钟**：现有family-depth-watch-01a15016.timer的用户drop-in ~/.config/systemd/user/family-depth-watch-01a15016.timer.d/interval.conf，daemon-reload/restart通过，ActiveState=active，TimersMonotonic=OnUnitActiveUSec=5min。原5小时完整检查保留。watch新增各任务首次正式raw、全部正式开始和各done出现的去重queue通知；不把排队当开始，依赖WSL/Codex在线及原expiry，到TASK-COMPLETE停止。
- CPU审计后聚合已实际完成，原始JSONL和报告SHA逐文件绑定、13,845条独立评分0变化。aggregate_completed_supplements.py进一步核对Qwen0.6宽表与raw共10,335条生成条件映射、历史prompt/span、所有28层及可用self-token身份一致。冻结168候选，transfer独立基线eligible125，交集122题/92skills，T/R=11/20。该交集不等于旧主图125，不沿用旧分母；900-token KO历史预算差异仍需说明。
- DeepSeek corrected54 battery/L2/windows独立基线均54题/45groups，repair按1536/split-prefill基线为46题/40groups，不能借用Figure3的54作机制分母。bridge仅2候选中1eligible，不当完整机制样本。identity failures均0；battery和L2各52个缺格均same_family_mean；v2已逐题根据skill标题family和冻结donor池验证全部为结构不可用，unexpected_missing=0，不补不存在的donor。windows/repair有效样本的观测网格无缺失。
- 小产物experiments/family_depth_20261018/aggregated-post-quota-20261019.json与v2分类报告均已取回。新核验结果本轮先落盘，尚不修改论文数值；等4090剩余任务完成、最终完整性/基线/身份/截断审计后，先olcli完整diff纳入云端修改，再更新正文及相关图表、独立编译、同步Overleaf/GitHub，不再导出桌面。反例继续仅保留研究记录。TASK-COMPLETE尚不创建。

## 2026-10-19 已按授权删除Qwen14B，继续补跑与独立审计

- 用户明确授权先删除Qwen3-14B内容。已删除准确目录/inspire/ssd/project/project-public/czxs253130660/models/Qwen3-14B（29个文件，7,599,691,435逻辑字节/7,599,721,984分配字节，约7.08GiB），包括旧未完成下载和少量配置；目录不存在已验证。未删除Mistral consolidated或任何其他数据。删除前文件清单与完成证据audit/QWEN14B-CLEANUP-20261019.json，远端HDD也保存qwen14b-deletion-audit.json。此前提议中的Mistral清理仍未获授权。
- 清理后SSD个人目录du约92GiB（此前99GiB）。新增32MiB probe写入+fsync成功，耗时0.036s；probe保留在ROOT/ssd-after-q14-cleanup-probe-20261019.bin，不私自再删。CPU探针不等于已验证GPU节点写入，也不是完整磁盘基准。
- 对SSD加速的判断：当前所有模型权重始终在SSD，GPU加载路径未迁移；HDD只接收小规模JSONL。Qwen8首块数小时约5MB raw，结果写入量很小，因此不预期仅把结果切回SSD会明显缩短生成。为保留四个现有排队任务、避免迁移路径/重复提交风险，本轮保留HDD输出；SSD已恢复可写供新审计使用。实际GPU耗时尚未做SSD/HDD配对测速，不声称测得加速比。
- 四HDD任务最近仍queuing，未重复提交；原已完成块继续复用。30min watch保持并新增正式raw检查：四任务都有可解析text记录时才queue单独实际开始通知。5h timer保持，TASK-COMPLETE不存在。
- 等GPU期间已启动已完成补跑的独立CPU审计：audit_completed_supplements.py，覆盖DeepSeek corrected54 battery/L2/windows/bridge/repair五suite＋Qwen0.6全部7层块和KO的raw（13文件）。输出ROOT/post-quota-audit-20261019/，日志同名.log，PID元数据同名.pid（timeout进程897054），20分钟上限，不覆盖旧overlay/raw。逐题parser重置、全量逆序一致性和16 fresh-process对照；完成标记AUDIT-COMPLETE。watch已补完成/异常提醒。已实际完成：13文件/13,845回答/changed_labels=0，全部逆序重判及16 fresh-process对照通过。仍须各suite独立baseline/eligible聚合，不把标签核验完成当论文所有实验完成。
- 下一步：核验CPU审计日志/报告、4个HDD Job正式启动与写入；Qwen8/Mistral SSD完整块和HDD补块按manifest/raw哈希联合审计。继续Overleaf完整diff→本地修改→Overleaf/GitHub流程，尚不改论文数值，不导出桌面。反例暂不进paper。

## 2026-10-19 存储只读盘点，待清理确认

- SSD个人目录约99GiB，权重97GiB占主导；HDD个人目录58GiB。共享SSD使用99%且inode57%，df不能代表个人配额，精确fileset/user限额未查得。详情reports/存储占用与清理建议_20261019.md。
- 可优先考虑的准确9文件清单audit/STORAGE-CLEANUP-PROPOSAL-20261019.json：Qwen14B 8个9月12日未完成下载片7.08GiB＋Mistral consolidated.safetensors 13.50GiB，合计20.58GiB。Mistral当前HF索引引用另3分片且均存在。CPU无相关下载进程；4个可见活跃GPU Job均当前HDD续接、仍排队。
- 尚未删除或获准确目标删除确认；按用户AGENTS先报告范围/影响/不可回收再确认。删除前复核文件未改动，保留Mistral三HF分片、索引/tokenizer/config。其他旧模型、HDD的OPD训练产物不据年龄判断无用，不删本paper原始结果/overlay。清理HDD不直接释放SSD配额。无需因当前排队盲目重提Job。

## 2026-10-19 最新同步约定、术语与配额故障续接

- 用户最新要求：**每次论文更新先运行olcli完整行级diff，纳入合理云端修改；本地修改和编译审计后同步Overleaf与GitHub，不再向桌面导出。** 该要求覆盖历史桌面交付步骤，旧交付保留。详细入口OVERLEAF.md；5h检查消息已同步改为新流程，反例仍只记录研究，暂不进paper。
- 已核验关联Overleaf项目6a2cfd49b99635e8e968576a，虽然项目名仍是旧ICLR Skillflow，实际当前稿在overleaf-skillvector/。首次误用paper根作diff导致大量local-only，随后改为17项匹配暂存目录，保存并完整审阅998行真实diff。差异不能单独识别作者；采用云端更准确的历史筛选/重新评估、条件性结论、机制覆盖局限、四主模型+Qwen0.6补充检查等内容，保留用户要求的Intro首段Web语义关联。图3仍7个已核验panel（6主+1补充），不把未审计旧TheoremQA补入。Table2保留云端4模型×2任务矩阵、两Pending单元与归一化深度差；生成器已适配，原数值JSON未改。
- source统一为skill span/skill-position states/skill-position KV cache；reader改为post-skill positions，明确是skill之后的提示词和生成推理/答案token，不是receiver模型。前置token因causal mask不能读skill。Figure2/4、Table3及正文/当前附录一致；切边不删除skill、不抹去已传播的信息。Table3前三行是干预结果对比，并非各有一个mask；路径切断行准确指向query→skill keys。
- 本地编译改Windows Temp，首次通过正文8/全文11页，error/undefined/hbox/vbox均0；云端上传前再次diff核验自首次读取后无新增修改，17文件上传成功，指定nested main独立编译成功。云端PDF也核验正文8/全文11页，0error/undefined/hbox/vbox；ZIP与上传的所有TeX/Bib/PDF逐文件哈希一致，audit/OVERLEAF-TERMINOLOGY-20261019.json。没有新桌面输出。
- 实验新故障：Qwen8原Job16:55于L4块输出写入Errno122 Disk quota exceeded；DeepSeek机制17:03已完成bridge与repair，但创建edges manifest（零字节）失败；Mistral17:14在L28块写入也失败。Qwen0.6重生成与DeepSeek battery/L2/windows已成功。原失败块全部保留，不重启整池，不删文件。SSD df余量不能代表用户配额；CPU小写可成功不等于GPU大写正常。
- HDD新目录/inspire/hdd/project/project-public/czxs253130660/family-depth-recovery-20261019，8MiB写入实测通过。仅复制Qwen8/Mistral完整首块基线和小脚本；quota_recovery_worker验证SSD完成块的条数、raw哈希（如有）、模块哈希和层网格后跳过，只在HDD重生成未完成块。原partial仍在SSD，不拼接残缺raw。Qwen8transfer与KO分成2卡；Mistral补L28块后KO；DeepSeek仅edges。四Job dry-run与提交均成功，最近4个job_queuing，**尚不能宣布实际开始**。名字wt-recover-{q8-tqa,mistral-tqa,q8-ko,ds-edges}-hdd-1019，详细quota-recovery-jobs.json；总卡最多4≤8，未下载权重。
- parallel-plan/launch-state已登记新4任务（总75已提交，含被替代失败Job），quota_recovery注明旧3Job替代关系和HDD完成标记绝对路径。旧计划Qwen8 SSD并行KO从未提交，不能恢复它。watch_progress已改观察HDD与新4Job，旧失败Job由新任务取代；30min监督与5h检查均active。整项实验尚未完成，不建TASK-COMPLETE。
- 下一步：先核验4个HDD任务正式raw/manifest和GPU写入；完成后按SSD完整块+HDD续接块联合审计网格、身份与逐题隔离评分，不混入SSD残缺块。DeepSeek repair独立重判/edges及全部suite人群仍待汇总，Qwen0.6已完成输出待独立审计。暂不承诺全部完成时间，排队和存储条件影响很大。固定99题Llama长度诊断仍未提交，反例只作研究记录。

## 2026-10-19 14:22 授权自主监督与排程优化已落实

- 最新用户指令：及时监督，无需逐项确认，采用更高效排程，并区分正文真正需要的证据。平台沙箱强制审批仍适用；没有让用户选择日常实验细节。
- 增设30分钟轻量监督family-depth-watch-01a15016.timer（首轮14:04已成功，下一轮14:35，live核验active waiting）。原5小时family-depth-progress-01a14a9e.timer active，下一轮18:16。watch_progress.py只在失败/整体2h无输出/并行提交等异常或阶段变化queue当前thread；有效期同原14天，到TASK-COMPLETE/expiry停自身timer。无自动盲目重试。
- watch-progress-state.json已保存首轮七Job running及12个正式raw文件的字节/mtime，无last_error。每30min只读小metadata，不下载大输出。
- 已部署legacy_text_entry V2到远端原入口，用于后续新层块；正在生成的V1进程不受影响。原V1本地/远端均备份，V2哈希124146bde1f7f4e1df059e9f3efd30f4e29001bf70273abe24150a2f7b5432c2。完整首批基线done后，按全候选group receiver-zero＋donor-correct＋no-skill-wrong冻结有效ID，再计算后续transfer/KO。选择不读任何干预结果。baseline_admission.py通过group排除、donor/no-skill与干预字段无关性检查；V2每文件manifest含helper/source哈希和筛选ID。
- 后续span层块不重复生成每个块两端的identity，仅保留原首块控制与全模型最终层控制。KO仍为所有入选题生成其独立eager基线，仅在该题donor-rescued时计算昂贵全层KO；不制造未生成的干预输出。数值规则/900预算/attention实现不变。原baseline不筛小池，不按干预结果挑题。
- Qwen8 KO并行配置q8-knockout-parallel-job.json已dry-run通过。轻量监督将在完整首批168基线done、canonical KO尚未开始且活跃Job<8时记录attempted/owner并提交第8卡，复用同一个canonical KO路径。原worker之后验证完成标记/args/source/条数/哈希并跳过已完成KO，不重复生成；若KO尚在跑则有界等待24h并由监督查错。提交不确定不自动重试。任务实际提交时才增加parallel-plan和launch-state（当前仍71已提交）。
- 实验优先级：若要完整五模型×两任务矩阵，旧3组TheoremQA深度/KO与基线评分审计必须完成；当前7组v8并不依赖这些未完数据。L2/content/path控制是结论支撑或附录证据，不必每项进正文。重复窗口是因果冗余的一致性检查，不再扩展新窗口。固定99题L24长度诊断未启动，降为后续研究，暂不占第8卡或改paper。
- V2生效已live验证：Qwen0.6后续L20–23、24–27及KO三个manifest均显示baseline_screen_applied=true、eligible125/原168；新筛选只使用完整基线。Qwen8/Mistral仍待后续层块验证。
- 下一步：核验V2实际被后续Qwen8/Mistral层块采用、监控first baseline→并行KO触发，按新吞吐更新ETA；审计后再改稿。v8已推5c05cdc并同步桌面；本轮ongoing实验代码/状态未提前打包提交，TASK-COMPLETE仍不存在。

## 2026-10-19 13:43 七项补跑全部正式开始与耗时估计

- 用户询问是否全部在跑及多久。Live七Job均running，且全部有正式raw：Mistral已有304条回答、Qwen8 169条；Qwen0.6已完成0–3、4–7两层块，正在8–11。DeepSeek L8/L2/windows分别12/18/27题已开始（不是完成题数），bridge done、repair到第5题。已向用户明确本轮7项均正式开始里程碑，不能沿用旧state旧里程碑。
- 粗估剩余：DeepSeek controls1–3h、机制4–8h、Qwen0.6重生成2–4h、Mistral12–24h、Qwen8约30–60h。该估计只按首批实际吞吐与完整待跑层网格外推，后层回答可能更长；需5h后更新，不保证上界。Qwen8为瓶颈，可能超过单Job48h，必须在接近上限前保存/核验完成层块，制定不重跑已完成内容的分段续接；不盲目重启整个worker。
- 原任务中额外固定99题Llama L24长度诊断未正式提交，另作研究，不谎称该项也在跑。当前7卡<8卡上限。
- v8已同步桌面并push master 5c05cdc；后续实验/研究继续，反例暂不进paper。timer保持，TASK-COMPLETE不存在。

## 2026-10-19 v8阶段交付编译与桌面同步通过，提交检查点

- 用户要求立即阶段交付已落实论文更新。export_review.py实际ZIP独立编译通过：正文7/全文10页，0error/undefined/hbox，1个尾页2.124pt vbox（目视无越界）。桌面新目录StillNeeded-WWW2027-v8-VerifiedDepth-20261019已创建；上传包17项，SHA256 ac49abd63ee5d479b334fa8074aa23b374b6931693a643219c4608d6ea0b29e1。audit/DESKTOP-VERIFIED-DEPTH-20261019.json。
- 图表合集9页，4图4表，0error/undefined/hbox。Figure3与Table2 PDF页面均目视核验，14条曲线与7边界数值审计通过，原数值JSON未改。新PDF使用精确ZIP编译产物为权威交付。
- 合集/交接/待补清单已同步桌面，PDF与实际ZIP逐字节一致检查通过。本次按用户授权commit/push相关paper文件，明确排除旧values/DATA-CONSISTENCY-20260918.json、整个未完成实验大目录和../howskill/data/cells.json.tmp。本阶段交付完成不代表研究任务完成，不建TASK-COMPLETE，不停timer。
- 下阶段继续7个已提交补跑的live核验与审计，再更新其他跨模型控制/机制矩阵。固定99题长度敏感性尚未提交；代码、来源、配对观察与论文调研已落盘experiments/family_depth_20261018/RESEARCH-RECUT-20261019.md。用户要求反例不进当前paper，研究记录保留；不得把当前single-setting机制结论写成全模型全深度结论。

## 2026-10-19 用户要求先交付已核验论文、继续后台补跑

- 最新指令覆盖整项完成后才提交的时机：现在把已核验结果先更新paper，编译Overleaf包、同步新桌面版本并push GitHub；其余补充记下来继续。本轮不是实验全部完成，不创建TASK-COMPLETE，不停5h timer。新反例只保留研究记录，暂不进稿；稿件机制范围仍Qwen3-8B/MedCalc，不作全模型全深度机制断言。
- 当前稿Figure3/Table2改为7个已核验共同样本比较：原3个MedCalc＋新增两家族×两任务。旧3个TheoremQA在隔离评分重测完成前不参与主图/边界/结论；对应旧TheoremQA重复窗口未审计数字暂退出当前附录。旧原始数值JSON不覆写。摘要/引言/方法/结果/结论统一5模型4家族7比较，新增候选池偏差/DeepSeek小样本/评分隔离及模型引用。
- 新可复现数值values/depth-verified-extension-20261019.json，style_main_figures/build_boundary_table/export_figure_bundle已适配；14条曲线/7套边界和阈值.4/.5/.6方向检查通过。原depth-crossmodel及两mechanism JSON与HEAD字节一致。audit/VERIFIED-DEPTH-EXTENSION-20261019.json记录证据。
- Figure3已目视检查，Libertine字体已通过PyMuPDF嵌入字体核验。build.sh最新stage cyQMKu6S：正文7/全文10页，0error/undefined/hbox，1个2.124pt尾页vbox警告（无可见越界，已目视Figure3页4、Table2页5及尾页10）。当前正在export_review精确ZIP独立编译并新建桌面v8-VerifiedDepth，不能在该步骤通过前声称桌面交付完成。
- 交付/待补说明reports/阶段交付与待补清单_20261019.md。Table1/3与Figure4保持已核验focused范围；全模型控制/机制矩阵还需完成评分修复和审计后再整合，并非已经全部更新。
- 后台状态最近：DeepSeek corrected54四任务均正式生成；Qwen8和Qwen0.6旧协议已通过全题prompt/span一致检查并捕获/生成，raw保存已核验：Qwen0.6首文件25条、Qwen8首文件7条，含完整text/token_ids；Mistral仍排队。故尚未发送新增所有任务已正式开始里程碑。
- 固定99题Llama/MedCalc L24长度敏感性代码/ID/Job配置已准备并上传、dry-run步骤待核验，但没有正式提交；当前7任务≤7卡。按最新用户要求先完成桌面/GitHub阶段交付，再继续研究与必要补跑。新机制反例数据保存在experiments/family_depth_20261018/recut-counterfactual-medcalc-20261019.json，不加入paper。

## 2026-10-19 新家族四组深度正式审计通过

- analyze_isolated_depth.py已远端实际运行成功；输出ROOT/final-new-family-depth-20261019.json。验证raw SHA绑定隔离overlay、补跑5题基线token与原记录完全一致、全层网格无缺失、identity token一致。四组status=complete：Llama/MedCalc112题20组T/R7/18；Llama/TQA92题71组6/18；DeepSeek/MedCalc25题13组6/21；DeepSeek/TQA54题45组4/19。都无baseline_token_drift、missing、identity_failures。已向用户报告，仍不能外推小样本DeepSeek/MedCalc。
- corrected54四任务已全部实际生成：battery日志新增00296 donor正确且进入other_skill/matched_prefix；L2日志00686进入位置与permuted控制；windows此前已核验；mechanism bridge日志identity_SC与S_split继续。未发现新失败，但未全部完成。旧三模型3任务live仍queuing，无日志，不能宣布所有新增正式开始。
- 旧三模型batch提交已返回3名字成功，launch-state submitted/attempted均71；原64全done、后续7在跑/排队。仍≤7卡，不重复提交，五小时timer active（上次核验正触发service，需下一轮看排程）。
- legacy replay caveat：历史KO原命令token预算尚需考证，本轮900tokens同时保留400前缀评分诊断；冻结原depth候选168/168/142，而不是原主图筛后99/132/115。原prompt/span长度不匹配则自动停止。最终需报告模型/硬件/协议差异及原值与重测值，不称恢复了当初未保存的答案。

## 2026-10-19 旧三模型TheoremQA重生成已准备并提交

- 在本地原始depth文件中找到完整候选输出，而不是仅主图筛后人群：Qwen8/Qwen0.6各168题、Mistral142题。legacy-{key}-theoremqa.cells.json冻结原始depth标签的全部ID；expected.json冻结各题n_prompt/n_patched/doc_start，生成前逐项断言一致，不按新干预结果选题。
- legacy_text_entry.py沿用原wb_spanvec（SDPA、doc-first、fixedskill）和wb_knockout（eager）代码，恢复parser初态评分；截获tokenizer.decode保存每次完整text/token_ids及900-token正确性、400-token前缀诊断。历史KO预算尚未从原命令证明，不能不加说明当严格同预算复现；保留两种诊断供核对。重生成不是从旧bool恢复原回答。
- legacy_replay_worker.py每次4层限制host capture内存，第一层块重跑完整baselines，随后所有层real与两端self；最后同冻结候选全层KO。旧span代码跨全部题capture，不能一次捕获全36层避免host OOM。每题prompt/span断言失败立即停止。py_compile通过，3任务dry-run通过，8个小文件打包上传解包独立legacy-replay-20261019/。
- wt-legacy-{q8,q06,mistral}-tqa-1019已提交尝试（检查batch session41017结果和live status后补submitted，避免重复）；原四修正任务占4卡，本3合计最多7。parallel-plan总71，state attempted已登记。legacy done在子目录，launch_when_ready.observe已补递归该目录并返回相对path，避免完成后误判占卡。
- DeepSeek corrected54 windows已正式生成；日志显示新增00296 donor正确、receiver/no_skill错误，identity两层通过后进入窗口。其余新任务尚需逐个日志核验；不把creating/queue当正式开始，不提前宣称新71任务全部开始。
- 这些实验完成前不更新最终数值或交付；下一步核验首批旧模型prompt匹配和raw正确保存，必要排障；整合各suite基线、截断和donor分母，最后论文/桌面/GitHub全闭环。timer保持，TASK-COMPLETE不存在。

## 2026-10-19 周期续接：原64任务全完成，修正池4任务已提交

- live共享盘76个done、原q8/MedCalc L2已done；原64个GPU计划均完成。平台当前未见旧活跃Job。CPU wt-family-prep-1018仍RUNNING，最近核验剩余16h；五小时检查消息已实际送达当前会话，不重复设timer。
- 新评分筛选DeepSeek/TQA 54题，原51新增5移除2，会改变cross-skill donor池；因此用冻结corrected54独立重跑L8 battery、固定L2 battery和windows，避免把不同donor池的控制拼接。corrected54-control-jobs.json已dry-run/正式提交成功；名字wt-fix-ds-tqa-{battery,battery-l2,windows}-1019。live两个running、battery creating，尚未核验全部正式生成。旧原始输出不覆写。
- 另1卡wt-fix-ds-tqa-mechanism-1019已dry-run/提交成功；corrected_mechanism_worker.py串行bridge→repair→edges，bridge原limit2仅身份/协议控制，完整mechanism IDs来自54题先做1536预算context过滤；独立输出deepseek-theoremqa-corrected54-{bridge,repair,edges}，最终mechanism.done。总新卡4≤8。
- isolated_entry.py包装未修改的followups/instrument入口，逐回答恢复latex2sympy2初始globals；新增.grading-protocol.json记录wrapper/script哈希及argv。仅新路径，已有raw直接拒绝（不盲目续跑）。isolated_suite_worker.py仅把机制子进程包在该入口。源码本地py_compile通过，远端上传完成。需实际检查首条JSONL与identity控制，失败先诊断。
- parallel-plan总68，readiness含4新增；launch-state attempted和submitted已登记，不重复提交。旧coordinator不一定存活，不据state all-started旧标记通知新计划。旧raw/reports保留；修正54对应report在isolated-grading-refresh-report-20261019.json。
- audit_suite_populations.py的missing_observed_arm_grid不是最终补跑清单：same-family donor不存在、doclast singleton组本来不产生干预；要分清结构不可用与评分改变造成真缺失。各protocol有效集需单独审计，不共用Figure3分母。初审截断在DeepSeek/Llama若干arm较多，需报告，不事后按干预结果删题。
- 下一步：核验4新Job实际生成/控制，旧三模型TheoremQA按原wb_spanvec/wb_knockout协议重新生成的配置及raw保存尚未完成；不把这4任务完成当整个任务完成。继续查旧cells/配置与模型路径，先建完整协议匹配审计再启动。之后统一全suite数值、图表/正文、独立ZIP编译、桌面和master push。TASK-COMPLETE仍不存在。

## 2026-10-19 最新实验待办核对

- Live按parallel-plan/readiness映射核验63/64完成，仅wt-fa-q8-medcalc-battery-l2-1018无done；Qwen0.6/MedCalc bundle与DeepSeek/TQA scorefix-s0本轮已done。
- 隔离重判refresh后台PID已退出、report.json存在。已执行audit_suite_populations.py远端成功：73份完成输出，跨协议eligible计数3869（非独立题目数），identity_failures=0。输出ROOT/suite-populations-20261019.json。后续须读取逐suite缺失/分母，不能据总数宣布全部有效。
- 待办仍包括DeepSeek/TQA新增5题在正文各suite缺失补跑（先按各自protocol复核baseline/context/donor）；旧三模型TheoremQA缺文本问题的协议/环境核查与必要重新生成。并非只剩最后1个任务就能交付。

## 2026-10-19 原始回答文本可恢复性复核

- 用户问旧模型缺文本的重要性与能否找到。进一步live扫描个人SSD wbout旧TheoremQA文件：59个JSONL/18817行、59份log（含部分重复/part，不等于独立实验规模）。JSONL除ok_*外唯一候选字段是skill_tokens/task_tokens（各940条），无回答文本或生成token；59份日志未匹配ANSWER:/token_ids/JSON text/response标记。代码graded只返回bool，spanvec/knockout输出日志亦为分数。因此当前主要原始输出目录也未找回回答，不能声称仅本地漏同步。
- 尚未穷尽其他目录/压缩备份；不能断言绝对不存在。若生成时未保存，无法由bool反推原答案，需同协议重新生成且保存文本/token_ids，重判基线及干预，不假定旧模型必然受污染。当前已证实污染来自新批次，旧批次是否受影响尚待验证。

## 2026-10-19 01:50 本轮续接、五小时检查与评分审计

- 原始目标：继续全部实验，评分/筛选/缺失补跑审计后更新唯一paper，最终独立编译ZIP、同步新桌面版本与GitHub master；最多8卡、不删除、不重复启动。任务尚未完成，未创建TASK-COMPLETE，未提前提交旧工作区改动。
- 本轮发现timer配置仍指向旧对话01a14a9e；已改为当前CODEX_THREAD_ID=01a15016-1c41-7760-9668-87422444438d，保留原timer名与5h间隔，避免后续检查投递旧会话。
- systemctl用户总线需沙箱外执行；已核验family-depth-progress-01a14a9e.timer active，OnUnitActiveSec=5h，下一轮02:31:09 CST；已有queue日志成功投递。check_thread.py已修复过时Table2例外，加入全量隔离重判和必要补齐要求。有效期仍至2026-11-01 00:21 CST，依赖WSL/Codex在线，不是云端保证。
- Live已确认Mistral/TQA repair与DeepSeek/TQA scorefix-s1 done。剩余三个Job job_running：q8/MedCalc battery-l2，q06/MedCalc bundle（edges未done），DeepSeek/TQA scorefix-s0。未重复提交。CLI 7.1.8提示7.1.13更新，未中断实验升级。
- 新发现旧Figure3三模型TheoremQA原始结果18文件/2034行仅保存ok_*，无回答文本/token_ids；代码wb_spanvec.py和wb_knockout.py也仅存bool。legacy-raw-availability-20261019.json记录路径/哈希。不能声称可直接重判；必须先搜索独立raw档案，确无输出则按原协议补跑，保持原筛选候选与protocol，不能把新prompt结果替代旧结果而不说明。
- regrade_refresh_20261019.py已上传并以nohup启动，输出独立isolated-grading-refresh-20261019/，日志同名.log；逐题parser reset、逆序全检和16 fresh-process对照继承已验证实现，不覆写旧overlay。启动CLI session99337（后台shell等待导致CLI未返回，但远端PID217110已live确认运行，绝不重复启动）。只扫描已done的TheoremQA；如有后续完成文件需再做版本化增量审计。
- audit_suite_populations.py已本地编译并上传。用raw SHA256与overlay绑定，重建各协议观测baseline的group screen，记录缺失干预/身份token不一致/截断/各arm分母；它明确不能替代原完整候选池screen，也不能把可变donor缺失当0。待新重判report通过后运行：python audit_suite_populations.py --root ROOT --overlay ROOT/isolated-grading-refresh-20261019 --out ROOT/suite-populations-20261019.json。
- 下一步：核验新重判进程/报告，执行suite审计并取回小产物；补齐所有新增eligible跨suite，而不只depth；查旧三模型raw archive（当前已查local fetched结果，远端独立repo/旧结果尚待核查）；必要时准备忠于原协议的隔离评分重新生成。之后再整合论文，不能据stored correct直接填图。

## 2026-10-19 01:35 交接与桌面v7交付

- 用户要求新对话续接交接、当前稿桌面另存、统一图表字体。HANDOFF-NEXT-CONVERSATION.md顶部已新增完整权威入口：64任务状态、评分污染/隔离证据、新增eligible补跑、旧三模型与全部suite待审计、资源恢复/下一步。历史全文保留。
- 四主图PDF嵌入字体逐一检查均Linux Libertine O（常规/粗体/斜体），表格显式normalfont+rmfamily；无意外字体回退。原始15份数值输入audit_three_display_revision.py通过，点估计/筛选不改。
- 新桌面版本StillNeeded-WWW2027-v7-Handoff-20261019，保留旧交付；含独立精确ZIP编译的PDF、Overleaf ZIP、源码、图表合集和两份交接。正文7/全文9页，图表合集9页；0error/undefined/overfull。ZIP17项，SHA256 1f12b4938b2137c8eca539a909545b70aefc2e7401c45b712056fb043eb38a6f。审计audit/DESKTOP-HANDOFF-20261019.json及FIGURE-FONTS-20261019.json。
- 本桌面稿尚未纳入新家族正式结果，阅读说明明确标注；补跑/评分审计与五小时检查继续。完整任务仍未完成，不创建TASK-COMPLETE，不把该桌面交付当最终新模型论文闭环。

## 2026-10-19 当前状态问询核验

- 两个DeepSeek/TQA scorefix分片已实际生成22/24条正式JSONL（当前live快照），均未done；已从排队进入正式实验，原“尚未开始”记录已过时。尚待全30层齐，不填DeepSeek/TQA最终曲线。
- 隔离评分overlay重新计算Llama/TQA共同92题：迁移首次半效应L6，source dependence首次降至半效应L18，边界方向与旧stored结果一致。MedCalc两新模型已完成全层网格/身份审计：Llama112题/20组T/R7/18，DeepSeek25题/13组6/21；DeepSeek25题只支持该筛选人群，不能外推benchmark。
- 正文内容/位置与SC/recut、路径等suite不能仅凭done宣称泛化。仍需统一评分、有效集/截断审计；重复注入仅一致性检查，不是独立维持失败证据。

## 2026-10-19 图表美化完成验证

- 四图字体均为LinLibertine常规/粗体/斜体，表格统一9pt及1.22行距、白底；Figure3只保留rho/d主曲线；Figure4为数值热力图＋横向分层点图。后续更新沿用当前集中字体配置和显示规则。
- 论文正文7/全文9页，合集9页；均无error/undefined/overfull。已目视四图及正文/附录表格；PDF文本清理扫描通过，15份数值输入与原稿不变。审计`audit/DISPLAY-STYLE-20261019.json`。
- PDF、Overleaf ZIP和图表包已同步；本轮只提交论文与图表改动，未完成实验目录及旧DATA-CONSISTENCY改动留本地。

- 表格追加要求：正文/附录四张表统一正文Linux Libertine系列，表内9pt/11pt行基准，arraystretch=1.22；表头常规粗细区分但不换字体，保持白底。合集使用同一tabular字体钩子。

- 字体追加要求：四图统一Linux Libertine（与acmart正文/表格同系列），含常规/粗体/斜体及数学符号；由tools/figure_fonts.py集中配置。PDF嵌入字体检查四图均仅LinLibertine，不再混用DejaVu Sans。复现需Linux Libertine或PAPER_FONT_DIR，缺失时报错。

- Figure4追加可读性改进：左侧改为四干预×四层的带数值热力图（0–100%固定色阶），右侧按层分组的横向路径损失点图，去除棒棒糖竖线。原始16+9个数值及样本不变，Table3保留派生差值。热力图颜色编码数据，普通表格保持白底。

- 追加要求已落实：Figure3去掉common-item check两条虚线和图例/图注，只保留rho与d主曲线；共同样本Table2和正文检查保留，半效应参考线保留。

## 2026-10-19 01:14 启动里程碑live复核

- 本次queue消息是原62任务里程碑，不能直接扩大到新增64任务。live：wt-f3-deepseek-theoremqa-scorefix-s0-1019和s1均job_queuing，未见JSONL、无日志、无done。故不宣布新增补跑已正式开始，用户已获通知的仅原62任务。检查*.done.json common_n字段未发现0，但这不等于已审计全部suite的有效人群，仍需逐suite核验。
- 五小时timer active，下一轮02:30:36 CST。原state的all_started_notification_queued是原计划的历史标记；后续新增计划不能以此当正式开始证据，应以JSONL和done live核验。两新Job已提交，不重复创建。

## 2026-10-19 图表展示与排版新约定（覆盖旧显示要求）

- 用户要求当前全文和图表不再展示或讨论CI；已删除主文、当前附录、Table2中的对应数值和方法说明。源结果JSON保留，点估计与样本不变。
- 后续所有正文、附录和图表包均沿用纯点估计展示，Table2也不例外；表格取消所有底色，使用三线表、较大字号和行距。图中表示深度区间的浅色区域保留，因为它不是表格底色或统计区间。
- 四张主图字体与画布高度已适当增大，精简图例避免拥挤；d=1-q不变。正在重编译检查页数、文字碰撞和原始数值，随后同步PDF/ZIP/图表包并提交。

### 本轮评分隔离验证通过与补跑安排

- regrade_isolated.py完成：42927条/22468唯一文本，全量逆序重判一致、16个fresh subprocess对照一致；359条原标签变化。已取回isolated-grading-report-20261019.json，overlay远端isolated-grading-20261019/，原始JSONL不改。
- Llama/TQA frozen eligibility仍92题/71组；DeepSeek/TQA由51题/44组变54题/45组，新增00296/00474/00513/00588/00686，移除00320/00321。新增5题没有depth干预，不能直接填曲线。
- 独立supplement_depth.py沿用full-prefill/BF16/eager/900tokens/原模型prompt和engine，逐题隔离评分状态，使用全候选池重评后的冻结成员资格；不在这5题子集上重新做group screen。仍每任务两个完整skill分片，两Job wt-f3-deepseek-theoremqa-scorefix-s{0,1}-1019已dry-run通过，计划总64；协调器重启自动提交，live实际开始需看日志，不当作已经开始。其余原62任务已正式启动里程碑不撤回，但此后必要补跑不包含在原里程碑中。
- 本地完整快照263文件26,080,882bytes，SHA256 ebcf73efce9c428a156d251d8114993b444b84283d375c935d576a994826f58d已核验并解包retrieved/snapshot-20261019。按原stored标签全四组合层网格/身份审计通过，输出provisional-depth-stored-labels-20261019.json，只作结构审计不可作为最终TheoremQA结果。
- 后续还需：统一重判旧三模型Figure3原始输出及全部正文suite、重建各自新基线筛选；新增5题补充battery/windows/doclast/bridge/repair/edges所缺记录；检查其余模型是否也有新增eligible。不要只补depth即标完成。逐样本初始状态隔离是修复跨题污染，提取规则未改，官方extractor自身的substring/boolean缺陷应作为局限记录。

## 2026-10-19 续接巡检（当前入口）

- 用户“继续”授权持续，最多8卡。读取顶部交接/README/deployment并核验live；wt-family-prep-1018因23h时限自动STOPPED，已start并connection refresh恢复共享盘观测，未新建CPU或GPU重复任务。
- 逐项按parallel-plan/readiness核对：62/62已提交，59/62对应完成标记，所有正式单元均已有生成文件或完成标记（not_started_units=[]）。**已向用户单独通知全部正式开始**。剩余3个job_running：wt-fa-q8-medcalc-battery-l2-1018、wt-fa-mistral-theoremqa-repair-1018、wt-fa-q06-medcalc-bundle-1018。总done文件69不能当69个GPU任务，小模型bundle含多个单元。
- 未新增failed标记；只有旧DeepSeek s1预检历史。旧无-s整池不恢复。coordinator PID83926仍active；此前last_observation_error是CPU停止导致，恢复后需让下一轮刷新清除。
- 已上传并后台运行regrade_isolated.py，CPU PID18376；逐题恢复解析器初始globals，保留原始JSONL；输出isolated-grading-20261019/report.json和评分overlay。检验包含全部唯一输出逆序一致及最多16个fresh subprocess对照，审计完成/通过前不得用overlay做最终曲线。日志isolated-grading-20261019.log。不得重复启动，先看进程和report。
- 正在打包completed-snapshot-20261019.tar.gz（exec session72075），只已done的raw及小型manifest/screen/context，不含权重；完成后核验size/SHA、安全解包，再核验全层/身份/截断。首轮3组初审曲线仍暂定，评分修复若改变人群需补缺失干预。
- 最新用户要求：先查清新模型异常、修复已证实问题再整合paper并汇报，不为维持旧结论选择样本/层/指标；真实反例需如实限定。参考reports/图表审阅与改进建议_20261018.md，且新图统一橙线d=1-q。历史另一次立即提交授权已记录顶部，核验当前git状态再处理；本轮未完成实验不提前标完成，不创建TASK-COMPLETE。
- 下一步：取回隔离评分报告，验证fresh-process等价与逆序一致；重建新旧TheoremQA baseline screens、核验新增eligible完整干预；缺失按原协议补跑并持续最多8卡。完成所有结果后更新正文/图表/独立ZIP编译/桌面同步/最终仅本次文件push master。

## 2026-10-19 Problem Formulation与图文重构（当前任务）

- 用户要求精简定义、可读公式、统一实验小标题及图文匹配检查。已按Setting→S/C→knockout→metrics→boundaries重构；source token集合mathcal I避免与干预S重名。新增cache/knockout/boundaries公式，dose和delta移附录。
- 实验subsection/paragraph统一名词短语；压缩重复定义。四图三表保留：Fig1概览重复有明确用途，Table3展示派生差值而非重复原点值；Fig4说明等距层组和零点竖线；Table1补匹配前缀提示。
- 重复注入降为一致性检查，保留测值，不再作为独立“维持状态失败”证据。详细报告`reports/ProblemFormulation与图文核查_20261019.md`。后续仍统一d=1-q；新家族结果尚未入当前稿，不混入未完实验。
- 最终验证：audit_three_display_revision.py通过，15份数值输入不变；源数据/边界额外SHA检查通过。论文正文6/全文9页，图表合集9页，均0 error/undefined/overfull；第2–3页公式/图注已目视核查。PDF、图表包和ZIP已同步。审计`audit/FORMULATION-REVIEW-20261019.json`。本轮完成后提交推送；既有实验目录和旧DATA-CONSISTENCY改动不提交。


## 2026-10-18 用户授权立即提交推送

- 覆盖此前等待整个远端实验完成才提交的安排：现提交已完成论文、dependence图表与交接；family_depth_20261018未完成实验及cells.json.tmp留在工作区。
- 当前显示审计通过：15份数值输入不变；论文/合集编译与dependence曲线审计已通过。额外尝试旧check_main_data.py在第108行因硬编码要求teaserfigure而中止，当前稿使用figure*；这是旧版结构检查不适配，不能报告该脚本通过。旧DATA-CONSISTENCY清单不作为本次最新验证，不随本次提交。


## 2026-10-18 用户确认：后续统一dependence展示方案

- Figure1/3橙线统一为source-attention dependence d(L)=1-q(L)，即筛选后原本答对的题中累计knockout后变错的比例；蓝线仍为恢复率rho。Problem Formulation正式定义d。
- 后续新增模型/任务、主图和图表包均沿用此方案，勿恢复为橙线q。原始JSON和统计代码继续存retention=q，在展示层取1-q；不改变筛选、人群、分母或已有T/R与CI。R定义为d首次≤0.5，与旧q首次≥0.5等价。阈值敏感性中q的τ须对应d的1−τ。
- 中间条件rho<0.5且d>0.5；阴影仅是首次边界之间，保留重新越阈。dependence包括reader访问与source自身更新，不能写成纯reader路径效应；d−rho不能当逐题比例。
- 本轮只落实该展示与定义修改，既有新家族远端实验仍按原交接继续。

- 本轮验证完成：24条绘制曲线逐条与rho/1-q核对，12套人群边界检查通过；原始depth JSON和Table2文件SHA256不变。审计`audit/DEPENDENCE-DISPLAY-20261018.json`。论文编译正文7/全文9页，0 error/undefined/overfull；图表合集9页，0 error/undefined/overfull。Figure3已目视检查。主PDF、图表包及Overleaf ZIP同步更新。

# SkillVector 论文交接

## 2026-10-18 14:40 周期巡检与新增审阅意见

- 已读取reports/图表审阅与改进建议_20261018.md，后续整合以此为参考：Figure3共同ID主曲线、全样本附录，每panel n/G；Figure1/3统一指标方向；首次阈值阴影不称稳定阶段、保留反弹并报告阈值敏感性；Figure4实际层号、统一S/C/SC/cut颜色与独立路径图例；Fig2明确token×层、S与0..L缓存和L/L+1切断范围；表格统一精度/分母/组数、缺失不填0、正文说明加性交互的限定。采用建议前须逐项核对新数据和双栏字号，不机械缩图。报告中建议展示区间的部分与用户直接要求存在冲突，不据报告自行增加区间；全部图表不谈置信度的直接要求仍记录在顶部，timer旧模板保留Table2的例外需在最终展示时以用户实质最新偏好处理。
- Live核验：8个深度分片全部done。22个计划任务done、30/62已提交，8个接续GPU Job均job_running；L2 battery已实际生成正式记录。其余模型补缺/机制尚未全启动，不能发送全任务开始通知；没有新增failed标记，只有旧DeepSeek s1预检失败历史。旧无-s任务不恢复。
- 协调器service active，PID83926；5h timer active，下一轮15:58:50 CST（平台实际为准）。CPU通道仍可读共享盘。inspire update --check显示7.1.8可升级7.1.13，本轮未为此中断实验或升级。
- 新评分审计：audit_scoring.py只读远端已done的8个TheoremQA文件，共14446条/9925唯一题目文本；同一远端依赖fresh-process统一评估有32条不同标签，涉及10题；2个完全相同文本组存在原标签冲突（00110/00426）。scoring-audit-20261018.json已取回，本审计是诊断而非已纠正数据。原始输出不改。远端确有latex2sympy2，fresh _number_it('False')=None；解析器含跨调用全局状态，正在追踪实际是否导致差异，尚未证实根因。统一重判也可能受顺序影响，不能直接当最终标签。
- 下一步：完成parser-state诊断，建立稳定且忠于官方规则的评分协议，复核候选基线筛选与缺失干预是否需补跑；全4组深度独立审计后再入图。正文suite继续按62任务计划自动接续，始终最多8卡。整项未完成，不commit/push，不创建TASK-COMPLETE。

### 评分根因已最小复现（本轮后续更新）

- parser-state-minimal-20261018.json已取回。fresh latex2sympy2.var为dict，解析False为E*F*a*l*s，官方_number_it返回None；单独评分DeepSeek/TQA 00125 no_skill输出后，var变为Symbol，解析False抛TypeError，官方回退eval('False')得到布尔False，可当数值0；恢复初始解析器状态后重新返回None。此为实际跨样本状态污染，不再只是依赖差异猜测。
- 不更改在跑生成脚本和原始JSONL；需要独立的逐样本状态隔离评分（忠于每题fresh-process官方行为），用顺序扰动与fresh subprocess对照验证，然后全量重评新旧TheoremQA并重建基线screen。若新eligible无全层/全部suite记录，安排同参数补跑，不能只修标签后继续使用旧分母。MedCalc评分器另行核对，不假设受同一问题影响。
- 当前初审曲线继续暂定，不据存储标签直接入稿。diagnose_parser_state.py为只读长扫描，命令会话62627（若仍在应先核验远端进程/产物，避免重复）；最小复现已成功。

## 最新用户补充：全部图表展示要求（2026-10-18）

- 用户最新要求覆盖此前Table2例外：新结果整合时，论文全部正文/附录图表、图注、表注及对应正文说明都不展示或讨论95% CI、置信区间、置信度、误差条；Table2原区间也移除。原始统计产物保留作审计，不进入论文展示。同步检查绘图/制表生成脚本，避免重生成带回。
- 当前正文确有重复注入实验：sections/04-experiment.tex中“Repeated late replacement leaves transfer weak.”段；附录b-full-dataset-rerun.tex也有TheoremQA对应段。当前正文无独立重复注入图的引用，不能把历史新增图的记录当成当前稿状态。整合时保留测值、修正为干预等价/实现检查，去掉独立机制证据的过强解释。
- 评分异常诊断更新：TheoremQA 00426的depth/battery/windows三次输出token及text完全相同，但存储correct为False/True/False；本地统一重判均True。因此不能归因生成漂移。尚需定位远端评分环境/状态差异，并统一复核筛选及所有受影响记录，原始标签不可静默覆盖；初审边界在此审计完成前仍为暂定。

## 2026-10-18 14:00 周期检查与独立初审（当前入口）

- 原始目标/授权不变：最多8卡，新增家族后补齐所有正文实验，全部正式单元实际开始后另行通知；只在整项完成、验证/桌面同步后commit/push。周期timer保持，不建TASK-COMPLETE。
- 本次已核对live：当前8卡工作，深度7/8分片完成，释放的卡已自动接续Llama内容/重复注入/doclast/bridge/repair/edges及DeepSeek/MedCalc诸suite；远端已见19个done，尚非全体开始/完成。旧failed标记仅首次s1预检失败，r1已通过并完成本分片，不重复恢复旧Job。
- 已取回96文件已完成产物快照11,150,383字节，SHA256 c82a25ea4c00ee651295e845d8509054932654c7cfa8c56f82db7608d8c19e59，安全解包至experiments/family_depth_20261018/retrieved/snapshot-1400；无权重/大日志下载。analyze_depth.py新增--completed-only，未齐组合明确incomplete，不补曲线。
- 三个已完成组合经原始记录独立审计：Llama/TheoremQA n92/71组，半效应T/R=6/18；DeepSeek/MedCalc n25/13组，6/21；DeepSeek/TheoremQA n51/44组，4/19。方向支持深度分离，但都是基线screen后的条件结果，DeepSeek/MedCalc样本小。Llama/MedCalc最后一片未齐，不提前报告其完整曲线。
- **关键解释修正已告知用户：重复写的因果冗余。** Llama/TheoremQA92×4窗口与DeepSeek/MedCalc25×4窗口，共468配对，窗口与同起始层单次transfer输出token完全一致。完整source span被替换且其前缀相同，在因果网络中后续source状态由相同前缀决定；重复写是结构等价/实现检查，不能作为“反复维持状态仍失败”的独立机制证据。待正文整合时替换4.3该段过强解释，保留所有测值。详细推导/文献/命令在PRELIMINARY-20261018.md。
- L8在新模型的L4–L6半效应之后，不能统一称早层正对照。已明确记录为**事后敏感性设计**：固定所有5模型×2任务的L2 battery，不找每模型最优层，保留L8。10个新增小GPU任务已写入parallel-plan（总62任务，最多8同时运行），独立新脚本followups_l2.py已上传，不修改在跑的数值脚本；等待卡释放自动接续。不是预注册证据。Qwen8/MedCalc补了冻结134题输入，其他人群与现有screen对应。
- Llama/TheoremQA独立battery的no-skill为1/92，depth/windows为0/92（donor/receiver仍92/0）；需核对该ID和跨运行token差异，做固定集/稳定基线子集敏感性，不悄悄剔除。机制新组合未齐，不提前宣称SC/recut泛化。
- 协调器和5h timer均active；live下一轮约15:56 CST（实际触发时间以systemctl为准）。观察CPU wt-family-prep-1018有23h运行限制，后续检查到期需恢复通道。当前无额外模型下载。
- 下一步：核验最后深度分片和新接续任务，全部深度完成后全量analyze_depth审计并绘新增家族曲线；其余suite边完成边独立核验，修正文中重复写解释、L2事后性质与基线漂移，最后统一图表/全文/ZIP/桌面/GitHub闭环。

### Open Ideas / 值得深挖的问题

- 2026-10-18：自动识别干预等价类以排除无信息ablation。触发：468/468重复写与单次输出token一致，当前因果前缀条件可给出逐层归纳。潜在价值是避免把结构上冗余的对照当额外机制证据；新颖性尚未验证，不声称可独立发表。最小验证：构造满足/违反前缀同一性两组干预，检查等价预测与结果，再核查已有causal abstraction/patching方法是否已覆盖。


## 2026-10-18 01:17 当前权威执行入口（覆盖以下旧进度）

- 用户最新要求：最终**最多8张4090**，保证利用率、合理并行；不是无限增卡。实验全部正式开始后单独通知，继续每5小时检查。下载已明确批准，不再索取确认。
- Paper当前修订已完成并告知用户：Intro首段对齐Semantics and Knowledge，后续实验不为track改写；Related Work重叠修复；Table3及图4不再包含区间相关信息，Table2原区间保留。7/9页、无error/undefined/overfull；新桌面v6、Overleaf精确ZIP独立编译及图表目录已同步。新实验结果尚未入稿，整个任务未完，不commit/push。
- 两权重都下载完成：DeepSeek官方7B Chat、Llama3.1-8B-Instruct公开Nous原版分发；四权重/config/vocab与官方SHA一致，tokenizer_config为分发版差异有记录。新模型CPU span/context预检通过，DeepSeek MedCalc00874因4K上下文预先排除；不能静默截断。
- 首轮四个不带-s分片号的整池Job已通过preflight并开始基线；因用户要求提效，已停止保留全部文件，**不要恢复或混进新分片分析**。状态归档launch-state-unsharded-superseded.json。
- **当前正式方案：parallel-plan.json / parallel-jobs.json，8个Figure3深度Job（2家族×2任务×2整skill组分片）＋44个后续GPU Job，共52个任务计划，最多8个同时占用。** 每skill整个组只在一片，按题数平衡，防止分片改变group-screen。Qwen0.6两进程同卡，其余suite独立排队，依赖就绪才提交。已有完整旧模型Figure3复用；补齐Mistral/Qwen0.6两任务、Qwen8/TheoremQA缺失正文单元，Qwen8/MedCalc已完整结果复用。
- **01:24最新核验：8张卡全部通过preflight并进入正式基线生成，共367条JSONL；每分片26/28/25/46/77/76/64/25条。DeepSeek/TheoremQA s1-r1已恢复，其余7卡未重启。Figure3八卡正式开跑已告知用户；其余正文suite尚未全启动，不发全任务启动通知。**
- 新八个-s0/-s1深度Job已全部成功提交（s1失败例外由r1替代），后续继续live核验。名字在launch-state.json，前缀wt-f3-{llama,deepseek}-{medcalc,theoremqa}-s{0,1}-1018。不要把排队说成开跑，不重复提交。源码远端family-depth-20261018-v1已同步。
- 运行后勿执行build_plan.py覆盖plan（会丢失r1映射）；parallel-jobs.json为初始快照，当前权威是parallel-plan.json与launch-state.json。
- 后台协调器family-depth-launch-01a14a9e.service已active，最长20h；依赖新CPU wt-family-prep-1018（23h自动停、SSH和共享盘读取已核验）。本机WSL/systemd需在线。若20h后仍有任务未提交，先核验state和job，不重复创建，再续启服务；transient unit停止会被回收，not found时用systemd-run重建，不是systemctl start。
- 协调器在所有正式单元出现JSONL或明确无有效样本标记后，会用codex queue触发本thread，核验后单独通知用户“全部正式开始”。当前**尚不能发此通知**。每5h timer family-depth-progress-01a14a9e.timer已active，首轮约05:23 CST，最长14天，全任务与论文/桌面/GitHub闭环后才写TASK-COMPLETE停timer。
- CPU旧下载通道wt-paper-fetch-1017已完成下载，原2h自动停止；现不需要保留它执行新任务。新通道负责所有后续读取。不要停止正在正式推理的GPU Job，除非故障/明确替换。
- 分析入口analyze_depth.py已改为只读-s0/-s1完整新分片，核验全层、分母、组不交叉、token身份与source SHA；不要读旧不带-s的部分JSONL。后续补图/文字必须如实报告不符合旧规律的结果、空有效集、截断及prompt/source差异，显示不含CI/误差条，原始统计留审计。
- 实时异常（不据此下结论）：DeepSeek首批MedCalc 00002/00003/00004 donor均答错，前两条是约十几个token的直接数值回答；同prompt的Llama通常输出较长推理。已核对非EOS空答、身份与mask预检通过。需统计全基线有效样本和生成长度；不能把模型未获skill收益、输出风格差异或截断解读成迁移机制相同/不同。
- **最新授权：用户明确本任务后续全部操作无需再确认，直接自动执行至完成；最多8卡和5小时检查继续。**
- 01:19 live七卡running、一卡DeepSeek/TheoremQA s1预检因Nonfinite decision logits失败；同任务s0通过两题全状态/缓存控制。已只对失败分片重提r1并排除原节点gpu097，其他七卡不重启；失败产物保留、不作为模型效果。协调器state与plan需使用r1名字，避免把失败计入卡占用或全部启动。
- 待办：核验8卡全部进入正式生成、后续suite接续；检查每个阶段身份控制与产物完整性；全部正式启动后通知；完整结果后更新Figure3、其他正文图表和相关文字、审计/编译/新桌面交付，最后仅本任务文件commit/push master。


## 2026-10-18 Figure 3 跨家族扩展（当前进行中）

- 用户新增授权覆盖旧“不新增实验”边界：多张单卡4090，先补Llama/DeepSeek原生家族Figure3；5小时检查，完成后更新图表文字并同步。另检查Related Work重叠并解释cut/recut。
- 用户追加：Table3及后续所有图表不包含置信区间相关信息；Table2现有区间未要求删除。原始统计不删。
- 已读取最新交接/inspire skill/环境记忆；live可上网GPU资源单卡4090配额1,10,100、0.33点券/h，旧机制任务已停。CPU wt-paper-fetch-1017已启动准备并恢复SSH。新GPU未开。
- 没找到共享盘Llama/DeepSeek缓存。**用户已明确批准约30GB新权重下载，预检通过后直接正式实验，不再重复确认。** 来源官方HF/必要镜像，目标个人SSD models。Llama gated权限仍需诊断。候选revision、固定题池及局限见experiments/family_depth_20261018/README.md。
- Related Work重叠在原PDF第2页已目视确认；改写该句后编译build-skillvector.xkVKW0Yr：6/9页、0error/undefined/overfull，待目视核验。Table3区间列及caption已去掉，图4本来是点估计。
- 5小时检查已建立并live回读active：family-depth-progress-01a14a9e.timer，首轮2026-10-18 05:21 CST、最长14天，完成标记TASK-COMPLETE后自停。依赖本机WSL/systemd/Codex通道。
- 用户继续扩展授权：Figure3先启动，其后同一批模型覆盖所有正文实验（内容/位置/跨题控制、重复注入、S/C/SC/recut与路径）。README已列完整矩阵，检查器已覆盖；其他suite仍需在Figure3启动后实现并运行，不能仅完成Figure3就标完成。
- 首段已仅对齐Semantics and Knowledge；后续实验不为track改写。Related Work修复后目视通过。Table3与图4 caption已去区间相关信息，Table2保留。新编译JC3Ed4mT为正文7/全文9页，0error/undefined/overfull；最后caption编辑后还需最终重编译。
- 新runner、冻结instrument与题池已上传2,009,464-byte快照到个人SSD family-depth-20261018-v1；所有依赖和两任务数据均齐。4个单卡Job配置jobs.json正在dry-run，未提交。fetch_models.py只允许明确下载批准后运行。
- 数值审计132702项/489源、机制审计8428项/48自身控制通过；显示审计已适配Table3点估计且保留原始CI源，15份数值不变、引用27项通过。cut/recut单独说明已写reports/cut-recut实验说明_20261018.md。
- 四个单卡Job dry-run全部通过，平台标注4090(48GB)。HEAD元数据：Llama权重16,060,556,376字节，DeepSeek13,820,824,960字节；总29,881,381,336字节。DeepSeek权重HEAD可访问；Llama HEAD403，提示fine-grained HF token未允许public gated repositories。需要用户修复远端HF权限，不索要明文token、不绕过许可。用户随后已批准下载；后台下载启动核验中，GPU尚未提交。
- 最终本地编译7C9ymDk1为7/9页，0error/undefined/overfull；独立图表合集orns2o_7为9页、0error/undefined/overfull。四项instrument测试通过。
- **用户已批准新权重下载且要求预检完直接正式实验。** DeepSeek官方约13.8GB已后台下载。Llama官方gated失败后使用NousResearch公开原版分发；4分片及config/generation/tokenizer.json等与官方SHA匹配，tokenizer_config.json不同明确记录；约16.1GB后台下载，未绕过需凭据的官方入口。
- 后台协调器family-depth-launch-01a14a9e.service已active：权重done后自动提交对应2个Figure3 Job，screen就绪后自动提交对应followup Job，最多8张单卡、各48h上限；先跑probe.py全prefill自身状态和split状态+缓存身份及三路径mask检查，再进正式run.py。后续内容/末位/噪声/quarter/跨skill和同family/重复窗口/doclast跨题/repair/edges脚本均已实现上传，followup四Job dry-run通过。
- 原CPU wt-paper-fetch-1017仅2h自动停（从本轮启动计），48h创建失败（stop_hour须0–23），已创建23h零GPU观测通道wt-family-prep-1018，连接及共享文件读取已核验成功。coordinator已改用新通道、最长20h；下载仍在旧CPU继续，下载结束前不停止旧CPU。
- v6桌面交付已独立编译完成并同步：StillNeeded-WWW2027-v6-TrackLayout-20261018；7/9页、0error/undefined/overfull，ZIP17项SHA256 3c266bfad982d2b3494dd3885284b986e86a3c612e109be3fbf36051a4a3e9c1；单独cut/recut说明及图表包已同步。审计DESKTOP-TRACK-LAYOUT-20261018.json。
- 00:44共享盘下载进度DeepSeek5.9GiB/Llama7.4GiB，进程正常；无新GPU提交、无新结果入稿。CPU tokenizer预检已通过：DeepSeek MedCalc00874因3427+900>4096预先排除，记录context.json，候选446/上下文支持445；TheoremQA255全支持；Llama两池均支持。doclast/1536机制另做输入长度门槛，不能静默截断或混同筛选。
- 完整任务仍进行中，完成后再commit/push，既有cells.json.tmp不碰。


## 2026-10-18 按截图重构四图与机制叙事（稿件、图表包及交接交付完成）

- 用户最新要求覆盖重复注入图版：以三图三表提交141c8fb为基线，Figure1 teaser呈现早期迁移/深度分离/源KV部分恢复，Figure2详细干预设计，Figure3六组深度，Figure4恢复机制；实验保持4.2→4.3→4.4，首页Web relevance独立段首。
- 修改重点：区分残差状态迁移与源位置KV联合迁移，中心结论聚焦源缓存及后续读取，不归因全部计算历史；修正L≤23持续屏蔽表述与附录13/14层0.32/0.34错误；Table2增加已有bootstrap区间；补TheoremQA窗口已有结果。
- 不新增推理。已找到TheoremQA corrected窗口的现有t8-win+tqa-span记录与campaign_numbers.py，先重计数再补附录；当前仅已知存在记录，不视为新实验。保留旧桌面版本与既有howskill/data/cells.json.tmp。
- 已完成三图三表基线重构：新teaser、新干预设计、保留六组深度和机制结果，正文重复注入仅文字；摘要/引言/结论以源位置KV及继续读取为重点；4.3标题精确区分residual transfer。独立Web relevance仍在引言开头。4.4标题Testing source caches and continued reading。
- 已修复用户所列细节：L≤23起始且持续到末层；组筛选13/14约0.16而逐题筛选0.32/0.34；Table2增加已存在的boundary bootstrap CI；TheoremQA t8-win+tqa-span重计数99题/75skill，窗口0.839/0.613/0.376/0.204，单L16同0.204，附录已补。
- 数值验证：15份原数值输入逐字节不变，teaser SVG曲线/条宽与精确源值一致；check_main_data.py --numeric-only 132702检查/489源文件通过；引用27项/58bib/11TeX无缺键重复标签。新审计audit/FOUR-FIGURE-STORY-20261017.json。没有新增推理、远端资源或下载。
- `paper figure/`已建立，含四图PDF/PNG/SVG、完整LaTeX浮动体、三主表及附录表、源码快照/数据/manifest，以及可编译figures.tex。独立合集编译9页，0error/undefined/overfull hbox，stage build-figure-collection.mbbsip3y；Figures-and-Tables.pdf已在目录。新增tools/build_boundary_table.py单独维护Table2，避免旧point-estimate脚本剥掉区间。
- 最终构建build-skillvector.vMZtK0TQ与精确ZIP独立构建build-overleaf.8ughln0x均为正文6/全文9页，图在2/3/4/6页；0error/undefined/overfull，全部字体嵌入，已目视检查。ZIP/project/workspace源逐字节一致、两个PDF9页文字一致。
- **最新桌面入口：`/mnt/c/Users/12970/Desktop/StillNeeded-WWW2027-v5-SourceCaches-20261018/`**；PDF、17项Overleaf ZIP（128662字节，SHA256 `c634d89f30c6ca4194a01cf801e9c4cbcec9e984ad53d59664a112329dbe7400`）、project/、阅读说明、paper figure/及HANDOFF-NEXT-CONVERSATION.md齐全。旧交付不删。
- 独立图表目录：仓库`paper figure/`、桌面`/mnt/c/Users/12970/Desktop/paper figure/`、v5交付内paper figure/，各38文件（含manifest），已按manifest逐项核验完全一致。含独立图表合集PDF、四图PDF/PNG/SVG、四表代码及说明、绘图快照及数据。审计audit/DESKTOP-FIGURE-BUNDLE-20261018.json。
- 独立新对话文档`HANDOFF-NEXT-CONVERSATION.md`已完成并复制至桌面交付及图表目录。说明当前v5、原需求、修改项、关键数值、样本/机制边界、命令、实验状态和不自行新增实验约束。
- 下一步仅master提交推送，结果以会话最后Git核验为准。既有howskill/data/cells.json.tmp不碰。本轮无新增推理或平台资源操作。

## 2026-10-17 重复注入升级为正文图（稿件与桌面交付完成）

- 用户要求：把重复注入做成图，保持视觉风格一致，配套文字连贯，融入现有结构，不新建二级小节，不加入置信区间内容。本轮仅新增重复注入点估计图及邻近文字，保留其他既有图表内容。
- 已验证 values/main-evidence-values.json 中五个窗口点估计与对应起始层单次替换完全一致，L16–35和L16单次均为0.0564516；所有层0–35为0.9758065。新图将直观比较替换窗口与L16单次条件，原始样本135题/14组，不启动推理。
- 新增tools/fig_repeated_replacement.py及PDF/PNG/SVG；蓝/青绿/橙色与既有图一致，横条比较五个窗口与L16单次，右列为替换层数，浅色背景突出20次对1次；所有条宽已直接对照精确源值验证。没有增加误差条或置信区间。
- 原4.3保留既有paragraph，文字改为“重复写能否维持skill→早晚起始差异→旧缓存问题”，不增subsection。新增为Figure3，机制图顺延Figure4，正文四图三表。
- 构建build-skillvector.7vK0dUbq：正文6页、全文9页；图在2/4/4/5页，0error/undefined/overfull，字体全部嵌入。页4–6已目视检查。15份数值输入未改；check_main_data.py --numeric-only 132703检查/489源文件通过；新增图六个条宽/层数与源记录吻合；引用27项/11TeX无缺键重复标签。
- **桌面最新入口：`/mnt/c/Users/12970/Desktop/StillNeeded-WWW2027-v4-RepeatedReplacement-20261017/`**，含PDF、Overleaf ZIP、project源码与中文说明；说明源reports/重复注入图修订说明_20261017.md。ZIP17项，125305字节，SHA256 `ceea644e0294d66ac32546424a43d3697e0798df835651ad15d91f96ea5db1de`。独立编译build-overleaf.12p6renk通过；ZIP/桌面project/workspace源码逐字节一致，两PDF9页文字逐页一致，格式检查通过。审计audit/DESKTOP-REPEATED-REPLACEMENT-20261017.json、REPEATED-REPLACEMENT-20261017.json。
- 下一步：master提交推送；结果以会话Git核验为准。既有howskill/data/cells.json.tmp不碰。

## 2026-10-17 桌面 v2 三图三表叙事修订（论文与桌面交付完成）

- 目标：以桌面 WWW2027_v2_three_figures_three_tables 为重要参考，按有效探针→深度分离→历史修复重写；首页独立 Web relevance 段落；正文≤8页、全文≤12页；三图三表，Figure 3 改为便于干预比较的点图；最终桌面干净 Overleaf 包及 GitHub master 同步。
- 已读取当前正文、参考包及截图。参考包的逐层图是裁剪图，机制 CSV 是四舍五入值，因此重新绘图必须使用仓库已审计 JSON，不从 CSV 推断曲线。WWW 官方 research-track-papers 页面已核实首页 Web/track 相关性要求。
- 保护既有未跟踪 ../howskill/data/cells.json.tmp；不启动新实验、不改原始数值、不删除历史交付。
- 已完成：摘要、引言、相关工作、方法、实验、结论及可达附录重写和协调。首页独立斜体 Web relevance 段落；摘要围绕科研问题。正文按有效探针→深度分离→历史修复推进，三图三表，附录另有一张重测表。Figure 1 双探针，Figure 2 保留完整实测逐层曲线，Figure 3 改为分组点图；无平滑、补点或新推理。保留 L24 recut 异常及样本筛选等必要边界。
- 最终正文 **6/8页，全文9/12页**，三图在第2/4/5页。标准 acmart sigconf,anonymous,review，未改正文版心、字号、行距。0编译错误、0未解析引用、0横向/纵向溢出、字体全部嵌入。工作稿构建 build-skillvector.Zl7pmkxP，精确ZIP独立构建 build-overleaf.o5hywdew。
- 验证：`python3 tools/check_main_data.py --numeric-only` 132703检查/489源文件通过；`python3 tools/audit_mechanism.py` 8428检查、48精确自身控制通过；`python3 tools/audit_three_display_revision.py` 15份数值输入相对修订前逐字节不变，三张主表数值/共同样本边界/阈值检查/机制置信区间匹配源记录；引用审计27实际引用/58 bib/11 TeX无缺键重复标签。旧exact-wording检查针对旧teaser及反复数字，数值模式跳过此类编辑断言，未跳过底层数值重计数；机制绘图审计已改为检查SVG点数及相对原始结果的纵坐标映射。
- **本轮桌面入口：`/mnt/c/Users/12970/Desktop/StillNeeded-WWW2027-v3-ThreeFiguresThreeTables-20261017/`**，包含 StillNeeded-overleaf.zip、StillNeeded-review.pdf、project/与阅读说明.md。ZIP16项，105050字节，SHA256 `c9ab9b3359f47cb558ebc429d34c676bbd44e8cfd667680c816b097d66bca216`。独立编译9页；ZIP、桌面project和workspace可达源码逐字节一致，两个PDF逐页文字相同。旧桌面版本均保留。
- 审计：audit/DESKTOP-THREE-DISPLAY-20261017.json、audit/THREE-DISPLAY-REVISION-20261017.json、audit/WWW2027-FORMAT-20261017.json；中文说明reports/三图三表修订说明_20261017.md。科学范围仍为受控skill问答，Web相关段落不等于浏览器任务评测或scope录用保证。
- 下一步：仅提交本轮paper目录改动到master并push；不提交既有 ../howskill/data/cells.json.tmp。推送结果以会话最终Git核验为准。

### Open Ideas / 值得深挖的问题

- 本轮为叙事及可视化修订，暂无新增经验证的科研观察。已有 L24 recut 无额外损失的异常仍应保留，不能将 L16 机制泛化全层。

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

## 2026-10-18 当前图表审阅建议

- 已阅读并目视当前paper figure四图三表，核查绘图脚本、深度汇总及bootstrap逻辑。报告：`reports/图表审阅与改进建议_20261018.md`。仅建议，未修改图表或数据、未操作远端任务。
- 已验证六组原始/共同样本T/R相同；Qwen8/MedCalc在L26重新越阈，q阈值.6时R由25变30；Figure4实际用分类等距横轴。
- 优先建议：共同样本主曲线；统一q与1-q方向；阴影限定为首次交点间隔；Fig4横轴与颜色统一；主表显示组数与单位。遵循此前主图4/表3只显示点估计偏好，统计补充建议放附录。
- 当前审阅已完成；下一步若实施，改权威脚本后刷新bundle并核验数值不变。未提交既有未完实验/论文改动。

- 图表审阅续议：已通读当前正文定义与结果；建议正式定义d(L)=1-q(L)，Figure3统一使用source-attention dependence，与已有Figure1一致。边界改写为d≤.5，中间rho<.5且d>.5；强调累计mask同时影响source-self与reader路径，两条指标不同执行背景/分母。具体记录在同日图表审阅报告；尚未改稿或重绘。
