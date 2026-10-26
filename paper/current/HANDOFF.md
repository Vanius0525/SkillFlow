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
