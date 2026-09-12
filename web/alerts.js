'use strict';
(() => {
  const seen = new Set();
  let loaded=false, enabled=false, current=[];
  window.renderAlerts = state => {
    current=state.alerts||[];
    const count=state.unread||0;
    document.querySelector('#alert-summary').textContent=`共 ${state.alert_total||0} 条提醒，${count} 条未读。未读优先显示，每批最多200条；标记本批已读后可查看下一批未读。`;
    document.querySelector('#read-alerts').disabled=!current.some(a=>!a.read);
    document.querySelector('#alert-badge').textContent=count?`（${count}未读）`:'';
    updateHTML('#alert-list',current.length?current.map(a=>`<article class="result-card"><div class="result-top"><span class="tag">${a.read?'已读':'未读'}</span><span>${a.event==='new'?'新发现公示':'公告元数据更新'} · ${esc(stamp(a.created))}</span>${a.match_status==='review'?'<span class="tag amber">筛选信息待核对</span>':''}</div><h3><a href="${esc(a.url)}" target="_blank" rel="noreferrer">${esc(a.title)}</a></h3><p>${esc(a.source)} · 公告发布 ${esc(a.published||'未知')}</p></article>`).join(''):'<div class="empty">暂无提醒。查询后在“关注与闹钟”开启定时检查与提醒。</div>');
    const fresh=current.filter(a=>!a.read&&!seen.has(a.id));
    if(loaded&&enabled&&fresh.length&&Notification.permission==='granted'){
      try{const n=new Notification(`发现 ${fresh.length} 条公告提醒`,{body:'打开赛博包青天查看官方链接及来源状态',tag:'wuzhong-notices'});n.onclick=()=>{window.focus();tab('alerts');n.close();};}
      catch(e){document.querySelector('#browser-alert-status').textContent='浏览器通知不可用，请查看站内提醒。';}
    }
    current.forEach(a=>seen.add(a.id));loaded=true;
  };
  document.querySelector('#enable-browser-alerts').onclick=async()=>{
    const status=document.querySelector('#browser-alert-status');
    if(!('Notification' in window)){status.textContent='此浏览器不支持桌面通知，请使用站内提醒。';return;}
    try{enabled=(await Notification.requestPermission())==='granted';status.textContent=enabled?'已开启本次页面会话的通知，请保持页面打开；系统免打扰或浏览器限制可能阻止弹窗。':'未获得通知权限，站内提醒仍可使用。';}
    catch(e){status.textContent='无法开启通知，站内提醒仍可使用。';}
  };
  document.querySelector('#read-alerts').onclick=async()=>{
    try{await api('alerts/read','POST',{ids:current.filter(a=>!a.read).map(a=>a.id)});loaded=false;await refresh();}
    catch(e){document.querySelector('#browser-alert-status').textContent=e.message;}
  };
})();
