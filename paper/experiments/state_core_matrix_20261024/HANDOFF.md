## 2026-10-24 全部科学审计与论文同步完成

核心24条件七新cell10944/10944均SUCCEEDED并完成独立进程审计；46小JSON/60KB归档取回，本地逐题标签/截断/全部新paired bootstrap及完整键/身份/哈希声明核验通过。复用Qwen/MedCalc后八cell580模型—题目配对；SC_exact3480对输出token一致、完整prefix1160对复现donor。六cell两背景早减晚点估计正；Llama/TQA与DeepSeek/MC不稳定，Qwen/TQA neutral CI触0，不能写统一深度规律。原始回答与KV保留远端，无推理重跑。科学任务和只读收集均已结束，专用CPUstop，HPC两失败记录保留；TASK-COMPLETE/SUPERVISION-COMPLETE存在、三小时timer inactive，迟到通知仅去重，绝不恢复旧任务。
用户授权的新论文任务已完成Overleaf增量同步：§4.4 Table3扩成八cell×两背景，附录Table7基线/身份与Table8区间/截断，abstract/intro/discussion/conclusion最小新增衔接，coverage只更新BF16经验核验范围。共7现有文本文件，旧公式/证明、related work、旧图与旧表数据不变。docID保留、无整文件上传；History2444–2454共11条操作回放重建7份最终稿。摘要Unicode位置偏移已修复为UTF16并添加回归检查；ASCII编辑payload之外提前拒绝未验证编码。
最终完整olcli diff无差异，云端编译无未定义引用/水平越界，表格列宽与9/11pt/浅蓝表头/线型统一，已目检。正文仍8页、Table3第8页，总15页（旧13页，超仓库12页目标）；为尽量保留原文未删旧内容压页，未声称满足投稿页数。附录仍有1.474pt微小竖向排版告警，无表格裁切。PDF skillvector-www2027.pdf；科学结果/逐节文字修改清单reports/state_core_matrix_20261024；全差异/History/编译证据audit/state-matrix-paper-20261024。本地只同步7文字+PDF，旧版本/tmp/state-matrix-paper-20261024-active-before。Git交付提交以git log为准，仅纳入本轮文件，不含其他线程改动。下一步若用户要求再处理篇幅，不自动开新实验或恢复timer。

## 本轮科学实验与全部小产物核验已完成（2026-10-24）

10944/10944正式记录、七份独立进程审计、46个小JSON（完整cells/冻结source/model资产元数据、逐题正确/截断标签、gate/core done与manifest）全部核验。60257字节归档已逐chunk恢复并校验SHA256=6b37be2734e0413a1f0d79696ab087b43e00754e3fff98102210e3be6b5a440f；本地verify_matrix.py复算所有新准确率、截断计数、全部paired skill bootstrap区间，且核对完整arm键集合/题目ID/身份/SC_exact/fullcopy配对数/原始文件hash声明一致。原始回答与KV未取回，没有重跑推理。

七科学Job均SUCCEEDED，末Llama/TQA于13:33:33完成。CPU收集HPC两同名记录最终均CREATE_FAILED；专用CPUstart曾InternalError后迟到实际RUNNING，已再次stop成功。备用只读wt-sc24-small-artifacts-1024只导出小JSON、不加载模型，已SUCCEEDED并释放。没有删除任何实例/数据，没有操作其他对话实验。watch修复后14:14:35确认7/7完整，SUPERVISION-COMPLETE存在、三小时timer inactive；TASK-COMPLETE存在，迟到通知只去重。

用户随后明确要求将完整新结果更新论文及说明各部分文字修改（覆盖原“不自动改稿”的约束）。正在进行新论文任务，基线与完整diff在audit/state-matrix-paper-20261024；新数据reports/state_core_matrix_20261024/paper-data.json，stage=/tmp/state-matrix-paper-20261024-edited。不要重新启动任何本轮GPU或timer。科学结论：source全覆盖/SC_exact token一致/fullprefix donor一致八cell成立；深度差异六cell两背景点估计正向，Llama/TQA和DeepSeek/MC均有不稳定/反向，Qwen/TQA neutral CI触0，不能写统一早晚规律；内容/窗口仍仅Qwen/MC案例。

## 2026-10-24 术语追问与只读收集备用通道

用户问“完整skill缓存”是residual还是KV。已明确完整指skill位置所有层K/V，不是所有位置/层residual；S复制单层skill residual，C_all只全层skill KV，SC含residual+低层cache且本轮最终全层skillKV精确对齐，SC_exact再显式全覆盖验证。不等于完整执行状态，题目/模板等非source位置KV尚可能不同。

CPU HPC导出一次请求超时留下两个同名记录，pick1排队后stop冲突（提示已不处于可停止态），pick2先前CREATE_FAILED；正在核对终态，不删除。专用CPUstart再次InternalError，未成功启动。为完成必要小产物取回，已提交唯一只读wt-sc24-small-artifacts-1024（原镜像13.2、max15min，完全不加载模型、不推理、不重跑科学记录），现SUCCEEDED。待取SC24_ARTIFACT_HEADER/CHUNK日志，校验归档SHA后只提取小JSON，进行逐题标签/完整键集合与矩阵统计核对。科学七任务及该只读任务均已成功释放GPU。

## 2026-10-24 用户追问反例的界定

已向用户明确：反例只针对新增SC完整source条件的“所有模型/任务早层均优于晚层”推广，不直接反驳原S迁移 vs KO依赖曲线的T<R结论；新实验未重测原完整曲线。八cell有六cell在Wrong/Neutral均正向；Llama/TQA(-5.4,+6.5pp)与DeepSeek/MC(+8.3,-8.3pp)方向混合，四个对应组级CI均跨0，不能宣称统计上晚层更优。Qwen/TQA Neutral+12.7pp的CI下端恰为0，不能将六个方向正例全称稳健显著。这些区间探索性且未多重比较校正。共同证据是全source复制不足、其他位置状态影响；深度规律异质。纸面Qwen/MC局部结论仍兼容，未改稿。

CPU HPC export当前pick1(14:07:08)QUEUEING，pick2(14:06:06)CREATE_FAILED，后者终态不需stop；一次请求超时后CLI/平台留下两条记录，不再提交同名任务。准备恢复仅本轮专用CPU取小文件，若成功则停止排队收集任务，禁止重跑科学推理。七GPU均已成功释放。

## 2026-10-24 14:05 七生成任务全成功，日志限量读取已修复，待取小产物

本次收到03:32迟到通知，实际处理到14点。Live七任务均SUCCEEDED，末任务Llama/TQA13:33:33完成。七份独立audit小摘要均已从结束前10min的完整日志取回retrieved/*.audit.json，总10944正式记录，source_error_SC_items均空。未重跑任何推理。原watch.py以--tail20 --limit50读取会反复得到旧样本：12:52仍显示03:32旧计数。修复仅本地watch.py（不改远端冻结计算代码）：运行任务按最近30min完整窗口；终态按finished_at向前10min取完整无输出cap日志，已缓存audit直接复用，core进度从审计总数填实。CLI --all也可能只返回1000条，因此必须加结束时间窗口，不能凭SUCCEEDED和旧计数认定丢结果。

已发生的统计反例需保留：Llama/TQA Wrong SC8=45.7%、SC24=51.1%（早减晚-5.4pp、组级CI跨0），Neutral57.6%→51.1%（+6.5pp、CI跨0）；DeepSeek/MC中性25.0%→33.3%也反向、n24。不能声称跨模型统一深度规律；原Qwen/MedCalc局部结论未被推翻。仍未自动改稿。

下一步CPU-only HPC只读收集小artifact archive（不跑模型，名称wt-sc24-artifact-export-1024，先查artifact-export-submission.json和平台状态再处理提交歧义），取回cells/source-manifest、七binary-outcomes与done/manifest，整矩阵核对键/身份/截断/统计并记录异常。原七GPU已释放，原始回答与KV不取回。当前还没有TASK-COMPLETE，不能把已取audit小摘要等同于全部收尾完成。timer在最终产物审计后关闭；若监督到期明确报告。

## 2026-10-24 00:53 七任务全部进入正式core，7张4090

00:50:50 watch --no-notify实测七状态均RUNNING、七cell均出现core（即各自50条gate已通过），无observation_error或failure。正式快照q8/TQA150/1512、Mistral/MC87/1104、Mistral/TQA204/1560、Llama/MC67/2688、Llama/TQA54/2208、DeepSeek/MC213/576、DeepSeek/TQA127/1296；合计902/10944=8.24%。每任务1张4090 48GB，共7卡，不是仍在gate。

00:53附加日志：Llama/MC从00:45:07的core48到00:53:13的77，约214.6条/h，线性剩余12.2h；Llama/TQA从00:47:00的48到00:53:14的59，约105.6条/h，线性剩余20.3h。只有约6–8min的正式采样窗，不含gate/复用种子计数作为新吞吐。面向用户给粗略剩余18–30h（今天晚间到明早），独立审计与输出长度差异另考虑，03:16用更长窗修订。没有重提、重跑或改稿，周期监督保持。

## 2026-10-24 00:36 正式生成已开始（覆盖仅gate阶段的旧快照）

平台日志明确显示：Qwen/TheoremQA core 66/1512（00:36:17），Mistral/TheoremQA core94/1560（00:36:11）。两者已通过全部50条gate并复用前两题48条，不再只是加载或gate阶段。其他cell最近00:30均RUNNING，不能用尚未刷新的monitor-state断言还全在gate；后续三小时检查会更新。启动代码与冻结配置已提交326b6f2；push已确认成功。本轮尚未生成全完成、独立审计未完成，不输出科学结论。

## 2026-10-24 00:30 启动阶段完成：七GPU均RUNNING

七个唯一GPU Job全部提交成功且均RUNNING，generation尚未完成。各cell正在gate（50条=两题×24正式条件+两条身份控制）；通过后前两题48条复用进正式结果，不重复生成，随后自动继续其余题并运行独立进程audit。00:30进度为q8/TQA31、Mistral/MC15、Mistral/TQA38、Llama/MC10、Llama/TQA2、DeepSeek/MC18、DeepSeek/TQA1，均/50，无failed。全部输入预检与源码/数据SHA已通过，正式456题×24=10944条。模型/任务人群不等大；历史候选固定，仅DeepSeek/MC1题因上下文排除，不能表述为全benchmark或每组124题。

三小时timer已active，下一次约03:16 CST，按实际systemctl为准；监督脚本已对七任务实测成功，后续仅用平台日志，不依赖Notebook。独立audit的小型汇总将从AUDIT_SUMMARY提取到retrieved/；完整cells.json/源元数据及逐题二值标签后续仍需取回，原始回答留远端。7天监督到期必须明确报告，完成自动停；周期唤醒依赖本机WSL/systemd/Codex可用。

本轮专用两个同名CPU均STOPPED且保留不删；无CPU实例需要恢复，不把旧Notebook错误当GPU失败。无提交器正在运行，无in_flight；submit.py正常退出。不能重提七任务、旧Qwen/MedCalc、取消depth或其他实验。论文此前同步875119b，本轮不自动改稿。代码/设计/启动证据准备提交GitHub；接下来每3h真实观察，结束独立审计后汇总跨组合。

# 核心24条件跨模型扩展（2026-10-24）

## 目标与授权
用户明确授权直接在启智运行新增正文核心24条件，扩展剩余7个组合，运行后每3小时检查。Qwen3-8B/MedCalc已完成124题结果复用，不重跑；4模型×2benchmark其余组合为Qwen3-8B/TheoremQA、Mistral/Llama/DeepSeek各MedCalc与TheoremQA。只运行24条件，不扩原49或附录41条件，不恢复旧depth，不操作其他实验，不自动修改论文。

24条件：donor/wrong/neutral-A/no-skill四基线；两背景×SC及SC_exact×L8/16/24共12；两背景×C_all/B_only/full_copy/suffix_replay共8。使用原冻结Engine与同协议（BF16/eager/split/greedy），每模型先gate，正式人群预先冻结，不按新结果选题。原约120GPU小时是假定每组合124题的线性估算，实际规模与速度待核对。

## 当前阶段
已读取inspire skill与环境记忆，正在核对实时CPU/GPU资源、模型/数据路径和历史候选池。尚未提交任何新GPU任务。每3小时timer已启动（state-core-matrix-3h-01a162f7.timer），首次2026-10-24 03:14:59 CST，7天监督到期明确报告，完成自动停。旧本轮状态完整性任务已完结，禁止恢复。下一步读取各模型适配实现，准备独立目录/冻结清单，运行局部测试与各模型gate，提交无重复正式任务并启动每3小时监督。

## Open Ideas / 值得深挖的问题
沿用原观察：完整source相同仍强烈依赖reader缓存背景，待本轮验证跨模型/任务一致性；不提前假定结果。

## 00:15 准备进度与平台连接故障

候选7池合计457题（63/46/65/112/92/25/54），待输入长度预检。24条件源码已准备，3项本地测试通过，Frozen Engine AST与原轮一致；TheoremQA逐答案重置latex2sympy2状态。新CPU创建一次超时，平台留下两同名实例；pick1(1792771463000,cpu-nat-100)RUNNING保留，pick2(1792771429000)PENDING已stop，不删。源码尚未上传：ssh-config/connection refresh在Jupyter terminal打开阶段失败，正在修复本轮通道，不代表GPU实验失败。wt-dev-cpu仅尝试只读连接也未成功，未启动/停止其他实验或其CPU。GPU实时13.2有4空卡，12.8满载，拟同镜像13.2组1卡/组合。

## 00:20 切换为无Notebook依赖的GPU内部署

CPU Jupyter终端连接多次失败，用户追问后改为GPU Job命令携带约44KB压缩源码，直接在独立ROOT部署；数据从旧状态实验/既有family仓库只读复制并逐SHA核验，不下载模型，不修改旧结果。bootstrap持锁串行完成七组合输入预检并冻结cells.json，每cell自身先gate，再复用gate前2题的24条件进正式文件，不重复生成；独立CPU进程audit在GPUworker结束前执行。观察改为平台Job logs，AUDIT_SUMMARY携带小型完整审计，完全不依赖Notebook。七个唯一名字wt-sc24-{cell}-1024，每任务1张4090，最多7卡，固定使用已验证同镜像13.2组；正在首任务dry-run，实际submitted以launch-state为准。新CPU多余实例pick2已STOPPED，pick1待通道不再需要后stop；不删除。每3h timer照常。

## 00:24 首个GPU已RUNNING，部署与输入预检通过

wt-sc24-q8-theoremqa-1024已唯一提交且RUNNING；00:22:33 BOOTSTRAP_READY，00:22:44开始加载模型。七组合输入预检正式保留63/46/65/112/92/24/54题，共456题、10944正式条件；仅DeepSeek/MedCalc排除1题上下文超限。完整cells.json与source-manifest.json已在远端ROOT持锁冻结，摘要preflight-summary.json。旧Qwen/MedCalc不重跑。gate每cell首两题×(24+identity)=50条，其中48条复用入正式输出，新增身份控制总14条。其余六Job正在submit.py会话78310串行提交，launch-state含in_flight防重；不要同时启动第二个提交器。GPU部署不再依赖Notebook；两个专用CPU均已STOPPED。周期观察只读Joblogs，独立audit通过后取回小摘要，不自动更新论文。

## 00:28 七任务已全部提交，未重复命名

submit.py会话78310已正常退出，launch-state.status=all_seven_core24_jobs_submitted_not_completion，submitted七名称齐全，in_flight为空。七cell为q8-theoremqa、mistral-medcalc/theoremqa、llama-medcalc/theoremqa、deepseek-medcalc/theoremqa。00:25手动watch --no-notify成功读取当时三RUNNING及gate进度，未发现故障；当前正在复测全七任务监督与timer，状态以monitor-state最新为准。所有正式结果尚未完成，不预报科学结论。下一步每3小时观察；后续完成取回小audit、完整cells/frozen元数据与二值标签（原始回答仍远端），审计后汇总跨组合。
