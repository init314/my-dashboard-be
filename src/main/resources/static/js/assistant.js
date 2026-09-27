'use strict';
/** Home and full-screen views share one conversation instance and the authenticated API helper. */
window.WorkspaceAssistant = (() => {
  let ui, shell, panel, codex, project, busy=false, loginJob=null;
  const day = date => {
    const parts=new Intl.DateTimeFormat('en',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
    const value=type=>parts.find(part=>part.type===type).value;
    return `${value('year')}-${value('month')}-${value('day')}`;
  };
  function status(message){shell.querySelector('[data-assistant-status]').textContent=message;}
  function setBusy(value){busy=value;panel.setAttribute('aria-busy',String(value));shell.querySelectorAll('[data-assistant="connect"], [data-assistant="login"]').forEach(button=>button.disabled=value);}
  async function prepare(){if(!project)project=await ui.api('/assistant');return project;}
  async function api(path,method,body){
    await prepare();
    const target=path.replace(/^\/studio\/jobs/, '/assistant/jobs');
    const input=target==='/assistant/jobs'&&method==='POST'?{action:body.action,args:body.args}:body;
    return ui.api(target,method,input);
  }
  async function today(){
    const host=shell.querySelector('[data-assistant-today]');host.textContent='일정 조회 중…';
    try{
      const now=new Date(),next=new Date(now.getTime()+86400000);
      const events=await ui.api(`/calendar/events?from=${day(now)}&to=${day(next)}`);
      host.replaceChildren();
      if(!events.length){host.textContent='오늘 등록된 일정이 없습니다.';return;}
      for(const event of events.slice(0,4)){
        const button=document.createElement('button');button.className='assistant-event';button.dataset.view='calendar';
        const time=document.createElement('small');time.textContent=event.allDay?'종일':event.start.slice(11,16);
        const title=document.createElement('span');title.textContent=event.title;button.append(time,title);host.append(button);
      }
      if(events.length>4){const rest=document.createElement('small');rest.textContent=`외 ${events.length-4}개 일정`;host.append(rest);}
    }catch(error){host.textContent=error.message;}
  }
  async function login(action='codex-login'){
    if(busy)throw Error('진행 중인 요청이 끝난 뒤 로그인해 주세요.');
    setBusy(true);const box=shell.querySelector('[data-assistant-auth]');box.replaceChildren();box.hidden=false;
    const cancel=shell.querySelector('[data-assistant="cancel-login"]');cancel.hidden=false;
    try{
      let job=await api('/studio/jobs','POST',{action});loginJob=job.id;
      let last='';
      while(true){
        const identity=JSON.stringify(job.events||[]);
        if(identity!==last){last=identity;box.replaceChildren();for(const event of job.events||[]){
          if(event.url){let url;try{url=new URL(event.url);}catch{}if(url?.protocol==='https:'&&url.hostname==='auth.openai.com'){const link=document.createElement('a');link.href=url.href;link.textContent='Codex 로그인 페이지 열기';link.target='_blank';link.rel='noopener noreferrer';box.append(link);}}
          if(event.code){const code=document.createElement('code');code.textContent=event.code;box.append(code);}
        }}
        if(job.state!=='RUNNING')break;
        status(action==='setup'?'Codex 도구를 준비하고 있습니다.':'로그인 페이지에서 인증 코드를 입력해 주세요.');
        await new Promise(resolve=>setTimeout(resolve,600));job=await api('/studio/jobs/'+job.id);
      }
      if(job.state!=='SUCCEEDED')throw Error(job.error||'로그인이 중지되었습니다.');
      box.hidden=true;box.replaceChildren();status(action==='setup'?'도구 준비 완료':'로그인 완료');
    }finally{loginJob=null;cancel.hidden=true;setBusy(false);}
    codex.reset();await codex.load();
  }
  async function guard(work){try{await work();}catch(error){status(error.message);ui.toast(error.message);}}
  return {
    init(helpers){
      if(shell)return;ui=helpers;
      shell=document.createElement('section');shell.className='assistant-shell';shell.setAttribute('aria-label','SENTIS AI 비서');
      shell.innerHTML='<header class="assistant-heading"><div class="assistant-identity"><span class="sentis-core" aria-hidden="true"><span></span></span><div><span class="eyebrow">PERSONAL INTELLIGENCE</span><h2>SENTIS</h2><small data-assistant-status role="status">일정 · 파일 · 앱 제어 · 코드 수정</small></div></div><div class="actions"><button data-assistant="connect">연결 확인</button><button data-assistant="login">Codex 로그인</button><button data-assistant="cancel-login" hidden>로그인 중지</button><button data-view="assistant" data-assistant-expand aria-label="SENTIS 크게 보기">↗</button></div></header><div class="assistant-usage"></div><div class="assistant-body"><div class="assistant-main"><div class="assistant-suggestions" aria-label="빠른 요청"><button data-assistant-prompt="오늘 일정과 수업을 알려줘">오늘 일정</button><button data-assistant-prompt="웹에서 조사할 내용을 질문해줘">웹 검색</button><button data-assistant-prompt="개인 드라이브에서 찾을 파일 이름을 물어봐줘">파일 찾기</button><button data-assistant-prompt="SENTIS에서 제어할 수 있는 기능과 코드 수정 가능 상태를 확인해줘">SENTIS 제어</button></div><div class="assistant-auth" data-assistant-auth hidden></div><div class="assistant-codex-panel"></div></div><aside class="assistant-sidebar"><header><h3>오늘 일정</h3><button data-assistant="today" class="ghost sm" aria-label="오늘 일정 새로고침">↻</button></header><div data-assistant-today></div><footer><button data-view="calendar">캘린더</button><button data-view="cloud">드라이브</button><button data-view="files">서버 파일</button></footer></aside></div>';
      document.querySelector('#assistant-home').append(shell);panel=shell.querySelector('.assistant-codex-panel');
      const mcpStatus=document.createElement('small');mcpStatus.dataset.assistantMcp='';mcpStatus.setAttribute('role','status');mcpStatus.textContent='MCP 확인 중';shell.querySelector('.assistant-heading h2').after(mcpStatus);
      codex=window.StudioCodex(panel,{
        namespace:'assistant',assistant:true,usageTarget:shell.querySelector('.assistant-usage'),escape:ui.escape,api,toast:ui.toast,editor:ui.editor,
        project:()=>project,busy:()=>busy,setBusy,dirty:()=>false,confirm:ui.confirmAction,context:()=>null,
        publish:detail=>status(detail.codex==='실행 중'?'요청을 처리하고 있습니다.':'요청 완료'),
        connections:servers=>{const dashboard=servers.find(server=>server.name==='dashboard_assistant');mcpStatus.textContent=dashboard?.status==='available'?'MCP 도구 '+dashboard.toolCount+'개 사용 가능':'대시보드 MCP를 확인해 주세요.';},
        auth:authenticated=>{panel.querySelector('#assistant-studio-auth').textContent=authenticated?'연결됨':'로그인 필요';panel.querySelector('#assistant-studio-auth-cta').hidden=authenticated;shell.querySelector('[data-assistant="login"]').hidden=authenticated;status(authenticated?'Codex 자동 연결됨':'Codex에 로그인해 주세요.');}
      });
      shell.addEventListener('click',event=>{
        const suggestion=event.target.closest('[data-assistant-prompt]');
        if(suggestion){const input=panel.querySelector('#assistant-studio-prompt');input.value=suggestion.dataset.assistantPrompt;input.focus();return;}
        const button=event.target.closest('[data-assistant], [data-studio="codex-login"]');if(!button)return;
        event.stopPropagation();guard(async()=>{
          if(button.dataset.studio==='codex-login'||button.dataset.assistant==='login')await login();
          if(button.dataset.assistant==='connect'){await prepare();codex.reset();await codex.load();}
          if(button.dataset.assistant==='setup')await login('setup');
          if(button.dataset.assistant==='today')await today();
          if(button.dataset.assistant==='cancel-login'&&loginJob)await ui.api('/assistant/jobs/'+loginJob,'DELETE');
        });
      });
      const setup=document.createElement('button');setup.dataset.assistant='setup';setup.textContent='도구 준비';
      shell.querySelector('.assistant-heading .actions').prepend(setup);
      // Reuse server-side cached authentication without starting login or a paid model turn.
      guard(async()=>{await prepare();await codex.load();});today();
    },
    open(view){
      if(!shell)return;
      if(view==='assistant')document.querySelector('#assistant').append(shell);
      if(view==='home')document.querySelector('#assistant-home').append(shell);
      const expanded=shell.closest('#assistant')!==null;
      const button=shell.querySelector('[data-assistant-expand]');button.dataset.view=expanded?'home':'assistant';button.textContent=expanded?'↙':'↗';button.setAttribute('aria-label',expanded?'홈으로 돌아가기':'SENTIS 크게 보기');
      if(view==='home'||view==='assistant')today();
    }
  };
})();
