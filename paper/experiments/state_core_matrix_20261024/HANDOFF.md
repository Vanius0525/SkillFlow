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
