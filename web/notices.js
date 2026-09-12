'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state=null,query=null,records=[],polling=false,submitting=false,requestNumber=0;
const statusNames={running:'检查中',completed:'本轮栏目读取完成',partial:'部分未查完',failed:'来源读取失败',cancelled:'已停止',interrupted:'上次运行中断',not_covered:'尚未接入'};
const renderedHTML=new Map();
function updateHTML(selector,content){if(renderedHTML.get(selector)!==content){$(selector).innerHTML=content;renderedHTML.set(selector,content);}}
const stamp=s=>s?new Date(s).toLocaleString('zh-CN',{hour12:false}):'尚未检查';
async function api(path,method='GET',data){const r=await fetch('/api/notices/'+path,{method,headers:{'Content-Type':'application/json','X-Local-Token':state?.token||''},body:data===undefined?undefined:JSON.stringify(data)});const d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d;}
function tab(name){document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===name));document.querySelectorAll('.nav').forEach(v=>v.classList.toggle('active',v.dataset.tab===name));}
function formData(){return Object.fromEntries(new FormData($('#notice-form')));}
function applyFilters(f){for(const key of ['month_from','month_to','year_from','year_to','region','kind','source_id','notice_scope'])$('#notice-form').elements[key].value=f[key]??(key==='notice_scope'?'all':'');}
function range(f){return `${f.month_from} 至 ${f.month_to} · ${f.region||'不限地区'} · ${f.kind||'全部类型'} · ${f.notice_scope==='public'?'录聘公示及变更':'全部阶段'}${f.source_id?' · '+(state?.sources.find(s=>s.id===f.source_id)?.name||f.source_id):''}${f.year_from?' · 招考'+f.year_from+'—'+f.year_to+'年度':''}`;}
function showError(e){$('#query-error').textContent=e.message;}
function renderRecords(){
 const mode=$('#notice-filter').value;
 $('#notice-filter').options[0].textContent='符合条件（'+records.filter(n=>n.match_status==='matched').length+'）';
 $('#notice-filter').options[1].textContent='信息待核对（'+records.filter(n=>n.match_status==='review').length+'）';
 const selectedStage=$('#stage-filter').value,changedOnly=$('#changed-filter').checked;
 const shown=records.filter(n=>(mode==='all'||n.match_status===mode)&&(!selectedStage||n.stage===selectedStage)&&(!changedOnly||n.changed_at));
 $('#notice-count').textContent=`${shown.length}份公告`;
 updateHTML('#notice-list',shown.length?shown.map(n=>`<article class="result-card"><div class="result-top"><span class="tag">${esc(n.stage)}</span>${n.match_status==='review'?'<span class="tag amber">筛选信息待核对</span>':''}<span>${esc(n.published||'发布日期未知')} · ${esc(n.owner)}</span></div><h3><a href="${esc(n.url)}" target="_blank" rel="noreferrer">${esc(n.title)}</a></h3><div class="result-bottom"><span>${n.changed_at?`<strong>元数据更新：${esc(stamp(n.changed_at))}</strong> · `:''}${esc(n.kind||'类型待核对')} · ${esc(n.region||'地区以原文为准')}${n.exam_year?' · 招考'+n.exam_year+'年度':''}</span><a href="${esc(n.url)}" target="_blank" rel="noreferrer">查看官方原文与附件 ↗</a></div></article>`).join(''):`<div class="empty"><h3>${query?'本机暂无符合条件的公告':'先选择范围，再查询公告'}</h3><p>${query?'请结合本轮来源状态判断是否已经查完。':'公告会在检查过程中陆续显示。'}</p></div>`);
}
function render(){
 if(window.renderAlerts)window.renderAlerts(state);
 $('#connection').textContent='本地服务已连接';
 $('#scan-banner').hidden=!state.engine.running;$('#scan-message').textContent=state.engine.message;
 $('#search-submit').disabled=state.engine.running;$('#save-query').disabled=!query||state.engine.running;
 updateHTML('#source-list',state.sources.map(s=>{const report=state.runs.flatMap(r=>r.sources).find(r=>r.id===s.id&&r.status!=='running');return `<article class="source-card"><h2>${esc(s.name)}</h2><p>${esc(s.note)}</p><a href="${esc(s.url)}" target="_blank" rel="noreferrer">打开官方栏目 ↗</a><div class="source-bottom">${report?`${esc(statusNames[report.status])} · 读取${report.pages}页 · ${report.found}份公告`:'新版适配器尚未实测'}${report?.warnings?.map(w=>`<p class="warning">${esc(w)}</p>`).join('')||''}${report?.earliest?`<span>本轮识别日期 ${report.earliest} 至 ${report.latest}（不代表期间无缺口）</span>`:''}</div></article>`;}).join(''));
 updateHTML('#saved-list',state.saved.length?state.saved.map(s=>`<article class="task-card"><div><h3>${esc(range(s.filters))}</h3><p>${s.enabled?`${s.schedule_mode==='daily'?'每天北京时间'+s.daily_time:'每'+s.interval_hours+'小时'}检查；下次 ${stamp(s.next_run)}；${s.notify_enabled?'有变化生成提醒':'不生成提醒'}`:'已暂停闹钟，仅保留条件'}</p></div><div class="task-actions"><button data-use="${s.id}">查看公示</button><button data-edit="${s.id}">设置闹钟</button>${s.enabled?`<button data-pause="${s.id}" ${state.engine.running?'disabled':''}>暂停定时</button>`:`<button data-resume="${s.id}" ${state.engine.running?'disabled':''}>开启定时</button>`}<button data-remove="${s.id}" ${state.engine.running?'disabled':''}>删除</button></div></article>`).join(''):'<p>还没有保存的查询。</p>');
 // Preserve manually expanded run reports across polling.
 const opened=new Set([...document.querySelectorAll('#run-list details[open]')].map(x=>x.dataset.run));
 updateHTML('#run-list',state.runs.length?state.runs.map(r=>`<details class="run" data-run="${r.id}" ${opened.has(r.id)?'open':''}><summary>${esc(statusNames[r.status])} · ${stamp(r.started)}</summary><div class="run-body"><p>${esc(range(r.filters))}</p><p>公告索引新增 ${r.new} · 元数据更新 ${r.updated}</p>${r.sources.map(s=>`<div class="run-source"><strong>${esc(s.name)}：${esc(statusNames[s.status])}</strong><p>读取${s.pages}页，发现${s.found}份公告。</p>${s.warnings.map(w=>`<p class="warning">${esc(w)}</p>`).join('')}</div>`).join('')}<p>完成时间：${stamp(r.ended)}。栏目读取完成不等于全国或历史完整覆盖。</p></div></details>`).join(''):'<p>首次查询后显示检查记录。</p>');
 if(query){const latest=state.runs.find(r=>JSON.stringify(r.filters)===JSON.stringify(query));$('#query-status').textContent=state.engine.running?'正在更新公告索引；以下结果会陆续刷新':latest?`${statusNames[latest.status]} · ${latest.sources.map(s=>`${s.name}：${statusNames[s.status]}`).join('；')}`:'显示本机公告索引';}
}
async function loadResults(f){const number=++requestNumber;const result=await api('query','POST',f);if(number!==requestNumber)return;query=result.filters;records=result.records;$('#date-summary').textContent=`公告发布 ${query.date_from} 至 ${query.date_to}`+(query.year_from?`；同时筛选招考 ${query.year_from}—${query.year_to} 年度`:'');$('#coverage-summary').textContent=result.sources.length?`本次可检查：${result.sources.map(s=>s.name).join('、')}。${query.region?'地区未知的公告单列待核对。':''}尚未覆盖其他发布单位。`:'所选地区和类型尚无已接入栏目。';renderRecords();render();return result;}
async function refresh(){if(polling||submitting)return;polling=true;try{state=await api('state');render();if(query&&!submitting)await loadResults(query);}catch(e){$('#connection').textContent='本地服务未连接';}finally{polling=false;}}
$('#notice-form').onsubmit=async e=>{e.preventDefault();submitting=true;$('#query-error').textContent='';$('#search-submit').disabled=true;try{const result=await loadResults(formData());if(result?.sources.length){await api('scan','POST',query);state=await api('state');render();}}catch(err){showError(err);}finally{submitting=false;$('#search-submit').disabled=!!state?.engine.running;}};
$('#notice-filter').onchange=renderRecords;
$('#stage-filter').onchange=renderRecords;
$('#changed-filter').onchange=renderRecords;
$('#stop-scan').onclick=async()=>{try{await api('stop','POST');$('#query-status').textContent='已请求停止，等待当前请求结束';}catch(e){showError(e);}};
let savingFilters=null;
function openAlarm(f,s={}){savingFilters=f;$('#save-form').reset();for(const key of ['enabled','notify_enabled'])if(key in s)$('#save-form').elements[key].checked=s[key];for(const key of ['schedule_mode','daily_time','interval_hours'])if(key in s)$('#save-form').elements[key].value=s[key];$('#save-range').textContent=range(f);$('#save-error').textContent='';$('#save-dialog').showModal();}
$('#save-query').onclick=()=>{if(query)openAlarm(query);};
$('#close-save').onclick=()=>$('#save-dialog').close();
$('#save-form').onsubmit=async e=>{e.preventDefault();try{await api('saved','POST',{filters:savingFilters,enabled:e.target.elements.enabled.checked,notify_enabled:e.target.elements.notify_enabled.checked,schedule_mode:e.target.elements.schedule_mode.value,daily_time:e.target.elements.daily_time.value,interval_hours:Number(e.target.elements.interval_hours.value)});$('#save-dialog').close();await refresh();tab('saved');}catch(err){$('#save-error').textContent=err.message;}};
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.tab)tab(b.dataset.tab);try{if(b.dataset.edit){const s=state.saved.find(x=>x.id===b.dataset.edit);openAlarm(s.filters,s);}if(b.dataset.use){const s=state.saved.find(x=>x.id===b.dataset.use);applyFilters(s.filters);tab('browse');await loadResults(s.filters);}if(b.dataset.remove){await api('saved/'+b.dataset.remove,'DELETE');await refresh();}if(b.dataset.pause||b.dataset.resume){const s=state.saved.find(x=>x.id===(b.dataset.pause||b.dataset.resume));await api('saved','POST',{...s,enabled:!!b.dataset.resume});await refresh();}}catch(err){showError(err);}});
(async()=>{try{state=await api('state');$('#region-select').innerHTML='<option value="">不限地区</option>'+state.regions.map(r=>`<option>${r}</option>`).join('');$('#source-select').innerHTML='<option value="">全部已接入栏目</option>'+state.sources.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');const today=new Date(),y=today.getFullYear(),m=String(today.getMonth()+1).padStart(2,'0');applyFilters({month_from:`${y}-01`,month_to:`${y}-12`,region:'',kind:'',notice_scope:'public',source_id:''});render();renderRecords();}catch(e){showError(e);$('#connection').textContent='本地服务未连接';}})();
setInterval(refresh,3000);
