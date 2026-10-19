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
