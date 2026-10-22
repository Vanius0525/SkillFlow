"""Read-only platform storage directory discovery via installed Inspire CLI internals."""
import json
from pathlib import Path
from inspire.platform.web.session import get_web_session
from inspire.platform.web.browser_api.workspaces import try_enumerate_workspaces
from inspire.platform.web.browser_api.core import _request_json,_v2_result,_get_base_url
s=get_web_session();workspaces=try_enumerate_workspaces(s)
report={}
for ws in workspaces:
 if ws['name'] not in ('CPU资源空间','可上网GPU资源'):continue
 referer=_get_base_url()+'/jobs/files?spaceId='+ws['id']
 def query(action,body):
  return _v2_result(_request_json(s,'POST','/api/v2/file?Action='+action,referer=referer,body=body,timeout=25))
 pools=query('GetSystemStorageTypeList',{'filter':{'workspace_id':ws['id']}})
 data={'pools':pools,'directories':{}}
 for pool in pools.get('system_storages',[]):
  if pool['name'].lower() not in ('hdd','ssd','sj-ssd3'):continue
  for scope in ('global_user','project'):
   filt={'workspace_id':ws['id'],'system_storage_type':pool['name'],'name':scope}
   if pool.get('cluster_id'):filt['cluster_id']=pool['cluster_id']
   try:data['directories'][pool['name']+'/'+scope]=query('GetDirList',{'filter':filt})
   except Exception as e:data['directories'][pool['name']+'/'+scope]={'error_type':type(e).__name__,'error':str(e)[:500]}
 report[ws['name']]=data
p=Path(__file__).resolve().parent/'platform-directories.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
