## 2026-10-24 完整矩阵交付与Unicode增量编辑修正

七文件增量更新、History2444–2454回放验证、全文diff一致。完整八cell数据Table3，附录Table7/8，正文8页、总15页，超过12页目标未作删减。用户要求完整结果更新与文字修改清单，已保存reports/state_core_matrix_20261024/论文修改清单.md。
ShareJS p位置必须按JavaScript UTF-16 code units，不能按UTF8字节；此前ASCII文档未暴露错误，摘要含curly apostrophe时偏移2字符已被回读拦截并修复。tools/overleaf_text_edits.mjs先模拟decoded文本，回归测试覆盖Unicode上下文与旧byte偏移失败；非ASCII插入/删除payload尚未验证，直接拒绝。只读joinDoc后确认实际版本再修复，不能重发已成功文件。仍不是Track Changes接受/拒绝模式。

## 2026-10-23 原生增量编辑与History文本留痕已实测

正式论文四个现有文本doc已通过tools/update_overleaf_text.mjs走editor socket applyOtUpdate，版本与原文校验后提交具体插入/删除操作，docID保持，逐份回读一致。History2440–2443保存textOperation，独立回放精确重建修改后全文。不是olcli push整文件上传。工具遇超时不盲重发，先核对receipt与线上原文；使用前完整olcli diff并准备逐文件before/after/ops。证据audit/state-paper-update-20261023；Track Changes未启用，网页UI视觉呈现未检查，但历史后台文本操作已直接验证。今后现有正文优先此路径；新文件/二进制另行处理。

## 2026-10-23 更新留痕偏好（覆盖默认整文件更新方式）

用户希望在Overleaf内看到文件内部的行级修改记录。已核验当前olcli push为整文件上传替换，olcli diff只产生本地行级比较；不能把二者混称云端逐行编辑。正式正文更新前，需验证原生增量文本编辑及本项目History的实际呈现；若要求逐条接受/拒绝，再确认Track Changes权限。未验证前不承诺现有push符合要求。PDF图等二进制文件仍按文件更新。
本轮仅下载/完整diff/编译，没有上传或修改活动稿；最新版23文件与12页PDF在audit/overleaf-review-20261023/，阅读说明reports/Overleaf版本核查与更新留痕_20261023.md。

# 论文同步约定（2026-10-19）

用户最新要求：今后每次修改论文，先查看 Overleaf 完整行级 diff，理解并纳入合理的云端修改；本地修改、编译及审计完成后，再同步 Overleaf 和 GitHub。**不再向桌面导出**，保留已有桌面交付。

当前关联项目 ID：`6a2cfd49b99635e8e968576a`。
线上项目仍显示旧名 `ICLR 2027: Skillflow: Long-Horizon Agent Execution With Residual Context`，但实际17个文件已经核验为本篇 WWW 稿；论文位于 `overleaf-skillvector/`，根文档为 `overleaf-skillvector/main.tex`。不要因旧名另建项目，或把整个paper目录上传到云端根目录。

用 `python tools/stage_overleaf.py /tmp/自选的新目录` 创建只包含当前稿可达源码和PDF图的关联暂存目录，然后执行：

```
olcli diff 6a2cfd49b99635e8e968576a /tmp/自选的新目录
```

必须阅读完整行级差异，不能只看文件名。diff的a侧是云端，b侧是本地；它不能单独证明谁修改了内容。结合上次上传哈希基线、Git历史和必要的网页History，保留云端合理修改。2026-10-19首次基线和完整差异见audit/OVERLEAF-BASELINE-20261019.json与audit/OVERLEAF-BEFORE-TERMINOLOGY-20261019.diff。

修改后在新目录重新暂存并diff；上传前确认云端没有检查后新增的修改。仅用 `olcli push 暂存目录 --project 6a2cfd49b99635e8e968576a`，不用`--delete`，不传播删除。随后以`--resource overleaf-skillvector/main.tex`云端编译，下载PDF和log核验；最终diff应只有有意保留的remote-only文件或没有差异。记录本次上传文件哈希供下一次比较。

本地 `bash build.sh` 已改在Windows临时目录编译，不再使用桌面；`PAPER_BUILD_STAGE_ROOT`可覆盖构建目录。旧的桌面导出脚本仅保留历史用途，当前流程不调用。GitHub仅提交本次文件、推master，不包含原始大输出、凭据或无关修改。
