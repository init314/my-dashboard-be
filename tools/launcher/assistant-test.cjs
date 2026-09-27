const {JSDOM}=require('jsdom');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const dom=new JSDOM(fs.readFileSync(path.join(root,'src/main/resources/templates/home.html'),'utf8'),{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window,d=w.document,calls=[];let jobs=0,running=false,done=false;
w.setInterval=()=>1;w.setTimeout=(fn,delay)=>setTimeout(fn,Math.min(delay,15));
const escape=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const reply={assistant:{thread:{id:'assistant-thread',turns:[{id:'turn',items:[{id:'answer',type:'agentMessage',text:'보고서 [다운로드](/api/v1/cloud/content?path=%2Freport.txt) · [출처](https://example.com/report) · [bad](javascript:alert(1)) <img src=x onerror=alert(1)>'}]}]}}};
const api=async(url,method,body)=>{
  calls.push({url,method,body});
  if(url==='/assistant')return {deviceId:'local',root:'/app/data/files/.assistant'};
  if(url.startsWith('/calendar/events'))return [{title:'<img src=x>',start:'2026-09-26T10:00:00',allDay:false}];
  if(url.endsWith('/inputs')){if(body.type==='interrupt')done=true;return null;}
  if(method==='DELETE'){done=true;return null;}
  if(url.startsWith('/assistant/jobs/')&&!method)return {id:'active',state:done?'SUCCEEDED':'RUNNING',events:[],result:done?reply:null};
  if(url==='/assistant/jobs'&&method==='POST'){
    assert.deepEqual(Object.keys(body).sort(),['action','args']);
    const id=String(++jobs);let result={assistant:{}};
    if(body.action==='codex-models')result={assistant:{models:[{id:'fixture',name:'Fixture',defaultModel:true,defaultEffort:'medium',efforts:[{reasoningEffort:'medium'}]}]}};
    if(body.action==='codex-account')result={assistant:{authenticated:process.env.ASSISTANT_TEST_AUTH!=='missing'}};
    if(body.action==='codex-connections')result={assistant:{connections:[{name:'dashboard_assistant',status:'available',toolCount:12,authStatus:'unsupported'}]}};
    if(body.action==='codex-run'){
      assert.equal(body.args.mode,'danger-full-access');
      if(running)return {id:'active',state:'RUNNING',events:[]};
      result=reply;
    }
    return {id,state:'SUCCEEDED',events:[],result};
  }
  throw Error('Unexpected API: '+url);
};
const helpers={api,escape,toast:()=>{},editor:()=>{},confirmAction:async()=>true};
for(const file of ['codex-usage.js','studio-codex.js','assistant.js'])w.eval(fs.readFileSync(path.join(root,'src/main/resources/static/js',file),'utf8'));
const tick=()=>new Promise(resolve=>setTimeout(resolve,30));
(async()=>{
  w.WorkspaceAssistant.init(helpers);await tick();
  assert.deepEqual(calls.filter(call=>call.url==='/assistant/jobs').map(call=>call.body.action),['codex-models','codex-account','codex-connections'],'Opening Home must check tools and cached authentication without login or a model turn');
  assert.equal(d.querySelector('[data-assistant-mcp]').textContent,'MCP 도구 12개 사용 가능');
  if(process.env.ASSISTANT_TEST_AUTH==='missing'){
    assert.equal(d.querySelector('[data-assistant="login"]').hidden,false,'Missing authentication must keep login available');
    assert.equal(d.querySelector('#assistant-studio-auth-cta').hidden,false);
    console.log('Missing authentication keeps login available without automatic device login.');dom.window.close();return;
  }
  assert.equal(d.querySelector('[data-assistant="login"]').hidden,true,'Cached authentication must hide the login button');
  assert.equal(d.querySelector('[data-assistant-today] img'),null,'Calendar titles must be text');
  const card=d.querySelector('.assistant-shell'),input=d.querySelector('#assistant-studio-prompt');
  assert.ok(input);assert.equal(d.querySelector('#studio-prompt'),null);
  d.querySelector('[data-assistant="connect"]').click();await tick();
  assert.equal(d.querySelector('#assistant-studio-auth').textContent,'연결됨');
  d.querySelector('[data-assistant-prompt]').click();assert.match(input.value,/오늘 일정/);
  input.value='보고서 찾아줘';d.querySelector('#assistant-studio-prompt-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
  const links=[...d.querySelectorAll('#assistant-studio-conversation a')];
  assert.equal(links.length,2);assert.match(links[0].href,/\/api\/v1\/cloud\/content/);
  assert.equal(links[1].rel,'noopener noreferrer');assert.equal(links[1].target,'_blank');
  assert.equal(d.querySelector('#assistant-studio-conversation img'),null);
  w.WorkspaceAssistant.open('assistant');assert.equal(card.parentElement.id,'assistant');
  assert.equal(d.querySelector('#assistant-studio-prompt'),input,'Expanding must preserve the conversation instance');
  w.WorkspaceAssistant.open('home');assert.equal(card.parentElement.id,'assistant-home');
  const ide=d.createElement('div');ide.id='studio-codex';d.querySelector('#studio').append(ide);
  w.StudioCodex(ide,{...helpers,project:()=>({deviceId:'local',root:'/app/data/files/project'}),busy:()=>false,setBusy:()=>{},dirty:()=>false,confirm:async()=>true,context:()=>null,publish:()=>{},auth:()=>{}});
  const identifiers=[...d.querySelectorAll('[id]')].map(element=>element.id);assert.equal(new Set(identifiers).size,identifiers.length,'IDE and assistant must not duplicate DOM IDs');
  running=true;input.value='다음 요청';d.querySelector('#assistant-studio-prompt-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await tick();
  input.value='파일 범위를 좁혀줘';input.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));await tick();
  assert.ok(calls.some(call=>call.url.endsWith('/inputs')&&call.body.type==='steer'));
  card.querySelector('[data-cx="stop"]').click();await tick();
  assert.ok(calls.some(call=>call.url.endsWith('/inputs')&&call.body.type==='interrupt'));
  assert.equal(calls.filter(call=>call.url==='/assistant/jobs'&&call.body.action==='codex-run').length,2,'Steering must not start another turn');
  console.log('Assistant home, safe links, independent IDE IDs, steering and interrupt passed.');dom.window.close();
})().catch(error=>{console.error(error);dom.window.close();process.exitCode=1;});
