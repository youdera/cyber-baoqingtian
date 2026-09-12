// Exercise every download path without network, real people or browser storage.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map(),listeners={},windowEvents={},urls=new Map(),downloads=[];
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:id==='#report-channels'?'材料交给谁？提交与跟进测试文本':'',addEventListener(type,fn){this[type]=fn;}});return nodes.get(id);}
const context={Blob,setTimeout(fn){fn();},URL:{createObjectURL(blob){const url='blob:'+urls.size;urls.set(url,blob);return url;},revokeObjectURL(){}},window:{addEventListener(type,fn){windowEvents[type]=fn;}},document:{querySelector:node,querySelectorAll(){return [];},addEventListener(type,fn){listeners[type]=fn;},createElement(){return {click(){downloads.push({name:this.download,blob:urls.get(this.href)});}};}}};
vm.runInNewContext(fs.readFileSync('web/guide.js','utf8'),context);
function click(dataset={},id=''){listeners.click({target:{closest(){return {dataset,id};}}});}
(async()=>{
 for(const id of ['rumor','violence','insult','property','privacy','missing'])click({instruction:id});
 for(let i=0;i<6;i++)click({template:String(i)});
 click({},'download-all');
 assert.equal(downloads.length,13);
 assert.equal(new Set(downloads.map(d=>d.name)).size,13);
 for(const d of downloads){assert.ok(d.blob.type.startsWith('text/plain'));assert.ok((await d.blob.text()).length>100);}
 assert.match(await downloads[1].blob.text(),/病历/);
 assert.match(await downloads[5].blob.text(),/不能统一承诺/);
 const pack=await downloads[12].blob.text();
 assert.match(pack,/提交与跟进测试文本/);assert.match(pack,/证人独立陈述/);assert.match(pack,/court.gov.cn/);
 console.log('PASS: 13 material downloads; six categories; source references. No network or real-person inputs.');
})().catch(e=>{console.error(e);process.exitCode=1;});
