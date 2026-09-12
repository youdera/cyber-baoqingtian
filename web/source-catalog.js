'use strict';
window.renderSourceCatalog=function(s){
 const audit=s.source_audit||{},report=audit.report,rows=report?.results||[];
 const names={sample_ok:'首页可解析',candidate_sample:'样本可识别，待接入',portal_checked:'门户已检查',needs_adapter:'需要适配',failed:'本次访问失败',cancelled:'已停止'};
 $('#audit-sources').disabled=!!(audit.running||s.engine.running);
 $('#stop-source-audit').hidden=!audit.running;
 $('#source-audit-status').textContent=audit.running?audit.message:`${audit.message||'登记入口由爬虫批量巡检。'}${report?' 最近巡检：'+stamp(report.started):' 尚未执行目录巡检。'}`;
 const entries=s.catalog||[];
 $('#source-catalog-count').textContent=`登记 ${entries.length} 个入口，其中 ${entries.filter(x=>x.enabled).length} 个已接入公告索引。登记数量不代表全国覆盖率。`;
 updateHTML('#source-catalog-list',entries.map(source=>{const result=rows.find(x=>x.id===source.id);return `<article class="source-card"><h3>${esc(source.name)}</h3><p>${source.enabled?'已接入公告索引':source.linked_source_ids?.length?`已接入${source.linked_source_ids.length}个相关栏目，其余范围待核验`:source.portal?'门户候选，尚未接入公告索引':'候选栏目，尚未接入公告索引'} · ${esc(source.region||'中央部门／地区待核对')}</p><a href="${esc(source.url)}" target="_blank" rel="noreferrer">打开登记入口 ↗</a><p>${result?`${esc(names[result.status]||result.status)} · ${esc(stamp(result.checked_at))}`:'本机尚未巡检'}</p><p>${esc(result?.reason||'等待爬虫检查；不据此判断有没有公告。')}</p>${result?.discovered?.length?`<details><summary>发现的候选栏目（需逐项核验）</summary>${result.discovered.map(x=>`<p><a href="${esc(x.url)}" target="_blank" rel="noreferrer">${esc(x.title)} ↗</a></p>`).join('')}</details>`:''}</article>`;}).join(''));
};
$('#audit-sources').onclick=async()=>{try{await api('source-audit','POST');await refresh();}catch(e){$('#source-audit-status').textContent=e.message;}};
$('#stop-source-audit').onclick=async()=>{try{await api('source-audit/stop','POST');await refresh();}catch(e){$('#source-audit-status').textContent=e.message;}};
