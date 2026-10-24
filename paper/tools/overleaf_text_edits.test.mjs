import {test} from 'node:test';import assert from 'node:assert/strict';import {validateTextEdits} from './overleaf_text_edits.mjs';
test('Unicode context uses editor UTF-16 offsets and rejects the previous UTF-8 offset bug',()=>{
  const before='model’s result. These findings.',addition='New evidence. ',position=before.indexOf('These'),after=before.slice(0,position)+addition+before.slice(position);
  assert.equal(validateTextEdits(before,after,[{p:position,i:addition}]),after);
  const wrongOffset=Buffer.byteLength(before.slice(0,position),'utf8');
  assert.throws(()=>validateTextEdits(before,after,[{p:wrongOffset,i:addition}]),/simulation mismatch/);
});
test('non-BMP context and stale deletion are checked before any network mutation',()=>{
  const before='A 😀 old text.',p=before.indexOf('old');assert.equal(validateTextEdits(before,'A 😀 new text.',[{p,d:'old'},{p,i:'new'}]),'A 😀 new text.');
  assert.throws(()=>validateTextEdits(before,'unused',[{p,d:'different'}]),/Invalid deletion/);
});
test('unverified non-ASCII payloads are rejected rather than silently encoded',()=>{
  assert.throws(()=>validateTextEdits('a','a中文',[{p:1,i:'中文'}]),/ASCII/);
});
