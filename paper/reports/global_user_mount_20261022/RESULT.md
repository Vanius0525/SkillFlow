# global_user供CPU与GPU Job使用：本轮查询结论

2026-10-22，使用已安装InspireSkill CLI v7.1.13（update --check显示最新）进行查询。当前没有成功挂载global_user，不能把它作为已经验证可用的实验迁移目标。

## 实际验证

|检查|CPU Notebook|GPU Job|
|---|---|---|
|实例|wt-family-prep-1018|wt-lfull-deepseek-s0-1022，rank0|
|访问方式|inspire notebook exec|inspire job shell，独立shell，用后正常exit|
|/inspire/hdd/global_user|不存在|不存在|
|/inspire/ssd/global_user|不存在|不存在|
|/inspire/sj-ssd3/global_user|不存在|不存在|
|/proc/mounts中的global_user|无|无|

GPU Job仍可见个人项目HDD/SSD挂载，global_public为只读；GPU容器有效capabilities不含CAP_SYS_ADMIN，不能据容器内root身份认为可自行做系统级挂载。独立shell已正常关闭，未修改推理进程或实验文件。

## CLI和平台目录查询

- notebook create、job create的当前--help均无global_user/custom-mount参数，notebook也无独立mount/update挂载子命令。
- 使用已安装CLI内部Web session及其只读请求封装，按其契约调用file.GetSystemStorageTypeList、file.GetDirList。未调用返回文件服务明文凭据的GetSftpgoConnectionInfo。
- CPU资源空间与可上网GPU资源的hdd/global_user均返回files=[]、total=0，未发现当前账号可见的全局个人目录。**这不能单独区分尚未开通、权限或平台目录发现策略，不能据此断言配额为0。**
- 两个Workspace的hdd/project均返回真实项目目录，包括当前/inspire/hdd/project/project-public/czxs253130660，作为查询接口正常工作的对照。
- ssd/global_user查询返回：API error: InvalidParameter: invalid directory name。
- 两个Workspace当前可见存储池清单含hdd、ssd等，不含sj-ssd3。
- skill的既有API验证记录指出：notebook/train的mounts/mount_path字段虽被接受存储，但不会生成真实容器挂载，CLI因此未将其作为挂载参数。此条是既有核查，不是本轮新建实例重新证明。

## 为什么没有继续强行mount或创建新实例

目前既无平台返回的可用global_user源目录，也无CLI有效挂载入口。新建标准CPU/GPU实例本身不能指定global_user挂载，因此没有为重复验证默认配置而额外申请实例；没有构造未知GPFS/NFS源、申请特权、创建同名空目录冒充挂载或读取文件服务凭据。没有发生实际成功挂载或读写互见验证。

这修正此前“global_user可以迁移”的表述：它在概念上是跨项目个人目录，但**本账号在当前N卡实例上的可用性尚未成立**。能否在申请开通后自动挂载，仍需平台确认。

## 发给学院/平台的具体问题

> 我使用CPU资源空间和可上网GPU资源的NVIDIA4090任务。拟申请hdd（N卡集群）的global_user个人空间，但当前file.GetDirList在两个Workspace下对hdd/global_user均返回空，CPU Notebook和真实GPU Job也都未挂载/inspire/hdd/global_user。现行CLI v7.1.13没有挂载开关。请确认：是否需要先开通/初始化个人全局目录；目录的准确路径是什么；审批后是否自动挂载到CPU Notebook与GPU Job，是否需要新建/重启；若不自动挂载，有何正式配置入口？申请额度是否可实际用于这些N卡任务？

存储池应向平台确认**hdd（N卡集群）**；sj-ssd3不在当前两Workspace的可见池清单中，不能替代。

证据：platform-directories.json、cpu-mounts.json、gpu-mounts.json；目录查询代码query_directory.py。本轮只有只读查询和独立shell检查，无数据迁移、删除、新GPU作业或运行实验变更。
