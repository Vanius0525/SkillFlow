# 当前唯一论文版本

目标：消除根目录旧稿和Overleaf最新稿混用。用户已指定以Overleaf最新稿及其修订为唯一依据。

已完成：2026-10-26T07:24:21.211Z完整olcli diff返回0；将线上最新稿加有限书目修订的完整source和已验证PDF收敛到本目录。source相对线上仅skillvector.bib不同，SHA256见provenance.json。正文8页、总12页、33引用；此前完整编译验证位于reports/bib-final-20261026。未修改或上传线上内容，无运行中任务。

下一步：所有论文修订从source/main.tex开始，先重新核对最新Overleaf差异；维护paper.pdf，不再使用根目录历史稿或其build.sh。桌面文件为WWW2027-current.pdf。

## Open Ideas / 值得深挖的问题

本轮只收敛版本，不新增科研结论或实验。

## 2026-10-26 完整再审计

本轮重新核对线上（07:34:59 UTC）、重新编译current/source，验证与paper.pdf的12页文字/像素一致。正文8页/全文12页，33引用，0错误/undefined/Overfull，全字体嵌入。论文未改。待修：Figure1文字最小3.22pt、两条正式EMNLP/Findings出处、113/124附录对应及书目缺字段。完整报告：../reports/current-review-20261026/完整检查报告.md；33篇逐项一手链接、机器结果及编译证据同目录。后续只从current/source修订，未上传Overleaf。

## 2026-10-26 两条正式出处修订完成（最新）

用户明确忽略上轮1/3/5，只修2，问4是否需要修。Hajimiri与WebXSkill已改用正式EMNLP2026/Findings2026出处并补页码/出版社/地址/链接。正文不变，重新编译8/12页、33引用、0错误/undefined/Overfull，前8页像素一致；警告74→70。正式出版条目缺字段建议补齐，预印本不虚构卷期页码；未扩大修订。current/paper.pdf、provenance及桌面唯一副本已更新，未上传Overleaf。记录../reports/formal-bib-fix-20261026/修订结果.md。上轮1/3/5不再作为待执行事项。

## 2026-10-26 第4项可修复书目字段已完成（最新）

14条补齐可核验出版社/地点/卷号/页码，另整理重复arXiv/DOI/URL/会议缩写；不改正文/图表或用户忽略事项。中间13页尝试未交付，最终仍正文8页/全文12页、33引用、0错误/undefined/Overfull，前8页像素一致；警告70→41，未知或本不存在字段留空。current/paper.pdf、provenance及桌面WWW2027-current.pdf均已更新，未上传Overleaf，无运行中任务。来源和验证：../reports/bib-metadata-20261026/修订结果.md。

## 2026-10-26 当前稿与线上再核对（08:07 UTC）

本轮只读审阅，完整olcli diff返回0（remote fetched 08:07:27.649Z）。当前源码仅bib与线上不同；当前PDF第1–8及11–12页文字与线上快照一致，变化为9–10页书目；跨云端/本地构建并非前8页像素全部一致，不扩大此前同环境像素验证结论。正文8页/总12页，官方CFP重新读取，模板和页数符合可核验条件；系统投稿状态未检查。具体书目修改及格式判断见../reports/current-vs-overleaf-20261026/核查结果.md。未修改论文、未上传Overleaf，无运行中任务；用户此前忽略事项仅记录不执行。

## 2026-10-26 用户授权同步Overleaf完成

完整同步前diff：09:11:46 UTC返回0，线上没有新增改动。仅skillvector.bib通过原生editor socket提交276个文本操作，docID保持，v0→v1，逐字回读通过。同步后09:13:08 UTC完整diff返回0；云端编译下载12页PDF，12页提取文字全部与current/paper.pdf一致。证据../audit/bib-overleaf-sync-20261026/。current/provenance.json及CURRENT-PAPER.md已更新，论文正文/PDF未改，无未同步源码差异。

云端compile.log检查：编译错误0、undefined0、Overfull0。全部验证完成，无待执行任务。
