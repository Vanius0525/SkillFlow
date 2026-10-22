## 本轮已完成

RESULT.md为最终结论：当前CPU/GPU均无global_user挂载；平台hdd/global_user目录查询均为空；CLI无有效挂载入口，尚未成功挂载。需要管理员确认目录开通/路径/审批后自动挂载方式。未新建实例、未迁移数据、未修改运行实验。GPU独立shell已正常exit。查询和容器证据已落盘。

# global_user挂载查询与验证

目标：用户要求结合启智CLI查询并尝试global_user能否供CPU Notebook与GPU Job使用；不迁移/删除当前实验数据，不停止或修改当前GPU实验。

已知：CLI create帮助没有global_user/custom-mount参数。当前skill Browser API契约记录mounts/mount_path可被接受存储但未产生实际容器挂载；不能把API接受当挂载成功。需以当前平台目录清单和真实容器验证。

下一步：通过CLI底层只读file目录接口定位global_user；用CPU exec、GPU job shell只读检查实际挂载与权限；有合法可访问路径才创建唯一小marker。若无挂载控制接口，不使用未知NFS源/特权mount绕过平台，报告管理员需提供的具体能力。
