# 唯一活动论文基线

2026-10-26用户明确指定：之后只考虑Overleaf最新稿及其修订版本。本约定覆盖旧README、交接和构建入口中的版本描述。

- **唯一当前PDF：[`current/paper.pdf`](current/paper.pdf)**。
- **唯一活动源码：[`current/source/main.tex`](current/source/main.tex)**，同目录内含全部图、表、附录与书目。
- 桌面交付：`C:\Users\12970\Desktop\WWW2027-current.pdf`，与current/paper.pdf的SHA256一致。
- Overleaf项目：`6a2cfd49b99635e8e968576a`；云端根文档：`overleaf-skillvector/main.tex`。
- 最新完整diff检查：2026-10-26 07:43:09 UTC，线上与下载快照无差异。

当前版本基于该线上稿，仅修订skillvector.bib：两篇改用正式NeurIPS出版信息、Hajimiri/WebXSkill改用正式EMNLP2026/Findings2026出处，五条标题保护专名大小写；正文、图、表、版权块及ACM Reference Format未改。正文8页、全文12页，本地编译验证记录见reports/bib-final-20261026/。书目修订尚未上传Overleaf；不能声称当前PDF与线上逐字一致。

根目录main.tex、skillvector-www2027.pdf、reports/submission-audit-20261026/main.pdf及桌面的WWW2027-GitHub-current-root-20261026.pdf均为历史版本，不再用于后续修改、编译或交付。保留历史文件，不删除、不据此混入旧内容。根目录build.sh/make_overleaf_zip.py入口针对旧稿，不应继续用于当前稿。

后续每次更新，先完整读取Overleaf行级diff，以最新线上协作内容为基础，与current/source的本地未同步修改合并；编译并检查后更新current/paper.pdf与provenance.json，按用户授权同步线上、GitHub和桌面。现有文本同步仍遵循原生OT及回读规则，不盲目整文件替换。
