/* SiteGit Concept Prototype
 * Static, offline-capable, localStorage-based concept UI.
 * Public project figures are derived from the uploaded Sasang-gu analysis report.
 * Manufacturer specifications are based on official HD Hyundai Construction Equipment pages.
 * Spatial geometry, autonomy API, live progress, evidence and conflicts are simulated.
 */

const STORAGE_KEY = 'sitegit-concept-prototype-v2';
const ONBOARD_KEY = 'sitegit-concept-onboarded-v2';
const PROJECT_ID = 'SASANG-001';
const API_BASE = '/api/v1';
const EQUIPMENT_PHOTOS = {
  HX210AL:'/static/assets/equipment/hx210al.jpg',
  HX48AZ:'/static/assets/equipment/hx48az.jpg',
  'HL930A TM':'/static/assets/equipment/hl930a-tm.jpg',
  'Generic Dump 4.5t':'/static/assets/equipment/generic-dump-4-5t.png',
  'Generic Dump 24t':'/static/assets/equipment/generic-dump-24t.png',
};
let remoteRevision = null;
let remoteReady = false;
let remoteApplying = false;
let remoteSaveInFlight = false;
let remoteSaveTimer = null;
let remoteSocket = null;
let remoteCanEdit = true;
let currentUser = null;
// Isaac 지시·Commit은 DB 테이블이라 공동 state payload에 들어 있지 않습니다.
// 별도로 받아 두고 대시보드 카드에서만 사용합니다.
let isaacInstructions = [];
let aiWorkPackageDraft = null;
let stageInventory = {connected:false,equipment:[],diggable_targets:[],age_seconds:0};

const DEFAULT_STATE = {
  selectedPage: 'dashboard',
  selectedWpId: 'WP-SASANG-C01',
  manager: { name: '김현장', role: '현장관리자' },
  company: {
    name: 'HDMI 스마트건설 실증팀',
    contractor: '한빛건설(데모)',
    manufacturer: 'HD현대 건설기계',
  },
  project: {
    name: '사상구 감전처리분구 하수관로 정비사업',
    shortName: '사상구 감전처리분구',
    location: '부산광역시 사상구 감전동',
    scope: 'D80–200 mm · L=537.1 m · 배수설비 70가구',
    startDate: '2024-12-05',
    endDate: '2025-10-30',
    totalCost: 1742700000,
    contractCost: 1593790000,
    netCost: 557351145,
    earthworkCost: 248343950,
    earthworkShare: 44.6,
    excavationVolume: 2279,
    coordinateSystem: '현장 로컬 좌표계 — 관리자 확인 필요',
    sourceType: 'PUBLIC PROJECT DATA',
  },
  readiness: [
    { id:'coord', name:'현장 좌표계', category:'현장 기준', grade:'A', status:'needs-confirmation', source:'USER INPUT', value:'현장 로컬 좌표계', action:'배포 전 관리자 확인', desc:'모든 작업영역과 장비 위치를 동일 기준으로 연결합니다.' },
    { id:'zone', name:'작업구역 Geometry', category:'작업지시', grade:'A', status:'simulated', source:'SIMULATED', value:'Zone A–D · 537.1m 데모 분할', action:'컨셉 배포 가능', desc:'실제 GIS 좌표가 없어 공개 연장을 4개 Zone으로 가상 분할했습니다.' },
    { id:'quantity', name:'목표 작업량', category:'작업지시', grade:'A', status:'ready', source:'PUBLIC PROJECT', value:'터파기 2,279㎥', action:'정상', desc:'사상구 설계·도급 내역에서 확인한 전체 터파기 물량입니다.' },
    { id:'restricted', name:'금지·보호구역', category:'안전 제약', grade:'A', status:'needs-confirmation', source:'USER INPUT', value:'도로 점유구역 1개 · 매설물 미확인', action:'조건부 배포', desc:'자율화 장비가 반드시 회피해야 할 공간 제약입니다.' },
    { id:'baseline', name:'작업 전 기준 형상', category:'결과 검토', grade:'B', status:'simulated', source:'SIMULATED', value:'Synthetic baseline surface v1', action:'자동 비교 활성', desc:'실제 PCD 대신 가상 기준면을 사용합니다.' },
    { id:'tolerance', name:'허용오차·완료기준', category:'결과 검토', grade:'B', status:'needs-confirmation', source:'ASSUMED', value:'깊이 ±50mm · 관측률 90%', action:'관리자 승인 필요', desc:'공식 현장 기준이 아니라 컨셉 검증용 가정값입니다.' },
    { id:'evidence', name:'필수 Evidence', category:'결과 검토', grade:'B', status:'ready', source:'STANDARD-BASED', value:'Pose · Tool path · Before/After · Events', action:'정상', desc:'장비의 완료 선언을 검토하기 위한 반환 데이터 항목입니다.' },
    { id:'spec', name:'장비 Capability', category:'장비 연동', grade:'C', status:'ready', source:'MANUFACTURER SPEC', value:'HD 공식 공개 제원 3종', action:'적합성 판정 가능', desc:'공개 제원과 자율화 인터페이스 가정을 구분해 관리합니다.' },
    { id:'route', name:'권장 이동경로', category:'운영 효율', grade:'C', status:'missing', source:'USER INPUT', value:'미제공', action:'경고 후 진행 가능', desc:'장비 자율화 시스템이 자체 경로를 생성할 수 있다고 가정합니다.' },
    { id:'utilities', name:'지중 매설물 정보', category:'현장 변화', grade:'D', status:'missing', source:'USER INPUT', value:'미등록', action:'현장 확인으로 대체', desc:'실제 투입 전에는 별도 확인이 필요한 데이터입니다.' },
    { id:'remote', name:'원격개입 정책', category:'현장 변화', grade:'D', status:'simulated', source:'ASSUMED', value:'중대 예외 발생 시 원격 중지', action:'컨셉 적용', desc:'실제 제조사 원격제어 정책이 아닌 데모 가정입니다.' },
  ],
  equipment: [
    {
      id:'HX210AL-01', model:'HX210AL', manufacturer:'HD Hyundai', type:'중형 굴착기', icon:'excavator', status:'available',
      operatingWeight:22.15, bucketCapacity:0.92, workBucket:0.60, power:128, maxDepth:6.64, travelSpeed:5.8,
      supports:['EXCAVATION','GRADING'], evidence:['Equipment Pose','Tool Pose','Work Events','Engine Status'],
      autonomy:['Work Package 수신','작업 상태 반환','원격 중지'], autonomySource:'ASSUMED', specSource:'MANUFACTURER SPEC',
      sourceUrl:'https://www.hyundai-ce.com/en/products/view?productsSeq=374', color:'#f3b331', assigned:'WP-SASANG-C01'
    },
    {
      id:'HX48AZ-02', model:'HX48AZ', manufacturer:'HD Hyundai', type:'소형 굴착기', icon:'excavator', status:'available',
      operatingWeight:5.03, bucketCapacity:0.15, workBucket:0.15, power:29.1, maxDepth:3.50, travelSpeed:4.4,
      supports:['SMALL_EXCAVATION','UTILITY'], evidence:['Equipment Pose','Tool Pose','Work Events'],
      autonomy:['Work Package 수신','작업 상태 반환'], autonomySource:'ASSUMED', specSource:'MANUFACTURER SPEC',
      sourceUrl:'https://www.hyundai-ce.com/en/products/view?productsSeq=573', color:'#f0aa2c', assigned:'WP-SASANG-B01'
    },
    {
      id:'HL930ATM-01', model:'HL930A TM', manufacturer:'HD Hyundai', type:'휠 로더', icon:'loader', status:'standby',
      operatingWeight:11.96, bucketCapacity:1.70, workBucket:1.70, power:96, maxDepth:0, travelSpeed:39.5,
      supports:['LOADING','STOCKPILE','HAUL_SUPPORT'], evidence:['Equipment Pose','Cycle Events','Engine Status'],
      autonomy:['작업 패키지 수신','적재 사이클 반환'], autonomySource:'ASSUMED', specSource:'MANUFACTURER SPEC',
      sourceUrl:'https://www.hyundai-ce.com/en/products/view?productsSeq=510', color:'#eaa52a', assigned:'WP-HAUL-01'
    },
    {
      id:'DUMP45-01', model:'Generic Dump 4.5t', manufacturer:'Fleet Partner', type:'덤프트럭', icon:'dump', status:'working',
      operatingWeight:4.5, bucketCapacity:0, workBucket:0, power:0, maxDepth:0, travelSpeed:80,
      supports:['HAUL'], evidence:['Vehicle Pose','Trip Events','Payload Estimate'],
      autonomy:['배차 명령 수신','운반 이벤트 반환'], autonomySource:'ASSUMED', specSource:'PROJECT REQUIREMENT',
      sourceUrl:'', color:'#4d9ab5', assigned:'WP-HAUL-01'
    },
    {
      id:'DUMP24-01', model:'Generic Dump 24t', manufacturer:'Fleet Partner', type:'대형 덤프트럭', icon:'dump', status:'offline',
      operatingWeight:24, bucketCapacity:0, workBucket:0, power:0, maxDepth:0, travelSpeed:70,
      supports:['HAUL','DISPOSAL'], evidence:['Vehicle Pose','Trip Events','Payload Estimate'],
      autonomy:['배차 명령 수신','운반 이벤트 반환'], autonomySource:'ASSUMED', specSource:'PROJECT REQUIREMENT',
      sourceUrl:'', color:'#5f7d92', assigned:''
    },
  ],
  workPackages: [
    { id:'WP-SASANG-A01', zone:'A', name:'본관 터파기 — 서측 구간', task:'EXCAVATION', length:120, target:420, raw:100, qualified:100, remaining:0, status:'accepted', version:1, eta:'완료', risk:'low', start:'08:20', end:'11:40', x:104, y:278, width:190, color:'#2d9477', completionThreshold:100, observationThreshold:90, toleranceMm:50, assignments:[{id:'AS-A-1',equipmentId:'HX210AL-01',role:'주 작업',quantity:1}] },
    { id:'WP-SASANG-B01', zone:'B', name:'배수설비 소구경 굴착', task:'SMALL_EXCAVATION', length:140, target:590, raw:42, qualified:37, remaining:372, status:'executing', version:1, eta:'3h 20m', risk:'medium', start:'10:05', end:'-', x:294, y:258, width:205, color:'#159f96', completionThreshold:100, observationThreshold:90, toleranceMm:50, assignments:[{id:'AS-B-1',equipmentId:'HX48AZ-02',role:'주 작업',quantity:1}] },
    { id:'WP-SASANG-C01', zone:'C', name:'본관 터파기 — 교차로 구간', task:'EXCAVATION', length:140, target:639, raw:78, qualified:69, remaining:198, status:'review', version:1, eta:'검토 중', risk:'high', start:'09:10', end:'14:42', x:499, y:238, width:207, color:'#e5a832', completionThreshold:100, observationThreshold:90, toleranceMm:50, assignments:[{id:'AS-C-1',equipmentId:'HX210AL-01',role:'주 작업',quantity:1},{id:'AS-C-2',equipmentId:'DUMP45-01',role:'운반',quantity:5}] },
    { id:'WP-SASANG-D01', zone:'D', name:'본관 터파기 — 동측 구간', task:'EXCAVATION', length:137.1, target:630, raw:0, qualified:0, remaining:630, status:'ready', version:1, eta:'대기', risk:'low', start:'-', end:'-', x:706, y:218, width:194, color:'#3d7fa0', completionThreshold:100, observationThreshold:90, toleranceMm:50, assignments:[{id:'AS-D-1',equipmentId:'HX210AL-01',role:'주 작업',quantity:1}] },
    { id:'WP-HAUL-01', zone:'H', name:'가적치장 반출·운반', task:'HAUL', length:0, target:700, raw:33, qualified:33, remaining:469, status:'executing', version:1, eta:'5h 10m', risk:'medium', start:'09:35', end:'-', x:0, y:0, width:0, color:'#4d9ab5', completionThreshold:100, observationThreshold:85, toleranceMm:0, assignments:[{id:'AS-H-1',equipmentId:'HL930ATM-01',role:'상차',quantity:1},{id:'AS-H-2',equipmentId:'DUMP45-01',role:'운반',quantity:5}] },
  ],
  evidence: {
    'WP-SASANG-A01': { rule:100, completeness:100, confidence:94, observation:96, workFinished:true, resultDeviationMm:22, overcutVolume:0, state:'accepted', missing:[], conflicts:[], externalEvidence:[{id:'EXT-A01',type:'현장관리자 확인',performer:'김현장',time:'11:42',target:'Zone A 전체',result:'완료 확인',accuracy:'관리자 확인',attachment:'zone-a-check.jpg'}] },
    'WP-SASANG-B01': { rule:96, completeness:62, confidence:78, observation:74, workFinished:false, resultDeviationMm:0, overcutVolume:0, state:'collecting', missing:['작업 종료 이벤트','After Surface'], conflicts:[], externalEvidence:[] },
    'WP-SASANG-C01': { rule:94, completeness:82, confidence:68, observation:76, workFinished:true, resultDeviationMm:78, overcutVolume:9, state:'additional-check', missing:['남측 12% 구역 관측 데이터','외부 확인 기록'], conflicts:[], externalEvidence:[] },
    'WP-SASANG-D01': { rule:0, completeness:25, confidence:0, observation:0, workFinished:false, resultDeviationMm:0, overcutVolume:0, state:'not-started', missing:['Execution Session','Result Evidence'], conflicts:[], externalEvidence:[] },
    'WP-HAUL-01': { rule:98, completeness:58, confidence:81, observation:82, workFinished:false, resultDeviationMm:0, overcutVolume:0, state:'collecting', missing:['운반 종료 이벤트'], conflicts:[], externalEvidence:[] },
  },
  events: [
    { time:'17:42', type:'warning', title:'Zone C 추가 확인 필요', desc:'남측 12% 구역의 관측 데이터가 누락되었습니다.' },
    { time:'17:36', type:'success', title:'Zone A 결과 승인', desc:'Evidence Bundle EB-A02가 Plan v1 기준 상태에 반영되었습니다.' },
    { time:'17:21', type:'info', title:'HX48AZ 작업 상태 수신', desc:'WP-SASANG-B01 Raw Progress 42% · ETA 3h 20m' },
    { time:'16:58', type:'danger', title:'Acceptance Conflict 생성', desc:'WP-SASANG-C01 결과 인수 전 관리자 검토가 필요합니다.' },
    { time:'16:42', type:'info', title:'Work Commit 수신', desc:'HX210AL-01이 작업 종료 이벤트와 결과 패키지를 제출했습니다.' },
  ],
  versions: [
    { type:'site', code:'Site Base v1', title:'사상구 공개 발주 데이터 등록', desc:'공사규모, 물량, 장비 산출조건과 가상 Zone geometry를 결합했습니다.', time:'08:10', actor:'SiteGit', state:'done' },
    { type:'plan', code:'Plan v1.0', title:'자율화 작업계획 발행', desc:'Zone A–D를 Work Package로 분할하고 장비 요구조건을 연결했습니다.', time:'08:18', actor:'김현장', state:'done' },
    { type:'work', code:'WP-SASANG-A01 v1', title:'Zone A 작업 완료', desc:'HX210AL-01 작업 결과가 승인되어 기준 상태에 반영됐습니다.', time:'11:45', actor:'HX210AL-01', state:'success' },
    { type:'work', code:'WP-SASANG-C01 v1', title:'Zone C Immediate Commit', desc:'품질 유효 진척률 69%, 잔여 198㎥, 관측 누락 12%.', time:'14:42', actor:'HX210AL-01', state:'warning', branch:true },
    { type:'evidence', code:'EB-C01', title:'추가 확인 대기', desc:'관리자 확인 또는 외부 Evidence 추가 후 인수 여부를 결정합니다.', time:'17:42', actor:'SiteGit', state:'current', branch:true },
  ],
  simulation: { running:false, stage:5, selectedScenario:'conflict' },
};

let state = loadState();
let onboardingStep = 0;
let simTimer = null;

const PAGE_META = {
  dashboard: ['AUTONOMOUS WORK ASSURANCE','통합 관리자 Control Center'],
  readiness: ['WORK PACKAGE PRE-CHECK','작업지시 준비 확인'],
  workpackages: ['PLAN TO MACHINE LANGUAGE','Work Package 관리'],
  equipment: ['SITEGIT READY EQUIPMENT','장비 Registry & Capability'],
  evidence: ['EVIDENCE & TRUST','결과 검토·인수 판단'],
  versions: ['VERSION & AUDIT','작업 Version 이력'],
  settings: ['PROJECT CONFIGURATION','설정·데이터 관리'],
};

function deepClone(obj){ return JSON.parse(JSON.stringify(obj)); }
function safeGetItem(key){ try{return localStorage.getItem(key)}catch(e){return null} }
function safeSetItem(key,value){ try{localStorage.setItem(key,value);return true}catch(e){return false} }
function safeRemoveItem(key){ try{localStorage.removeItem(key)}catch(e){} }
function loadState(){
  try{
    const saved = safeGetItem(STORAGE_KEY);
    if(saved){
      const parsed = JSON.parse(saved);
      return mergeDefaults(deepClone(DEFAULT_STATE), parsed);
    }
  }catch(e){ console.warn('State load failed',e); }
  return deepClone(DEFAULT_STATE);
}
function mergeDefaults(base, saved){
  if(!saved || typeof saved !== 'object') return base;
  Object.keys(saved).forEach(k=>{
    if(Array.isArray(saved[k])) base[k]=saved[k];
    else if(saved[k] && typeof saved[k]==='object' && base[k] && typeof base[k]==='object' && !Array.isArray(base[k])) base[k]=mergeDefaults(base[k],saved[k]);
    else base[k]=saved[k];
  });
  return base;
}
function saveState(){
  safeSetItem(STORAGE_KEY,JSON.stringify(state));
  scheduleRemoteSave();
}
function updateSyncIndicator(label,tone='online'){
  const el=$('#syncIndicator');
  if(!el)return;
  el.className=`sync-indicator ${tone}`;
  el.innerHTML=`<span></span>${esc(label)}`;
}
async function apiFetch(path,options={}){
  const response=await fetch(`${API_BASE}${path}`,{
    credentials:'same-origin',
    headers:{'Content-Type':'application/json',...(options.headers||{})},
    ...options,
  });
  if(response.status===401){location.href='/login';throw new Error('AUTH_REQUIRED')}
  return response;
}
function scheduleRemoteSave(){
  if(!remoteReady||remoteApplying||!remoteCanEdit)return;
  clearTimeout(remoteSaveTimer);
  remoteSaveTimer=setTimeout(pushRemoteState,800);
}
async function pushRemoteState(){
  if(remoteSaveInFlight||!remoteReady||remoteApplying||!remoteCanEdit)return;
  remoteSaveInFlight=true;
  updateSyncIndicator('저장 중','syncing');
  try{
    const response=await apiFetch(`/state/${PROJECT_ID}`,{
      method:'PUT',
      body:JSON.stringify({payload:state,revision:remoteRevision,source:'web'}),
    });
    if(response.status===403){
      remoteCanEdit=false;
      updateSyncIndicator('조회 전용','readonly');
      return;
    }
    if(response.status===409){
      updateSyncIndicator('동시 수정 감지','warning');
      toast('공동 데이터가 먼저 변경됨','최신 상태를 다시 불러옵니다.','warning');
      await pullRemoteState();
      return;
    }
    if(!response.ok)throw new Error(`SAVE_${response.status}`);
    const data=await response.json();
    remoteRevision=data.revision;
    updateSyncIndicator(`공동 DB · r${remoteRevision}`,'online');
  }catch(error){
    if(error.message!=='AUTH_REQUIRED'){
      console.warn('Remote save failed',error);
      updateSyncIndicator('서버 연결 끊김','offline');
    }
  }finally{
    remoteSaveInFlight=false;
  }
}
async function pullRemoteState(){
  const response=await apiFetch(`/state/${PROJECT_ID}`);
  if(!response.ok)throw new Error(`LOAD_${response.status}`);
  const data=await response.json();
  remoteApplying=true;
  state=mergeDefaults(deepClone(DEFAULT_STATE),data.payload||{});
  remoteRevision=data.revision;
  renderAll();
  remoteApplying=false;
  updateSyncIndicator(`공동 DB · r${remoteRevision}`,'online');
}
function connectRealtime(){
  if(remoteSocket)try{remoteSocket.close()}catch(e){}
  const protocol=location.protocol==='https:'?'wss':'ws';
  remoteSocket=new WebSocket(`${protocol}://${location.host}${API_BASE}/state/ws/${PROJECT_ID}`);
  remoteSocket.addEventListener('open',()=>updateSyncIndicator(`공동 DB · r${remoteRevision??'-'}`,'online'));
  remoteSocket.addEventListener('message',async event=>{
    try{
      const message=JSON.parse(event.data);
      if(message.type==='state.updated'&&Number(message.revision)>Number(remoteRevision||0)&&!remoteSaveInFlight){
        await pullRemoteState();
        toast('공동 데이터 갱신',`${message.updated_by||'다른 사용자'}의 변경사항을 반영했습니다.`,'success');
      }
      // Isaac 지시·Commit·승인은 같은 소켓으로 알립니다. 승인된 경우에만
      // 맵 오브젝트가 바뀌므로 그때만 뷰어를 다시 읽게 합니다.
      if(message.type==='isaac.map.updated'){
        if(message.reason==='stage.inventory'){await loadStageInventory();return}
        await loadIsaacInstructions();
        if(String(message.reason||'').startsWith('review.'))reloadIsaacMapObjects();
      }
    }catch(error){console.warn('Realtime message failed',error)}
  });
  remoteSocket.addEventListener('close',()=>{
    updateSyncIndicator('재연결 대기','offline');
    setTimeout(()=>{if(document.visibilityState!=='hidden')connectRealtime()},3000);
  });
}
async function bootstrapSharedState(){
  updateSyncIndicator('공동 DB 연결 중','syncing');
  try{
    const meResponse=await apiFetch('/auth/me');
    const me=await meResponse.json();
    currentUser=me;
    remoteCanEdit=['admin','manager','reviewer'].includes(me.role);
    const roleLabel={admin:'관리자',manager:'현장관리자',reviewer:'검토자',viewer:'조회자'}[me.role]||me.role;
    const profileName=$('#topManagerName');if(profileName)profileName.textContent=me.full_name;
    const avatar=$('#profileBtn .avatar');if(avatar)avatar.textContent=(me.full_name||me.username).trim().slice(0,1).toUpperCase();
    const profile=$('#profileBtn small');if(profile)profile.textContent=roleLabel;
    await pullRemoteState();
    await loadStageInventory();
    await loadIsaacInstructions();
    remoteReady=true;
    connectRealtime();
    if(!remoteCanEdit)updateSyncIndicator('조회 전용','readonly');
  }catch(error){
    if(error.message!=='AUTH_REQUIRED'){
      console.warn('Shared bootstrap failed',error);
      updateSyncIndicator('로컬 백업 모드','offline');
      toast('공동 DB 연결 실패','브라우저의 로컬 백업 데이터로 실행합니다.','warning');
    }
  }
}
function $ (sel, root=document){ return root.querySelector(sel); }
function $$ (sel, root=document){ return [...root.querySelectorAll(sel)]; }
function num(v){ return new Intl.NumberFormat('ko-KR').format(Math.round(Number(v)||0)); }
function won(v){
  const n=Number(v)||0;
  if(n>=100000000) return `${(n/100000000).toFixed(n%100000000?1:0)}억원`;
  if(n>=10000) return `${(n/10000).toFixed(0)}만원`;
  return `${num(n)}원`;
}
function nowTime(){ return new Date().toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',hour12:false}); }
function esc(s=''){ return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function statusText(status){ return ({accepted:'결과 승인',executing:'작업 중',review:'검토 필요',ready:'배포 가능',draft:'초안',correction:'보완 작업','correction-issued':'보완 지시 발행',paused:'일시중지',dispatched:'배포됨','review-ready':'검토 가능','approval-ready':'승인 가능'}[status]||status); }
function badgeClass(status){ return ({accepted:'accepted',executing:'progress',review:'warning',ready:'info',draft:'neutral',correction:'danger','correction-issued':'warning',paused:'warning',dispatched:'info','review-ready':'info','approval-ready':'ready'}[status]||'neutral'); }
function sourceBadge(source){
  const s=String(source||'').toUpperCase();
  const cls=s.includes('PUBLIC')?'public':s.includes('MANUFACTURER')?'manufacturer':s.includes('ASSUMED')?'assumed':s.includes('SIMULATED')?'simulated':'user';
  return `<span class="origin ${cls}">${esc(source)}</span>`;
}
function readinessStatusLabel(status){ return ({ready:'준비 완료',simulated:'준비 완료','needs-confirmation':'확인 필요',missing:'누락'}[status]||status); }
const READINESS_REQUIRED_IDS=['zone','quantity','coord','restricted','baseline','tolerance','evidence'];
const READINESS_SECTIONS=[
  {key:'what',eyebrow:'WHAT TO DO',title:'작업을 정의할 수 있는가?',description:'작업 대상과 목표량이 명확해야 작업지시를 만들 수 있습니다.',ids:['zone','quantity']},
  {key:'where',eyebrow:'WHERE TO STOP',title:'작업 범위를 제한할 수 있는가?',description:'좌표 기준과 금지·보호구역이 있어야 장비의 작업 경계를 정할 수 있습니다.',ids:['coord','restricted']},
  {key:'verify',eyebrow:'HOW TO VERIFY',title:'완료 여부를 판단할 수 있는가?',description:'작업 전 기준과 허용오차, 결과 데이터가 있어야 완료 여부를 검증할 수 있습니다.',ids:['baseline','tolerance','evidence']},
];
function readinessUiStatus(item){
  if(item.status==='missing')return 'missing';
  if(item.status==='needs-confirmation')return 'review';
  return 'ready';
}
function readinessResult(){
  const required=READINESS_REQUIRED_IDS.map(id=>state.readiness.find(r=>r.id===id)).filter(Boolean);
  const counts={ready:0,review:0,missing:0};
  required.forEach(item=>counts[readinessUiStatus(item)]++);
  const canCreate=required.length===READINESS_REQUIRED_IDS.length&&!counts.review&&!counts.missing;
  const score=Math.round((counts.ready/Math.max(1,READINESS_REQUIRED_IDS.length))*100);
  return {score,stateText:canCreate?'Work Package 생성 가능':'생성 전 확인이 필요합니다',tone:canCreate?'ready':'blocked',canCreate,counts,required,issues:required.filter(item=>readinessUiStatus(item)!=='ready')};
}
function selectedWp(){ return state.workPackages.find(w=>w.id===state.selectedWpId) || state.workPackages[0]; }
function selectedEvidence(){ return state.evidence[state.selectedWpId] || {rule:0,completeness:0,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:[],conflicts:[],externalEvidence:[]}; }
function equipmentById(id){ return state.equipment.find(e=>e.id===id); }
function assignmentsForWp(wp){
  if(Array.isArray(wp.assignments)) return wp.assignments;
  if(wp.equipmentId) return [{id:`AS-${wp.id}-1`,equipmentId:wp.equipmentId,role:'주 작업',quantity:1}];
  return [];
}
function primaryAssignment(wp){return assignmentsForWp(wp).find(a=>a.role==='주 작업')||assignmentsForWp(wp)[0]||null}
function primaryEquipment(wp){const a=primaryAssignment(wp);return a?equipmentById(a.equipmentId):null}
function assignmentSummary(wp,compact=false){
  const rows=assignmentsForWp(wp);
  if(!rows.length) return '장비 미배정';
  const parts=rows.map(a=>`${equipmentById(a.equipmentId)?.model||'미등록 장비'} ×${Math.max(1,Number(a.quantity)||1)}`);
  return compact&&parts.length>2?`${parts.slice(0,2).join(' · ')} 외 ${parts.length-2}`:parts.join(' · ');
}
function assignmentRoleSummary(wp){return assignmentsForWp(wp).map(a=>`${a.role} ${equipmentById(a.equipmentId)?.model||'미등록'} ×${a.quantity||1}`).join(' / ')||'미배정'}
function equipmentPlannedQuantity(equipmentId){return state.workPackages.reduce((sum,w)=>sum+assignmentsForWp(w).filter(a=>a.equipmentId===equipmentId).reduce((s,a)=>s+(Number(a.quantity)||1),0),0)}
function taskForRole(wp,role){if(role==='운반')return 'HAUL';if(role==='상차'||role==='보조')return 'LOADING';return wp.task}
function assignmentCompatibility(wp,a){
  const eq=equipmentById(a.equipmentId); if(!eq)return {ok:false,label:'장비 정보 없음'};
  const task=taskForRole(wp,a.role);
  const ok=eq.supports.includes(task)||(task==='EXCAVATION'&&eq.supports.includes('SMALL_EXCAVATION'))||(task==='LOADING'&&eq.supports.includes('HAUL_SUPPORT'));
  return {ok,label:ok?'적합':'조건부/부적합'};
}
function approvalGate(wp,ev){
  const conflicts=ev.conflicts||[];
  const threshold=Number(wp.completionThreshold??100);
  const observationThreshold=Number(wp.observationThreshold??90);
  const tolerance=Number(wp.toleranceMm??50);
  const checks=[
    {key:'finished',label:'장비 작업 종료 이벤트',ok:!!ev.workFinished,note:ev.workFinished?'수신 완료':'작업 종료 전'},
    {key:'progress',label:`Qualified Progress ${threshold}%`,ok:Number(wp.qualified)>=threshold&&Number(wp.remaining)<=0,note:`${wp.qualified}% · 잔여 ${num(wp.remaining)}㎥`},
    {key:'result',label:`결과 허용오차 ±${tolerance}mm`,ok:Number(ev.resultDeviationMm||0)<=tolerance&&Number(ev.overcutVolume||0)<=0,note:`최대 편차 ${num(ev.resultDeviationMm||0)}mm · 과굴착 ${num(ev.overcutVolume||0)}㎥`},
    {key:'rule',label:'Hard Rule 통과',ok:Number(ev.rule)>=90,note:`Rule ${ev.rule}%`},
    {key:'evidence',label:'Evidence 완결성 95% 이상',ok:Number(ev.completeness)>=95,note:`${ev.completeness}%`},
    {key:'observation',label:`관측률 ${observationThreshold}%·신뢰도 85% 이상`,ok:Number(ev.observation)>=observationThreshold&&Number(ev.confidence)>=85,note:`관측 ${ev.observation}% · 신뢰 ${ev.confidence}%`},
    {key:'conflict',label:'Blocking Conflict 0건',ok:conflicts.length===0,note:`미해결 ${conflicts.length}건`},
  ];
  return {ready:checks.every(c=>c.ok),checks};
}
function recomputeConflicts(wp,ev){
  if(!ev){return []}
  const conflicts=[];
  const completionThreshold=Number(wp.completionThreshold??100);
  const observationThreshold=Number(wp.observationThreshold??90);
  const tolerance=Number(wp.toleranceMm??50);
  if(ev.workFinished&&(Number(wp.qualified)<completionThreshold||Number(wp.remaining)>0)){
    conflicts.push({id:`PC-${wp.id}`,type:'Progress Conflict',severity:'high',category:'physical',title:`품질 유효 잔여량 ${num(wp.remaining)}㎥`,desc:`Qualified Progress ${wp.qualified}%로 완료조건 ${completionThreshold}%를 충족하지 못했습니다.`,impact:'보완 Work Package 필요'});
  }
  if(ev.workFinished&&(Number(ev.resultDeviationMm||0)>tolerance||Number(ev.overcutVolume||0)>0)){
    conflicts.push({id:`RC-${wp.id}`,type:'Result Conflict',severity:'high',category:'physical',title:`결과 형상 허용기준 미달`,desc:`최대 편차 ${num(ev.resultDeviationMm||0)}mm(기준 ±${tolerance}mm), 과굴착 ${num(ev.overcutVolume||0)}㎥가 확인됐습니다.`,impact:'물리적 보완·재검토'});
  }
  const acceptanceIssue=ev.workFinished&&(Number(ev.completeness)<95||Number(ev.confidence)<85||Number(ev.observation)<observationThreshold||(ev.missing||[]).length>0);
  if(acceptanceIssue){
    conflicts.push({id:`AC-${wp.id}`,type:'Acceptance Conflict',severity:'medium',category:'evidence',title:'인수 판단 근거 부족',desc:`Evidence ${ev.completeness}%, 관측 ${ev.observation}%, 신뢰도 ${ev.confidence}%입니다. 추가 확인 결과가 필요합니다.`,impact:'추가 확인 결과 등록'});
  }
  ev.conflicts=conflicts;
  if(ev.state!=='accepted'){
    const gate=approvalGate(wp,ev);
    if(gate.ready){ev.state='approval-ready';wp.status='approval-ready'}
    else if(wp.status!=='correction-issued'&&ev.workFinished){ev.state=acceptanceIssue?'additional-check':'review';wp.status='review'}
  }
  return conflicts;
}
function prepareState(){
  state.workPackages.forEach(w=>{
    w.assignments=assignmentsForWp(w);
    w.completionThreshold=Number(w.completionThreshold??100);w.observationThreshold=Number(w.observationThreshold??90);w.toleranceMm=Number(w.toleranceMm??50);
    const ev=state.evidence[w.id];if(ev){ev.externalEvidence=Array.isArray(ev.externalEvidence)?ev.externalEvidence:[];ev.workFinished=!!ev.workFinished;ev.resultDeviationMm=Number(ev.resultDeviationMm||0);ev.overcutVolume=Number(ev.overcutVolume||0);if(ev.state!=='accepted')recomputeConflicts(w,ev)}
  });
}
function allExcavationWps(){ return state.workPackages.filter(w=>!['HAUL','PLACE_CUBE'].includes(w.task)); }
function totalQualified(){ return allExcavationWps().reduce((s,w)=>s+w.target*w.qualified/100,0); }
function totalRaw(){ return allExcavationWps().reduce((s,w)=>s+w.target*w.raw/100,0); }
function totalTarget(){ return allExcavationWps().reduce((s,w)=>s+w.target,0); }
function totalRemaining(){ return Math.max(0,totalTarget()-totalQualified()); }
function activeCount(){ return state.workPackages.filter(w=>['executing','review','correction','dispatched'].includes(w.status)).length; }
function alertCount(){ return Object.values(state.evidence).reduce((s,e)=>s+(e.conflicts?.length||0),0); }
function acceptedCount(){ return state.workPackages.filter(w=>w.status==='accepted').length; }

function machineSvg(type='excavator',color='#f0ad2e'){
  if(type==='loader') return `<svg class="machine-svg" viewBox="0 0 240 130" aria-hidden="true"><g fill="none" stroke="#223a46" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"><circle cx="70" cy="100" r="23" fill="#273f4c"/><circle cx="174" cy="100" r="27" fill="#273f4c"/><circle cx="70" cy="100" r="10" fill="#91a5af"/><circle cx="174" cy="100" r="12" fill="#91a5af"/><path d="M62 78h116l-17-39h-50L88 78z" fill="${color}"/><path d="M112 39v39M120 46h35l11 26h-54" fill="#b9e5ef"/><path d="M178 74l33-18 15 12-23 25-25 2z" fill="${color}"/><path d="M181 76l-30-29"/><path d="M54 78h135"/></g></svg>`;
  if(type==='dump') return `<svg class="machine-svg" viewBox="0 0 250 130" aria-hidden="true"><g fill="none" stroke="#203944" stroke-width="5" stroke-linejoin="round"><circle cx="65" cy="103" r="22" fill="#263f4d"/><circle cx="184" cy="103" r="22" fill="#263f4d"/><circle cx="65" cy="103" r="9" fill="#9bb0b9"/><circle cx="184" cy="103" r="9" fill="#9bb0b9"/><path d="M34 77h179v25H34z" fill="${color}"/><path d="M36 74l18-33h42l13 36" fill="${color}"/><path d="M52 45h31l9 25H42z" fill="#bfe5ee"/><path d="M112 31h113l-23 54h-90z" fill="${color}"/><path d="M118 38h96"/><path d="M35 101h177"/></g></svg>`;
  return `<svg class="machine-svg" viewBox="0 0 250 140" aria-hidden="true"><g fill="none" stroke="#213944" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"><rect x="27" y="102" width="134" height="25" rx="12" fill="#293f4a"/><circle cx="53" cy="114" r="8" fill="#9aadb5"/><circle cx="82" cy="114" r="8" fill="#9aadb5"/><circle cx="111" cy="114" r="8" fill="#9aadb5"/><circle cx="140" cy="114" r="8" fill="#9aadb5"/><path d="M59 99h87l-8-45H84z" fill="${color}"/><path d="M91 57h32l10 33H82z" fill="#b9e4ee"/><path d="M130 57l36-31 39 8"/><path d="M166 26l50 45"/><path d="M216 71l-14 37 28 4 10-30z" fill="${color}"/><path d="M141 96l25-70" stroke="${color}" stroke-width="13"/><path d="M166 28l49 43" stroke="${color}" stroke-width="12"/><path d="M55 99h100"/></g></svg>`;
}
function miniMachineSvg(type,color='#f2b338'){
  if(type==='dump') return `<svg viewBox="0 0 48 30"><path fill="${color}" d="M4 15h30v8H4zM18 6h23l-5 12H18zM7 9h8l4 8H4z"/><circle cx="12" cy="25" r="4" fill="#29414d"/><circle cx="32" cy="25" r="4" fill="#29414d"/></svg>`;
  if(type==='loader') return `<svg viewBox="0 0 48 30"><path fill="${color}" d="M6 12h25l5 11H6zM31 15l13-7 3 5-11 10z"/><circle cx="13" cy="24" r="5" fill="#29414d"/><circle cx="33" cy="24" r="5" fill="#29414d"/></svg>`;
  return `<svg viewBox="0 0 48 30"><path fill="${color}" d="M6 18h22v7H6zM11 9h14l3 10H9zM23 10l9-7 10 2-1 3-8-1-6 11z"/><circle cx="12" cy="26" r="3" fill="#29414d"/><circle cx="23" cy="26" r="3" fill="#29414d"/></svg>`;
}

function renderAll(){
  prepareState();
  renderHeader();
  renderDashboard();
  // renderDashboard가 page.innerHTML을 갈아끼우므로 Isaac 카드는 그 뒤에 채웁니다.
  renderIsaacPanel();
  renderReadiness();
  renderWorkPackages();
  renderEquipment();
  applyOfficialEquipmentPhotos();
  renderEvidence();
  renderVersions();
  renderSettings();
  applyPage();
  saveState();
}
function renderHeader(){
  const meta=PAGE_META[state.selectedPage]||PAGE_META.dashboard;
  $('#pageEyebrow').textContent=meta[0];
  $('#pageTitle').textContent=meta[1];
  $('#topManagerName').textContent=currentUser?.full_name||state.manager.name;
  const notificationBadge=$('#notificationsBtn .tiny-badge');
  if(notificationBadge){const count=Math.min(alertCount(),99);notificationBadge.textContent=count;notificationBadge.classList.toggle('hidden',count===0)}
  $('#navAlertBadge').textContent=alertCount();
  $('#projectMini').innerHTML=`<span class="pulse-dot"></span><div><strong>${esc(state.project.shortName)}</strong><small>Plan v1.0 · Shared Local DB</small></div>`;
  $$('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===state.selectedPage));
}
function applyPage(){
  $$('.page').forEach(p=>p.classList.remove('active'));
  $(`#page-${state.selectedPage}`)?.classList.add('active');
}

function renderDashboard(){
  const r=readinessResult();
  const qualified=totalQualified();
  const raw=totalRaw();
  const qualifiedPct=Math.round(qualified/totalTarget()*100);
  const rawPct=Math.round(raw/totalTarget()*100);
  const wp=selectedWp();
  const ev=selectedEvidence();
  const isaacWaiting=isaacInstructions.filter(i=>i.status==='committed').length;
  const isaacRunning=isaacInstructions.filter(i=>['pending','dispatched'].includes(i.status)).length;
  const activeDiggable=(stageInventory.diggable_targets||[]).filter(item=>item.active!==false).length;
  const page=$('#page-dashboard');
  page.innerHTML=`
    <div class="project-hero">
      <div class="hero-grid">
        <div>
          <div class="hero-kicker">SASANG-GU AUTONOMOUS WORK DEMO · PLAN V1.0</div>
          <h2>${esc(state.project.name)}</h2>
          <p>시공계획을 자율화 장비의 Work Package로 전달하고, 장비 결과를 검토 가능한 Evidence로 연결하는 SiteGit Core 컨셉입니다.</p>
          <div class="hero-meta">
            <span><b>공사범위</b>${esc(state.project.scope)}</span>
            <span><b>공사기간</b>${state.project.startDate} — ${state.project.endDate}</span>
            <span><b>총 터파기</b>${num(state.project.excavationVolume)}㎥</span>
          </div>
        </div>
        <div class="hero-right">
          <div class="hero-status">
            <div class="hero-status-ring" style="--pct:${r.score}%"><b>${r.score}</b></div>
            <div><strong>${r.stateText}</strong><small>필수 데이터 2건 관리자 확인<br/>시뮬레이션 기반 결과검토 활성</small></div>
          </div>
        </div>
      </div>
    </div>

    <div class="kpi-grid">
      ${kpiCard('전체 목표량',num(totalTarget()),'㎥','사상구 공개 발주 물량','▦','navy')}
      ${kpiCard('작업 진행',rawPct,'%','장비가 수행한 전체 변화량','↗','teal')}
      ${kpiCard('완료 조건 충족',qualifiedPct,'%','검증을 통과한 작업 비율','✓','teal')}
      ${kpiCard('품질 유효 잔여량',num(totalRemaining()),'㎥','목표 형상까지 남은 물량','◒','amber')}
      ${kpiCard('활성 Work Package',activeCount(),'건','작업 중·검토·보완 포함','▤','navy')}
      ${kpiCard('확인 필요 Conflict',alertCount(),'건','관리자 행동이 필요한 업무 객체','!','red')}
    </div>

    <div class="dashboard-main">
      <article class="card map-card">
        <div class="card-header">
          <div><h2>Site Work Map</h2><p>게시된 지형 Mesh 위에 관리자가 승인한 Isaac 작업 결과를 얹어 보여줍니다.</p></div>
          <div class="map-toolbar"><div class="segmented"><button class="active">Work</button><button>Evidence</button><button>Constraint</button></div><button class="ghost-button button-sm" data-action="fit-map">화면 맞춤</button></div>
        </div>
        <div class="site-map-wrap isaac-map">
          <iframe class="isaac-map-frame" src="/static/isaac-map-viewer.html" title="Isaac Sim Mud Map 3D viewer" loading="eager"></iframe>
          <div class="map-info-float">
            <div class="map-zone-title">Zone ${esc(wp.zone)} · ${esc(wp.id)}</div>
            <div class="map-zone-sub">${esc(wp.name)}</div>
            <div class="mini-progress"><span style="width:${wp.qualified}%"></span></div>
            <div class="map-stat-row"><span>진행 / 조건 충족</span><b>${wp.raw}% / ${wp.qualified}%</b></div>
            <div class="map-stat-row"><span>잔여량</span><b>${num(wp.remaining)}㎥</b></div>
            <div class="map-stat-row"><span>상태</span><b>${statusText(wp.status)}</b></div>
          </div>
          <div class="isaac-map-note">승인된 Isaac 작업 ${isaacInstructions.filter(i=>i.status==='approved').length}건 · 좌클릭 회전 · 우클릭 이동 · 휠 확대</div>
        </div>
      </article>

      <aside class="card command-card manager-console">
        <div class="card-header manager-console-head">
          <div><h2>Manager Action</h2><p>실제 Isaac 작업 발행부터 결과 승인까지</p></div>
          <span class="manager-stage-chip ${stageInventory.connected?'online':'offline'}"><i class="stage-live-dot ${stageInventory.connected?'online':'offline'}"></i>${stageInventory.connected?'STAGE LIVE':'OFFLINE'}</span>
        </div>

        <section class="manager-launch">
          <div class="manager-section-title"><div><span>REAL ISAAC</span><strong>새 Work Package</strong></div><small>${activeDiggable?`굴착 가능 토사 ${activeDiggable}개`:'굴착 대상 없음'}</small></div>
          <p class="map-work-status">${stageInventory.connected?`장비 ${stageInventory.equipment.length}대 · 활성 굴착 대상 ${activeDiggable}개`:'Isaac Runner를 실행하면 실제 Prim을 선택할 수 있습니다.'}</p>
          <button class="primary-button map-work-create" data-action="dispatch-isaac-wp" ${stageInventory.connected&&activeDiggable?'':'disabled'}>＋ 실제 작업 지시 생성</button>
        </section>

        <div class="manager-live-metrics">
          <div><span>실행 대기·중</span><b>${isaacRunning}</b></div>
          <div class="${isaacWaiting?'attention':''}"><span>승인 대기</span><b>${isaacWaiting}</b></div>
          <div><span>승인 반영</span><b>${isaacInstructions.filter(i=>i.status==='approved').length}</b></div>
        </div>

        <section class="manager-section manager-queue-section">
          <div class="manager-section-heading"><div><strong>Isaac 작업 큐</strong><small>최근 작업과 Evidence 판정</small></div><span id="isaacLoopCount" class="badge ${isaacWaiting?'warning':'info'}">${isaacWaiting?`승인 대기 ${isaacWaiting}건`:'승인 대기 없음'}</span></div>
          <div class="manager-isaac-list" id="isaacLoopList"></div>
        </section>

        <section class="manager-section selected-work-section">
          <div class="manager-section-heading"><div><strong>기존 공정 Plan (Concept)</strong><small>실제 Isaac 작업과 별도 · Zone ${esc(wp.zone)} · ${esc(wp.id)}</small></div><span class="badge ${badgeClass(wp.status)}">${statusText(wp.status)}</span></div>
          <div class="manager-selected-summary">
            <span class="equipment-mini-icon">${miniMachineSvg(primaryEquipment(wp)?.icon,primaryEquipment(wp)?.color)}</span>
            <div><strong>${esc(wp.name)}</strong><small>${esc(assignmentSummary(wp,true))}</small></div>
            <div class="manager-confidence"><b>${ev.confidence}%</b><span>Confidence</span></div>
          </div>
          <div class="manager-action-grid">
            <button class="ghost-button" data-action="edit-assignments">장비팀 배정</button>
            <button class="ghost-button" data-action="add-evidence">Evidence 등록</button>
            <button class="ghost-button" data-action="create-correction">보완 WP 발행</button>
            <button class="secondary-button" data-action="approve-result" ${approvalGate(wp,ev).ready?'':'disabled'}>결과 승인</button>
          </div>
        </section>

        <section class="manager-simulation">
          <div><div class="simulation-strip-top"><strong>Concept Simulation</strong><small>${state.simulation.running?'RUNNING':'STANDBY'}</small></div><div class="sim-steps">${[0,1,2,3,4,5,6,7].map((s,i)=>`<span class="sim-step ${i<state.simulation.stage?'done':i===state.simulation.stage?'active':''}"></span>`).join('')}</div></div>
          <button class="ghost-button button-sm" data-action="run-demo">가상 흐름 실행</button>
        </section>
      </aside>
    </div>

    <div class="dashboard-bottom">
      <article class="card">
        <div class="card-header"><div><h2>Work Package Status</h2><p>Plan Version에 연결된 작업 단위와 품질 유효 진척도</p></div><button class="ghost-button button-sm" data-page-link="workpackages">전체 보기</button></div>
        <div class="table-wrap">${workPackageTable(state.workPackages.filter(w=>w.task!=='HAUL'))}</div>
      </article>
      <article class="card">
        <div class="card-header"><div><h2>Live Audit Stream</h2><p>지시·실행·검토·승인 이벤트</p></div><span class="badge info">LOCAL LOG</span></div>
        <div class="event-list">${renderEvents(state.events.slice(0,5))}</div>
      </article>
    </div>

    `;
}
function kpiCard(label,value,unit,delta,icon,tone){return `<article class="card kpi-card ${tone}"><div class="kpi-icon">${icon}</div><div class="kpi-label">${label}</div><div class="kpi-value">${value}<span class="kpi-unit">${unit}</span></div><div class="kpi-delta">${delta}</div></article>`}
function renderSiteMap(selected){
  const zoneWps=allExcavationWps();
  const zonePolys={A:'105,302 290,282 290,321 105,342',B:'290,282 495,262 495,301 290,321',C:'495,262 702,242 702,281 495,301',D:'702,242 899,222 899,261 702,281'};
  const zoneLabels={A:[180,315],B:[380,296],C:[590,275],D:[790,254]};
  const markerPos={A:[205,270],B:[394,236],C:[594,214],D:[790,193],H:[842,365]};
  const patterns=`<defs><pattern id="dangerHatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#f5d8d8" opacity=".8"/><line x1="0" y1="0" x2="0" y2="10" stroke="#d95757" stroke-width="3"/></pattern><linearGradient id="water" x1="0" x2="1"><stop stop-color="#77b8c8"/><stop offset="1" stop-color="#9fd2db"/></linearGradient></defs>`;
  const zones=zoneWps.map(w=>`<polygon class="zone-shape ${selected.id===w.id?'selected':''}" data-wp-id="${w.id}" points="${zonePolys[w.zone]}" fill="${w.color}" stroke="${w.color}" opacity="${w.status==='ready'?.66:.88}"/><text class="map-label" x="${zoneLabels[w.zone][0]}" y="${zoneLabels[w.zone][1]}">ZONE ${w.zone}</text><text class="map-small" x="${zoneLabels[w.zone][0]-10}" y="${zoneLabels[w.zone][1]+14}">${w.qualified}% · ${num(w.remaining)}㎥</text>`).join('');
  const markers=zoneWps.flatMap(wp=>assignmentsForWp(wp).map((a,i)=>{
    const e=equipmentById(a.equipmentId);if(!e)return '';
    const [baseX,baseY]=markerPos[wp.zone]||[820,350];const x=baseX+i*62,y=baseY+i*4;
    return `<g class="machine-marker ${wp.status==='executing'?'working':''}" data-equipment-id="${e.id}" transform="translate(${x} ${y}) scale(.72)"><rect x="-23" y="-36" width="104" height="24" rx="8" fill="#0c3349" opacity=".94"/><text x="29" y="-20" text-anchor="middle" font-size="8.5" font-weight="900" fill="#fff">${e.model} ×${a.quantity||1}</text>${machineMarkerSvg(e.icon,e.color)}</g><circle class="map-radar" cx="${x+24}" cy="${y+8}" r="8"/>`;
  })).join('');
  return `<svg class="site-map-svg" viewBox="0 0 1000 445" preserveAspectRatio="xMidYMid meet">${patterns}
    <path d="M0 410L1000 310V445H0z" fill="url(#water)" opacity=".28"/>
    <polygon class="map-sidewalk" points="0,235 1000,135 1000,300 0,405"/>
    <polygon class="map-road" points="0,260 1000,160 1000,285 0,385"/>
    <line x1="0" y1="322" x2="1000" y2="222" stroke="#dbe4e8" stroke-width="4" stroke-dasharray="26 18" opacity=".8"/>
    <polygon class="map-trench-bg" points="88,295 912,210 912,270 88,356"/>
    ${zones}
    <rect class="restricted-area" x="610" y="115" width="120" height="65" rx="5" transform="rotate(-6 670 148)"/><text class="map-small" x="635" y="145">NO-GO / 매설물 확인</text>
    <g opacity=".95"><rect class="map-building" x="70" y="66" width="126" height="89" rx="4" transform="rotate(-6 133 110)"/><rect class="map-building" x="235" y="48" width="95" height="80" rx="4" transform="rotate(-6 282 88)"/><rect class="map-building" x="778" y="48" width="145" height="91" rx="4" transform="rotate(-6 850 94)"/></g>
    <g opacity=".7"><circle cx="48" cy="190" r="24" fill="#8ab39a"/><circle cx="340" cy="170" r="22" fill="#7cad8f"/><circle cx="950" cy="185" r="27" fill="#86b197"/></g>
    ${markers}
    <text x="25" y="430" class="map-small">SIMULATED GEOMETRY · NOT FOR CONSTRUCTION</text>
  </svg>`;
}
function machineMarkerSvg(type,color){
  if(type==='dump') return `<g transform="translate(-4,-5)"><path d="M0 16h46v12H0z" fill="${color}" stroke="#213a46" stroke-width="3"/><path d="M22 2h35l-8 18H22z" fill="${color}" stroke="#213a46" stroke-width="3"/><circle cx="12" cy="30" r="7" fill="#243e4a"/><circle cx="41" cy="30" r="7" fill="#243e4a"/></g>`;
  if(type==='loader') return `<g><path d="M0 15h40l8 14H0z" fill="${color}" stroke="#213a46" stroke-width="3"/><path d="M41 18l18-9 3 7-14 13z" fill="${color}" stroke="#213a46" stroke-width="3"/><circle cx="12" cy="31" r="8" fill="#243e4a"/><circle cx="42" cy="31" r="8" fill="#243e4a"/></g>`;
  return `<g><path d="M0 24h42v11H0z" fill="#243e4a"/><path d="M8 10h27l4 16H5z" fill="${color}" stroke="#213a46" stroke-width="3"/><path d="M31 13L49 0l21 5M50 2l18 22" fill="none" stroke="${color}" stroke-width="7"/><path d="M67 21l-3 16 13 2 5-13z" fill="${color}" stroke="#213a46" stroke-width="3"/></g>`;
}
function workPackageTable(wps){
  return `<table class="data-table"><thead><tr><th>Work Package</th><th>장비팀 배정</th><th>품질 유효 진척</th><th>잔여량</th><th>상태</th><th></th></tr></thead><tbody>${wps.map(w=>`<tr><td><div class="table-primary">Zone ${w.zone} · ${esc(w.name)}</div><div class="table-sub">${w.id} / v${w.version}</div></td><td><div class="table-primary">${esc(assignmentSummary(w,true))}</div><div class="table-sub">${esc(assignmentRoleSummary(w))}</div></td><td class="progress-cell"><div class="bar ${w.status==='review'?'amber':w.status==='correction'?'red':''}"><span style="width:${w.qualified}%"></span></div><div class="bar-labels"><span>Raw ${w.raw}%</span><b>${w.qualified}%</b></div></td><td><b>${num(w.remaining)}㎥</b></td><td><span class="badge ${badgeClass(w.status)}">${statusText(w.status)}</span></td><td><button class="ghost-button button-sm" data-select-wp="${w.id}">열기</button></td></tr>`).join('')}</tbody></table>`;
}
function renderEvents(events){return events.map(e=>`<div class="event-item ${e.type}"><div class="event-icon">${e.type==='success'?'✓':e.type==='danger'?'!':e.type==='warning'?'△':'↗'}</div><div><strong>${esc(e.title)}</strong><p>${esc(e.desc)}</p></div><div class="event-time">${e.time}</div></div>`).join('')}

function renderReadiness(){
  const gate=readinessResult();
  const supporting=state.readiness.filter(item=>!READINESS_REQUIRED_IDS.includes(item.id));
  $('#page-readiness').innerHTML=`
    <div class="section-heading precheck-heading"><div><h2>작업지시 준비 확인</h2><p>Work Package를 만들기 전에 작업에 필요한 현장 정보와 기준이 준비되었는지 확인합니다.</p></div><div class="section-actions"><button class="ghost-button" data-action="edit-project">현장 기본정보 수정</button><button class="primary-button" data-action="add-readiness">+ 확인 항목 추가</button></div></div>
    <nav class="precheck-process" aria-label="작업 준비 과정"><span>현장 데이터</span><i>→</i><span class="active">준비 확인</span><i>→</i><span>Work Package</span><i>→</i><span>자율장비</span></nav>
    ${readinessSummary(gate)}
    <div class="precheck-sections">${READINESS_SECTIONS.map(section=>readinessSection(section)).join('')}</div>
    <details class="card precheck-supporting"><summary><span><b>운영 보조 데이터</b><small>필수 생성 Gate에는 포함되지 않는 권장 항목 ${supporting.length}개</small></span><span>펼쳐보기</span></summary><div class="precheck-support-list">${supporting.map(item=>readinessCompactItem(item)).join('')}</div></details>
    ${readinessActionGate(gate)}`;
}
function readinessSummary(gate){
  const message=gate.canCreate?'필수 조건이 모두 준비되었습니다.':'Work Package를 만들기 전에 확인할 항목이 있습니다.';
  return `<article class="card precheck-summary ${gate.canCreate?'ready':'blocked'}"><div class="precheck-summary-icon">${gate.canCreate?'✓':'!'}</div><div class="precheck-summary-copy"><div class="eyebrow">ACTION GATE</div><h3>${gate.stateText}</h3><p>${message}</p></div><div class="precheck-counts"><div><b>${gate.counts.ready}</b><span>준비 완료</span></div><div><b>${gate.counts.review}</b><span>확인 필요</span></div><div><b>${gate.counts.missing}</b><span>누락</span></div></div><button class="${gate.canCreate?'secondary-button':'primary-button'}" data-action="${gate.canCreate?'go-work-packages':'focus-readiness-issues'}">${gate.canCreate?'Work Package로 이동':'확인 항목 보기'}</button></article>`;
}
function readinessSection(section){
  const items=section.ids.map(id=>state.readiness.find(r=>r.id===id)).filter(Boolean);
  return `<section class="card precheck-section"><header><div><div class="eyebrow">${section.eyebrow}</div><h3>${section.title}</h3><p>${section.description}</p></div><span>${items.filter(i=>readinessUiStatus(i)==='ready').length} / ${items.length} 준비</span></header><div class="precheck-items">${items.map(readinessItem).join('')}</div></section>`;
}
function readinessItem(item){
  const status=readinessUiStatus(item);
  const detail=item.status==='simulated'?'가상 데이터로 준비됨':item.value;
  return `<article class="precheck-item ${status}" data-readiness-row="${item.id}"><span class="precheck-state-icon">${status==='ready'?'✓':status==='review'?'!':'×'}</span><div class="precheck-item-copy"><div><strong>${esc(item.name)}</strong><span class="precheck-status ${status}">${readinessStatusLabel(item.status)}</span></div><p>${esc(item.desc)}</p><small>${esc(detail)}</small></div><div class="precheck-item-actions">${status!=='ready'?`<button class="secondary-button button-sm" data-edit-readiness="${item.id}">확인하기</button>`:''}<button class="ghost-button button-sm" data-readiness-source="${item.id}">출처·상세</button></div></article>`;
}
function readinessCompactItem(item){
  const status=readinessUiStatus(item);
  return `<div class="precheck-support-row"><div><strong>${esc(item.name)}</strong><small>${esc(item.desc)}</small></div><span class="precheck-status ${status}">${readinessStatusLabel(item.status)}</span><button class="ghost-button button-sm" data-readiness-source="${item.id}">출처·상세</button></div>`;
}
function readinessActionGate(gate){
  const issueText=gate.issues.map(item=>item.name).join(', ');
  return `<section class="card precheck-action-gate ${gate.canCreate?'ready':'blocked'}"><div><div class="eyebrow">WORK PACKAGE ACTION GATE</div><h3>${gate.canCreate?'작업지시를 만들 수 있습니다':'필수 확인을 마쳐야 작업지시를 만들 수 있습니다'}</h3><p>${gate.canCreate?`필수 조건 ${gate.required.length}개가 모두 준비되었습니다.`:`남은 항목: ${esc(issueText)}`}</p></div><div class="precheck-gate-actions">${!gate.canCreate?'<button class="ghost-button" data-action="focus-readiness-issues">확인 항목 처리</button>':''}<button class="primary-button" data-action="go-work-packages" ${gate.canCreate?'':'disabled'}>Work Package 만들기</button></div></section>`;
}

function renderWorkPackages(){
  if(window.SiteGitWorkPackagesPage){
    window.SiteGitWorkPackagesPage.mount($('#page-workpackages'),PROJECT_ID,state.workPackages);
    return;
  }
  $('#page-workpackages').innerHTML=`
    <div class="section-heading"><div><h2>Work Package Compiler</h2><p>자연어 지시를 검증 가능한 Work Package로 변환한 뒤 Isaac Sim 실행 대기열에 전달합니다.</p></div><div class="section-actions"><button class="ghost-button" data-action="check-all-compatibility">장비 적합성 일괄검사</button><button class="primary-button" data-action="create-wp">+ AI Work Package 생성</button></div></div>
    <div class="filter-strip"><button class="filter-chip active">전체 ${state.workPackages.length}</button><button class="filter-chip">작업 중 ${state.workPackages.filter(w=>w.status==='executing').length}</button><button class="filter-chip">검토 필요 ${state.workPackages.filter(w=>w.status==='review').length}</button><button class="filter-chip">승인 완료 ${acceptedCount()}</button></div>
    <div class="wp-grid">${state.workPackages.map(wpCard).join('')}</div>`;
}
function wpCard(w){
  const ev=state.evidence[w.id]||{};const primary=primaryEquipment(w);const gate=approvalGate(w,ev);
  return `<article class="card wp-card" style="--card-tint:${w.status==='review'?'#fff3dc':w.status==='accepted'?'#e6f5ef':'#e9f4f7'}"><div class="wp-card-head"><div><div class="wp-code">${w.id} · PLAN V1.${w.version-1}</div><h3>Zone ${w.zone} · ${esc(w.name)}</h3><p>${w.task} · ${w.length?`${w.length}m · `:''}목표 ${num(w.target)}${w.task==='HAUL'?'㎥ 운반':'㎥'}</p></div><span class="badge ${badgeClass(w.status)}">${statusText(w.status)}</span></div><div class="wp-card-body"><div class="wp-metric"><span>Raw / Qualified</span><b>${w.raw}% / ${w.qualified}%</b></div><div class="wp-metric"><span>잔여량 / ETA</span><b>${num(w.remaining)}㎥ · ${w.eta}</b></div><div class="wp-metric"><span>미해결 Conflict</span><b>${ev.conflicts?.length||0}건</b></div><div class="wp-metric"><span>Release Gate</span><b>${gate.ready?'승인 가능':'조건 미충족'}</b></div></div><div class="bar ${w.status==='review'?'amber':''}"><span style="width:${w.qualified}%"></span></div><div class="assignment-stack compact">${assignmentsForWp(w).map(a=>{const eq=equipmentById(a.equipmentId);const c=assignmentCompatibility(w,a);return `<span class="assignment-chip ${c.ok?'ok':'warn'}"><span class="equipment-mini-icon">${miniMachineSvg(eq?.icon,eq?.color)}</span><b>${esc(a.role)}</b> ${esc(eq?.model||'미등록')} ×${a.quantity||1}</span>`}).join('')||'<span class="assignment-chip warn">장비 미배정</span>'}</div><div class="wp-card-actions"><div class="equipment-pill"><span>${esc(assignmentSummary(w,true))}</span></div><div class="button-row"><button class="ghost-button button-sm" data-edit-wp="${w.id}">장비·조건 편집</button><button class="secondary-button button-sm" data-select-wp="${w.id}">검토</button></div></div></article>`;
}
function renderEquipment(){
  const available=state.equipment.filter(e=>['available','standby'].includes(e.status)).length;
  const connected=state.equipment.filter(e=>equipmentPlannedQuantity(e.id)>0).length;
  const totalQty=state.workPackages.reduce((s,w)=>s+assignmentsForWp(w).reduce((q,a)=>q+(Number(a.quantity)||1),0),0);
  $('#page-equipment').innerHTML=`
    <div class="section-heading"><div><h2>Equipment Registry</h2><p>공개 제조사 제원과 가정한 자율화 인터페이스를 분리하고, Zone별로 장비 모델·역할·수량을 직접 배정합니다.</p></div><div class="section-actions"><button class="ghost-button" data-action="show-sources">공개 제원 출처</button><button class="primary-button" data-action="add-equipment">+ 장비 등록</button></div></div>
    <div class="equipment-summary"><div class="card summary-stat"><span>등록 장비 Profile</span><b>${state.equipment.length}</b></div><div class="card summary-stat"><span>가용 Profile</span><b class="text-teal">${available}</b></div><div class="card summary-stat"><span>Work Package 연결</span><b>${connected}</b></div><div class="card summary-stat"><span>계획 장비 수량</span><b>${totalQty}대</b></div></div>
    <div class="equipment-grid">${state.equipment.map(equipmentCard).join('')}</div>
    <article class="card matrix-card"><div class="card-header"><div><h2>Capability Matrix</h2><p>작업 유형별 장비 적합성과 반환 가능한 Evidence</p></div><span class="badge info">RULE-BASED</span></div><div class="table-wrap">${capabilityMatrix()}</div></article>`;
}
function equipmentCard(e){
  const qty=equipmentPlannedQuantity(e.id);const linked=state.workPackages.filter(w=>assignmentsForWp(w).some(a=>a.equipmentId===e.id));
  const status=qty>0?'working':e.status;
  return `<article class="card equipment-card"><div class="equipment-visual">${machineSvg(e.icon,e.color)}<div style="position:absolute;z-index:3;left:14px;top:13px">${sourceBadge(e.specSource)}</div></div><div class="equipment-card-body"><div class="equipment-name-row"><div><h3>${esc(e.model)}</h3><div class="type">${esc(e.manufacturer)} · ${esc(e.type)}</div></div><span class="badge ${status==='working'?'progress':status==='available'||status==='standby'?'ready':'neutral'}">${status==='working'?`계획 ${qty}대`:status==='available'?'가용':status==='standby'?'대기':'오프라인'}</span></div><div class="equipment-spec-grid"><div class="equipment-spec"><span>운전중량</span><b>${e.operatingWeight}t</b></div><div class="equipment-spec"><span>표준 버킷</span><b>${e.bucketCapacity||'-'}㎥</b></div><div class="equipment-spec"><span>정격출력</span><b>${e.power||'-'}kW</b></div><div class="equipment-spec"><span>작업 버킷</span><b>${e.workBucket||'-'}㎥</b></div><div class="equipment-spec"><span>최대 굴착깊이</span><b>${e.maxDepth||'-'}m</b></div><div class="equipment-spec"><span>연결 Zone</span><b>${linked.map(w=>w.zone).join(', ')||'-'}</b></div></div><div class="capability-row">${e.supports.map(s=>`<span class="cap-chip">${s}</span>`).join('')}</div><div class="equipment-card-actions"><div>${e.sourceUrl?`<a class="source-link" href="${e.sourceUrl}" target="_blank" rel="noopener">공식 제원 ↗</a>`:sourceBadge(e.specSource)}</div><button class="ghost-button button-sm" data-edit-equipment="${e.id}">제원·연동 수정</button></div></div></article>`;
}
function applyOfficialEquipmentPhotos(){
  $$('.equipment-card').forEach(card=>{
    const model=card.querySelector('h3')?.textContent?.trim();
    const equipment=state.equipment.find(item=>item.model===model);
    if(equipment){card.querySelector('button[data-edit-equipment]')?.remove();card.dataset.editEquipment=equipment.id;card.tabIndex=0;card.setAttribute('role','button');card.setAttribute('aria-label',`${model} 제원 보기 및 수정`)}
    const imageUrl=EQUIPMENT_PHOTOS[model];
    const visual=card.querySelector('.equipment-visual');
    const illustration=visual?.querySelector('.machine-svg');
    if(!imageUrl||!visual||!illustration||visual.querySelector('.equipment-photo'))return;
    const photo=document.createElement('img');
    photo.className='equipment-photo';
    photo.src=imageUrl;
    photo.alt=`${model} 장비 참고 사진`;
    photo.addEventListener('error',()=>{photo.remove();illustration.hidden=false});
    illustration.hidden=true;
    visual.classList.add('has-photo');
    visual.insertBefore(photo,illustration);
  });
}
function capabilityMatrix(){
  const tasks=[['대형 굴착','EXCAVATION'],['소구경 굴착','SMALL_EXCAVATION'],['상차·적치','LOADING'],['운반','HAUL'],['Tool Pose 반환','Tool Pose'],['원격 중지','원격 중지']];
  return `<table class="data-table"><thead><tr><th>장비</th>${tasks.map(t=>`<th>${t[0]}</th>`).join('')}</tr></thead><tbody>${state.equipment.map(e=>`<tr><td><div class="table-primary">${e.model}</div><div class="table-sub">${e.id}</div></td>${tasks.map(([label,key])=>{const ok=e.supports.includes(key)||e.evidence.includes(key)||e.autonomy.includes(key);const partial=!ok && ((key==='EXCAVATION'&&e.supports.includes('SMALL_EXCAVATION'))||(key==='HAUL'&&e.supports.includes('HAUL_SUPPORT')));return `<td><span class="${ok?'matrix-check':partial?'matrix-partial':'matrix-none'}">${ok?'✓':partial?'△':'—'}</span></td>`}).join('')}</tr>`).join('')}</tbody></table>`;
}

function renderEvidence(){
  const wp=selectedWp(),ev=selectedEvidence(),gate=approvalGate(wp,ev);
  const stateTitle=ev.state==='accepted'?'결과 승인 완료':gate.ready?'승인 가능':ev.state==='additional-check'?'추가 확인 필요':ev.state==='collecting'?'Evidence 수집 중':'검토 전';
  $('#page-evidence').innerHTML=`
    <div class="section-heading"><div><h2>Evidence & Acceptance Gate</h2><p>추가 Evidence는 데이터 부족만 해소하며, 실제 잔여 작업·형상 미달은 보완 Work Package로만 해결합니다.</p></div><div class="section-actions"><select class="form-control" id="evidenceWpSelect" style="width:280px">${state.workPackages.map(w=>`<option value="${w.id}" ${w.id===wp.id?'selected':''}>${w.id} · Zone ${w.zone}</option>`).join('')}</select></div></div>
    <div class="trust-grid">${trustCard('Rule Compliance',ev.rule,'명시된 작업경계·Plan Version·중단조건',ev.rule>=90?'#20896d':'#d99516')}${trustCard('Evidence Completeness',ev.completeness,'필수 실행·결과·관측 데이터 완결성',ev.completeness>=95?'#20896d':'#d99516')}${trustCard('Observation Confidence',ev.confidence,'관측률·센서상태·시간 동기화',ev.confidence>=85?'#20896d':'#d99516')}</div>
    <div class="evidence-layout">
      <div>
        <article class="card"><div class="card-header"><div><h2>Plan — Before — After Diff</h2><p>${wp.id} · ${esc(assignmentSummary(wp,true))} · 목표 ${num(wp.target)}㎥</p></div><div class="origin-legend">${sourceBadge('SIMULATED RESULT')} ${sourceBadge('ASSUMED RULE')}</div></div><div class="diff-view"><div class="diff-grid"></div><div class="diff-trench"></div><div class="diff-complete"></div><div class="diff-missing"></div><div class="diff-overcut"></div><div class="diff-label one">품질 유효 완료 ${wp.qualified}%</div><div class="diff-label two">관측 ${ev.observation}%</div><div class="diff-label three">편차 ${num(ev.resultDeviationMm||0)}mm · 잔여 ${num(wp.remaining)}㎥</div></div></article>
        <article class="card" style="margin-top:14px"><div class="card-header"><div><h2>Evidence Bundle</h2><p>외부 측량·드론·현장확인은 생성 방법이 아니라 결과 등록·귀속·재판정까지 관리</p></div><button class="ghost-button button-sm" data-action="add-evidence">추가 확인 결과 등록</button></div><div class="evidence-checklist">${evidenceChecklist(wp,ev)}</div>${externalEvidenceList(ev)}</article>
        <article class="card" style="margin-top:14px"><div class="card-header"><div><h2>Release Gate</h2><p>시스템이 승인 가능 여부를 자동 계산하고 최종 Release는 관리자가 수행합니다.</p></div><span class="badge ${gate.ready?'ready':'warning'}">${gate.ready?'승인 가능':'조건 미충족'}</span></div><div class="gate-list">${gate.checks.map(c=>`<div class="gate-item ${c.ok?'pass':'fail'}"><span>${c.ok?'✓':'!'}</span><div><strong>${esc(c.label)}</strong><small>${esc(c.note)}</small></div></div>`).join('')}</div></article>
      </div>
      <aside>
        <article class="card decision-panel"><div class="eyebrow">HUMAN GATE</div><div class="decision-state"><h3>${stateTitle}</h3><p>${ev.state==='accepted'?'관리자 결정과 승인 Version이 기록되었습니다.':gate.ready?'모든 자동 Gate가 충족됐습니다. 관리자가 최종 Release를 결정합니다.':'미충족 조건에 따라 추가 확인 또는 보완 작업을 선택하세요.'}</p></div><div class="assignment-summary-panel"><strong>Zone 장비팀</strong><small>${esc(assignmentRoleSummary(wp))}</small><button class="ghost-button button-sm" data-action="edit-assignments">배정 수정</button></div><div class="decision-actions"><button class="primary-button" data-action="add-evidence">◎ 추가 확인 결과 등록</button><button class="ghost-button" data-action="create-correction">↻ 보완 Work Package 발행</button><button class="ghost-button" data-action="pause-work">Ⅱ 작업 보류</button><button class="secondary-button" data-action="approve-result" ${gate.ready?'':'disabled'}>✓ 결과 승인·Release</button></div></article>
        <article class="card conflict-card"><div class="card-header"><div><h3>Conflict Objects</h3><p>Evidence 문제와 물리적 작업 문제를 서로 다른 조치로 연결</p></div><span class="badge ${ev.conflicts.length?'warning':'ready'}">${ev.conflicts.length}건</span></div><div class="card-body">${ev.conflicts.length?ev.conflicts.map(conflictItem).join(''):'<div class="empty-state">현재 미해결 Conflict가 없습니다.</div>'}<div class="conflict-rule-note"><b>판정 기준</b><span>Progress: Qualified·잔여량</span><span>Result: 편차·과굴착</span><span>Acceptance: Evidence·관측·신뢰도</span></div></div></article>
      </aside>
    </div>`;
  $('#evidenceWpSelect')?.addEventListener('change',e=>{state.selectedWpId=e.target.value;renderAll()});
}
function trustCard(label,value,note,color){return `<article class="card trust-card"><div class="trust-label">${label}</div><div class="trust-value" style="color:${color}">${value}%</div><div class="trust-note">${note}</div><div class="trust-meter"><span style="width:${value}%;background:${color}"></span></div></article>`}
function evidenceChecklist(wp,ev){
  const items=[
    ['Work Package & Plan Version','WP ID와 실행 세션의 Version 연결','ok','PUBLIC + USER'],
    ['작업 시작·종료 이벤트',wp.status==='ready'?'아직 실행되지 않음':'장비 이벤트 로그 수신','ok','SIMULATED'],
    ['Equipment / Tool Pose','작업구역·작업기 궤적 연결','ok','ASSUMED API'],
    ['Before / After Surface','가상 형상 비교 데이터 생성','ok','SIMULATED'],
    ['Observation Coverage',ev.observation>=90?`관측률 ${ev.observation}%`:`관측률 ${ev.observation}% · 남측 미확인` ,ev.observation>=90?'ok':'warn','SIMULATED'],
    ['Human / External Evidence',(ev.externalEvidence||[]).length?`${ev.externalEvidence.length}건 등록`:'추가 확인 결과 미등록',(ev.externalEvidence||[]).length?'ok':'warn','USER INPUT'],
  ];
  return items.map(([name,desc,tone,source])=>`<div class="evidence-check"><span class="check-icon ${tone}">${tone==='ok'?'✓':'!'}</span><div><strong>${name}</strong><small>${desc}</small></div>${sourceBadge(source)}</div>`).join('');
}
function externalEvidenceList(ev){
  const rows=ev.externalEvidence||[];
  return `<div class="external-evidence-block"><div class="external-evidence-title"><strong>등록된 추가 확인 결과</strong><span>${rows.length}건</span></div>${rows.length?rows.map(x=>`<div class="external-evidence-row"><div><b>${esc(x.type)}</b><small>${esc(x.target)} · ${esc(x.performer)} · ${esc(x.time)}</small><p>${esc(x.result)}${x.attachment?` · 첨부 ${esc(x.attachment)}`:''}</p></div><span class="badge info">${esc(x.accuracy||'확인')}</span></div>`).join(''):'<div class="empty-state small">아직 등록된 외부 확인 결과가 없습니다.</div>'}</div>`;
}
function conflictItem(c){return `<div class="conflict-item ${c.severity==='high'?'high':''}"><span class="severity-bar"></span><div><strong>${esc(c.title)}</strong><p>${esc(c.desc)}</p><div style="margin-top:6px"><span class="badge ${c.severity==='high'?'danger':'warning'}">${esc(c.type)}</span></div></div><b>${esc(c.impact)}</b></div>`}

function renderVersions(){
  $('#page-versions').innerHTML=`<div class="section-heading"><div><h2>Version & Audit Trail</h2><p>작업지시, 장비 실행, Evidence, 보완, 관리자 결정을 덮어쓰지 않고 연결합니다.</p></div><div class="section-actions"><button class="ghost-button" data-action="export-json">JSON 내보내기</button><button class="primary-button" data-action="snapshot-version">현재 상태 Snapshot</button></div></div><div class="version-overview"><article class="card version-tree"><div class="version-flow">${state.versions.map(versionNode).join('')}</div></article><aside><article class="card"><div class="card-header"><div><h2>Audit Summary</h2><p>현재 프로젝트 Version 상태</p></div><span class="badge info">LOCAL</span></div><div class="card-body"><div class="wp-metric"><span>Active Plan</span><b>Plan v1.0</b></div><div class="wp-metric" style="margin-top:8px"><span>Work Package</span><b>${state.workPackages.length}개 · 승인 ${acceptedCount()}개</b></div><div class="wp-metric" style="margin-top:8px"><span>Decision Log</span><b>${state.versions.filter(v=>v.type==='decision').length}개</b></div><div class="divider"></div><div class="origin-legend">${sourceBadge('PUBLIC PROJECT')} ${sourceBadge('MANUFACTURER SPEC')} ${sourceBadge('ASSUMED')} ${sourceBadge('SIMULATED')}</div></div></article><article class="card" style="margin-top:14px"><div class="card-header"><div><h3>최근 감사 로그</h3></div></div><div class="audit-list">${state.events.slice(0,6).map(e=>`<div class="audit-item"><time>${e.time}</time><strong>${esc(e.title)}</strong><p>${esc(e.desc)}</p></div>`).join('')}</div></article></aside></div>`;
}
function versionNode(v){return `<div class="version-node ${v.state==='current'?'current':v.state==='warning'?'warning':v.state==='success'?'success':''} ${v.branch?'branch-offset':''}"><div class="version-dot">${v.type==='site'?'S':v.type==='plan'?'P':v.type==='work'?'W':v.type==='evidence'?'E':'D'}</div><div class="version-card-inner"><strong>${esc(v.code)} · ${esc(v.title)}</strong><p>${esc(v.desc)}</p><div class="version-meta"><span>${v.time}</span><span>${esc(v.actor)}</span><span>${v.state==='current'?'CURRENT':v.state.toUpperCase()}</span></div></div></div>`}

function renderSettings(){
  $('#page-settings').innerHTML=`
    <div class="section-heading"><div><h2>Project Configuration</h2><p>사상구 공개값, 제조사 공개 제원, 가정·시뮬레이션 데이터를 명확하게 분리합니다.</p></div></div>
    <div class="settings-grid">
      <article class="card settings-card"><h3>현장·건설사 기본정보</h3><p>${esc(state.project.name)}<br/>${esc(state.company.contractor)} · 담당 ${esc(state.manager.name)}</p><div class="settings-actions"><button class="primary-button" data-action="edit-project">기본정보 수정</button><button class="ghost-button" data-action="open-onboarding">초기 설정 Wizard</button></div></article>
      <article class="card settings-card"><h3>로컬 데이터 관리</h3><p>현재 프로토타입은 서버 없이 브라우저 localStorage에 저장됩니다. JSON으로 내보내거나 다시 불러올 수 있습니다.</p><div class="settings-actions"><button class="secondary-button" data-action="export-json">JSON 내보내기</button><button class="ghost-button" data-action="import-json">JSON 불러오기</button></div></article>
      <article class="card settings-card"><h3>데이터 출처</h3><p>화면에 표시되는 값의 성격을 네 가지 태그로 구분합니다.</p><div class="source-list"><div class="source-row"><div><strong>사상구 공개 발주 데이터</strong><small>공사규모·기간·물량·금액·설계 장비조건</small></div>${sourceBadge('PUBLIC PROJECT')}</div><div class="source-row"><div><strong>HD현대 건설기계 공식 제원</strong><small>HX210AL · HX48AZ · HL930A TM</small></div>${sourceBadge('MANUFACTURER SPEC')}</div><div class="source-row"><div><strong>자율화 장비 인터페이스</strong><small>Work Package 수신·상태 반환·원격 중지</small></div>${sourceBadge('ASSUMED')}</div><div class="source-row"><div><strong>공간·진척·Evidence</strong><small>실제 시뮬레이터 연동 전 가상 데이터</small></div>${sourceBadge('SIMULATED')}</div></div></article>
      <article class="card settings-card"><h3>컨셉 범위</h3><p>SiteGit은 자율화 장비의 인지·경로·제어를 개발하지 않습니다. 건설사의 계획을 작업 패키지로 전달하고 결과를 인수하는 운영·검증 계층입니다.</p><div class="settings-actions"><button class="ghost-button" data-action="show-architecture">아키텍처 보기</button></div></article>
      <article class="card settings-card danger-zone"><h3>데모 초기화</h3><p>일반 초기화는 현재 로그인 상태를 유지합니다. 완전 초기화는 공동 프로젝트 데이터와 초기 설정 기록을 모두 되돌린 뒤 로그아웃하여 다음 시연을 처음부터 시작합니다.</p><div class="settings-actions"><button class="ghost-button" data-action="reset-all">데모 데이터만 초기화</button><button class="danger-button" data-action="full-reset">완전 초기화 · 로그아웃</button></div></article>
    </div>`;
}

/* Navigation and event handling */
document.addEventListener('click',e=>{
  const nav=e.target.closest('[data-page]');
  if(nav){ navigate(nav.dataset.page); return; }
  const pageLink=e.target.closest('[data-page-link]');
  if(pageLink){ navigate(pageLink.dataset.pageLink); return; }
  const select=e.target.closest('[data-select-wp]');
  if(select){ state.selectedWpId=select.dataset.selectWp; navigate(select.closest('.wp-card')?'evidence':'dashboard'); renderAll(); return; }
  const zone=e.target.closest('[data-wp-id]');
  if(zone){ state.selectedWpId=zone.dataset.wpId; renderAll(); return; }
  const sourceR=e.target.closest('[data-readiness-source]'); if(sourceR){openReadinessSourceModal(sourceR.dataset.readinessSource);return}
  const editR=e.target.closest('[data-edit-readiness]'); if(editR){openReadinessModal(editR.dataset.editReadiness);return}
  if(e.target.closest('.equipment-card .source-link'))return;
  const editE=e.target.closest('[data-edit-equipment]'); if(editE){openEquipmentModal(editE.dataset.editEquipment);return}
  const editW=e.target.closest('[data-edit-wp]'); if(editW){openWpModal(editW.dataset.editWp);return}
  const approveIsaac=e.target.closest('[data-isaac-approve]'); if(approveIsaac){reviewIsaacCommit(approveIsaac.dataset.isaacApprove,'approved');return}
  const rejectIsaac=e.target.closest('[data-isaac-reject]'); if(rejectIsaac){reviewIsaacCommit(rejectIsaac.dataset.isaacReject,'rejected');return}
  const detailIsaac=e.target.closest('[data-isaac-detail]'); if(detailIsaac){openIsaacEvidence(detailIsaac.dataset.isaacDetail);return}
  const action=e.target.closest('[data-action]'); if(action){handleAction(action.dataset.action);return}
});
document.addEventListener('keydown',event=>{
  const card=event.target.closest?.('.equipment-card[data-edit-equipment]');
  if(!card||!['Enter',' '].includes(event.key))return;
  event.preventDefault();
  openEquipmentModal(card.dataset.editEquipment);
});
$('#navList').addEventListener('click',e=>{const b=e.target.closest('.nav-item');if(b)navigate(b.dataset.page)});
$('#mobileMenuBtn').addEventListener('click',()=>$('.sidebar').classList.toggle('open'));
$('#closeModalBtn').addEventListener('click',closeModal);
$('#modalBackdrop').addEventListener('click',e=>{if(e.target===e.currentTarget)closeModal()});
$('#openOnboardingBtn').addEventListener('click',openOnboarding);

function navigate(page){
  state.selectedPage=page; $('.sidebar').classList.remove('open'); renderHeader(); applyPage(); saveState(); window.scrollTo({top:0,behavior:'smooth'});
}
function handleAction(action){
  const handlers={
    'run-demo':runSimulation,'add-evidence':addEvidence,'create-correction':createCorrection,'approve-result':approveResult,'pause-work':pauseWork,
    'edit-project':openProjectModal,'add-readiness':()=>openReadinessModal(null),'create-wp':openCoreWorkPackageModal,'dispatch-isaac-wp':openAiWorkPackageModal,'add-equipment':()=>openEquipmentModal(null),'edit-assignments':()=>openWpModal(selectedWp().id),
    'check-all-compatibility':()=>toast('장비 적합성 검사 완료','5개 장비의 작업 유형·범위·Evidence 반환 가능성을 다시 계산했습니다.','success'),
    'show-sources':showSourcesModal,'export-json':exportJson,'import-json':()=>$('#jsonImportInput').click(),'snapshot-version':snapshotVersion,
    'focus-readiness-issues':focusReadinessIssues,'go-work-packages':goToWorkPackages,
    'open-onboarding':openOnboarding,'reset-all':confirmReset,'full-reset':confirmFullReset,'show-architecture':showArchitectureModal,'fit-map':()=>{const frame=document.querySelector('.isaac-map-frame');frame?.contentWindow?.postMessage({type:'sitegit.isaac-map.fit'},window.location.origin);toast('현장 뷰 재정렬','Isaac Sim Mud Map을 화면에 맞췄습니다.','success')},
  };
  handlers[action]?.();
}

function focusReadinessIssues(){
  const rows=$$('.precheck-item.review,.precheck-item.missing');
  if(!rows.length){toast('준비 확인 완료','모든 필수 조건이 준비되었습니다.','success');return}
  rows.forEach(row=>row.classList.add('attention'));
  rows[0].scrollIntoView({behavior:'smooth',block:'center'});
  setTimeout(()=>rows.forEach(row=>row.classList.remove('attention')),1800);
}
function goToWorkPackages(){
  const gate=readinessResult();
  if(!gate.canCreate){toast('Work Package 생성 대기','확인 필요 또는 누락 항목을 먼저 처리해 주세요.','warning');focusReadinessIssues();return}
  navigate('workpackages');
}

/* Simulation */
function runSimulation(){
  if(state.simulation.running){toast('시뮬레이션 실행 중','현재 가상 작업 흐름이 진행되고 있습니다.','warning');return}
  let wp=selectedWp();
  if(wp.status==='accepted'){wp=state.workPackages.find(w=>w.status==='ready')||state.workPackages.find(w=>w.status!=='accepted');state.selectedWpId=wp.id}
  if(!assignmentsForWp(wp).length){toast('장비 미배정','Zone 장비팀을 먼저 배정하세요.','danger');return}
  const primary=primaryAssignment(wp);if(!primary||!assignmentCompatibility(wp,primary).ok){toast('주 작업 장비 부적합','주 작업 역할에 해당 작업을 지원하는 장비를 배정하세요.','danger');return}
  const read=readinessResult();if(read.tone==='blocked'){toast('배포 차단','작업 준비 확인의 필수 항목을 먼저 처리해 주세요.','danger');return}
  state.simulation.running=true;state.simulation.stage=1;wp.status='dispatched';wp.raw=0;wp.qualified=0;wp.remaining=wp.target;wp.eta='계산 중';
  state.evidence[wp.id]={rule:100,completeness:28,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'collecting',missing:['작업 종료 이벤트','After Surface','외부 확인 기록'],conflicts:[],externalEvidence:[]};
  addEvent('info',`${wp.id} 배포`,`${assignmentRoleSummary(wp)} 장비팀에 Work Package를 전송했습니다.`);renderAll();
  setTimeout(()=>{state.simulation.stage=2;addEvent('success','장비팀 수신 확인',`${wp.id} Plan Version과 제약조건을 수신했습니다.`);renderAll()},650);
  setTimeout(()=>{state.simulation.stage=3;wp.status='executing';wp.start=nowTime();wp.eta='4h 10m';addEvent('info','자율화 작업 시작',`${wp.zone} 구역 Execution Session이 생성됐습니다.`);renderAll()},1250);
  let p=0;
  simTimer=setInterval(()=>{
    p+=Math.floor(6+Math.random()*7);wp.raw=Math.min(78,p);wp.qualified=Math.max(0,Math.round(wp.raw*(.84+Math.random()*.05)));wp.remaining=Math.round(wp.target*(100-wp.qualified)/100);wp.eta=wp.raw<40?'3h 35m':wp.raw<70?'1h 40m':'검토 준비';
    const ev=state.evidence[wp.id];ev.completeness=Math.min(70,30+Math.round(wp.raw*.5));ev.confidence=Math.min(76,40+Math.round(wp.raw*.45));ev.observation=Math.min(78,35+Math.round(wp.raw*.52));
    if(wp.raw>=78){
      clearInterval(simTimer);simTimer=null;state.simulation.stage=5;state.simulation.running=false;wp.status='review';wp.end=nowTime();wp.raw=78;wp.qualified=69;wp.remaining=Math.round(wp.target*.31);wp.eta='검토 중';
      if(wp.parentWpId){
        wp.raw=100;wp.qualified=100;wp.remaining=0;wp.eta='검토 완료';Object.assign(ev,{rule:100,completeness:100,confidence:93,observation:97,workFinished:true,resultDeviationMm:24,overcutVolume:0,state:'approval-ready',missing:[]});recomputeConflicts(wp,ev);
        const parent=state.workPackages.find(x=>x.id===wp.parentWpId);const parentEv=parent?state.evidence[parent.id]:null;if(parent&&parentEv){parent.raw=100;parent.qualified=100;parent.remaining=0;parent.status='review-ready';parentEv.resultDeviationMm=24;parentEv.overcutVolume=0;parentEv.workFinished=true;parentEv.completeness=Math.max(100,parentEv.completeness);parentEv.confidence=Math.max(91,parentEv.confidence);parentEv.observation=Math.max(96,parentEv.observation);parentEv.missing=[];recomputeConflicts(parent,parentEv)}
        addEvent('success',`${wp.id} 보완 결과 제출`,`잔여 작업과 형상 편차가 해소되어 승인 Gate 검토가 가능합니다.`);
        state.versions.push({type:'work',code:`${wp.id} v1`,title:'Correction Commit',desc:`Qualified 100% · 편차 24mm · 관측 97%`,time:nowTime(),actor:assignmentSummary(wp,true),state:'success',branch:true});
      }else{
        Object.assign(ev,{rule:94,completeness:82,confidence:68,observation:76,workFinished:true,resultDeviationMm:78,overcutVolume:9,state:'additional-check',missing:['남측 12% 구역 관측 데이터','외부 확인 기록']});recomputeConflicts(wp,ev);
        addEvent('warning',`${wp.id} 결과 검토 필요`,`${num(wp.remaining)}㎥ 잔여량, 형상 편차, 관측 데이터 누락이 확인됐습니다.`);
        state.versions.push({type:'work',code:`${wp.id} v${wp.version}`,title:'Immediate Work Commit',desc:`Raw 78% · Qualified 69% · 잔여 ${num(wp.remaining)}㎥ · 편차 78mm`,time:nowTime(),actor:assignmentSummary(wp,true),state:'warning',branch:true});
      }
    }
    renderAll();
  },520);
}
function addEvidence(){
  const wp=selectedWp(),ev=selectedEvidence();
  if(wp.status==='accepted'){toast('이미 승인된 작업','새 Evidence는 다음 Version에서 추가할 수 있습니다.','warning');return}
  openModal({eyebrow:'EXTERNAL / HUMAN EVIDENCE',title:'추가 확인 결과 등록',body:`<div class="evidence-scope-note"><b>이 기능이 해결하는 범위</b><span>관측 누락·센서 신뢰도·확인 기록 같은 Acceptance Conflict</span><em>잔여 작업량·형상 미달은 변경하지 않습니다.</em></div><div class="form-grid"><div class="form-group"><label>확인 유형</label><select class="form-control" id="xType"><option>외부 측량</option><option>드론 재촬영·스캔</option><option>현장관리자 확인</option><option>품질담당자 검사</option><option>장비 재스캔</option></select></div><div class="form-group"><label>수행자</label><input class="form-control" id="xPerformer" value="${esc(state.manager.name)}"></div><div class="form-group"><label>확인 시각</label><input class="form-control" id="xTime" value="${new Date().toISOString().slice(0,16)}" type="datetime-local"></div><div class="form-group"><label>대상 위치</label><input class="form-control" id="xTarget" value="Zone ${esc(wp.zone)} 미관측 구역"></div><div class="form-group full"><label>확인 결과</label><textarea class="form-control" id="xResult">미관측 구역을 추가 확인했으며 작업 결과 데이터와 일치함을 확인했습니다.</textarea></div><div class="form-group"><label>정확도·신뢰도</label><input class="form-control" id="xAccuracy" value="±20mm / 신뢰도 높음"></div><div class="form-group"><label>첨부 파일</label><input class="form-control" id="xFile" type="file"><span class="form-hint">정적 프로토타입에서는 파일명만 기록합니다.</span></div></div>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveExternalEvidenceBtn">결과 등록·재판정</button>`});
  $('#saveExternalEvidenceBtn').addEventListener('click',()=>{
    const file=$('#xFile').files[0];ev.externalEvidence=ev.externalEvidence||[];ev.externalEvidence.push({id:`EXT-${Date.now()}`,type:$('#xType').value,performer:$('#xPerformer').value,time:$('#xTime').value.replace('T',' '),target:$('#xTarget').value,result:$('#xResult').value,accuracy:$('#xAccuracy').value,attachment:file?.name||''});
    ev.completeness=Math.max(100,ev.completeness);ev.confidence=Math.max(91,ev.confidence);ev.observation=Math.max(96,ev.observation);ev.missing=[];state.simulation.stage=6;recomputeConflicts(wp,ev);closeModal();
    addEvent('success','추가 확인 결과 등록',`${wp.id} Acceptance Conflict를 재판정했습니다. 물리적 Conflict는 유지됩니다.`);
    state.versions.push({type:'evidence',code:`EB-${wp.zone}-${ev.externalEvidence.length}`,title:'External / Human Evidence',desc:`${ev.externalEvidence.at(-1).type} · 관측 ${ev.observation}% · 신뢰도 ${ev.confidence}%`,time:nowTime(),actor:ev.externalEvidence.at(-1).performer,state:'current',branch:true});
    const physical=(ev.conflicts||[]).some(c=>c.category==='physical');toast('추가 확인 등록 완료',physical?'Acceptance 문제는 해소됐지만 실제 보완 작업이 남아 있습니다.':'모든 자동 Gate를 다시 계산했습니다.',physical?'warning':'success');renderAll();
  });
}
function createCorrection(){
  const original=selectedWp(),ev=selectedEvidence();
  if(original.status==='accepted'){toast('승인 완료 작업','승인된 작업은 새 Plan Version으로 변경해야 합니다.','warning');return}
  const physical=(ev.conflicts||[]).filter(c=>c.category==='physical');
  if(!physical.length){toast('물리적 보완 불필요','현재는 추가 확인 결과 등록으로 해결할 Acceptance 항목만 존재합니다.','warning');return}
  const seq=state.workPackages.filter(w=>w.parentWpId===original.id).length+1;const id=`${original.id}-CORR-${String(seq).padStart(2,'0')}`;
  const correction={id,zone:original.zone,name:`${original.name} — 부분 보완 ${seq}`,task:original.task,length:0,target:Math.max(1,Number(original.remaining)||Math.round(original.target*.1)),raw:0,qualified:0,remaining:Math.max(1,Number(original.remaining)||Math.round(original.target*.1)),status:'correction',version:1,eta:'보완 대기',risk:'high',start:'-',end:'-',x:original.x,y:original.y,width:original.width,color:'#d95757',completionThreshold:100,observationThreshold:original.observationThreshold,toleranceMm:original.toleranceMm,parentWpId:original.id,sourceConflictIds:physical.map(c=>c.id),assignments:deepClone(assignmentsForWp(original))};
  state.workPackages.push(correction);state.evidence[id]={rule:0,completeness:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:['Correction Execution Session','Correction Result Evidence'],conflicts:[],externalEvidence:[]};
  original.status='correction-issued';ev.state='correction-issued';state.selectedWpId=id;state.simulation.stage=0;
  addEvent('info','보완 Work Package 발행',`${id} · 대상 ${num(correction.target)}㎥ · 원본 ${original.id} · ${assignmentRoleSummary(correction)}`);
  state.versions.push({type:'work',code:id,title:'Correction Work Package',desc:`원본 ${original.id}의 Progress·Result Conflict 보완 · ${num(correction.target)}㎥`,time:nowTime(),actor:state.manager.name,state:'warning',branch:true});
  toast('보완 작업지시 발행',`${id}가 생성됐습니다. 장비 배정을 확인한 뒤 가상 작업을 실행하세요.`,'success');renderAll();
}
function approveResult(){
  const wp=selectedWp(),ev=selectedEvidence();recomputeConflicts(wp,ev);const gate=approvalGate(wp,ev);
  if(!gate.ready){const failed=gate.checks.filter(c=>!c.ok).map(c=>c.label).join(', ');toast('승인 조건 미충족',failed,'danger');return}
  wp.status='accepted';wp.eta='완료';ev.state='accepted';state.simulation.stage=7;
  if(wp.parentWpId){const parent=state.workPackages.find(x=>x.id===wp.parentWpId);const parentEv=parent&&state.evidence[parent.id];if(parent&&parentEv){parent.status='accepted';parent.eta='완료';parentEv.state='accepted';parentEv.conflicts=[]}}
  const next=allExcavationWps().find(w=>w.status==='draft'||w.status==='ready');if(next&&next.id!==wp.id)next.status='ready';
  addEvent('success',`${wp.id} 결과 승인`,`${state.manager.name} 관리자가 모든 Gate를 확인하고 Release했습니다.`);
  state.versions.push({type:'decision',code:`Release ${wp.id}`,title:'관리자 결과 승인',desc:`Blocking Conflict 0건 · Qualified 100% · Evidence Gate 통과`,time:nowTime(),actor:state.manager.name,state:'success'});
  toast('Release 완료','시스템은 승인 가능을 계산했고, 최종 결정은 관리자가 수행했습니다.','success');renderAll();
}
function pauseWork(){const wp=selectedWp();wp.status='paused';addEvent('warning',`${wp.id} 작업 보류`,'관리자 결정으로 자동 작업을 일시중지했습니다.');toast('작업 보류','실제 장비 연동 전 컨셉 상태만 변경했습니다.','warning');renderAll()}
function snapshotVersion(){state.versions.push({type:'decision',code:`Snapshot ${state.versions.length+1}`,title:'현재 상태 Snapshot',desc:`선택 작업 ${selectedWp().id}, Qualified ${selectedWp().qualified}%`,time:nowTime(),actor:state.manager.name,state:'current'});toast('Snapshot 생성','현재 작업·Evidence 상태가 이력에 추가됐습니다.','success');renderAll()}
function addEvent(type,title,desc){state.events.unshift({time:nowTime(),type,title,desc});state.events=state.events.slice(0,30)}

/* Isaac 폐루프 — 웹 지시 → Isaac 실행 → Commit → 관리자 승인 → 맵 반영 */
const ISAAC_STATUS_TEXT={pending:'Isaac 대기',dispatched:'Isaac 실행 중',committed:'승인 대기',approved:'맵 반영됨',rejected:'반려됨'};
const ISAAC_STATUS_BADGE={pending:'neutral',dispatched:'info',committed:'warning',approved:'accepted',rejected:'danger'};
function isaacLatestCommit(instruction){return (instruction.commits||[]).at(-1)||null}
function isaacPositionText(instruction){
  const commit=isaacLatestCommit(instruction);
  if(instruction.kind==='excavate_prim')return commit?.result?.target_prim_path||instruction.params?.target_prim_path||'-';
  const p=commit?.result?.placed_position||instruction.params?.position||{};
  return `${Number(p.x||0).toFixed(1)} , ${Number(p.y||0).toFixed(1)} , ${Number(p.z||0).toFixed(1)}`;
}
function reloadIsaacMapObjects(){
  document.querySelector('.isaac-map-frame')?.contentWindow?.postMessage({type:'sitegit.isaac-map.reload-objects'},window.location.origin);
}
async function loadStageInventory(){
  try{
    const response=await apiFetch(`/isaac/stage-inventory?project_id=${encodeURIComponent(PROJECT_ID)}`);
    if(!response.ok)throw new Error(`STAGE_INVENTORY_${response.status}`);
    stageInventory=await response.json();
    updateStageInventoryUi();
    renderIsaacPanel();
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')console.warn('Stage inventory load failed',error);
    stageInventory={connected:false,equipment:[],diggable_targets:[],age_seconds:0};
    updateStageInventoryUi();
  }
}
function updateStageInventoryUi(){
  const activeTargets=(stageInventory.diggable_targets||[]).filter(item=>item.active!==false).length;
  const dot=document.querySelector('.stage-live-dot');
  if(dot)dot.className=`stage-live-dot ${stageInventory.connected?'online':'offline'}`;
  const status=document.querySelector('.map-work-status');
  if(status)status.textContent=stageInventory.connected
    ?`장비 ${stageInventory.equipment.length}대 · 활성 굴착 대상 ${activeTargets}개`
    :'Isaac Stage 연결 대기';
  const button=document.querySelector('.map-work-create');
  if(button)button.disabled=!stageInventory.connected||activeTargets===0;
}
async function loadIsaacInstructions(){
  try{
    const response=await apiFetch(`/isaac/instructions?project_id=${encodeURIComponent(PROJECT_ID)}&limit=20`);
    if(!response.ok)throw new Error(`ISAAC_${response.status}`);
    isaacInstructions=await response.json();
    if(syncAiWorkPackageStatuses())renderAll();
    else renderIsaacPanel();
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')console.warn('Isaac instruction load failed',error);
  }
}
function syncAiWorkPackageStatuses(){
  const statusMap={pending:'dispatched',dispatched:'executing',committed:'review',approved:'accepted',rejected:'paused'};
  let changed=false;
  isaacInstructions.forEach(instruction=>{
    const workPackageId=instruction.params?.work_package_id;
    if(!workPackageId)return;
    let wp=state.workPackages.find(item=>item.id===workPackageId);
    if(!wp){
      if(instruction.kind==='excavate_prim'){
        wp={
          id:workPackageId,zone:instruction.params?.zone_id||'-',name:`Prim 굴착 — ${instruction.params?.target_name||workPackageId}`,
          task:'EXCAVATE_PRIM',length:0,target:1,raw:0,qualified:0,remaining:1,status:'dispatched',version:1,
          eta:'Isaac 대기',risk:'medium',start:'-',end:'-',x:0,y:0,width:0,color:'#d95757',
          completionThreshold:100,observationThreshold:100,toleranceMm:0,assignments:[],
          isaacInstructionId:instruction.id,sourceText:instruction.params?.source_text||instruction.note||'',
          equipmentPrimPath:instruction.params?.equipment_prim_path,targetPrimPath:instruction.params?.target_prim_path,
        };
        state.workPackages.push(wp);
        state.evidence[workPackageId]={rule:100,completeness:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:['Isaac 실행 Commit','관리자 승인'],conflicts:[],externalEvidence:[]};
        changed=true;
      }else{
      const position=instruction.params?.position||{x:0,y:0,z:0};
      const size=instruction.params?.size||{x:1,y:1,z:1};
      const targetVolume=Number(size.x||0)*Number(size.y||0)*Number(size.z||0);
      wp={
        id:workPackageId,zone:instruction.params?.zone_id||'-',name:`AI 큐브 배치 — ${instruction.params?.label||workPackageId}`,
        task:'PLACE_CUBE',length:0,target:targetVolume,raw:0,qualified:0,remaining:targetVolume,status:'dispatched',version:1,
        eta:'Isaac 대기',risk:'low',start:'-',end:'-',x:Number(position.x||0),y:Number(position.y||0),width:Number(size.x||0),
        color:instruction.params?.color||'#FFD700',completionThreshold:100,observationThreshold:100,toleranceMm:0,assignments:[],
        isaacInstructionId:instruction.id,sourceText:instruction.note||'',position,size,
      };
      state.workPackages.push(wp);
      state.evidence[workPackageId]={rule:100,completeness:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:['Isaac 실행 Commit','관리자 승인'],conflicts:[],externalEvidence:[]};
      changed=true;
      }
    }
    const next=statusMap[instruction.status]||wp.status;
    if(wp.status!==next){wp.status=next;changed=true}
    const commit=isaacLatestCommit(instruction);
    if(commit?.status==='succeeded'&&wp.raw!==100){wp.raw=100;changed=true}
    if(instruction.status==='approved'&&wp.qualified!==100){wp.qualified=100;wp.remaining=0;wp.eta='완료';changed=true}
    else if(instruction.status==='committed'&&wp.eta!=='승인 대기'){wp.eta='승인 대기';changed=true}
    else if(instruction.status==='dispatched'&&wp.eta!=='Isaac 실행 중'){wp.eta='Isaac 실행 중';changed=true}
  });
  return changed;
}
function renderIsaacPanel(){
  const host=$('#isaacLoopList');
  if(!host)return;
  const waiting=isaacInstructions.filter(i=>i.status==='committed').length;
  const counter=$('#isaacLoopCount');
  if(counter){counter.textContent=waiting?`승인 대기 ${waiting}건`:'승인 대기 없음';counter.className=`badge ${waiting?'warning':'info'}`}
  host.innerHTML=isaacInstructions.length
    ?isaacInstructions.slice(0,4).map(isaacInstructionRow).join('')
    :'<div class="map-work-empty">발행된 실제 작업이 없습니다.</div>';
}
function isaacInstructionRow(instruction){
  const commit=isaacLatestCommit(instruction);
  const label=instruction.params?.label||instruction.kind;
  const color=instruction.kind==='excavate_prim'?'#d95757':(instruction.params?.color||'#f0b429');
  const workPackageId=instruction.params?.work_package_id;
  const failed=commit&&commit.status==='failed';
  const pendingReview=instruction.status==='committed'&&commit&&commit.review_status==='pending';
  const detail=failed
    ?`실행 실패 · ${esc(commit.result?.error||'원인 미기록')}`
    :instruction.kind==='excavate_prim'
      ?`${esc(instruction.params?.equipment_name||'장비')} → ${esc(instruction.params?.target_name||'대상 Prim')}`
      :`위치 ${esc(isaacPositionText(instruction))}${commit?.review_note?` · 사유 ${esc(commit.review_note)}`:''}`;
  return `<div class="isaac-row">
    <span class="isaac-swatch" style="background:${esc(color)}"></span>
    <div class="isaac-row-main">
      <strong>${esc(label)}</strong>
      <span>${detail}</span>
      <small>${workPackageId?`${esc(workPackageId)} · `:''}${esc(instruction.created_by_username||'-')} 발행${commit?.reviewed_by?` · ${esc(commit.reviewed_by)} 판정`:''}</small>
    </div>
    <span class="badge ${ISAAC_STATUS_BADGE[instruction.status]||'neutral'}">${ISAAC_STATUS_TEXT[instruction.status]||instruction.status}</span>
    ${commit?`<button class="isaac-evidence-button" data-isaac-detail="${esc(instruction.id)}">증거</button>`:''}
    ${pendingReview?`<div class="isaac-row-actions">
      <button class="secondary-button button-sm" data-isaac-approve="${esc(commit.id)}">✓ 승인</button>
      <button class="ghost-button button-sm" data-isaac-reject="${esc(commit.id)}">반려</button>
    </div>`:''}
  </div>`;
}
function openCoreWorkPackageModal(){
  openModal({
    eyebrow:'WORK PACKAGE',
    title:'새 작업 만들기',
    body:`<div class="form-grid core-wp-create-form">
      <div class="form-group full"><label>작업명</label><input class="form-control" id="coreWpTitle" placeholder="예: Zone A 본관 터파기"></div>
      <div class="form-group"><label>작업 구역</label><input class="form-control" id="coreWpZone" value="Zone A"></div>
      <div class="form-group"><label>작업 종류</label><select class="form-control" id="coreWpType"><option value="EXCAVATION">굴착</option></select></div>
      <div class="form-group"><label>목표량</label><input class="form-control" id="coreWpTarget" type="number" min="0" step="0.1" value="100"></div>
      <div class="form-group"><label>단위</label><select class="form-control" id="coreWpUnit"><option value="m3">㎥</option><option value="m">m</option><option value="job">작업</option></select></div>
      <div class="form-group full"><label>설명</label><textarea class="form-control" id="coreWpDescription" placeholder="필요한 경우 작업 범위나 주의사항을 입력하세요."></textarea></div>
      <div class="core-wp-create-note full"><b>Isaac 연결 없이 생성할 수 있습니다.</b><span>Work Package를 먼저 계획하고, 실제 실행 단계에서 장비와 Isaac Stage를 연결합니다.</span></div>
    </div>`,
    footer:'<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveCoreWpBtn">작업 만들기</button>',
  });
  $('#saveCoreWpBtn').addEventListener('click',createCoreWorkPackage);
  setTimeout(()=>$('#coreWpTitle')?.focus(),0);
}
async function createCoreWorkPackage(){
  const title=$('#coreWpTitle').value.trim();
  const zone=$('#coreWpZone').value.trim();
  if(!title||!zone){toast('필수 정보 확인','작업명과 작업 구역을 입력해 주세요.','warning');return}
  const button=$('#saveCoreWpBtn');button.disabled=true;button.textContent='생성 중...';
  const target=Number($('#coreWpTarget').value)||0;
  try{
    const response=await apiFetch('/work-packages',{method:'POST',body:JSON.stringify({
      project_id:PROJECT_ID,work_type:$('#coreWpType').value,zone_id:zone,title,
      description:$('#coreWpDescription').value.trim()||null,
      target:{amount:target,unit:$('#coreWpUnit').value},constraints:{},
    })});
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Work Package를 생성하지 못했습니다.');
    closeModal();navigate('workpackages');renderWorkPackages();
    toast('Work Package 생성 완료','실제 실행 전까지 Isaac 연결은 필요하지 않습니다.','success');
  }catch(error){button.disabled=false;button.textContent='작업 만들기';if(error.message!=='AUTH_REQUIRED')toast('생성 실패',error.message,'danger')}
}
function openAiWorkPackageModal(){
  if(!stageInventory.connected){
    toast('Isaac Stage 연결 필요','Isaac Runner를 실행해 실제 장비와 굴착 대상 Prim을 먼저 등록하세요.','warning');
    return;
  }
  aiWorkPackageDraft=null;
  const equipmentOptions=(stageInventory.equipment||[]).map(item=>`<option value="${esc(item.path)}">${esc(item.name)} · ${esc(item.path)}</option>`).join('');
  const maxExcavationSpan=25;
  const targetOptions=(stageInventory.diggable_targets||[]).map(item=>{
    const size=item.bounds_size||{};
    const span=Math.max(Number(size.x)||0,Number(size.y)||0);
    const active=item.active!==false;
    const safe=active&&span<=maxExcavationSpan;
    const scope=`${(Number(size.x)||0).toFixed(1)}×${(Number(size.y)||0).toFixed(1)}m`;
    const reason=!active?' · 굴착 완료 — 선택 불가':span>maxExcavationSpan?' · 전체 맵 Mesh 가능성 — 굴착 불가':'';
    return `<option value="${safe?esc(item.path):''}" ${safe?'':'disabled'}>${esc(item.name)} · ${scope}${reason}</option>`;
  }).join('');
  openModal({
    eyebrow:'REAL ISAAC WORK PACKAGE',
    title:'굴착 작업 지시 생성',
    body:`<div class="wp-chat-shell">
      <div class="stage-binding-grid">
        <label><span>실제 장비 Prim</span><select class="form-control" id="aiWpEquipment">${equipmentOptions||'<option value="">연결된 장비 없음</option>'}</select></label>
        <label><span>실제 굴착 대상 Prim</span><select class="form-control" id="aiWpTarget">${targetOptions||'<option value="">굴착 대상 없음</option>'}</select></label>
      </div>
      <div class="wp-chat-messages" id="aiWpMessages">
        <div class="wp-chat-message assistant"><span>SiteGit AI</span><p>위 목록은 현재 실행 중인 Isaac Stage에서 직접 읽은 Prim입니다. 장비와 굴착 대상을 선택하고 작업 내용을 입력하세요.</p><small>예: 선택한 굴착기로 Zone A의 선택 Prim을 굴착해줘.</small></div>
      </div>
      <div class="wp-chat-compose">
        <textarea class="form-control" id="aiWpPrompt" placeholder="실제 굴착 작업을 자연어로 입력하세요">선택한 굴착기로 Zone A의 선택한 Prim을 굴착해줘</textarea>
        <button class="primary-button" id="aiWpAnalyzeBtn">LLM 지시 검증</button>
      </div>
      <div class="ai-wp-preview hidden" id="aiWpPreview"></div>
    </div>`,
    footer:`<button class="ghost-button" data-modal-close>취소</button><button class="secondary-button" id="dispatchAiWpBtn" disabled>검증 완료 후 실제 Isaac에 전송</button>`,
  });
  $('#aiWpAnalyzeBtn').addEventListener('click',analyzeAiWorkPackage);
  $('#dispatchAiWpBtn').addEventListener('click',dispatchAiWorkPackage);
  $('#aiWpPrompt').addEventListener('keydown',event=>{
    if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();analyzeAiWorkPackage()}
  });
}
async function analyzeAiWorkPackage(){
  const prompt=$('#aiWpPrompt').value.trim();
  const equipmentPrimPath=$('#aiWpEquipment')?.value||'';
  const targetPrimPath=$('#aiWpTarget')?.value||'';
  if(prompt.length<3){toast('작업지시 필요','굴착 작업 내용을 입력해 주세요.','warning');return}
  if(!equipmentPrimPath||!targetPrimPath){toast('Prim 선택 필요','실제 장비와 굴착 대상 Prim을 선택하세요.','warning');return}
  const button=$('#aiWpAnalyzeBtn');
  button.disabled=true;button.textContent='로컬 LLM 분석 중...';
  $('#dispatchAiWpBtn').disabled=true;
  const messages=$('#aiWpMessages');
  messages.insertAdjacentHTML('beforeend',`<div class="wp-chat-message user"><span>관리자</span><p>${esc(prompt)}</p></div><div class="wp-chat-message assistant pending" id="aiWpPending"><span>SiteGit AI</span><p>자연어 지시와 현재 Stage의 장비·대상 Prim을 교차 검증하고 있습니다…</p></div>`);
  messages.scrollTop=messages.scrollHeight;
  try{
    const response=await apiFetch('/work-packages/ai/excavation/interpret',{
      method:'POST',body:JSON.stringify({project_id:PROJECT_ID,message:prompt,equipment_prim_path:equipmentPrimPath,target_prim_path:targetPrimPath}),
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok){
      const detail=data.detail||{};
      const error=new Error(detail.message||`AI_WORK_PACKAGE_${response.status}`);
      error.code=detail.code;throw error;
    }
    aiWorkPackageDraft=data;
    $('#aiWpPending')?.remove();
    const assistantText=data.plan.ready
      ?`${data.plan.summary} 실행 전 검증 결과를 확인해 주세요.`
      :(data.plan.clarification_question||'작업지시를 실행하려면 추가 정보가 필요합니다.');
    messages.insertAdjacentHTML('beforeend',`<div class="wp-chat-message assistant"><span>SiteGit AI · ${esc(data.model)}</span><p>${esc(assistantText)}</p></div>`);
    renderAiWorkPackageDraft();
  }catch(error){
    $('#aiWpPending')?.remove();
    const message=error.code==='LLM_NOT_CONFIGURED'
      ?'로컬 Ollama 앱과 qwen3:8b 모델이 실행 가능한지 확인해 주세요.'
      :(error.message||'LLM 요청에 실패했습니다.');
    messages.insertAdjacentHTML('beforeend',`<div class="wp-chat-message assistant error"><span>SiteGit AI</span><p>${esc(message)}</p></div>`);
    toast('Work Package 생성 실패',message,'danger');
  }finally{
    button.disabled=false;button.textContent='LLM 지시 검증';
    messages.scrollTop=messages.scrollHeight;
  }
}
function renderAiWorkPackageDraft(){
  const host=$('#aiWpPreview');
  if(!host||!aiWorkPackageDraft)return;
  const draft=aiWorkPackageDraft,plan=draft.plan;
  const executable=Boolean(plan.ready&&draft.equipment&&draft.target&&(draft.checks||[]).every(check=>check.ok));
  host.classList.remove('hidden');
  host.innerHTML=`<div class="ai-wp-preview-head"><div><span>실제 Stage 결합 초안</span><strong>${esc(plan.summary)}</strong></div><span class="badge ${executable?'ready':'warning'}">${executable?'실행 가능':'추가 입력 필요'}</span></div>
    <div class="ai-wp-preview-grid">
      <div><span>장비</span><b>${esc(draft.equipment?.name||'미확정')}</b></div>
      <div><span>작업 구역</span><b>${esc(plan.zone_id||'미지정')}</b></div>
      <div class="full"><span>장비 Prim</span><b class="prim-path-value">${esc(draft.equipment?.path||'미확정')}</b></div>
      <div class="full"><span>굴착 대상 Prim</span><b class="prim-path-value">${esc(draft.target?.path||'미확정')}</b></div>
    </div>
    <div class="ai-wp-checks">${(draft.checks||[]).map(check=>`<div class="${check.ok?'pass':'fail'}"><span>${check.ok?'✓':'!'}</span><p>${esc(check.message)}</p></div>`).join('')}</div>
    <div class="ai-wp-source">LLM은 지시를 구조화할 뿐입니다. 실행 경로는 최신 Isaac Stage inventory의 정확한 Prim path만 사용합니다.</div>`;
  $('#dispatchAiWpBtn').disabled=!executable;
  $('#dispatchAiWpBtn').textContent=executable?'Work Package 확정 · 실제 Isaac 전송':'검증 완료 후 Isaac에 전송';
}
async function dispatchAiWorkPackage(){
  if(!aiWorkPackageDraft)return;
  const button=$('#dispatchAiWpBtn');button.disabled=true;button.textContent='Isaac 대기열 전송 중...';
  try{
    const response=await apiFetch('/work-packages/ai/excavation/dispatch',{
      method:'POST',
      body:JSON.stringify({
        project_id:PROJECT_ID,
        message:aiWorkPackageDraft.source_text,
        plan:aiWorkPackageDraft.plan,
        equipment_prim_path:aiWorkPackageDraft.equipment?.path,
        target_prim_path:aiWorkPackageDraft.target?.path,
      }),
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(data.detail?.message||`AI_DISPATCH_${response.status}`);
    const record=data.work_package;
    if(!state.workPackages.some(item=>item.id===record.id)){
      state.workPackages.push({
        id:record.id,zone:record.zone_id||'-',name:`Prim 굴착 — ${record.target.name}`,task:'EXCAVATE_PRIM',length:0,
        target:1,raw:0,qualified:0,remaining:1,status:'dispatched',version:1,
        eta:'Isaac 대기',risk:'medium',start:'-',end:'-',x:0,y:0,width:0,
        color:'#d95757',completionThreshold:100,observationThreshold:100,toleranceMm:0,assignments:[],
        isaacInstructionId:data.instruction.id,sourceText:record.source_text,
        equipmentPrimPath:record.equipment.path,targetPrimPath:record.target.path,
      });
      state.evidence[record.id]={rule:100,completeness:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:['Isaac 실행 Commit','관리자 승인'],conflicts:[],externalEvidence:[]};
      state.versions.push({type:'work',code:record.id,title:'실제 Prim 굴착 Work Package 발행',desc:`${record.equipment.name} → ${record.target.name}`,time:nowTime(),actor:currentUser?.full_name||state.manager.name,state:'current',branch:true});
    }
    state.selectedWpId=record.id;
    addEvent('info','AI Work Package 발행',`${record.id} · 실제 Isaac Sim 실행 대기`);
    closeModal();
    await loadIsaacInstructions();
    renderAll();navigate('dashboard');
    toast('Work Package 전송 완료','Isaac Adapter가 실제 장비 Prim을 이동시키고 대상 Prim을 굴착 처리합니다.','success');
  }catch(error){
    button.disabled=false;button.textContent='Work Package 확정 · Isaac 전송';
    toast('Isaac 전송 실패',error.message||'서버 상태를 확인하세요.','danger');
  }
}
function evidenceUrl(storageKey){
  return `/evidence/${String(storageKey||'').split('/').map(encodeURIComponent).join('/')}`;
}
function evidencePhaseCard(title,data){
  const image=data?.image||{};
  const lidar=data?.lidar||{};
  const stage=data?.stage||{};
  return `<section class="commit-evidence-phase">
    <h3>${title}</h3>
    <div class="commit-evidence-image">${image.available&&image.storage_key
      ?`<img src="${evidenceUrl(image.storage_key)}" alt="${title} Isaac viewport">`
      :`<span>Viewport 이미지 없음<br><small>${esc(image.reason||'캡처되지 않음')}</small></span>`}</div>
    <dl>
      <div><dt>대상 Prim 상태</dt><dd>${stage.target_active===false?'비활성화됨':stage.target_active===true?'활성':'확인 불가'}</dd></div>
      <div><dt>LiDAR</dt><dd>${lidar.available&&lidar.storage_key
        ?`<a href="${evidenceUrl(lidar.storage_key)}" target="_blank" rel="noopener">${num(lidar.point_count)} points · PLY 열기</a>`
        :esc(lidar.reason||'데이터 없음')}</dd></div>
    </dl>
  </section>`;
}
function openIsaacEvidence(instructionId){
  const instruction=isaacInstructions.find(item=>item.id===instructionId);
  const commit=instruction&&isaacLatestCommit(instruction);
  if(!instruction||!commit)return;
  const evidence=commit.evidence||{};
  const result=commit.result||{};
  openModal({
    eyebrow:'ISAAC EXECUTION COMMIT',
    title:'작업 전·후 증거 검토',
    body:`<div class="commit-evidence-summary">
      <strong>${esc(instruction.params?.label||instruction.kind)}</strong>
      <span>${esc(instruction.params?.equipment_prim_path||'-')} → ${esc(instruction.params?.target_prim_path||'-')}</span>
      <small>실행 원본: ${esc(result.simulator||'-')} · 검증: ${esc(result.source||'-')}</small>
    </div>
    <div class="commit-evidence-grid">
      ${evidencePhaseCard('작업 전',evidence.before)}
      ${evidencePhaseCard('작업 후',evidence.after)}
    </div>`,
    footer:`<button class="ghost-button" data-modal-close>닫기</button>${commit.review_status==='pending'?`<button class="secondary-button" data-isaac-approve="${esc(commit.id)}">증거 확인 · 승인</button>`:''}`,
  });
}
async function reviewIsaacCommit(commitId,decision){
  const note=decision==='rejected'?(prompt('반려 사유를 입력하세요.')||'').slice(0,500):null;
  if(decision==='rejected'&&!note){toast('반려 취소','사유를 입력해야 반려할 수 있습니다.','warning');return}
  try{
    const response=await apiFetch(`/isaac/commits/${encodeURIComponent(commitId)}/review`,{
      method:'POST',body:JSON.stringify({decision,note}),
    });
    if(response.status===409){toast('이미 판정된 결과','다른 관리자가 먼저 처리했습니다.','warning');await loadIsaacInstructions();return}
    if(!response.ok){const payload=await response.json().catch(()=>({}));throw new Error(typeof payload.detail==='string'?payload.detail:`REVIEW_${response.status}`)}
    await loadIsaacInstructions();
    closeModal();
    if(decision==='approved'){
      reloadIsaacMapObjects();
      addEvent('success','Isaac 결과 승인','승인된 작업 결과가 Site Work Map에 반영됐습니다.');
      toast('승인 완료','맵에 작업 결과가 반영됐습니다.','success');
    }else{
      addEvent('warning','Isaac 결과 반려',`사유: ${note}`);
      toast('반려 처리','맵에는 반영되지 않습니다.','warning');
    }
    renderAll();
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')toast('판정 실패','서버 연결과 권한을 확인하세요.','danger');
  }
}

/* Modal helpers */
function openModal({eyebrow='EDIT',title,body,footer}){
  $('#modalEyebrow').textContent=eyebrow;$('#modalTitle').textContent=title;$('#modalBody').innerHTML=body;$('#modalFooter').innerHTML=footer||`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" data-modal-save>저장</button>`;$('#modalBackdrop').classList.remove('hidden');$('#modalBackdrop').setAttribute('aria-hidden','false');
  $$('[data-modal-close]',$('#modalFooter')).forEach(b=>b.addEventListener('click',closeModal));
}
function closeModal(){$('#modalBackdrop').classList.add('hidden');$('#modalBackdrop').setAttribute('aria-hidden','true')}
function openNotificationsModal(){
  const recentEvents=state.events.slice(0,10);
  openModal({
    eyebrow:'NOTIFICATIONS',
    title:'최근 알림',
    body:recentEvents.length
      ?`<div class="notification-list">${renderEvents(recentEvents)}</div>`
      :'<div class="empty-state">새로운 알림이 없습니다.</div>',
    footer:'<button class="primary-button" data-modal-close>확인</button>',
  });
}
function openProfileModal(){
  if(!currentUser){
    toast('사용자 정보 확인 중','로그인 정보를 불러온 뒤 다시 시도해 주세요.','warning');
    return;
  }
  const roleLabel={admin:'관리자',manager:'현장관리자',reviewer:'검토자',viewer:'조회자'}[currentUser.role]||currentUser.role;
  const statusLabel=currentUser.is_active?'활성':'비활성';
  openModal({
    eyebrow:'MY PROFILE',
    title:'내 계정 정보',
    body:`<div class="profile-summary">
      <div class="profile-summary-avatar">${esc((currentUser.full_name||currentUser.username).trim().slice(0,1).toUpperCase())}</div>
      <div><strong>${esc(currentUser.full_name)}</strong><span>${esc(roleLabel)}</span></div>
    </div>
    <div class="profile-detail-list">
      <div><span>로그인 아이디</span><strong>${esc(currentUser.username)}</strong></div>
      <div><span>표시 이름</span><strong>${esc(currentUser.full_name)}</strong></div>
      <div><span>권한</span><strong>${esc(roleLabel)}</strong></div>
      <div><span>계정 상태</span><strong class="profile-status ${currentUser.is_active?'active':'inactive'}">${statusLabel}</strong></div>
    </div>
    <p class="profile-security-note">비밀번호와 로그인 보안 키는 화면에 표시하지 않습니다.</p>`,
    footer:'<button class="primary-button" data-modal-close>확인</button>',
  });
}
function openProjectModal(){
  const p=state.project;
  openModal({eyebrow:'PROJECT CONFIGURATION',title:'현장·건설사 기본정보',body:`<div class="form-grid"><div class="form-group full"><label>프로젝트명</label><input class="form-control" id="fProjectName" value="${esc(p.name)}"></div><div class="form-group"><label>건설사 / 시공사</label><input class="form-control" id="fContractor" value="${esc(state.company.contractor)}"></div><div class="form-group"><label>현장관리자</label><input class="form-control" id="fManager" value="${esc(state.manager.name)}"></div><div class="form-group"><label>현장 위치</label><input class="form-control" id="fLocation" value="${esc(p.location)}"></div><div class="form-group"><label>좌표계</label><input class="form-control" id="fCoord" value="${esc(p.coordinateSystem)}"></div><div class="form-group"><label>착공일</label><input type="date" class="form-control" id="fStart" value="${p.startDate}"></div><div class="form-group"><label>준공일</label><input type="date" class="form-control" id="fEnd" value="${p.endDate}"></div><div class="form-group"><label>터파기 물량 (㎥)</label><input type="number" class="form-control" id="fVolume" value="${p.excavationVolume}"></div><div class="form-group"><label>도급 총공사비 (원)</label><input type="number" class="form-control" id="fCost" value="${p.contractCost}"></div></div>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveProjectBtn">변경 저장</button>`});
  $('[data-modal-close]').addEventListener('click',closeModal);$('#saveProjectBtn').addEventListener('click',()=>{p.name=$('#fProjectName').value;p.shortName=p.name.replace(/하수관로.*/,'').trim()||p.name;state.company.contractor=$('#fContractor').value;state.manager.name=$('#fManager').value;p.location=$('#fLocation').value;p.coordinateSystem=$('#fCoord').value;p.startDate=$('#fStart').value;p.endDate=$('#fEnd').value;p.excavationVolume=Number($('#fVolume').value)||p.excavationVolume;p.contractCost=Number($('#fCost').value)||p.contractCost;closeModal();toast('기본정보 저장','현장과 관리자 정보가 로컬 데이터에 반영됐습니다.','success');renderAll()});
}
function openReadinessModal(id){
  const item=id?state.readiness.find(r=>r.id===id):{id:`custom-${Date.now()}`,name:'',category:'운영 보조 데이터',grade:'C',status:'missing',source:'USER INPUT',value:'',action:'관리자 확인',desc:''};
  openModal({eyebrow:'WORK PACKAGE PRE-CHECK',title:id?'확인 항목 처리':'확인 항목 추가',body:`<div class="form-grid"><div class="form-group"><label>항목명</label><input class="form-control" id="rName" value="${esc(item.name)}"></div><div class="form-group"><label>구분</label><input class="form-control" id="rCategory" value="${esc(item.category)}"></div><div class="form-group"><label>준비 상태</label><select class="form-control" id="rStatus">${[['ready','준비 완료'],['simulated','준비 완료 · 가상 데이터'],['needs-confirmation','확인 필요'],['missing','누락']].map(([v,l])=>`<option value="${v}" ${v===item.status?'selected':''}>${l}</option>`).join('')}</select></div><div class="form-group"><label>데이터 출처</label><select class="form-control" id="rSource">${['PUBLIC PROJECT','MANUFACTURER SPEC','STANDARD-BASED','USER INPUT','ASSUMED','SIMULATED'].map(x=>`<option ${x===item.source?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group full"><label>확인 값</label><input class="form-control" id="rValue" value="${esc(item.value)}"></div><div class="form-group full"><label>판단 기준 설명</label><textarea class="form-control" id="rDesc">${esc(item.desc)}</textarea></div><div class="form-group full"><label>확인 필요 시 조치</label><input class="form-control" id="rAction" value="${esc(item.action)}"></div><div class="form-group full"><label>관련 파일 (로컬 파일명만 표시)</label><input type="file" class="form-control" id="rFile"><span class="form-hint">파일 내용은 자동 분석하지 않으며 등록 여부와 파일명만 저장합니다.</span></div></div>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveReadinessBtn">확인 내용 저장</button>`});
  $('[data-modal-close]').addEventListener('click',closeModal);$('#saveReadinessBtn').addEventListener('click',()=>{item.name=$('#rName').value;item.category=$('#rCategory').value;item.status=$('#rStatus').value;item.source=$('#rSource').value;item.value=$('#rValue').value;item.desc=$('#rDesc').value;item.action=$('#rAction').value;item.updatedAt=new Date().toISOString();const f=$('#rFile').files[0];if(f){item.value=`${item.value} · ${f.name}`;item.status='ready';item.source='USER INPUT'}if(!id)state.readiness.push(item);closeModal();toast('작업 준비 확인 갱신',`${item.name} 항목이 저장됐습니다.`,'success');renderAll()});
}
function openReadinessSourceModal(id){
  const item=state.readiness.find(r=>r.id===id);if(!item)return;
  const kind=['SIMULATED','ASSUMED'].includes(String(item.source).toUpperCase())||item.status==='simulated'?'가상·가정 데이터':'실제·입력 데이터';
  const updated=item.updatedAt?new Date(item.updatedAt).toLocaleString('ko-KR'):'프로젝트 초기 데이터';
  openModal({eyebrow:'SOURCE & STATUS',title:item.name,body:`<div class="source-detail-grid"><div><span>데이터 출처</span><strong>${esc(item.source)}</strong></div><div><span>데이터 구분</span><strong>${kind}</strong></div><div><span>마지막 수정</span><strong>${esc(updated)}</strong></div><div><span>현재 상태</span><strong>${readinessStatusLabel(item.status)}</strong></div></div><div class="source-detail-value"><span>확인 값</span><strong>${esc(item.value||'입력된 값 없음')}</strong><p>${esc(item.desc)}</p></div>`,footer:`<button class="ghost-button" data-modal-close>닫기</button><button class="primary-button" data-edit-readiness="${item.id}">확인 내용 수정</button>`});
}
function equipmentEditorPreview(e){
  const imageUrl=EQUIPMENT_PHOTOS[e.model];
  const visual=imageUrl
    ?`<img src="${imageUrl}" alt="${esc(e.model)} 장비 전체 사진">`
    :machineSvg(e.icon,e.color);
  return `<div class="equipment-editor-preview">${visual}<div><strong>${esc(e.model)}</strong><span>${esc(e.manufacturer)} · ${esc(e.type)}</span></div></div>`;
}
function openEquipmentModal(id){
  const e=id?state.equipment.find(x=>x.id===id):{id:`EQ-${Date.now()}`,model:'',manufacturer:'HD Hyundai',type:'건설기계',icon:'excavator',status:'available',operatingWeight:0,bucketCapacity:0,workBucket:0,power:0,maxDepth:0,travelSpeed:0,supports:[],evidence:[],autonomy:[],autonomySource:'ASSUMED',specSource:'USER INPUT',sourceUrl:'',color:'#f0ad2e',assigned:''};
  queueMicrotask(()=>$('#modalBody')?.insertAdjacentHTML('afterbegin',equipmentEditorPreview(e)));
  openModal({eyebrow:'EQUIPMENT REGISTRY',title:id?`${e.model} 제원·연동 수정`:'장비 등록',body:`<div class="form-grid"><div class="form-group"><label>장비 ID</label><input class="form-control" id="eId" value="${esc(e.id)}" ${id?'readonly':''}></div><div class="form-group"><label>모델명</label><input class="form-control" id="eModel" value="${esc(e.model)}"></div><div class="form-group"><label>제조사</label><input class="form-control" id="eManufacturer" value="${esc(e.manufacturer)}"></div><div class="form-group"><label>장비 종류</label><input class="form-control" id="eType" value="${esc(e.type)}"></div><div class="form-group"><label>운전중량 (t)</label><input type="number" step="0.01" class="form-control" id="eWeight" value="${e.operatingWeight}"></div><div class="form-group"><label>표준 버킷 (㎥)</label><input type="number" step="0.01" class="form-control" id="eBucket" value="${e.bucketCapacity}"></div><div class="form-group"><label>프로젝트 작업 버킷 (㎥)</label><input type="number" step="0.01" class="form-control" id="eWorkBucket" value="${e.workBucket}"></div><div class="form-group"><label>정격출력 (kW)</label><input type="number" step="0.1" class="form-control" id="ePower" value="${e.power}"></div><div class="form-group"><label>최대 굴착깊이 (m)</label><input type="number" step="0.01" class="form-control" id="eDepth" value="${e.maxDepth}"></div><div class="form-group"><label>제원 출처</label><select class="form-control" id="eSource">${['MANUFACTURER SPEC','PROJECT REQUIREMENT','USER INPUT','ASSUMED'].map(x=>`<option ${x===e.specSource?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group full"><label>지원 작업 (쉼표 구분)</label><input class="form-control" id="eSupports" value="${esc(e.supports.join(', '))}"></div><div class="form-group full"><label>반환 Evidence (쉼표 구분)</label><input class="form-control" id="eEvidence" value="${esc(e.evidence.join(', '))}"></div><div class="form-group full"><label>가정한 자율화 인터페이스 (쉼표 구분)</label><input class="form-control" id="eAutonomy" value="${esc(e.autonomy.join(', '))}"><span class="form-hint">실제 HD 장비 API가 아니라 컨셉 검증용 ASSUMED 항목입니다.</span></div><div class="form-group full"><label>공식 제원 URL</label><input class="form-control" id="eUrl" value="${esc(e.sourceUrl)}"></div></div>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveEquipmentBtn">장비 저장</button>`});
  $('[data-modal-close]').addEventListener('click',closeModal);$('#saveEquipmentBtn').addEventListener('click',()=>{e.id=$('#eId').value;e.model=$('#eModel').value;e.manufacturer=$('#eManufacturer').value;e.type=$('#eType').value;e.operatingWeight=Number($('#eWeight').value)||0;e.bucketCapacity=Number($('#eBucket').value)||0;e.workBucket=Number($('#eWorkBucket').value)||0;e.power=Number($('#ePower').value)||0;e.maxDepth=Number($('#eDepth').value)||0;e.specSource=$('#eSource').value;e.supports=$('#eSupports').value.split(',').map(s=>s.trim()).filter(Boolean);e.evidence=$('#eEvidence').value.split(',').map(s=>s.trim()).filter(Boolean);e.autonomy=$('#eAutonomy').value.split(',').map(s=>s.trim()).filter(Boolean);e.sourceUrl=$('#eUrl').value;if(!id)state.equipment.push(e);closeModal();toast('장비 Registry 저장',`${e.model}의 제원과 Capability가 반영됐습니다.`,'success');renderAll()});
}
function openWpModal(id){
  const w=id?state.workPackages.find(x=>x.id===id):{id:`WP-SASANG-${String.fromCharCode(65+state.workPackages.length)}01`,zone:String.fromCharCode(65+state.workPackages.length),name:'신규 자율화 작업',task:'EXCAVATION',length:0,target:100,raw:0,qualified:0,remaining:100,status:'draft',version:1,eta:'대기',risk:'low',start:'-',end:'-',x:0,y:0,width:0,color:'#3d7fa0',completionThreshold:100,observationThreshold:90,toleranceMm:50,assignments:[]};
  const rows=deepClone(assignmentsForWp(w));
  const assignmentRow=(a={id:`AS-${Date.now()}-${Math.random()}`,equipmentId:'',role:'주 작업',quantity:1})=>`<div class="assignment-editor-row" data-assignment-row><select class="form-control assignment-role"><option ${a.role==='주 작업'?'selected':''}>주 작업</option><option ${a.role==='상차'?'selected':''}>상차</option><option ${a.role==='운반'?'selected':''}>운반</option><option ${a.role==='보조'?'selected':''}>보조</option></select><select class="form-control assignment-equipment"><option value="">장비 선택</option>${state.equipment.map(e=>`<option value="${e.id}" ${e.id===a.equipmentId?'selected':''}>${e.model} · ${e.type}</option>`).join('')}</select><input type="number" min="1" class="form-control assignment-qty" value="${a.quantity||1}"><button type="button" class="icon-button plain assignment-remove" title="삭제">×</button></div>`;
  openModal({eyebrow:'WORK PACKAGE COMPILER',title:id?`${w.id} · 조건·장비팀 편집`:'Work Package 생성',body:`<div class="form-grid"><div class="form-group"><label>Work Package ID</label><input class="form-control" id="wId" value="${esc(w.id)}" ${id?'readonly':''}></div><div class="form-group"><label>Zone</label><input class="form-control" id="wZone" value="${esc(w.zone)}"></div><div class="form-group full"><label>작업명</label><input class="form-control" id="wName" value="${esc(w.name)}"></div><div class="form-group"><label>작업 종류</label><select class="form-control" id="wTask">${['EXCAVATION','SMALL_EXCAVATION','GRADING','LOADING','HAUL'].map(x=>`<option ${x===w.task?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group"><label>목표 물량 (㎥)</label><input type="number" class="form-control" id="wTarget" value="${w.target}"></div><div class="form-group"><label>작업 연장 (m)</label><input type="number" step="0.1" class="form-control" id="wLength" value="${w.length}"></div><div class="form-group"><label>Qualified 완료조건 (%)</label><input type="number" min="0" max="100" class="form-control" id="wCompletion" value="${w.completionThreshold??100}"></div><div class="form-group"><label>관측률 기준 (%)</label><input type="number" min="0" max="100" class="form-control" id="wObservation" value="${w.observationThreshold??90}"></div><div class="form-group"><label>결과 허용오차 (mm)</label><input type="number" min="0" class="form-control" id="wTolerance" value="${w.toleranceMm??50}"></div><div class="form-group full"><label>Zone 장비팀 배정</label><div class="assignment-editor-head"><span>역할</span><span>장비 Profile</span><span>수량</span><span></span></div><div class="assignment-editor" id="assignmentEditor">${rows.map(assignmentRow).join('')}</div><button type="button" class="ghost-button button-sm" id="addAssignmentBtn">+ 장비 역할 추가</button><span class="form-hint">계획 단계에는 모델×수량을 배정하고, 실제 연동 단계에서 개별 장비 ID에 연결합니다.</span></div><div class="form-group full"><label>목표·종료조건</label><textarea class="form-control" id="wConditions">목표 작업량 달성, 작업경계 준수, 필수 Evidence 수집 후 결과 제출</textarea></div><div class="form-group full"><label>금지·중단조건</label><textarea class="form-control" id="wStop">금지구역 침범, 위치 신뢰도 저하, 장비 이상 이벤트 발생 시 작업 중단</textarea></div></div>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveWpBtn">저장·장비팀 적합성 확인</button>`});
  const addRow=(a)=>{$('#assignmentEditor').insertAdjacentHTML('beforeend',assignmentRow(a));bindRemove()};const bindRemove=()=>$$('.assignment-remove',$('#assignmentEditor')).forEach(b=>b.onclick=()=>b.closest('[data-assignment-row]').remove());bindRemove();$('#addAssignmentBtn').onclick=()=>addRow();
  $('#saveWpBtn').addEventListener('click',()=>{
    w.id=$('#wId').value;w.zone=$('#wZone').value;w.name=$('#wName').value;w.task=$('#wTask').value;w.target=Number($('#wTarget').value)||0;w.remaining=Math.round(w.target*(100-w.qualified)/100);w.length=Number($('#wLength').value)||0;w.completionThreshold=Number($('#wCompletion').value)||100;w.observationThreshold=Number($('#wObservation').value)||90;w.toleranceMm=Number($('#wTolerance').value)||0;
    w.assignments=$$('[data-assignment-row]',$('#assignmentEditor')).map((row,i)=>({id:`AS-${w.id}-${i+1}`,role:$('.assignment-role',row).value,equipmentId:$('.assignment-equipment',row).value,quantity:Math.max(1,Number($('.assignment-qty',row).value)||1)})).filter(a=>a.equipmentId);
    const primary=primaryAssignment(w);const compatibility=w.assignments.map(a=>assignmentCompatibility(w,a));const primaryOk=primary&&assignmentCompatibility(w,primary).ok;
    if(!id){state.workPackages.push(w);state.evidence[w.id]={rule:0,completeness:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:['Execution Session','Result Evidence'],conflicts:[],externalEvidence:[]}}
    closeModal();toast(primaryOk&&compatibility.every(c=>c.ok)?'장비팀 배정 완료':'조건부 Work Package 저장',primaryOk?`${assignmentRoleSummary(w)} 배정이 저장됐습니다.`:'주 작업 장비의 Capability 또는 역할을 확인하세요.',primaryOk?'success':'warning');renderAll();
  });
}
function showSourcesModal(){openModal({eyebrow:'SOURCE DISCLOSURE',title:'공개 장비 제원 출처',body:`<div class="source-list"><div class="source-row"><div><strong>HX210AL</strong><small>22.15t · 0.92㎥ · 128kW · 최대 굴착깊이 6.64m</small></div><a class="source-link" target="_blank" rel="noopener" href="https://www.hyundai-ce.com/en/products/view?productsSeq=374">공식 페이지 ↗</a></div><div class="source-row"><div><strong>HX48AZ</strong><small>5.03t · 0.15㎥ · 29.1kW · 최대 굴착깊이 3.50m</small></div><a class="source-link" target="_blank" rel="noopener" href="https://www.hyundai-ce.com/en/products/view?productsSeq=573">공식 페이지 ↗</a></div><div class="source-row"><div><strong>HL930A TM</strong><small>11.96t · 1.7㎥ · 96kW · 최고속도 39.5km/h</small></div><a class="source-link" target="_blank" rel="noopener" href="https://www.hyundai-ce.com/en/products/view?productsSeq=510">공식 페이지 ↗</a></div></div><div class="divider"></div><p class="muted" style="font-size:10px;line-height:1.65">자율화 Work Package 수신, Tool Pose 반환, 원격 중지와 같은 인터페이스는 실제 제품 기능을 주장하는 것이 아니라 컨셉 검증을 위한 ASSUMED 데이터입니다.</p>`,footer:`<button class="primary-button" data-modal-close>확인</button>`});$('[data-modal-close]').addEventListener('click',closeModal)}
function showArchitectureModal(){openModal({eyebrow:'SITEGIT CORE',title:'자율화 운영·검증 아키텍처',body:`<div class="onboard-summary"><div class="onboard-summary-row"><strong>01 · Site Data Onboarding</strong><span>건설사 기존 데이터 → Data Readiness</span></div><div class="onboard-summary-row"><strong>02 · Work Package Compiler</strong><span>작업 대상·목표·제약·종료조건</span></div><div class="onboard-summary-row"><strong>03 · HD Equipment Connector</strong><span>장비 Capability 비교·작업 배포</span></div><div class="onboard-summary-row"><strong>04 · Autonomous Equipment</strong><span>인지·경로·작업기 제어·실제 수행</span></div><div class="onboard-summary-row"><strong>05 · Execution & Evidence</strong><span>장비 이벤트·궤적·작업 결과 귀속</span></div><div class="onboard-summary-row"><strong>06 · Trust & Human Gate</strong><span>Rule·완결성·관측 신뢰도 → 관리자 결정</span></div><div class="onboard-summary-row"><strong>07 · Version Update</strong><span>결정 이력·보완·다음 Plan 연결</span></div></div>`,footer:`<button class="primary-button" data-modal-close>확인</button>`});$('[data-modal-close]').addEventListener('click',closeModal)}

/* Onboarding */
function openOnboarding(){onboardingStep=0;renderOnboarding();$('#onboardingBackdrop').classList.remove('hidden')}
function closeOnboarding(){safeSetItem(ONBOARD_KEY,'1');$('#onboardingBackdrop').classList.add('hidden');renderAll()}
function renderOnboarding(){
  $('#onboardingProgress').style.setProperty('--step-progress',`${(onboardingStep+1)*25}%`);
  const c=$('#onboardingContent');
  if(onboardingStep===0)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 1 / 4 · PROJECT</div><h2>건설사와 현장 기본정보</h2><p class="intro">사상구 공개 발주 정보를 기본값으로 채웠습니다. 실제 프로젝트에 맞게 언제든 수정할 수 있습니다.</p><div class="form-grid"><div class="form-group full"><label>프로젝트명</label><input class="form-control" id="oProject" value="${esc(state.project.name)}"></div><div class="form-group"><label>시공사</label><input class="form-control" id="oContractor" value="${esc(state.company.contractor)}"></div><div class="form-group"><label>현장관리자</label><input class="form-control" id="oManager" value="${esc(state.manager.name)}"></div><div class="form-group"><label>현장 위치</label><input class="form-control" id="oLocation" value="${esc(state.project.location)}"></div><div class="form-group"><label>좌표계</label><input class="form-control" id="oCoord" value="${esc(state.project.coordinateSystem)}"></div></div></div>`;
  if(onboardingStep===1)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 2 / 4 · PRE-CHECK</div><h2>작업지시 준비 확인</h2><p class="intro">Work Package 생성 전에 필요한 현장 정보와 판단 기준을 확인합니다.</p><div class="onboard-summary">${state.readiness.slice(0,8).map(r=>`<div class="onboard-summary-row"><div><strong>${esc(r.name)}</strong><div style="margin-top:5px">${sourceBadge(r.source)}</div></div><span class="status-chip ${r.status}">${readinessStatusLabel(r.status)}</span></div>`).join('')}</div></div>`;
  if(onboardingStep===2)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 3 / 4 · EQUIPMENT</div><h2>제조사 장비 Capability</h2><p class="intro">HD현대 공식 공개 제원을 기본 등록했습니다. 자율화 인터페이스는 ASSUMED로 분리했습니다.</p>${state.equipment.slice(0,4).map(e=>`<div class="onboard-equip"><div class="onboard-equip-icon">${miniMachineSvg(e.icon,e.color)}</div><div><strong>${e.model} · ${e.type}</strong><small>${e.operatingWeight}t · ${e.bucketCapacity||'-'}㎥ · ${e.power||'-'}kW</small></div><div class="spacer"></div>${sourceBadge(e.specSource)}</div>`).join('')}</div>`;
  if(onboardingStep===3)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 4 / 4 · LAUNCH</div><h2>SiteGit Concept 준비 완료</h2><p class="intro">시뮬레이터 없이도 Data Readiness → Work Package → 장비 적합성 → 가상 실행 → Evidence → 관리자 승인 흐름을 조작할 수 있습니다.</p><div class="onboard-summary"><div class="onboard-summary-row"><strong>프로젝트</strong><span>${esc(state.project.shortName)}</span></div><div class="onboard-summary-row"><strong>공개 터파기 물량</strong><span>${num(state.project.excavationVolume)}㎥</span></div><div class="onboard-summary-row"><strong>Work Package</strong><span>${state.workPackages.length}개</span></div><div class="onboard-summary-row"><strong>장비 Registry</strong><span>${state.equipment.length}대</span></div><div class="onboard-summary-row"><strong>연동 모드</strong><span>SHARED DB · SIMULATED</span></div></div><div style="margin-top:17px;padding:13px;border-radius:12px;background:#fff3dc;color:#785d29;font-size:9px;line-height:1.65"><b>주의:</b> 공간 좌표, 자율화 API, 진행률, Evidence와 Conflict는 컨셉 검증용 가상 데이터이며 실제 시공·품질 판단에 사용할 수 없습니다.</div></div>`;
  $('#onboardingPrevBtn').style.visibility=onboardingStep===0?'hidden':'visible';$('#onboardingNextBtn').textContent=onboardingStep===3?'Control Center 열기':'다음';
}
function saveOnboardingStep(){
  if(onboardingStep===0){state.project.name=$('#oProject')?.value||state.project.name;state.project.shortName=state.project.name.replace(/하수관로.*/,'').trim()||state.project.name;state.company.contractor=$('#oContractor')?.value||state.company.contractor;state.manager.name=$('#oManager')?.value||state.manager.name;state.project.location=$('#oLocation')?.value||state.project.location;state.project.coordinateSystem=$('#oCoord')?.value||state.project.coordinateSystem;}
}
$('#onboardingPrevBtn').addEventListener('click',()=>{saveOnboardingStep();onboardingStep=Math.max(0,onboardingStep-1);renderOnboarding()});
$('#onboardingNextBtn').addEventListener('click',()=>{saveOnboardingStep();if(onboardingStep<3){onboardingStep++;renderOnboarding()}else closeOnboarding()});
$('#quickStartBtn').addEventListener('click',closeOnboarding);

/* Data import/export/reset */
function exportJson(){
  const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='SiteGit_Sasang_Concept_Data.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('JSON 내보내기','현재 프로젝트·장비·작업·Evidence 데이터가 저장됐습니다.','success')
}
$('#jsonImportInput').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const parsed=JSON.parse(await file.text());state=mergeDefaults(deepClone(DEFAULT_STATE),parsed);renderAll();toast('JSON 불러오기 완료',file.name,'success')}catch(err){toast('불러오기 실패','유효한 SiteGit JSON 파일인지 확인하세요.','danger')}e.target.value=''});
function confirmReset(){openModal({eyebrow:'DANGER ZONE',title:'전체 데모를 초기화할까요?',body:`<p style="font-size:11px;line-height:1.7;color:var(--slate-600)">현장정보, 장비 수정값, Work Package, Evidence와 Version 이력이 기본 사상구 데모 상태로 돌아갑니다. 내보내지 않은 변경사항은 복구할 수 없습니다.</p>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="danger-button" id="confirmResetBtn">초기화</button>`});$('[data-modal-close]').addEventListener('click',closeModal);$('#confirmResetBtn').addEventListener('click',()=>{if(simTimer)clearInterval(simTimer);state=deepClone(DEFAULT_STATE);safeRemoveItem(STORAGE_KEY);closeModal();toast('데모 초기화 완료','기본 사상구 컨셉 데이터로 돌아갔습니다.','success');renderAll()})}
function confirmFullReset(){
  openModal({
    eyebrow:'DEMO FULL RESET',
    title:'처음부터 다시 시연할까요?',
    body:`<div class="full-reset-warning"><strong>다음 항목이 초기화됩니다.</strong><ul><li>현장정보·장비 제원·Work Package</li><li>Evidence·Conflict·Version 데모 이력</li><li>이 브라우저의 초기 설정 완료 기록</li><li>현재 로그인 세션</li></ul><p>사용자 계정과 서버의 감사 로그는 삭제하지 않습니다. 내보내지 않은 데모 변경사항은 복구할 수 없습니다.</p></div>`,
    footer:'<button class="ghost-button" data-modal-close>취소</button><button class="danger-button" id="confirmFullResetBtn">완전 초기화 후 로그아웃</button>',
  });
  $('#confirmFullResetBtn').addEventListener('click',performFullReset);
}
async function performFullReset(){
  const button=$('#confirmFullResetBtn');
  const previousState=state;
  const previousOnboarded=safeGetItem(ONBOARD_KEY);
  button.disabled=true;button.textContent='초기화 중...';
  if(simTimer)clearInterval(simTimer);
  clearTimeout(remoteSaveTimer);
  state=deepClone(DEFAULT_STATE);
  safeRemoveItem(STORAGE_KEY);
  safeRemoveItem(ONBOARD_KEY);
  try{
    if(!remoteReady||!remoteCanEdit)throw new Error('RESET_NOT_READY');
    const response=await apiFetch(`/state/${PROJECT_ID}`,{method:'PUT',body:JSON.stringify({payload:state,revision:remoteRevision,source:'full-reset'})});
    if(!response.ok)throw new Error(`RESET_${response.status}`);
    await apiFetch('/auth/logout',{method:'POST',body:'{}'}).catch(()=>null);
    location.href='/login';
  }catch(error){
    state=previousState;
    safeSetItem(STORAGE_KEY,JSON.stringify(previousState));
    if(previousOnboarded)safeSetItem(ONBOARD_KEY,previousOnboarded);
    button.disabled=false;button.textContent='완전 초기화 후 로그아웃';
    toast('완전 초기화 실패','공동 DB 연결을 확인한 뒤 다시 시도해 주세요.','danger');
  }
}

function toast(title,message,type='success'){
  const el=document.createElement('div');el.className=`toast ${type}`;el.innerHTML=`<div class="toast-icon">${type==='success'?'✓':type==='danger'?'!':'△'}</div><div><strong>${esc(title)}</strong><p>${esc(message)}</p></div>`;$('#toastStack').appendChild(el);setTimeout(()=>{el.style.opacity='0';el.style.transform='translateY(8px)';setTimeout(()=>el.remove(),250)},3500)
}

/* Initial boot */
prepareState();
renderAll();
if(!safeGetItem(ONBOARD_KEY)) openOnboarding();
bootstrapSharedState();
$('#notificationsBtn')?.addEventListener('click',openNotificationsModal);
$('#profileBtn')?.addEventListener('click',openProfileModal);
$('#logoutBtn')?.addEventListener('click',async()=>{
  try{await apiFetch('/auth/logout',{method:'POST',body:'{}'})}catch(e){}
  location.href='/login';
});
document.addEventListener('visibilitychange',()=>{
  if(document.visibilityState==='visible'&&remoteReady&&(!remoteSocket||remoteSocket.readyState===WebSocket.CLOSED))connectRealtime();
});
document.addEventListener('click',event=>{
  if(remoteCanEdit)return;
  const button=event.target.closest('button');
  if(!button)return;
  const allowed=button.matches('.nav-item,#mobileMenuBtn,#logoutBtn,#notificationsBtn,#profileBtn,#closeModalBtn,[data-modal-close],[data-select-wp],[data-wp-id],[data-zone]');
  if(allowed)return;
  event.preventDefault();
  event.stopImmediatePropagation();
  toast('조회 전용 계정','공동 DB를 변경할 권한이 없습니다.','warning');
},true);
