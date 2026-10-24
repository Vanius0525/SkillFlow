// ShareJS positions count JavaScript UTF-16 code units, not UTF-8 bytes.
// Non-ASCII *context* is supported; non-ASCII insert/delete payloads are
// deliberately rejected until their private-protocol encoding is verified.
export function validateTextEdits(before, after, ops) {
  let text=before;
  for(const op of ops){
    if(!Number.isSafeInteger(op.p)||op.p<0||op.p>text.length) throw Error('Invalid text position');
    const payload=op.d ?? op.i;
    if(typeof payload!=='string'||/[^\x00-\x7f]/.test(payload)) throw Error('Only verified ASCII edit payloads are supported');
    if(op.d!==undefined){
      if(text.slice(op.p,op.p+op.d.length)!==op.d) throw Error('Invalid deletion');
      text=text.slice(0,op.p)+text.slice(op.p+op.d.length);
    }else if(op.i!==undefined) text=text.slice(0,op.p)+op.i+text.slice(op.p);
    else throw Error('Unsupported edit');
  }
  if(text!==after) throw Error('Edit simulation mismatch (check UTF-16 offsets)');
  return text;
}
