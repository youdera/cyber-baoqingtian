'use strict';
window.sourceCoverageMatches=source=>{
 const selected=$('#coverage-region').value;
 return !selected||(selected==='national'?!source.region:source.region===selected);
};
window.renderSourceCatalog=function(s){
 const selected=$('#coverage-region').value;
 const groups=s.regions.map(region=>({region,count:s.sources.filter(x=>x.region===region).length}));
 updateHTML('#coverage-region','<option value="">全部已登记范围</option><option value="national">全国／中央招录</option>'+groups.map(g=>`<option value="${esc(g.region)}">${esc(g.region)} · ${g.count}个已接入栏目</option>`).join(''));
 $('#coverage-region').value=selected;
 const missing=groups.filter(g=>!g.count).map(g=>g.region);
 $('#region-coverage-summary').textContent=`按31个省级地区及兵团逐项核验，目前${groups.filter(g=>g.count).length}个范围至少接入一个局部栏目。${missing.length?'尚无已接入栏目：'+missing.join('、')+'。':''}有来源不等于全省、全部类型或全部历史覆盖。`;
 const shown=s.sources.filter(window.sourceCoverageMatches);
 $('#selected-coverage-summary').textContent=`当前显示${shown.length}个已接入栏目${selected?'（'+(selected==='national'?'全国／中央':selected)+'）':''}。具体发布单位和历史缺口见各栏目说明；单部门、市级来源不能代表全省。`;
 const audit=s.source_audit||{},report=audit.report,rows=report?.results||[];
 const names={sample_ok:'首页可解析',candidate_sample:'样本可识别，待接入',portal_checked:'门户已检查',needs_adapter:'需要适配',failed:'本次访问失败',cancelled:'已停止'};
 $('#audit-sources').disabled=!!(audit.running||s.engine.running);
 $('#stop-source-audit').hidden=!audit.running;
 $('#source-audit-status').textContent=audit.running?audit.message:`${audit.message||'登记入口由爬虫批量巡检。'}${report?' 最近巡检：'+stamp(report.started):' 尚未执行目录巡检。'}`;
 const entries=s.catalog||[];
 $('#source-catalog-count').textContent=`登记 ${entries.length} 个入口，其中 ${entries.filter(x=>x.enabled).length} 个已接入公告索引。登记数量不代表全国覆盖率。`;
 updateHTML('#source-catalog-list',entries.filter(window.sourceCoverageMatches).map(source=>{const result=rows.find(x=>x.id===source.id);return `<article class="source-card"><h3>${esc(source.name)}</h3><p>${source.enabled?'已接入公告索引':source.linked_source_ids?.length?`已接入${source.linked_source_ids.length}个相关栏目，其余范围待核验`:source.portal?'门户候选，尚未接入公告索引':'候选栏目，尚未接入公告索引'} · ${esc(source.region||'中央部门／地区待核对')}</p><a href="${esc(source.url)}" target="_blank" rel="noreferrer">打开登记入口 ↗</a><p>${result?`${esc(names[result.status]||result.status)} · ${esc(stamp(result.checked_at))}`:'本机尚未巡检'}</p><p>${esc(result?.reason||'等待爬虫检查；不据此判断有没有公告。')}</p>${result?.transport==='p256_compat'?'<p>TLS曲线兼容重试已启用，证书验证保持开启。</p>':''}${result?.discovered?.length?`<details><summary>发现的候选栏目（需逐项核验）</summary>${result.discovered.map(x=>`<p><a href="${esc(x.url)}" target="_blank" rel="noreferrer">${esc(x.title)} ↗</a></p>`).join('')}</details>`:''}</article>`;}).join(''));
};
$('#coverage-region').onchange=()=>render();
$('#audit-sources').onclick=async()=>{try{await api('source-audit','POST');await refresh();}catch(e){$('#source-audit-status').textContent=e.message;}};
$('#stop-source-audit').onclick=async()=>{try{await api('source-audit/stop','POST');await refresh();}catch(e){$('#source-audit-status').textContent=e.message;}};
