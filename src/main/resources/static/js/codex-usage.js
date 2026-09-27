'use strict';
/** Shared presentation of authoritative quota snapshots and locally ticking reset times. */
window.WorkspaceCodexUsage = element => {
  element.classList.add('cx-usage-panel');
  element.setAttribute('aria-label', 'Codex 사용량과 초기화까지 남은 시간');
  element.innerHTML = `<header class="cx-usage-heading"><strong><span class="dot"></span> CODEX <span>사용량</span></strong><small data-usage-updated>연결 확인 중</small></header>
    <div class="cx-usage-grid"><div class="cx-account-gauges"></div><article class="cx-gauge-card cx-context-card"><div class="cx-gauge-label"><span>현재 대화</span><b data-context-value>—</b></div><div class="cx-gauge-track" data-context-track role="progressbar" aria-label="현재 대화 컨텍스트 사용량" aria-valuemin="0" aria-valuemax="100"><span></span></div><small data-context-detail>대화 시작 후 표시됩니다.</small><small class="cx-context-note">대화 용량 · 계정 한도와 별도</small></article></div>`;
  const accountContainer=element.querySelector('.cx-account-gauges');
  const updated=element.querySelector('[data-usage-updated]');
  let snapshots=new Map(), resetViews=[], fetchedAt=null;
  const finite=value => typeof value==='number' && Number.isFinite(value);
  const clamp=value => Math.max(0,Math.min(100,value));
  const percent=value => Number.isInteger(value)?String(value):value.toFixed(1);
  function gauge(track, value, label){
    track.firstElementChild.style.width=(value===null?0:clamp(value))+'%';
    track.dataset.known=String(value!==null);
    if(value===null)track.removeAttribute('aria-valuenow');
    else track.setAttribute('aria-valuenow',String(clamp(value)));
    track.setAttribute('aria-valuetext',label);
  }
  function remaining(seconds){
    const value=Math.max(0,Math.ceil(seconds));
    const days=Math.floor(value/86400),hours=Math.floor(value/3600)%24,minutes=Math.floor(value/60)%60;
    const clock=[hours,minutes,value%60].map(part=>String(part).padStart(2,'0')).join(':');
    return (days?days+'일 ':'')+clock;
  }
  function tick(){
    const now=Date.now()/1000;
    for(const view of resetViews){
      const {limit,track,text}=view;
      const seconds=finite(limit.resetsAt)&&limit.resetsAt>0?limit.resetsAt-now:null;
      const duration=finite(limit.windowDurationMins)&&limit.windowDurationMins>0?limit.windowDurationMins*60:null;
      const label=seconds===null?'시각 미제공':seconds<=0?'초기화 확인 중':remaining(seconds);
      text.textContent=label;
      gauge(track,seconds===null||duration===null?null:clamp(seconds/duration*100),label);
    }
  }
  function drawLimits(){
    accountContainer.replaceChildren();resetViews=[];
    if(!snapshots.size){
      const empty=document.createElement('p');empty.className='cx-gauge-empty';
      empty.textContent='계정에서 사용 한도 정보를 제공하지 않습니다.';accountContainer.append(empty);return;
    }
    for(const limit of snapshots.values()){
      const card=document.createElement('article');card.className='cx-gauge-card';
      card.innerHTML='<div class="cx-gauge-label"><span data-limit-name></span><b data-limit-value></b></div><div class="cx-gauge-track" data-limit-track role="progressbar" aria-valuemin="0" aria-valuemax="100"><span></span></div><div class="cx-reset-label"><span>초기화까지</span><time></time></div><div class="cx-gauge-track cx-reset-track" role="progressbar" aria-valuemin="0" aria-valuemax="100"><span></span></div>';
      const duration=limit.windowDurationMins;
      const windowName=duration===300?'5시간 한도':duration===10080?'주간 한도':duration>0?(duration%60===0?duration/60+'시간':duration+'분')+' 한도':limit.name||'계정 한도';
      const name=card.querySelector('[data-limit-name]');name.textContent=windowName;name.title=limit.name||windowName;
      const value=finite(limit.usedPercent)?clamp(limit.usedPercent):null;
      const label=value===null?'미제공':percent(value)+'% 사용';
      card.querySelector('[data-limit-value]').textContent=label;
      const track=card.querySelector('[data-limit-track]');track.setAttribute('aria-label',windowName+' 사용량');
      gauge(track,value,label);card.dataset.level=value>=90?'high':value>=75?'warning':'normal';
      const reset=card.querySelector('.cx-reset-track');reset.setAttribute('aria-label',windowName+' 초기화까지 남은 시간');
      const time=card.querySelector('time');
      if(finite(limit.resetsAt)&&limit.resetsAt>0){const date=new Date(limit.resetsAt*1000);if(!Number.isNaN(date.getTime())){time.dateTime=date.toISOString();time.title='초기화 예정: '+date.toLocaleString();}}
      resetViews.push({limit,track:reset,text:time});accountContainer.append(card);
    }
    tick();
  }
  function limits(values, merge=false){
    if(!merge)snapshots.clear();
    for(const limit of Array.isArray(values)?values:[])snapshots.set(limit.id||limit.name,limit);
    drawLimits();
    fetchedAt=new Date();updated.textContent='갱신 '+fetchedAt.toLocaleTimeString();element.dataset.state='ready';
  }
  function context(usage){
    const used=usage?.contextTokens,capacity=usage?.contextWindow;
    const value=finite(used)&&used>=0&&finite(capacity)&&capacity>0?clamp(used/capacity*100):null;
    const label=value===null?'—':percent(Math.round(value*10)/10)+'%';
    element.querySelector('[data-context-value]').textContent=label;
    element.querySelector('[data-context-detail]').textContent=value===null?'대화 시작 후 표시됩니다.':used.toLocaleString()+' / '+capacity.toLocaleString()+' 토큰';
    gauge(element.querySelector('[data-context-track]'),value,value===null?'대화 사용량 미확인':label+' 사용');
  }
  function pending(){snapshots.clear();drawLimits();context(null);fetchedAt=null;updated.textContent='연결 확인 중';element.dataset.state='pending';accountContainer.firstElementChild.textContent='Codex 계정 사용량을 불러옵니다.';}
  pending();
  const timer=setInterval(tick,1000);
  return {
    account(result){limits(result.rateLimits);if(result.authenticated===false){updated.textContent='로그인 필요';element.dataset.state='unavailable';accountContainer.replaceChildren();const notice=document.createElement('p');notice.className='cx-gauge-empty';notice.textContent='Codex에 로그인하면 사용 한도가 표시됩니다.';accountContainer.append(notice);resetViews=[];}},
    limits,context,pending,
    stale(){element.dataset.state='stale';updated.textContent=fetchedAt?'갱신 지연 · 마지막 '+fetchedAt.toLocaleTimeString():'사용량 조회 실패';if(!snapshots.size)accountContainer.firstElementChild.textContent='연결 확인 후 다시 조회해 주세요.';},
    destroy(){clearInterval(timer);}
  };
};
