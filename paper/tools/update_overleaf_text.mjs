// Apply reviewed, minimal ShareJS text edits through Overleaf's editor socket.
// No uploads, deletes, credential output, or blind retries after uncertain writes.
import fs from 'node:fs';
import crypto from 'node:crypto';
const lib=process.env.OLCLI_LIB || '/home/vanius/.nvm/versions/node/v22.22.1/lib/node_modules/@aloth/olcli/dist';
const {OverleafClient}=await import(`${lib}/client.js`);
const {getSessionCookie,getSessionCookieName,getBaseUrl}=await import(`${lib}/config.js`);
const [projectId,editsPath,receiptPath]=process.argv.slice(2);
if(!projectId||!editsPath||!receiptPath) throw Error('Usage: node update_overleaf_text.mjs PROJECT EDITS.json RECEIPT.json');
if(fs.existsSync(receiptPath)) throw Error('Receipt already exists; inspect it before another update.');
const edits=JSON.parse(fs.readFileSync(editsPath,'utf8'));
const c=await OverleafClient.fromSessionCookie(getSessionCookie(),getBaseUrl(),getSessionCookieName());
const receipt={projectId,method:'editor-socket/applyOtUpdate',started_at:new Date().toISOString(),documents:[]};
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const persist=()=>fs.writeFileSync(receiptPath,JSON.stringify(receipt,null,2)+'\n');
const info=await c.getProjectInfo(projectId); const docs=c.collectProjectDocs(info);
const session=await c.openProjectSocket(projectId);
try {
  // Validate every base and simulate all edits before the first mutation.
  for(const e of edits){
    const doc=docs.find(d=>d.path===e.path); if(!doc) throw Error(`Missing document ${e.path}`);
    const j=await c.joinDocument(session,doc.id);
    if(j.type!=='sharejs-text-ot'||j.content!==e.before) throw Error(`Protocol/base conflict: ${e.path}`);
    let simulated=Buffer.from(e.before,'utf8').toString('latin1');
    for(const op of e.ops){
      if(op.d!==undefined){if(simulated.slice(op.p,op.p+op.d.length)!==op.d) throw Error('Invalid deletion'); simulated=simulated.slice(0,op.p)+simulated.slice(op.p+op.d.length);}
      else if(op.i!==undefined) simulated=simulated.slice(0,op.p)+op.i+simulated.slice(op.p);
      else throw Error('Unsupported edit');
    }
    if(Buffer.from(simulated,'latin1').toString('utf8')!==e.after) throw Error('Edit simulation mismatch');
    e.docId=doc.id;
  }
  for(const e of edits){
    const j=await c.joinDocument(session,e.docId);
    if(j.content!==e.before) throw Error(`Concurrent change before write: ${e.path}`);
    const entry={path:e.path,docId:e.docId,before_version:j.version,before_sha256:hash(e.before),after_sha256:hash(e.after),operations:e.ops.length,status:'sending'};
    receipt.documents.push(entry);persist();
    // On a timeout/error, the receipt remains ambiguous. Read state; never resend blindly.
    await c.socketRpc(session,'applyOtUpdate',[e.docId,{doc:e.docId,op:e.ops,v:j.version}]);
    entry.status='acknowledged';persist();
    const after=await c.joinDocument(session,e.docId);
    if(after.content!==e.after) throw Error(`Read-back mismatch after ${e.path}`);
    entry.after_version=after.version;entry.status='verified';persist();
    console.log(`${e.path}: editor text operations verified, v${j.version} -> v${after.version}`);
  }
  receipt.completed_at=new Date().toISOString();persist();
} catch(e){receipt.error=e.message;persist();throw e;} finally {await c.closeProjectSocket(session);}
