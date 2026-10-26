# 2026-10-26 当前论文最终检查

原始目标：从Overleaf下载最新paper，检查引用、参考文献、格式、篇幅并对齐WWW 2027 long paper。用户明确：不上传修改，由用户手动修复；后续明确停止搜索新资料，只检查当前稿。

已完成：先执行完整olcli diff，首次因缺少项目关联失败、沙箱网络失败；明确指定项目并获平台网络权限后成功。注意将整个paper直接作为diff目录导致initial-full.diff包含大量无关本地文件，346MiB，不纳入Git，不据此判断合作者作者身份；相关稿件差异另存manuscript-local-to-remote.diff。无文件删除。

下载21个远端文件至remote-source/，不覆盖根目录本地旧稿或已有未提交工作。线上根为overleaf-skillvector/main.tex。执行olcli pdf与olcli output log下载最新12页PDF和编译日志；无上传或远端源码写入。独立快照即本轮同步交付，根目录旧稿未更新。

验证：python audit/final-check-20261026/check.py；可达15个TeX，64条bib/33条实际引用，缺失引用0、重复key0、未定义ref0、重复label0；字体全部嵌入，US Letter。正文止第8页、References第9页、全文12页。云端日志错误0/undefined0/Overfull0；4处Underfull、balance与showhyphens提示。已目视12页拼图，无明显遮挡或裁切。

结论及精确手动修复：手动修复清单.md。主要为Davidson NeurIPS2025、Tsuzuku NeurIPS2018的正式出处和标题专名大小写。首页版权块建议调整但不是CFP明确硬错误。未修改正式TeX/BibTeX。33篇一手落地页/摘要核对不等于逐篇全文审阅或所有预印本录用状态核查；OpenReview部分页面验证阻挡，不推断后续录用。

下一步：用户手动改Overleaf，重新从头编译并复查8/12页限制。没有运行中远端实验或待完成下载。

## Open Ideas / 值得深挖的问题

本轮仅做用户限定的引用和格式审阅，不新增科研立项。用户收窄前检索中遇到MedCalc-Bench数据质量审计arXiv:2603.02222，报告其发现20余项实现/标注问题；它与本项目所用SRA版本的重叠未核实，不能据此认定本项目数据有错，也不能忽略为已解决。用户要求不继续扩展资料，本轮停止跟进，不纳入格式修复项。后续只有明确研究授权再检查版本与受影响item交集。
