/* SiteGit Concept Prototype
 * Static, offline-capable, localStorage-based concept UI.
 * Public project figures are derived from the uploaded Sasang-gu analysis report.
 * Manufacturer specifications are based on official HD Hyundai Construction Equipment pages.
 * Spatial geometry, autonomy API, live progress, evidence and conflicts are simulated.
 */

const STORAGE_KEY = 'sitegit-concept-prototype-v2';
const ONBOARD_KEY = 'sitegit-concept-onboarded-v2';
const VIEW_STORAGE_KEY = 'sitegit-view-state-v1';
const JUDGE_DEMO_ONBOARD_SESSION_KEY = 'sitegit-judge-demo-onboarding-v1';
const PROJECT_ID = 'SASANG-001';
const API_BASE = '/api/v1';
// Zone/Timeline 기능 도입 이전의 데모 Work Package와 Commit은 새 지도에서
// Baseline으로만 취급합니다. 이 시각 이후 발행된 실제 지시부터 동적 Zone과
// Timeline 항목으로 노출됩니다.
const MAP_FEATURE_CUTOVER_AT = '2026-08-19T14:52:00.000Z';
const EQUIPMENT_PHOTOS = {
  HX210AL:'/static/assets/equipment/hx210al-registry.jpg',
  HX48AZ:'/static/assets/equipment/hx48az.jpg',
  'HL930A TM':'/static/assets/equipment/hl930a-tm.jpg',
  'Generic Dump 4.5t':'/static/assets/equipment/generic-dump-4-5t.png',
  'Generic Dump 24t':'/static/assets/equipment/generic-dump-24t.png',
};
const CURRENT_DEMO_PROFILE_VERSION = 'pipeline-demo-equipment-v4';
const CURRENT_DEMO_PROJECT = {
  name:'건설현장 관로 시공 통합 데모',
  shortName:'관로 시공 통합 데모',
  location:'관로 시공 데모 현장',
  scope:'Zone A · 관로 79.2m · 터파기 → 관로 설치 → 되메우기',
  startDate:'2026-08-24', endDate:'2026-08-24',
  totalCost:0, contractCost:0, netCost:0, earthworkCost:0, earthworkShare:0,
  excavationVolume:1826.9,
  coordinateSystem:'현장 로컬 좌표 · Z-up · 단위 m',
  sourceType:'APPROVED SCENARIO DRAWING',
};
const CURRENT_DEMO_EQUIPMENT = [
  {
    id:'EXC-001', model:'HX210AL', manufacturer:'HD Hyundai', type:'중형 굴착기', icon:'excavator', status:'available',
    operatingWeight:22.15, bucketCapacity:0.92, workBucket:0.60, power:128, maxDepth:6.64, travelSpeed:5.8,
    supports:['터파기','관로 설치','되메우기'], evidence:['Equipment Camera','3D Raycast LiDAR','IMU','Equipment Pose','Bucket Tip Depth','Work Events'],
    autonomy:['Work Package 수신','작업 실행','진행 상태 반환','Evidence Commit 생성','원격 중지'], autonomySource:'FIELD SYSTEM', specSource:'MANUFACTURER SPEC',
    sourceUrl:'https://www.hyundai-ce.com/en/products/view?productsSeq=374', color:'#f3b331', assigned:'Zone A · 작업전선 1', workfrontId:'EXC-FRONT-01', primPath:'/World/Equipment/EXC_001'
  },
  {
    id:'EXC-002', model:'HX210AL', manufacturer:'HD Hyundai', type:'중형 굴착기', icon:'excavator', status:'available',
    operatingWeight:22.15, bucketCapacity:0.92, workBucket:0.60, power:128, maxDepth:6.64, travelSpeed:5.8,
    supports:['터파기','관로 설치','되메우기','보완 굴착'], evidence:['Equipment Camera','3D Raycast LiDAR','IMU','Equipment Pose','Bucket Tip Depth','Work Events'],
    autonomy:['Work Package 수신','작업 실행','보완 작업 실행','진행 상태 반환','Evidence Commit 생성','원격 중지'], autonomySource:'FIELD SYSTEM', specSource:'MANUFACTURER SPEC',
    sourceUrl:'https://www.hyundai-ce.com/en/products/view?productsSeq=374', color:'#f0aa2c', assigned:'Zone A · 작업전선 2', workfrontId:'EXC-FRONT-02', primPath:'/World/Equipment/EXC_002'
  },
  {
    id:'EXC-003', model:'HX210AL', manufacturer:'HD Hyundai', type:'중형 굴착기', icon:'excavator', status:'available',
    operatingWeight:22.15, bucketCapacity:0.92, workBucket:0.60, power:128, maxDepth:6.64, travelSpeed:5.8,
    supports:['터파기','관로 설치','되메우기'], evidence:['Equipment Camera','3D Raycast LiDAR','IMU','Equipment Pose','Bucket Tip Depth','Work Events'],
    autonomy:['Work Package 수신','작업 실행','진행 상태 반환','Evidence Commit 생성','원격 중지'], autonomySource:'FIELD SYSTEM', specSource:'MANUFACTURER SPEC',
    sourceUrl:'https://www.hyundai-ce.com/en/products/view?productsSeq=374', color:'#eaa52a', assigned:'Zone A · 작업전선 3', workfrontId:'EXC-FRONT-03', primPath:'/World/Equipment/EXC_003'
  },
  {
    id:'EXC-004', model:'HX210AL', manufacturer:'HD Hyundai', type:'중형 굴착기', icon:'excavator', status:'available',
    operatingWeight:22.15, bucketCapacity:0.92, workBucket:0.60, power:128, maxDepth:6.64, travelSpeed:5.8,
    supports:['토사 굴착','상부체 선회','토사 적치'], evidence:['Equipment Camera','IMU','Equipment Pose','Bucket Tip Depth','Work Events'],
    autonomy:['Work Package 수신','작업 실행','진행 상태 반환','Evidence Commit 생성','원격 중지'], autonomySource:'FIELD SYSTEM', specSource:'MANUFACTURER SPEC',
    sourceUrl:'https://www.hyundai-ce.com/en/products/view?productsSeq=374', color:'#d99a28', assigned:'Zone B · 토사 이동', workfrontId:'SOIL-RELOCATION-01', primPath:'/World/Equipment/EXC_004'
  },
];
const CURRENT_DEMO_READINESS = [
  {id:'coord',name:'현장 좌표계',category:'현장 기준',grade:'A',status:'ready',source:'FIELD SYSTEM',value:'Z-up · meter',action:'정상',desc:'도면, 지형, 장비와 센서 좌표를 같은 현장 좌표계로 연결합니다.'},
  {id:'zone',name:'작업구역 Geometry',category:'작업지시',grade:'A',status:'ready',source:'APPROVED DRAWING',value:'Zone A · 관로 공사 79.2m',action:'정상',desc:'관로 공사 전체를 Zone A로 관리하고 내부를 3개 작업전선으로 분할합니다.'},
  {id:'quantity',name:'목표 작업량',category:'작업지시',grade:'A',status:'ready',source:'APPROVED DRAWING',value:'터파기 1,826.9㎥ · 관로 79.2m · 되메우기 1,737.4㎥',action:'정상',desc:'승인된 관로 데모 도면에서 공정별 목표량을 가져옵니다.'},
  {id:'restricted',name:'금지·보호구역',category:'안전 제약',grade:'A',status:'needs-confirmation',source:'USER INPUT',value:'관리자 확인 필요',action:'하달 전 확인',desc:'실제 현장 적용 시 보호구역과 접근 제한선을 등록합니다.'},
  {id:'baseline',name:'작업 전 기준 지형',category:'결과 검증',grade:'B',status:'ready',source:'FIELD SYSTEM',value:'Construction Site Demolition · TrenchFill 01~08',action:'자동 비교',desc:'초기 채움 토사와 승인된 현장 상태를 공정 비교 기준으로 사용합니다.'},
  {id:'tolerance',name:'허용오차·완료기준',category:'결과 검증',grade:'B',status:'ready',source:'APPROVED DRAWING',value:'공정별 승인 기준 적용',action:'관리자 승인',desc:'터파기, 관로 설치, 되메우기에 서로 다른 승인 기준을 적용합니다.'},
  {id:'evidence',name:'필수 Evidence',category:'결과 검증',grade:'B',status:'ready',source:'SENSOR DATA',value:'Camera · LiDAR · IMU · Pose · Events',action:'정상',desc:'장비 장착 센서와 작업 결과 데이터로 작업 전후 근거를 구성합니다.'},
  {id:'spec',name:'장비 Capability',category:'장비 연동',grade:'C',status:'ready',source:'MANUFACTURER SPEC',value:'HD Hyundai HX210AL 4대',action:'적합성 확인 가능',desc:'Zone A와 Zone B 작업에 투입되는 EXC-001~004의 제조사 제원과 작업 Capability를 관리합니다.'},
  {id:'route',name:'장비 이동경로',category:'운영 제약',grade:'C',status:'simulated',source:'ROUTE PLAN',value:'작업전선별 배치 경로',action:'도면 경로 사용',desc:'승인 도면의 작업전선 배치 좌표를 사용합니다.'},
  {id:'utilities',name:'지중 매설물 정보',category:'현장 변수',grade:'D',status:'missing',source:'USER INPUT',value:'미등록',action:'실증 전 등록',desc:'실제 현장 적용 시 도면과 현장 조사 결과를 추가합니다.'},
  {id:'remote',name:'원격개입 정책',category:'현장 변수',grade:'D',status:'ready',source:'ASSUMED',value:'작업 중지 · 관리자 승인',action:'정상',desc:'Work Package 실행과 다음 공정 Release는 관리자 게이트를 통과합니다.'},
];
let remoteRevision = null;
let remoteReady = false;
let remoteApplying = false;
let remoteSaveInFlight = false;
let remoteSaveTimer = null;
let remoteSocket = null;
let remoteCanEdit = true;
let lastSharedPayloadJson = null;
let currentUser = null;
// Isaac 지시·Commit은 DB 테이블이라 공동 state payload에 들어 있지 않습니다.
// 별도로 받아 두고 대시보드 카드에서만 사용합니다.
let isaacInstructions = [];
let aiWorkPackageDraft = null;
let stageInventory = {connected:false,equipment:[],diggable_targets:[],scene_objects:[],age_seconds:0};
let activeMapLayer = 'work';
let timelineStepIndex = null;
let timelineZoneFilter = 'ALL';
let mapTimelineCommitRefs = null;
let isaacPlanningOverlay = null;
let sitePlans = [];
let approvedSitePlan = null;

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
    { id:'zone', name:'작업구역 Geometry', category:'작업지시', grade:'A', status:'simulated', source:'PLANNING DATA', value:'Zone A–D · 537.1m 작업구간 분할', action:'작업 계획 배포 가능', desc:'승인 도면의 연장을 4개 작업구간으로 분할했습니다.' },
    { id:'quantity', name:'목표 작업량', category:'작업지시', grade:'A', status:'ready', source:'PUBLIC PROJECT', value:'터파기 2,279㎥', action:'정상', desc:'사상구 설계·도급 내역에서 확인한 전체 터파기 물량입니다.' },
    { id:'restricted', name:'금지·보호구역', category:'안전 제약', grade:'A', status:'needs-confirmation', source:'USER INPUT', value:'도로 점유구역 1개 · 매설물 미확인', action:'조건부 배포', desc:'자율화 장비가 반드시 회피해야 할 공간 제약입니다.' },
    { id:'baseline', name:'작업 전 기준 형상', category:'결과 검토', grade:'B', status:'simulated', source:'BASELINE DATA', value:'Baseline surface v1', action:'자동 비교 활성', desc:'등록된 작업 전 기준면을 사용합니다.' },
    { id:'tolerance', name:'허용오차·완료기준', category:'결과 검토', grade:'B', status:'needs-confirmation', source:'ASSUMED', value:'깊이 ±50mm · 관측률 90%', action:'관리자 승인 필요', desc:'공식 현장 기준이 아니라 컨셉 검증용 가정값입니다.' },
    { id:'evidence', name:'필수 Evidence', category:'결과 검토', grade:'B', status:'ready', source:'STANDARD-BASED', value:'Pose · Tool path · Before/After · Events', action:'정상', desc:'장비의 완료 선언을 검토하기 위한 반환 데이터 항목입니다.' },
    { id:'spec', name:'장비 Capability', category:'장비 연동', grade:'C', status:'ready', source:'MANUFACTURER SPEC', value:'HD 공식 공개 제원 3종', action:'적합성 판정 가능', desc:'공개 제원과 자율화 인터페이스 가정을 구분해 관리합니다.' },
    { id:'route', name:'권장 이동경로', category:'운영 효율', grade:'C', status:'missing', source:'USER INPUT', value:'미제공', action:'경고 후 진행 가능', desc:'장비 자율화 시스템이 자체 경로를 생성할 수 있다고 가정합니다.' },
    { id:'utilities', name:'지중 매설물 정보', category:'현장 변화', grade:'D', status:'missing', source:'USER INPUT', value:'미등록', action:'현장 확인으로 대체', desc:'실제 투입 전에는 별도 확인이 필요한 데이터입니다.' },
    { id:'remote', name:'원격개입 정책', category:'현장 변화', grade:'D', status:'simulated', source:'ASSUMED', value:'중대 예외 발생 시 원격 중지', action:'운영 기준 적용', desc:'현장 운영 정책에 따라 관리자 확인이 필요합니다.' },
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
restoreLocalView(loadTabView());
const renderedPages = new Set();
let lastRenderSignature = '';
let onboardingStep = 0;
let simTimer = null;

const PAGE_META = {
  dashboard: ['FIELD OPERATIONS','현장 대시보드'],
  readiness: ['SITE DATA ONBOARDING','자율화 작업 데이터 준비도'],
  workpackages: ['PLAN TO MACHINE LANGUAGE','작업 지시'],
  execution: ['FIELD EXECUTION','작업 현황'],
  equipment: ['EQUIPMENT MANAGEMENT','장비관리'],
  evidence: ['EVIDENCE & TRUST','검토·승인'],
  versions: ['VERSION & AUDIT','작업 이력'],
  settings: ['PROJECT CONFIGURATION','설정'],
};

function deepClone(obj){ return JSON.parse(JSON.stringify(obj)); }
function safeGetItem(key){ try{return localStorage.getItem(key)}catch(e){return null} }
function safeSetItem(key,value){ try{localStorage.setItem(key,value);return true}catch(e){return false} }
function safeRemoveItem(key){ try{localStorage.removeItem(key)}catch(e){} }
function safeGetSessionItem(key){ try{return sessionStorage.getItem(key)}catch(e){return null} }
function safeSetSessionItem(key,value){ try{sessionStorage.setItem(key,value);return true}catch(e){return false} }
function safeRemoveSessionItem(key){ try{sessionStorage.removeItem(key)}catch(e){} }
function loadTabView(){
  try{
    const saved=safeGetSessionItem(VIEW_STORAGE_KEY);
    if(saved)return JSON.parse(saved);
  }catch(e){console.warn('View state load failed',e)}
  return {selectedPage:'dashboard',selectedWpId:''};
}
function persistLocalView(){
  safeSetSessionItem(VIEW_STORAGE_KEY,JSON.stringify({
    selectedPage:state?.selectedPage||'dashboard',
    selectedWpId:state?.selectedWpId||'',
  }));
}
function loadState(){
  try{
    const saved = safeGetItem(STORAGE_KEY);
    if(saved){
      const parsed = JSON.parse(saved);
      const merged=mergeDefaults(deepClone(DEFAULT_STATE), parsed);
      applyCurrentDemoProfile(merged);
      if(merged.project?.coordinateSystem==='SiteGit demolition site frame · Z-up · meter'){
        merged.project.coordinateSystem='현장 로컬 좌표 · Z-up · 단위 m';
      }
      return merged;
    }
  }catch(e){ console.warn('State load failed',e); }
  const fresh=deepClone(DEFAULT_STATE);
  applyCurrentDemoProfile(fresh);
  return fresh;
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
function applyCurrentDemoProfile(target){
  if(!target||typeof target!=='object')return false;
  const equipment=Array.isArray(target.equipment)?target.equipment:[];
  const hasLegacyEquipment=equipment.some(item=>['HX210AL-01','HX48AZ-02','HL930ATM-01','DUMP45-01','DUMP24-01'].includes(item?.id));
  const hasLegacyProject=/사상구|감전처리분구/i.test(`${target.project?.name||''} ${target.project?.shortName||''} ${target.project?.location||''}`);
  const needsProfile=target.demoProfileVersion!==CURRENT_DEMO_PROFILE_VERSION||hasLegacyEquipment||hasLegacyProject;
  if(!needsProfile)return false;

  target.demoProfileVersion=CURRENT_DEMO_PROFILE_VERSION;
  target.company={
    ...(target.company||{}),
    name:'SiteGit 관로 시공 실증팀',
    contractor:'SiteGit 데모 현장',
    manufacturer:'HD Hyundai',
  };
  target.project={...(target.project||{}),...deepClone(CURRENT_DEMO_PROJECT)};
  target.readiness=deepClone(CURRENT_DEMO_READINESS);
  target.equipment=deepClone(CURRENT_DEMO_EQUIPMENT);

  const legacyWorkIds=new Set((Array.isArray(target.workPackages)?target.workPackages:[])
    .filter(item=>/^WP-(?:SASANG|HAUL)-/i.test(String(item?.id||'')))
    .map(item=>item.id));
  if(legacyWorkIds.size){
    target.workPackages=target.workPackages.filter(item=>!legacyWorkIds.has(item.id));
    target.evidence=Object.fromEntries(Object.entries(target.evidence||{}).filter(([id])=>!legacyWorkIds.has(id)));
    target.events=(target.events||[]).filter(item=>!/(?:WP-SASANG|WP-HAUL|HX210AL|HX48AZ|HL930A)/i.test(`${item?.title||''} ${item?.desc||''}`));
    target.versions=(target.versions||[]).filter(item=>!/(?:WP-SASANG|WP-HAUL|사상구|HX210AL|HX48AZ|HL930A)/i.test(`${item?.code||''} ${item?.title||''} ${item?.desc||''}`));
    if(legacyWorkIds.has(target.selectedWpId))target.selectedWpId=target.workPackages[0]?.id||'';
  }
  return true;
}
function sharedStatePayload(){
  const payload=deepClone(state);
  // View/navigation state belongs to one browser tab. Broadcasting either
  // field made every connected user jump to another manager's screen.
  delete payload.selectedPage;
  delete payload.selectedWpId;
  return payload;
}
function localViewState(){
  const tabView=loadTabView();
  return {
    selectedPage:tabView.selectedPage||state?.selectedPage||'dashboard',
    selectedWpId:tabView.selectedWpId||state?.selectedWpId||'',
  };
}
function restoreLocalView(view){
  state.selectedPage=view.selectedPage||'dashboard';
  const workPackages=Array.isArray(state.workPackages)?state.workPackages:[];
  state.selectedWpId=workPackages.some(item=>item.id===view.selectedWpId)
    ?view.selectedWpId
    :(workPackages[0]?.id||'');
}
function saveState(){
  // Navigation and selected cards are tab-local. The local backup contains
  // the same project-data shape as the shared server payload only.
  safeSetItem(STORAGE_KEY,JSON.stringify(sharedStatePayload()));
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
    cache:'no-store',
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
  const payload=sharedStatePayload();
  const payloadJson=JSON.stringify(payload);
  // renderAll also runs for local-only navigation. Do not create a shared DB
  // revision or WebSocket event when no actual project data changed.
  if(payloadJson===lastSharedPayloadJson)return;
  remoteSaveInFlight=true;
  updateSyncIndicator('저장 중','syncing');
  try{
    const response=await apiFetch(`/state/${PROJECT_ID}`,{
      method:'PUT',
      body:JSON.stringify({payload,revision:remoteRevision,source:'web'}),
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
    lastSharedPayloadJson=payloadJson;
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
async function pullRemoteState({render=true}={}){
  const view=localViewState();
  const response=await apiFetch(`/state/${PROJECT_ID}`);
  if(!response.ok)throw new Error(`LOAD_${response.status}`);
  const data=await response.json();
  remoteApplying=true;
  const serverPayload=data.payload||{};
  state=mergeDefaults(deepClone(DEFAULT_STATE),serverPayload);
  const migrated=applyCurrentDemoProfile(state);
  restoreLocalView(view);
  lastSharedPayloadJson=migrated?JSON.stringify(serverPayload):JSON.stringify(sharedStatePayload());
  remoteRevision=data.revision;
  if(render)renderAll();
  remoteApplying=false;
  if(migrated)saveState();
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
    // The shared project state is the source of truth. Load it before creating
    // the large 3D map iframe so a remote/Cloudflare client never settles on
    // an empty browser-local backup while map assets are still downloading.
    await pullRemoteState({render:false});
    remoteReady=true;
    connectRealtime();
    // Show the shared work history immediately. Site-plan, Stage inventory,
    // and instruction requests can be noticeably slower through a tunnel and
    // must not leave a remote client looking like the project is empty.
    renderAll(true);
    // These supplemental records are independent and can finish in parallel.
    await Promise.all([loadSitePlans(),loadStageInventory(),loadIsaacInstructions()]);
    // Site plan and Isaac instruction caches live outside the shared state.
    // Force one redraw after bootstrap so workflow renderers see those records.
    renderAll(true);
    if(!remoteCanEdit)updateSyncIndicator('조회 전용','readonly');
  }catch(error){
    if(error.message!=='AUTH_REQUIRED'){
      console.warn('Shared bootstrap failed',error);
      updateSyncIndicator('로컬 백업 모드','offline');
      toast('공동 DB 연결 실패','브라우저의 로컬 백업 데이터로 실행합니다.','warning');
      renderAll(true);
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
function displayPlanId(planId=''){ return String(planId||'-').replace(/^SASANG-PIPE-/i,'PIPELINE-').replace(/^SASANG-/i,''); }
function statusText(status){ return ({blocked:'자원 대기',accepted:'결과 승인',executing:'작업 중',review:'검토 필요',ready:'배포 가능',draft:'초안',correction:'보완 작업','correction-issued':'보완 지시 발행',paused:'일시중지',dispatched:'배포됨','review-ready':'검토 가능','approval-ready':'승인 가능'}[status]||status); }
function badgeClass(status){ return ({blocked:'warning',accepted:'accepted',executing:'progress',review:'warning',ready:'info',draft:'neutral',correction:'danger','correction-issued':'warning',paused:'warning',dispatched:'info','review-ready':'info','approval-ready':'ready'}[status]||'neutral'); }
function sourceBadge(source){
  const s=String(source||'').toUpperCase();
  const label=({'ISAAC STAGE':'FIELD SYSTEM','SIMULATED':'SENSOR DATA','SIMULATED RESULT':'SENSOR RESULT'}[s]||source);
  const cls=s.includes('PUBLIC')||s.includes('DRAWING')?'public':s.includes('MANUFACTURER')||s.includes('ISAAC')||s.includes('FIELD')||s.includes('SENSOR')?'manufacturer':s.includes('ASSUMED')?'assumed':s.includes('SIMULATED')?'simulated':'user';
  return `<span class="origin ${cls}">${esc(label)}</span>`;
}
function readinessStatusLabel(status){ return ({ready:'확보',simulated:'검증용 데이터','needs-confirmation':'확인 필요',missing:'미제공'}[status]||status); }
function readinessResult(){
  const weights={A:4,B:3,C:2,D:1};
  let total=0,earned=0,aProblem=false,bProblem=false;
  state.readiness.forEach(r=>{
    const w=weights[r.grade]||1; total+=w;
    const f=r.status==='ready'?1:r.status==='simulated'?.82:r.status==='needs-confirmation'?.58:0;
    earned+=w*f;
    if(r.grade==='A' && r.status==='missing') aProblem=true;
    if(r.grade==='A' && r.status==='needs-confirmation') aProblem='conditional';
    if(r.grade==='B' && ['missing','needs-confirmation'].includes(r.status)) bProblem=true;
  });
  const score=Math.round(earned/total*100);
  let stateText='자율화 작업 배포 가능', tone='ready';
  if(aProblem===true){stateText='작업 배포 차단';tone='blocked'}
  else if(aProblem==='conditional'||bProblem){stateText='조건부 작업 가능';tone='warning'}
  return {score,stateText,tone};
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

function currentRenderSignature(){
  return JSON.stringify({
    project:sharedStatePayload(),
    selectedWpId:state?.selectedWpId||'',
  });
}
function refreshRenderedPageCache(){
  const signature=currentRenderSignature();
  if(signature!==lastRenderSignature){
    renderedPages.clear();
    lastRenderSignature=signature;
  }
}
function renderCurrentPage(force=false){
  const page=state.selectedPage||'dashboard';
  if(!force&&renderedPages.has(page)){
    wireIsaacMapFrames();
    return;
  }
  const renderers={
    dashboard:()=>{renderDashboard();renderIsaacPanel()},
    readiness:renderReadiness,
    workpackages:renderWorkPackages,
    execution:()=>{if(typeof renderExecution==='function')renderExecution()},
    equipment:()=>{renderEquipment();applyOfficialEquipmentPhotos()},
    evidence:renderEvidence,
    versions:renderVersions,
    settings:renderSettings,
  };
  (renderers[page]||renderers.dashboard)();
  renderedPages.add(page);
  wireIsaacMapFrames();
}
function renderAll(force=false){
  prepareState();
  refreshRenderedPageCache();
  renderHeader();
  // 숨겨진 페이지까지 모두 다시 만들면 3D map iframe과 Evidence 이미지도
  // 불필요하게 로드된다. 현재 페이지는 이동할 때 즉시 렌더링한다.
  renderCurrentPage(force);
  applyPage();
  persistLocalView();
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

const DYNAMIC_ZONE_COLORS=['#d99620','#2ca66f','#3478cf','#b74983','#7658c7','#d45f3f','#2c9ca6','#70823b'];
const SCENARIO_PHASE_ORDER={excavation:1,pipe_installation:2,backfill:3};
const SCENARIO_ZONE_COLORS={A:DYNAMIC_ZONE_COLORS[0],B:DYNAMIC_ZONE_COLORS[1],C:DYNAMIC_ZONE_COLORS[2]};
function afterMapFeatureCutover(value){
  const timestamp=Date.parse(value||'');
  return Number.isFinite(timestamp)&&timestamp>=Date.parse(MAP_FEATURE_CUTOVER_AT);
}
function dynamicMapInstructions(){
  return (isaacInstructions||[])
    .filter(instruction=>afterMapFeatureCutover(instruction.created_at))
    .sort((a,b)=>(Date.parse(a.created_at)||0)-(Date.parse(b.created_at)||0)||String(a.id).localeCompare(String(b.id)));
}
function activeDynamicZoneInstructions(instructions=dynamicMapInstructions()){
  const ordinary=[];
  const scenarioRuns=new Map();
  instructions.forEach(instruction=>{
    const runId=String(instruction?.params?.scenario_run_id||'');
    if(!runId){ordinary.push(instruction);return;}
    if(!scenarioRuns.has(runId))scenarioRuns.set(runId,[]);
    scenarioRuns.get(runId).push(instruction);
  });
  scenarioRuns.forEach(members=>{
    const phases=new Map();
    members.forEach(instruction=>{
      const params=instruction.params||{};
      const phaseId=String(params.scenario_phase_id||'excavation');
      if(!phases.has(phaseId))phases.set(phaseId,[]);
      phases.get(phaseId).push(instruction);
    });
    const ordered=[...phases.entries()].sort((left,right)=>{
      const leftOrder=Number(left[1][0]?.params?.scenario_phase_order||SCENARIO_PHASE_ORDER[left[0]]||999);
      const rightOrder=Number(right[1][0]?.params?.scenario_phase_order||SCENARIO_PHASE_ORDER[right[0]]||999);
      return leftOrder-rightOrder;
    });
    const active=ordered.find(([,phaseMembers])=>!phaseMembers.every(item=>item.status==='approved'));
    if(active)ordinary.push(...active[1]);
  });
  return ordinary.sort((a,b)=>(Date.parse(a.created_at)||0)-(Date.parse(b.created_at)||0)||String(a.id).localeCompare(String(b.id)));
}
function normalizedDynamicZoneId(value){
  return String(value||'').replace(/^zone\s*/i,'').trim().toUpperCase();
}
function dynamicInstructionZoneId(instruction,index,instructions=dynamicMapInstructions()){
  const requested=normalizedDynamicZoneId(instruction?.params?.zone_id);
  if(requested&&requested!=='-')return requested;
  const unresolved=instructions.filter(item=>{
    const zone=normalizedDynamicZoneId(item?.params?.zone_id);
    return !zone||zone==='-';
  });
  const fallbackIndex=Math.max(0,unresolved.findIndex(item=>item.id===instruction?.id));
  return String.fromCharCode(65+(fallbackIndex%26));
}
function mapWorkTypeLabel(instruction){
  const operation=String(instruction?.params?.operation||instruction?.kind||'').toLowerCase();
  if(operation.includes('excavat')||operation.includes('dig'))return '터파기 작업';
  if(operation.includes('install')||operation.includes('pipe'))return '관로 매설 작업';
  if(operation.includes('backfill')||operation.includes('fill'))return '되메우기 작업';
  if(operation.includes('grade')||operation.includes('level'))return '정지 작업';
  if(operation.includes('move')||operation.includes('haul')||operation.includes('relocat'))return '토사 이동 작업';
  if(operation.includes('soil')||operation.includes('create')||operation.includes('place'))return '토사 배치 작업';
  return instruction?.params?.summary||'현장 작업';
}
function validMapVector(value){
  if(!value||typeof value!=='object')return null;
  const vector={x:Number(value.x),y:Number(value.y),z:Number(value.z)};
  return Object.values(vector).every(Number.isFinite)?vector:null;
}
function stagePrimForPath(path){
  if(!path)return null;
  return [
    ...(stageInventory.diggable_targets||[]),
    ...(stageInventory.scene_objects||[]),
    ...(stageInventory.equipment||[]),
  ].find(item=>item.path===path)||null;
}
function dynamicInstructionGeometry(instruction){
  const params=instruction?.params||{};
  const commit=isaacLatestCommit(instruction);
  const result=commit?.result||{};
  const changes=Array.isArray(result.map_changes)?result.map_changes:[];
  const targetPath=result.target_prim_path||params.target_prim_path||params.resource_bindings?.target||'';
  const targetChange=changes.find(change=>change?.prim_path===targetPath)||changes.find(change=>change?.position&&change?.size)||null;
  const stagePrim=stagePrimForPath(targetPath);
  const work=(state.workPackages||[]).find(item=>item.id===params.work_package_id||item.isaacInstructionId===instruction.id);
  const position=validMapVector(
    result.target_position||result.target_after_position||targetChange?.position||stagePrim?.world_position||work?.position
  );
  const size=validMapVector(
    result.target_bounds_size||result.target_after_bounds_size||targetChange?.size||stagePrim?.bounds_size||work?.size
  );
  if(!position||!size)return null;
  return {
    position,
    size:{x:Math.max(.5,Math.abs(size.x)),y:Math.max(.5,Math.abs(size.y)),z:Math.max(.25,Math.abs(size.z))},
  };
}
function dynamicInstructionWorkAreaBounds(instruction,geometry=null){
  const area=instruction?.params?.work_area_bounds;
  if(!area||typeof area!=='object')return null;
  const minX=Number(area.min_x??area.minX);
  const maxX=Number(area.max_x??area.maxX);
  const minY=Number(area.min_y??area.minY);
  const maxY=Number(area.max_y??area.maxY);
  if(![minX,maxX,minY,maxY].every(Number.isFinite)||maxX<=minX||maxY<=minY)return null;
  const centerZ=Number(geometry?.position?.z)||0;
  const halfZ=Math.max(.25,Number(geometry?.size?.z||0)*.5);
  return {minX,maxX,minY,maxY,minZ:centerZ-halfZ,maxZ:centerZ+halfZ};
}
function dynamicMapZones(){
  // A scenario registers A/B/C together, but the Zone layer represents the
  // current construction phase only. Approved phases remain visible through
  // Work/Timeline geometry, while their operational mask advances A -> B -> C.
  const instructions=activeDynamicZoneInstructions();
  const grouped=new Map();
  instructions.forEach((instruction,index)=>{
    const geometry=dynamicInstructionGeometry(instruction);
    const plannedBounds=dynamicInstructionWorkAreaBounds(instruction,geometry);
    if(!geometry&&!plannedBounds)return;
    const zoneId=dynamicInstructionZoneId(instruction,index,instructions);
    const halfX=geometry?Math.max(4,geometry.size.x*.5+1.5):0;
    const halfY=geometry?Math.max(4,geometry.size.y*.5+1.5):0;
    const bounds=plannedBounds||{
      minX:geometry.position.x-halfX,maxX:geometry.position.x+halfX,
      minY:geometry.position.y-halfY,maxY:geometry.position.y+halfY,
      minZ:geometry.position.z-geometry.size.z*.5,maxZ:geometry.position.z+geometry.size.z*.5,
    };
    const current=grouped.get(zoneId);
    if(!current){
      grouped.set(zoneId,{zoneId,instructions:[instruction],bounds,title:mapWorkTypeLabel(instruction)});
      return;
    }
    current.instructions.push(instruction);
    current.bounds={
      minX:Math.min(current.bounds.minX,bounds.minX),maxX:Math.max(current.bounds.maxX,bounds.maxX),
      minY:Math.min(current.bounds.minY,bounds.minY),maxY:Math.max(current.bounds.maxY,bounds.maxY),
      minZ:Math.min(current.bounds.minZ,bounds.minZ),maxZ:Math.max(current.bounds.maxZ,bounds.maxZ),
    };
  });
  return [...grouped.values()].map((group,index)=>{
    const {bounds}=group;
    const latest=group.instructions.at(-1);
    return {
      id:group.zoneId,
      label:`ZONE ${group.zoneId}`,
      title:group.instructions.length>1?`${group.title} 외 ${group.instructions.length-1}건`:group.title,
      color:SCENARIO_ZONE_COLORS[group.zoneId]||DYNAMIC_ZONE_COLORS[index%DYNAMIC_ZONE_COLORS.length],
      position:{x:(bounds.minX+bounds.maxX)/2,y:(bounds.minY+bounds.maxY)/2,z:bounds.maxZ},
      size:{x:bounds.maxX-bounds.minX,y:bounds.maxY-bounds.minY,z:Math.max(.5,bounds.maxZ-bounds.minZ)},
      status:latest.status,
      instructionIds:group.instructions.map(item=>item.id),
    };
  });
}

function timelineChangeSummary(instruction,commit){
  const result=commit?.result||{};
  const changes=Array.isArray(result.map_changes)?result.map_changes:[];
  const removed=changes.filter(item=>item?.action==='remove').length;
  const updated=changes.length-removed;
  const operation=String(result.operation||instruction?.params?.operation||'').toLowerCase();
  if(operation.includes('excavat')&&updated)return `흙더미 일부 굴착 · 토사 형상 ${updated}건 이동·생성`;
  if(operation.includes('excavat')||removed)return `굴착 대상 ${Math.max(removed,1)}건 제거`;
  if(changes.length)return `승인된 현장 형상 ${changes.length}건 변경`;
  if(instruction?.kind==='place_cube')return '승인된 작업 객체 1건 배치';
  return '승인된 Isaac 작업 결과 반영';
}
function approvedTimelineSteps(zoneId=timelineZoneFilter){
  const commits=[];
  const allInstructions=dynamicMapInstructions();
  const instructions=allInstructions.filter((instruction,index)=>
    zoneId==='ALL'||dynamicInstructionZoneId(instruction,index,allInstructions)===zoneId
  );
  instructions.forEach(instruction=>{
    const instructionZone=dynamicInstructionZoneId(instruction,allInstructions.indexOf(instruction),allInstructions);
    (instruction.commits||[]).forEach(commit=>{
      if(commit.review_status!=='approved'||!commit.reviewed_at)return;
      const params=instruction.params||{};
      const result=commit.result||{};
      const operation=String(result.operation||params.operation||'').toLowerCase();
      const fallbackTitle=params.summary||params.target_name||params.label||instruction.note||instruction.kind;
      const targetPath=result.target_prim_path||params.target_prim_path||null;
      const changePaths=(result.map_changes||[])
        .map(item=>item?.prim_path)
        .filter(Boolean);
      if(result.prim_path)changePaths.push(result.prim_path);
      const beforeObjects=operation.includes('excavat')&&result.target_active_before!==false&&
        targetPath&&result.target_position&&result.target_bounds_size
        ?[{
          path:targetPath,
          name:params.target_name||params.label||'작업 전 흙더미',
          world_position:result.target_position,
          bounds_size:result.target_bounds_size,
          display_color:params.color||'#76502d',
          active:true,
        }]
        :[];
      commits.push({
        key:commit.id,
        commitId:commit.id,
        instructionId:instruction.id,
        zoneId:instructionZone,
        approvedAt:commit.reviewed_at,
        approvedBy:commit.reviewed_by||'-',
        title:operation.includes('excavat')&&Array.isArray(result.map_changes)&&result.map_changes.length>1
          ?'흙더미 일부 굴착 및 토사 이동'
          :fallbackTitle,
        detail:timelineChangeSummary(instruction,commit),
        beforeObjects,
        changePaths:[...new Set(changePaths)],
      });
    });
  });
  const instructionIds=new Set(instructions.map(item=>item.id));
  const visibleRefs=Array.isArray(mapTimelineCommitRefs)
    ?mapTimelineCommitRefs.filter(ref=>instructionIds.has(ref.instructionId))
    :[];
  const visibleCommits=visibleRefs.length
    ?visibleRefs.map(ref=>commits.find(item=>ref.commitId===item.commitId)).filter(Boolean)
    :commits;
  visibleCommits.sort((a,b)=>new Date(a.approvedAt)-new Date(b.approvedAt)||String(a.commitId).localeCompare(String(b.commitId)));
  return [{
    key:'baseline',commitId:null,instructionId:null,approvedAt:null,approvedBy:'SiteGit',
    zoneId:zoneId==='ALL'?null:zoneId,
    title:zoneId==='ALL'?'현재 현장 Baseline':`Zone ${zoneId} 작업 전 Baseline`,
    detail:'새 Zone/Timeline 기능 적용 이후 Commit을 반영하기 전 현장 상태',
  },...visibleCommits];
}
function timelineBaselineObjects(steps=approvedTimelineSteps()){
  const objectsByPath=new Map();
  const changedPaths=new Set();
  steps.slice(1).forEach(step=>{
    (step.beforeObjects||[]).forEach(item=>{
      if(item?.path&&!changedPaths.has(item.path)&&!objectsByPath.has(item.path)){
        objectsByPath.set(item.path,item);
      }
    });
    (step.changePaths||[]).forEach(path=>changedPaths.add(path));
  });
  return [...objectsByPath.values()];
}
function normalizedTimelineIndex(steps=approvedTimelineSteps()){
  if(timelineStepIndex===null||timelineStepIndex<0||timelineStepIndex>=steps.length){
    timelineStepIndex=Math.max(0,steps.length-1);
  }
  return timelineStepIndex;
}
function formatTimelineTime(value){
  if(!value)return '작업 전';
  const date=new Date(value);
  return Number.isNaN(date.getTime())?'-':date.toLocaleString('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
}
function timelineControlMarkup(){
  const steps=approvedTimelineSteps();
  const index=normalizedTimelineIndex(steps);
  const step=steps[index];
  const zones=dynamicMapZones();
  const progress=steps.length<=1?0:(index/(steps.length-1))*100;
  return `<div class="timeline-head">
    <div><span>APPROVED COMMIT TIMELINE</span><strong>${esc(step.title)}</strong><small>${esc(step.detail)}</small></div>
    <div class="timeline-head-actions"><label>범위<select data-timeline-zone><option value="ALL">전체 맵</option>${zones.map(zone=>`<option value="${esc(zone.id)}" ${timelineZoneFilter===zone.id?'selected':''}>Zone ${esc(zone.id)} · ${esc(zone.title)}</option>`).join('')}</select></label><div class="timeline-position"><b>${index}</b><span>/ ${Math.max(0,steps.length-1)} Commit</span></div></div>
  </div>
  <div class="timeline-range-row">
    <span class="timeline-end-label">Baseline</span>
    <div class="timeline-range-wrap" style="--timeline-progress:${progress}%">
      <input type="range" min="0" max="${Math.max(0,steps.length-1)}" step="1" value="${index}" data-timeline-range aria-label="승인 Commit 타임라인">
      <div class="timeline-ticks">${steps.map((item,itemIndex)=>`<i class="${itemIndex<=index?'passed':''} ${itemIndex===index?'current':''}" style="left:${steps.length<=1?0:(itemIndex/(steps.length-1))*100}%" title="${esc(item.title)}"></i>`).join('')}</div>
    </div>
    <span class="timeline-end-label">현재</span>
  </div>
  <div class="timeline-meta"><span>${step.commitId?`Commit ${esc(step.commitId.slice(0,8))}`:'BASELINE'}</span><span>${esc(formatTimelineTime(step.approvedAt))}</span><span>${esc(step.approvedBy)} 승인</span></div>`;
}
function mapInfoMarkup(wp){
  if(activeMapLayer==='timeline'){
    const steps=approvedTimelineSteps();
    const index=normalizedTimelineIndex(steps);
    const step=steps[index];
    return `<div class="map-zone-title">Timeline · ${index}/${Math.max(0,steps.length-1)}</div>
      <div class="map-zone-sub">${esc(step.title)}</div>
      <div class="mini-progress"><span style="width:${steps.length<=1?0:(index/(steps.length-1))*100}%"></span></div>
      <div class="map-stat-row"><span>시점</span><b>${esc(formatTimelineTime(step.approvedAt))}</b></div>
      <div class="map-stat-row"><span>Version</span><b>${step.commitId?esc(step.commitId.slice(0,8)):'Baseline'}</b></div>
      <div class="map-stat-row"><span>상태</span><b>승인 이력 재생</b></div>`;
  }
  return `<div class="map-zone-title">Zone ${esc(wp.zone)} · ${esc(wp.id)}</div>
    <div class="map-zone-sub">${esc(wp.name)}</div>
    <div class="mini-progress"><span style="width:${wp.qualified}%"></span></div>
    <div class="map-stat-row"><span>Raw / Qualified</span><b>${wp.raw}% / ${wp.qualified}%</b></div>
    <div class="map-stat-row"><span>잔여량</span><b>${num(wp.remaining)}㎥</b></div>
    <div class="map-stat-row"><span>상태</span><b>${statusText(wp.status)}</b></div>`;
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
          <div class="hero-kicker">SITEGIT PIPELINE CONSTRUCTION DEMO · PLAN V1.0</div>
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
            <div><strong>${r.stateText}</strong><small>필수 데이터 2건 관리자 확인<br/>현장 데이터 기반 결과검토 활성</small></div>
          </div>
        </div>
      </div>
    </div>

    <div class="kpi-grid">
      ${kpiCard('전체 목표량',num(totalTarget()),'㎥','승인 관로 도면 기준 물량','▦','navy')}
      ${kpiCard('Raw Progress',rawPct,'%','장비가 수행한 전체 변화량','↗','teal')}
      ${kpiCard('Qualified Progress',qualifiedPct,'%','인수 가능한 품질 유효량','✓','teal')}
      ${kpiCard('품질 유효 잔여량',num(totalRemaining()),'㎥','목표 형상까지 남은 물량','◒','amber')}
      ${kpiCard('활성 Work Package',activeCount(),'건','작업 중·검토·보완 포함','▤','navy')}
      ${kpiCard('확인 필요 Conflict',alertCount(),'건','관리자 행동이 필요한 업무 객체','!','red')}
    </div>

    <div class="dashboard-main">
      <article class="card map-card">
        <div class="card-header">
          <div><h2>Site Work Map</h2><p>공식 기준 지형과 관리자 승인으로 Merge된 작업 결과만 보여줍니다.</p></div>
          <div class="map-toolbar"><div class="segmented"><button class="${activeMapLayer==='work'?'active':''}" data-map-layer="work">Work</button><button class="${activeMapLayer==='zone'?'active':''}" data-map-layer="zone">Zone</button><button class="${activeMapLayer==='evidence'?'active':''}" data-map-layer="evidence">Evidence</button><button class="${activeMapLayer==='constraint'?'active':''}" data-map-layer="constraint">Constraint</button><button class="${activeMapLayer==='timeline'?'active':''}" data-map-layer="timeline">Timeline</button></div><button class="ghost-button button-sm" data-action="fit-map">화면 맞춤</button></div>
        </div>
        <div class="site-map-wrap isaac-map">
          <iframe class="isaac-map-frame" src="/static/isaac-map-viewer.html?v=20260825-field-copy-1" title="현장 작업 맵" loading="eager"></iframe>
          <div class="map-info-float">${mapInfoMarkup(wp)}</div>
          <div class="isaac-map-note">${stageInventory.connected?`현장 데이터 연결 · 객체 ${(stageInventory.scene_objects||[]).length}개 · 1초 갱신`:'현장 데이터 연결 대기'} · 좌클릭 회전 · 우클릭 이동 · 휠 확대</div>
          <div class="map-timeline-shell ${activeMapLayer==='timeline'?'active':''}" id="mapTimelineControl">${timelineControlMarkup()}</div>
        </div>
      </article>

      <aside class="card command-card manager-console">
        <div class="card-header manager-console-head">
          <div><h2>Manager Action</h2><p>실제 Isaac 작업 발행부터 결과 승인까지</p></div>
          <span class="manager-stage-chip ${stageInventory.connected?'online':'offline'}"><i class="stage-live-dot ${stageInventory.connected?'online':'offline'}"></i>${stageInventory.connected?'STAGE LIVE':'OFFLINE'}</span>
        </div>

        <section class="manager-launch">
          <div class="manager-section-title"><div><span>AI CODE AGENT</span><strong>새 Work Package</strong></div><small>${activeDiggable?`실행 가능 토사 ${activeDiggable}개`:'자원 대기 가능'}</small></div>
          <p class="map-work-status">${stageInventory.connected?`장비 ${stageInventory.equipment.length}대 · 활성 작업 대상 ${activeDiggable}개`:'현장 시스템이 연결되지 않아도 작업을 접수하고 자원 대기로 저장합니다.'}</p>
          <button class="primary-button map-work-create" data-action="create-wp">＋ 자연어 작업 지시</button>
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
  const mapFrame=page.querySelector('.isaac-map-frame');
  mapFrame?.addEventListener('load',()=>syncIsaacMapLayer(mapFrame));
  requestAnimationFrame(()=>syncIsaacMapLayer(mapFrame));
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
    <text x="25" y="430" class="map-small">REFERENCE GEOMETRY · VERIFY BEFORE CONSTRUCTION</text>
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
  const r=readinessResult();
  const counts={ready:0,confirm:0,missing:0}; state.readiness.forEach(x=>{if(['ready','simulated'].includes(x.status))counts.ready++;else if(x.status==='needs-confirmation')counts.confirm++;else counts.missing++});
  $('#page-readiness').innerHTML=`
    <div class="section-heading"><div><h2>Data Readiness</h2><p>건설사의 기존 데이터를 자율화 작업에 필요한 형태로 정리하고, 누락 항목에 따라 배포·검토 동작을 다르게 합니다.</p></div><div class="section-actions"><button class="ghost-button" data-action="edit-project">현장 기본정보 수정</button><button class="primary-button" data-action="add-readiness">+ 데이터 항목 추가</button></div></div>
    <div class="readiness-grid">
      <aside class="card readiness-score-card">
        <div class="eyebrow">AUTONOMY DEPLOYMENT</div>
        <div class="score-ring" style="--score:${r.score}%"><div class="score-inner"><b>${r.score}</b><span>READINESS SCORE</span></div></div>
        <div class="readiness-message"><h3>${r.stateText}</h3><p>${r.tone==='blocked'?'필수 A등급 데이터가 누락되어 Work Package 배포를 차단합니다.':'필수 항목은 준비됐으나 일부 값은 관리자 확인 또는 가상 데이터로 대체되어 있습니다.'}</p></div>
        <div class="readiness-counts"><div><b class="text-teal">${counts.ready}</b><span>확보·대체</span></div><div><b class="text-amber">${counts.confirm}</b><span>확인 필요</span></div><div><b class="text-red">${counts.missing}</b><span>미제공</span></div></div>
        <div class="rule-guide"><h4>데이터 등급별 시스템 동작</h4>${ruleLine('#0b8e84','A · 작업 필수','누락 시 장비 배포 차단')}${ruleLine('#17678f','B · 자동 검토 필수','누락 시 자동 완료검토 제한')}${ruleLine('#f1b43b','C · 운영 효율','경고 후 작업 진행 가능')}${ruleLine('#7766b4','D · 현장 대체 가능','관리자 확인·사진·측량으로 대체')}</div>
      </aside>
      <div class="readiness-list">${state.readiness.map(readinessItem).join('')}</div>
    </div>`;
}
function ruleLine(color,title,desc){return `<div class="rule-line"><span class="rule-dot" style="background:${color}"></span><div><strong>${title}</strong><span>${desc}</span></div></div>`}
function readinessItem(r){return `<article class="card readiness-item"><div class="readiness-grade grade-${r.grade.toLowerCase()}">${r.grade}</div><div><div class="readiness-title">${esc(r.name)} <span class="status-chip ${r.status}">${readinessStatusLabel(r.status)}</span></div><div class="readiness-desc">${esc(r.desc)}</div></div><div><div class="readiness-value">${esc(r.value)}</div><div style="margin-top:6px">${sourceBadge(r.source)}</div></div><div class="readiness-action"><b>${esc(r.action)}</b><br/>${esc(r.category)}</div><div><button class="ghost-button button-sm" data-edit-readiness="${r.id}">수정</button></div></article>`}

function realWorkPackageId(instruction){
  return instruction.params?.work_package_id||`WP-${String(instruction.id||'').slice(0,8).toUpperCase()}`;
}
function realWorkPackageStatus(status){
  return ({
    blocked:{label:'자원 대기',badge:'warning',tone:'#fff3dc'},
    pending:{label:'실행 대기',badge:'info',tone:'#e9f4f7'},
    dispatched:{label:'현장 작업 중',badge:'progress',tone:'#e7f4f8'},
    committed:{label:'증거 검토',badge:'warning',tone:'#fff3dc'},
    approved:{label:'승인·Merge',badge:'accepted',tone:'#e6f5ef'},
    rejected:{label:'반려·Conflict',badge:'danger',tone:'#fdebea'},
  })[status]||{label:status||'상태 미확인',badge:'neutral',tone:'#edf2f4'};
}
function realWorkPackageKind(instruction){
  const operation=instruction.params?.operation;
  if(operation==='excavate')return '굴착';
  if(operation==='create_primitive')return 'Prim 생성';
  return ({generated_script:'AI 생성 작업',excavate_prim:'Prim 굴착',place_cube:'객체 배치'})[instruction.kind]||instruction.kind||'현장 작업';
}
function primShortName(path){
  const parts=String(path||'').split('/').filter(Boolean);
  return parts.at(-1)||'-';
}
function realWorkPackageCard(instruction){
  const params=instruction.params||{};
  const bindings=params.resource_bindings||{};
  const commit=isaacLatestCommit(instruction);
  const evidence=commit?.evidence||{};
  const quality=evidence.quality||{};
  const completeness=Number(quality.completeness_ratio);
  const status=realWorkPackageStatus(instruction.status);
  const equipmentPath=params.equipment_prim_path||bindings.equipment||'';
  const targetPath=params.target_prim_path||bindings.target||commit?.result?.target_prim_path||'';
  const equipment=params.equipment_name||primShortName(equipmentPath);
  const target=params.target_name||primShortName(targetPath);
  const summary=params.summary||params.label||instruction.note||realWorkPackageKind(instruction);
  const sourceText=params.source_text||instruction.note||'자연어 원문 미기록';
  const commitLabel=commit?`${commit.status==='succeeded'?'완료':'실패'} · ${commit.attempt||1}차`:'아직 없음';
  const evidenceLabel=commit
    ?Number.isFinite(completeness)?`${Math.round(completeness*100)}%`:'기존 형식'
    :'-';
  const createdAt=instruction.created_at?new Date(instruction.created_at).toLocaleString('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}):'-';
  return `<article class="card wp-card real-work-package-card" style="--card-tint:${status.tone}">
    <div class="wp-card-head">
      <div><div class="wp-code">${esc(realWorkPackageId(instruction))} · BACKEND</div><h3>${esc(summary)}</h3><p>${esc(realWorkPackageKind(instruction))} · ${esc(sourceText)}</p></div>
      <span class="badge ${status.badge}">${esc(status.label)}</span>
    </div>
    <div class="wp-card-body real-wp-metrics">
      <div class="wp-metric"><span>배정 장비</span><b>${esc(equipment)}</b></div>
      <div class="wp-metric"><span>작업 대상</span><b>${esc(target)}</b></div>
      <div class="wp-metric"><span>실행 Commit</span><b>${esc(commitLabel)}</b></div>
      <div class="wp-metric"><span>Evidence</span><b>${esc(evidenceLabel)}</b></div>
    </div>
    <div class="real-wp-bindings">
      <div><span>장비 Prim</span><code>${esc(equipmentPath||'미배정')}</code></div>
      <div><span>대상 Prim</span><code>${esc(targetPath||'미배정')}</code></div>
    </div>
    <div class="wp-card-actions">
      <div class="real-wp-origin"><span>생성 ${esc(createdAt)}</span><small>${esc(instruction.created_by_username||'시스템')}</small></div>
      <div class="button-row"><button class="ghost-button button-sm" data-real-wp-detail="${esc(instruction.id)}">작업 상세</button>${commit?`<button class="secondary-button button-sm" data-isaac-detail="${esc(instruction.id)}">Evidence 검토</button>`:''}</div>
    </div>
  </article>`;
}
function renderWorkPackages(){
  const actual=isaacInstructions;
  const executing=actual.filter(item=>['pending','dispatched'].includes(item.status)).length;
  const review=actual.filter(item=>item.status==='committed').length;
  const approved=actual.filter(item=>item.status==='approved').length;
  $('#page-workpackages').innerHTML=`
    <div class="section-heading"><div><h2>실제 Work Package</h2><p>Backend에 저장된 작업지시만 표시합니다. 자연어 지시부터 현장 작업 실행, Evidence 검토와 Merge까지 동일한 작업 ID로 추적합니다.</p></div><div class="section-actions"><span class="backend-source-chip"><i></i>BACKEND LIVE</span><button class="primary-button" data-action="create-wp">+ AI Work Package 생성</button></div></div>
    <div class="filter-strip real-wp-summary"><span class="filter-chip active">전체 ${actual.length}</span><span class="filter-chip">대기·실행 ${executing}</span><span class="filter-chip">증거 검토 ${review}</span><span class="filter-chip">승인·Merge ${approved}</span></div>
    ${actual.length?`<div class="wp-grid">${actual.map(realWorkPackageCard).join('')}</div>`:`<div class="card real-wp-empty"><span>▤</span><h3>Backend에 저장된 실제 Work Package가 없습니다.</h3><p>AI Work Package를 생성하면 현장 작업 실행 대기열과 이 화면에 동시에 등록됩니다.</p><button class="primary-button" data-action="create-wp">첫 Work Package 생성</button></div>`}`;
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
        <article class="card"><div class="card-header"><div><h2>Plan — Before — After Diff</h2><p>${wp.id} · ${esc(assignmentSummary(wp,true))} · 목표 ${num(wp.target)}㎥</p></div><div class="origin-legend">${sourceBadge('SENSOR RESULT')} ${sourceBadge('ASSUMED RULE')}</div></div><div class="diff-view"><div class="diff-grid"></div><div class="diff-trench"></div><div class="diff-complete"></div><div class="diff-missing"></div><div class="diff-overcut"></div><div class="diff-label one">품질 유효 완료 ${wp.qualified}%</div><div class="diff-label two">관측 ${ev.observation}%</div><div class="diff-label three">편차 ${num(ev.resultDeviationMm||0)}mm · 잔여 ${num(wp.remaining)}㎥</div></div></article>
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
    ['작업 시작·종료 이벤트',wp.status==='ready'?'아직 실행되지 않음':'장비 이벤트 로그 수신','ok','SENSOR DATA'],
    ['Equipment / Tool Pose','작업구역·작업기 궤적 연결','ok','ASSUMED API'],
    ['Before / After Surface','작업 전후 형상 비교 데이터 생성','ok','SENSOR DATA'],
    ['Observation Coverage',ev.observation>=90?`관측률 ${ev.observation}%`:`관측률 ${ev.observation}% · 남측 미확인` ,ev.observation>=90?'ok':'warn','SENSOR DATA'],
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
    <div class="section-heading"><div><h2>Project Configuration</h2><p>승인 도면, 현장 장비, 센서 데이터와 운영 기준을 통합 관리합니다.</p></div></div>
    <div class="settings-grid">
      <article class="card settings-card"><h3>현장·건설사 기본정보</h3><p>${esc(state.project.name)}<br/>${esc(state.company.contractor)} · 담당 ${esc(state.manager.name)}</p><div class="settings-actions"><button class="primary-button" data-action="edit-project">기본정보 수정</button><button class="ghost-button" data-action="open-onboarding">초기 설정 Wizard</button></div></article>
      <article class="card settings-card"><h3>로컬 데이터 관리</h3><p>현재 프로토타입은 서버 없이 브라우저 localStorage에 저장됩니다. JSON으로 내보내거나 다시 불러올 수 있습니다.</p><div class="settings-actions"><button class="secondary-button" data-action="export-json">JSON 내보내기</button><button class="ghost-button" data-action="import-json">JSON 불러오기</button></div></article>
      <article class="card settings-card"><h3>데이터 출처</h3><p>화면에 표시되는 값의 성격을 네 가지 태그로 구분합니다.</p><div class="source-list"><div class="source-row"><div><strong>승인 관로 시나리오 도면</strong><small>관로 79.2m · 공정별 물량 · 작업전선 Geometry</small></div>${sourceBadge('APPROVED DRAWING')}</div><div class="source-row"><div><strong>현장 장비 자원</strong><small>EXC-001 · EXC-002 · EXC-003 · EXC-004</small></div>${sourceBadge('FIELD SYSTEM')}</div><div class="source-row"><div><strong>자율화 장비 인터페이스</strong><small>Work Package 수신·상태 반환·원격 중지</small></div>${sourceBadge('ASSUMED')}</div><div class="source-row"><div><strong>공간·진척·Evidence</strong><small>Camera · LiDAR · IMU · Pose · 작업 이벤트</small></div>${sourceBadge('SENSOR DATA')}</div></div></article>
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
  if(select){ state.selectedWpId=select.dataset.selectWp; navigate(select.closest('.wp-card')?'evidence':'dashboard'); return; }
  const zone=e.target.closest('[data-wp-id]');
  if(zone){ state.selectedWpId=zone.dataset.wpId; renderAll(); return; }
  const editR=e.target.closest('[data-edit-readiness]'); if(editR){openReadinessModal(editR.dataset.editReadiness);return}
  if(e.target.closest('.equipment-card .source-link'))return;
  const editE=e.target.closest('[data-edit-equipment]'); if(editE){openEquipmentModal(editE.dataset.editEquipment);return}
  const editW=e.target.closest('[data-edit-wp]'); if(editW){openWpModal(editW.dataset.editWp);return}
  const approveIsaac=e.target.closest('[data-isaac-approve]'); if(approveIsaac){reviewIsaacCommit(approveIsaac.dataset.isaacApprove,'approved');return}
  const rejectIsaac=e.target.closest('[data-isaac-reject]'); if(rejectIsaac){reviewIsaacCommit(rejectIsaac.dataset.isaacReject,'rejected');return}
  const remediateIsaac=e.target.closest('[data-isaac-remediation]'); if(remediateIsaac){createIsaacRemediation(remediateIsaac.dataset.isaacRemediation);return}
  const dispatchRemediation=e.target.closest('[data-remediation-dispatch]'); if(dispatchRemediation){dispatchIsaacRemediation(dispatchRemediation.dataset.remediationDispatch);return}
  const openRemediation=e.target.closest('[data-open-remediation]'); if(openRemediation){loadRemediationPlan(openRemediation.dataset.openRemediation);return}
  const detailIsaac=e.target.closest('[data-isaac-detail]'); if(detailIsaac){openIsaacEvidence(detailIsaac.dataset.isaacDetail,detailIsaac.dataset.isaacCommit);return}
  const detailRealWp=e.target.closest('[data-real-wp-detail]'); if(detailRealWp){openRealWorkPackageDetail(detailRealWp.dataset.realWpDetail);return}
  const mapLayer=e.target.closest('[data-map-layer]'); if(mapLayer){setIsaacMapLayer(mapLayer.dataset.mapLayer);return}
  const action=e.target.closest('[data-action]'); if(action){handleAction(action.dataset.action);return}
});
document.addEventListener('input',e=>{
  const range=e.target.closest?.('[data-timeline-range]');
  if(!range)return;
  setTimelineStep(Number(range.value));
});
document.addEventListener('change',e=>{
  const zone=e.target.closest?.('[data-timeline-zone]');
  if(zone)setTimelineZone(zone.value);
});
window.addEventListener('message',event=>{
  if(event.origin!==window.location.origin||event.data?.type!=='sitegit.isaac-map.timeline-data')return;
  mapTimelineCommitRefs=Array.isArray(event.data.commits)?event.data.commits:[];
  if(activeMapLayer==='timeline')refreshTimelineControl();
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

function navigate(page,force=false){
  state.selectedPage=page;
  $('.sidebar').classList.remove('open');
  prepareState();
  refreshRenderedPageCache();
  renderHeader();
  renderCurrentPage(force);
  applyPage();
  persistLocalView();
  window.scrollTo({top:0,behavior:'smooth'});
}
function isaacMapFrames(){
  return [...document.querySelectorAll('.isaac-map-frame,.workflow-map')];
}
function mapFrameTargets(frame){return frame?[frame]:isaacMapFrames();}
function wireIsaacMapFrames(){
  isaacMapFrames().forEach(frame=>{
    if(frame.dataset.sitegitMapBound==='1')return;
    frame.dataset.sitegitMapBound='1';
    frame.addEventListener('load',()=>syncIsaacMapLayer(frame));
  });
  requestAnimationFrame(()=>syncIsaacMapLayer());
}
function syncIsaacMapZones(frame=null){
  const zones=dynamicMapZones();
  mapFrameTargets(frame).forEach(target=>target?.contentWindow?.postMessage({
    type:'sitegit.isaac-map.zones',zones,featureStartAt:MAP_FEATURE_CUTOVER_AT,
  },window.location.origin));
}
function syncIsaacMapLayer(frame=null){
  const targets=mapFrameTargets(frame);
  syncIsaacMapZones(frame);
  targets.forEach(target=>target?.contentWindow?.postMessage({type:'sitegit.isaac-map.layer',layer:activeMapLayer},window.location.origin));
  syncIsaacPlanningOverlay(frame);
  syncIsaacDesignOverlay(frame);
  if(activeMapLayer==='timeline')syncIsaacTimeline(frame);
}
function setIsaacPlanningOverlay(design=null){
  isaacPlanningOverlay=design||null;
  syncIsaacPlanningOverlay();
}
function syncIsaacPlanningOverlay(frame=null){
  mapFrameTargets(frame).filter(target=>target?.dataset?.planningMap==='1').forEach(target=>{
    target.contentWindow?.postMessage(
      isaacPlanningOverlay
        ?{type:'sitegit.isaac-map.plan',plan:isaacPlanningOverlay}
        :{type:'sitegit.isaac-map.plan-clear'},
      window.location.origin,
    );
  });
}
function syncIsaacDesignOverlay(frame=null){
  mapFrameTargets(frame).filter(target=>target?.dataset?.planningMap!=='1').forEach(target=>{
    target.contentWindow?.postMessage(
      activeMapLayer==='drawing'&&approvedSitePlan?.design
        ?{type:'sitegit.isaac-map.design',plan:approvedSitePlan.design,status:approvedSitePlan.status}
        :{type:'sitegit.isaac-map.design-clear'},
      window.location.origin,
    );
  });
}
function syncIsaacTimeline(frame=null){
  const steps=approvedTimelineSteps();
  const index=normalizedTimelineIndex(steps);
  const step=steps[index];
  const allInstructions=dynamicMapInstructions();
  const visibleInstructions=allInstructions.filter((instruction,instructionIndex)=>
    timelineZoneFilter==='ALL'||dynamicInstructionZoneId(instruction,instructionIndex,allInstructions)===timelineZoneFilter
  );
  mapFrameTargets(frame).forEach(target=>target?.contentWindow?.postMessage({
      type:'sitegit.isaac-map.timeline',
      baseline:index===0,
      approvedAt:step.approvedAt,
      commitId:step.commitId,
      zoneId:timelineZoneFilter,
      featureStartAt:MAP_FEATURE_CUTOVER_AT,
      instructionIds:visibleInstructions.map(item=>item.id),
      baselineObjects:timelineBaselineObjects(steps),
    },window.location.origin));
}
function refreshTimelineControl({sync=true}={}){
  document.querySelectorAll('#mapTimelineControl,.map-timeline-control').forEach(shell=>{
    shell.classList.toggle('active',activeMapLayer==='timeline');
    shell.innerHTML=timelineControlMarkup();
  });
  document.querySelectorAll('.site-map-wrap,.workflow-map-shell').forEach(shell=>{
    if(shell.classList.contains('planning'))return;
    shell.classList.toggle('timeline-active',activeMapLayer==='timeline');
  });
  document.querySelectorAll('.workflow-map-caption').forEach(caption=>{
    if(caption.closest('.workflow-map-shell')?.classList.contains('planning'))return;
    const title=caption.querySelector('b');
    const detail=caption.querySelector('span');
    if(title)title.textContent=activeMapLayer==='zone'?'작업 Zone':activeMapLayer==='timeline'?'Commit Timeline':activeMapLayer==='drawing'?'승인 도면 · 지하 관로':'현재 현장 맵';
    if(detail)detail.textContent=activeMapLayer==='zone'
      ?(dynamicMapZones().length?'작업 지시의 실제 대상 위치를 표시합니다.':'새 작업 지시가 발행되면 Zone이 생성됩니다.')
      :activeMapLayer==='timeline'
        ?(approvedTimelineSteps().length>1?'슬라이더로 승인 Commit을 재생합니다.':'새 Commit을 승인하면 Timeline에 추가됩니다.')
        :activeMapLayer==='drawing'
          ?(approvedSitePlan?`${displayPlanId(approvedSitePlan.design.plan_id)} Rev.${approvedSitePlan.design.revision} · 설계 깊이 ${approvedSitePlan.design.design_depth_m}m`:'승인된 현장 도면이 없습니다.')
        :'관리자 승인으로 Merge된 작업 결과를 표시합니다.';
  });
  const info=document.querySelector('.map-info-float');
  if(info)info.innerHTML=mapInfoMarkup(selectedWp());
  if(sync&&activeMapLayer==='timeline')syncIsaacTimeline();
}
function setTimelineStep(index){
  const steps=approvedTimelineSteps();
  timelineStepIndex=Math.max(0,Math.min(Number.isFinite(index)?Math.round(index):0,steps.length-1));
  refreshTimelineControl();
}
function setTimelineZone(zoneId){
  timelineZoneFilter=zoneId||'ALL';
  timelineStepIndex=Math.max(0,approvedTimelineSteps().length-1);
  refreshTimelineControl();
}
function setIsaacMapLayer(layer){
  const enteringTimeline=layer==='timeline'&&activeMapLayer!=='timeline';
  activeMapLayer=layer;
  if(enteringTimeline)timelineStepIndex=Math.max(0,approvedTimelineSteps().length-1);
  $$('[data-map-layer]').forEach(button=>button.classList.toggle('active',button.dataset.mapLayer===layer));
  refreshTimelineControl({sync:false});
  syncIsaacMapLayer();
  if(layer==='zone')toast('작업구역 표시',dynamicMapZones().length?'새 작업 지시의 실제 대상 범위를 Zone으로 표시합니다.':'아직 새 작업 지시가 없어 표시할 Zone이 없습니다.','success');
  if(layer==='timeline')toast('승인 이력 Timeline','전체 맵 또는 Zone을 선택하고 Baseline부터 새 승인 Commit까지 확인하세요.','success');
  if(layer==='drawing')toast('승인 도면 X-ray',approvedSitePlan?'설계 관로를 지표 아래 반투명 형상으로 표시합니다.':'도면 관리에서 승인 도면을 등록해 주세요.',approvedSitePlan?'success':'warning');
}
function handleAction(action){
  const handlers={
    'run-demo':runSimulation,'add-evidence':addEvidence,'create-correction':createCorrection,'approve-result':approveResult,'pause-work':pauseWork,
    'edit-project':openProjectModal,'add-readiness':()=>openReadinessModal(null),'create-wp':openAiWorkPackageModal,'add-equipment':()=>openEquipmentModal(null),'edit-assignments':()=>openWpModal(selectedWp().id),
    'check-all-compatibility':()=>toast('장비 적합성 검사 완료',`${state.equipment.length}개 장비의 작업 유형·범위·Evidence 반환 가능성을 다시 계산했습니다.`,'success'),
    'show-sources':showSourcesModal,'export-json':exportJson,'import-json':()=>$('#jsonImportInput').click(),'snapshot-version':snapshotVersion,
    'open-onboarding':openOnboarding,'reset-all':confirmReset,'full-reset':confirmFullReset,'show-architecture':showArchitectureModal,'manage-drawings':openDrawingManager,'fit-map':()=>{isaacMapFrames().forEach(frame=>frame?.contentWindow?.postMessage({type:'sitegit.isaac-map.fit'},window.location.origin));toast('현장 뷰 재정렬','관로 공사 현장을 화면에 맞췄습니다.','success')},
  };
  handlers[action]?.();
}

/* Simulation */
function runSimulation(){
  if(state.simulation.running){toast('작업 흐름 실행 중','현재 작업 흐름이 진행되고 있습니다.','warning');return}
  let wp=selectedWp();
  if(wp.status==='accepted'){wp=state.workPackages.find(w=>w.status==='ready')||state.workPackages.find(w=>w.status!=='accepted');state.selectedWpId=wp.id}
  if(!assignmentsForWp(wp).length){toast('장비 미배정','Zone 장비팀을 먼저 배정하세요.','danger');return}
  const primary=primaryAssignment(wp);if(!primary||!assignmentCompatibility(wp,primary).ok){toast('주 작업 장비 부적합','주 작업 역할에 해당 작업을 지원하는 장비를 배정하세요.','danger');return}
  const read=readinessResult();if(read.tone==='blocked'){toast('배포 차단','A등급 필수 데이터를 먼저 보완해야 합니다.','danger');return}
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
  toast('보완 작업지시 발행',`${id}가 생성됐습니다. 장비 배정을 확인한 뒤 작업을 실행하세요.`,'success');renderAll();
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
const ISAAC_STATUS_TEXT={blocked:'자원 대기',pending:'작업 대기',dispatched:'현장 작업 중',committed:'승인 대기',approved:'Merge 완료',rejected:'Conflict'};
const ISAAC_STATUS_BADGE={blocked:'warning',pending:'neutral',dispatched:'info',committed:'warning',approved:'accepted',rejected:'danger'};
function isaacLatestCommit(instruction){return (instruction?.commits||[]).at(-1)||null}
function isaacPositionText(instruction){
  const commit=isaacLatestCommit(instruction);
  if(instruction.kind==='excavate_prim')return commit?.result?.target_prim_path||instruction.params?.target_prim_path||'-';
  const p=commit?.result?.placed_position||instruction.params?.position||{};
  return `${Number(p.x||0).toFixed(1)} , ${Number(p.y||0).toFixed(1)} , ${Number(p.z||0).toFixed(1)}`;
}
function reloadIsaacMapObjects(){
  isaacMapFrames().forEach(frame=>frame?.contentWindow?.postMessage({type:'sitegit.isaac-map.reload-objects'},window.location.origin));
}
async function loadSitePlans(){
  try{
    const response=await apiFetch(`/site-plans?project_id=${encodeURIComponent(PROJECT_ID)}`);
    if(!response.ok)throw new Error(`SITE_PLANS_${response.status}`);
    sitePlans=await response.json();
    approvedSitePlan=sitePlans.find(item=>item.status==='approved')||sitePlans[0]||null;
    syncIsaacDesignOverlay();
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')console.warn('Site plan load failed',error);
    sitePlans=[];approvedSitePlan=null;
  }
}
async function loadStageInventory(){
  try{
    const response=await apiFetch(`/isaac/stage-inventory?project_id=${encodeURIComponent(PROJECT_ID)}`);
    if(!response.ok)throw new Error(`STAGE_INVENTORY_${response.status}`);
    stageInventory=await response.json();
    updateStageInventoryUi();
    renderIsaacPanel();
    syncIsaacMapZones();
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')console.warn('Stage inventory load failed',error);
    stageInventory={connected:false,equipment:[],diggable_targets:[],scene_objects:[],age_seconds:0};
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
    :'현장 데이터 연결 대기';
  const button=document.querySelector('.map-work-create');
  if(button)button.disabled=false;
}
async function loadIsaacInstructions(){
  try{
    const response=await apiFetch(`/isaac/instructions?project_id=${encodeURIComponent(PROJECT_ID)}&limit=500`);
    if(!response.ok)throw new Error(`ISAAC_${response.status}`);
    isaacInstructions=await response.json();
    if(syncAiWorkPackageStatuses())renderAll();
    else{
      renderIsaacPanel();
      refreshTimelineControl();
    }
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')console.warn('Isaac instruction load failed',error);
  }
}
function syncAiWorkPackageStatuses(){
  const statusMap={blocked:'blocked',pending:'dispatched',dispatched:'executing',committed:'review',approved:'accepted',rejected:'paused'};
  let changed=false;
  const liveInstructionIds=new Set(isaacInstructions.map(item=>item.id));
  for(let index=state.workPackages.length-1;index>=0;index-=1){
    const cached=state.workPackages[index];
    if(cached.isaacInstructionId&&!liveInstructionIds.has(cached.isaacInstructionId)){
      state.workPackages.splice(index,1);
      delete state.evidence[cached.id];
      changed=true;
    }
  }
  isaacInstructions.forEach(instruction=>{
    const workPackageId=instruction.params?.work_package_id;
    if(!workPackageId)return;
    let wp=state.workPackages.find(item=>item.id===workPackageId);
    if(!wp){
      if(instruction.kind==='generated_script'){
        const bindings=instruction.params?.resource_bindings||{};
        const missing=instruction.params?.missing_resources||[];
        const plannedTarget=Math.max(0,Number(instruction.params?.planned_quantity?.value||1));
        wp={
          id:workPackageId,zone:instruction.params?.zone_id||'-',name:instruction.params?.summary||'AI Code Work Package',
          task:'GENERATED_SCRIPT',length:0,target:plannedTarget,raw:0,qualified:0,remaining:plannedTarget,status:instruction.status,version:1,
          eta:instruction.status==='blocked'?'자원 대기':'작업 대기',risk:instruction.status==='blocked'?'high':'medium',start:'-',end:'-',x:0,y:0,width:0,color:'#d95757',
          completionThreshold:100,observationThreshold:100,toleranceMm:0,assignments:[],
          isaacInstructionId:instruction.id,sourceText:instruction.params?.source_text||instruction.note||'',
          equipmentPrimPath:bindings.equipment||'',targetPrimPath:bindings.target||'',generatedCode:instruction.params?.generated_code||'',
        };
        state.workPackages.push(wp);
        state.evidence[workPackageId]={rule:100,completeness:instruction.status==='blocked'?10:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:[...missing,'작업 실행 Commit','관리자 승인'],conflicts:[],externalEvidence:[]};
        changed=true;
      }else if(instruction.kind==='excavate_prim'){
        wp={
          id:workPackageId,zone:instruction.params?.zone_id||'-',name:`Prim 굴착 — ${instruction.params?.target_name||workPackageId}`,
          task:'EXCAVATE_PRIM',length:0,target:1,raw:0,qualified:0,remaining:1,status:'dispatched',version:1,
          eta:'작업 대기',risk:'medium',start:'-',end:'-',x:0,y:0,width:0,color:'#d95757',
          completionThreshold:100,observationThreshold:100,toleranceMm:0,assignments:[],
          isaacInstructionId:instruction.id,sourceText:instruction.params?.source_text||instruction.note||'',
          equipmentPrimPath:instruction.params?.equipment_prim_path,targetPrimPath:instruction.params?.target_prim_path,
        };
        state.workPackages.push(wp);
        state.evidence[workPackageId]={rule:100,completeness:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:['작업 실행 Commit','관리자 승인'],conflicts:[],externalEvidence:[]};
        changed=true;
      }else{
      const position=instruction.params?.position||{x:0,y:0,z:0};
      const size=instruction.params?.size||{x:1,y:1,z:1};
      const targetVolume=Number(size.x||0)*Number(size.y||0)*Number(size.z||0);
      wp={
        id:workPackageId,zone:instruction.params?.zone_id||'-',name:`AI 큐브 배치 — ${instruction.params?.label||workPackageId}`,
        task:'PLACE_CUBE',length:0,target:targetVolume,raw:0,qualified:0,remaining:targetVolume,status:'dispatched',version:1,
        eta:'작업 대기',risk:'low',start:'-',end:'-',x:Number(position.x||0),y:Number(position.y||0),width:Number(size.x||0),
        color:instruction.params?.color||'#FFD700',completionThreshold:100,observationThreshold:100,toleranceMm:0,assignments:[],
        isaacInstructionId:instruction.id,sourceText:instruction.note||'',position,size,
      };
      state.workPackages.push(wp);
      state.evidence[workPackageId]={rule:100,completeness:25,confidence:0,observation:0,workFinished:false,resultDeviationMm:0,overcutVolume:0,state:'not-started',missing:['작업 실행 Commit','관리자 승인'],conflicts:[],externalEvidence:[]};
      changed=true;
      }
    }
    const next=statusMap[instruction.status]||wp.status;
    if(wp.status!==next){wp.status=next;changed=true}
    const progress=instruction.params?.execution_progress;
    if(instruction.status==='dispatched'&&progress){
      const livePercent=Math.max(0,Math.min(100,Math.round(Number(progress.progress_ratio||0)*100)));
      if(wp.raw!==livePercent){wp.raw=livePercent;changed=true}
      const target=Number(wp.target||1);
      const remaining=Math.max(0,target*(1-livePercent/100));
      if(wp.remaining!==remaining){wp.remaining=remaining;changed=true}
      const nextEta=`${Number(progress.step_index||0)}/${Number(progress.step_count||0)}회 굴착 중`;
      if(wp.eta!==nextEta){wp.eta=nextEta;changed=true}
    }
    const commit=isaacLatestCommit(instruction);
    if(commit?.status==='succeeded'&&wp.raw!==100){wp.raw=100;changed=true}
    if(instruction.status==='approved'&&wp.qualified!==100){wp.qualified=100;wp.remaining=0;wp.eta='완료';changed=true}
    else if(instruction.status==='committed'&&wp.eta!=='승인 대기'){wp.eta='승인 대기';changed=true}
    else if(instruction.status==='dispatched'&&!progress&&wp.eta!=='현장 작업 중'){wp.eta='현장 작업 중';changed=true}
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
  const generated=instruction.kind==='generated_script';
  const label=instruction.params?.summary||instruction.params?.label||instruction.kind;
  const color=instruction.kind==='excavate_prim'||generated?'#d95757':(instruction.params?.color||'#f0b429');
  const workPackageId=instruction.params?.work_package_id;
  const failed=commit&&commit.status==='failed';
  const pendingReview=instruction.status==='committed'&&commit&&commit.review_status==='pending';
  const needsRemediation=pendingReview&&commit.result?.quality_assessment?.status==='needs_remediation';
  const detail=failed
    ?`실행 실패 · ${esc(commit.result?.error||'원인 미기록')}`
    :generated
      ?instruction.status==='blocked'
        ?`실행 불가 · ${esc((instruction.params?.missing_resources||[])[0]||'현장 자원 확인 필요')}`
        :`${esc(instruction.params?.summary||instruction.params?.target_name||'현장 작업')} · ${esc(instruction.params?.operation||'generated_program')}`
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
    <span class="badge ${needsRemediation?'danger':(ISAAC_STATUS_BADGE[instruction.status]||'neutral')}">${needsRemediation?'검토 필요':(ISAAC_STATUS_TEXT[instruction.status]||instruction.status)}</span>
    ${commit?`<button class="isaac-evidence-button" data-isaac-detail="${esc(instruction.id)}">증거</button>`:''}
    ${pendingReview?`<div class="isaac-row-actions">
      ${needsRemediation?`<button class="secondary-button button-sm" data-isaac-detail="${esc(instruction.id)}">부족량 확인</button>`:`<button class="secondary-button button-sm" data-isaac-approve="${esc(commit.id)}">✓ 승인</button>
      <button class="ghost-button button-sm" data-isaac-reject="${esc(commit.id)}">반려</button>`}
    </div>`:''}
  </div>`;
}
function openAiWorkPackageModal(){
  aiWorkPackageDraft=null;
  const activeTargets=(stageInventory.diggable_targets||[]).filter(item=>item.active!==false).length;
  openModal({
    eyebrow:'AI WORK PACKAGE AGENT',
    title:'자연어 Work Package 생성',
    body:`<div class="wp-chat-shell">
      <div class="stage-binding-grid">
        <div class="stage-binding-status"><span>현장 연결</span><b>${stageInventory.connected?'연결됨':'연결 대기'}</b></div>
        <div class="stage-binding-status"><span>현재 자원</span><b>장비 ${(stageInventory.equipment||[]).length}대 · 작업 대상 ${activeTargets}개</b></div>
      </div>
      <div class="wp-chat-messages" id="aiWpMessages">
        <div class="wp-chat-message assistant"><span>SiteGit Code Agent</span><p>현장에서 수행할 작업을 자연어로 입력하세요. LLM이 승인된 작업 명령을 구성하고 현재 장비와 작업 대상을 검사합니다.</p><small>토사 생성, 작업 대상 이동·상태 변경, 장비 이동·굴착을 한 지시 안에서 조합할 수 있습니다.</small></div>
      </div>
      <div class="wp-chat-compose">
        <textarea class="form-control" id="aiWpPrompt" placeholder="예: Zone A 중앙에 5m x 5m x 2m 토사를 만들어줘"></textarea>
        <button class="primary-button" id="aiWpAnalyzeBtn">작업 해석</button>
      </div>
      <div class="ai-wp-preview hidden" id="aiWpPreview"></div>
    </div>`,
    footer:`<button class="ghost-button" data-modal-close>취소</button><button class="secondary-button" id="dispatchAiWpBtn" disabled>분석 후 Work Package 저장</button>`,
  });
  $('#aiWpAnalyzeBtn').addEventListener('click',analyzeAiWorkPackage);
  $('#dispatchAiWpBtn').addEventListener('click',dispatchAiWorkPackage);
  $('#aiWpPrompt').addEventListener('keydown',event=>{
    if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();analyzeAiWorkPackage()}
  });
}
async function analyzeAiWorkPackage(){
  const prompt=$('#aiWpPrompt').value.trim();
  if(prompt.length<3){toast('작업지시 필요','현장에서 수행할 작업을 입력해 주세요.','warning');return}
  const button=$('#aiWpAnalyzeBtn');
  button.disabled=true;button.textContent='로컬 LLM 분석 중...';
  $('#dispatchAiWpBtn').disabled=true;
  const messages=$('#aiWpMessages');
  messages.insertAdjacentHTML('beforeend',`<div class="wp-chat-message user"><span>관리자</span><p>${esc(prompt)}</p></div><div class="wp-chat-message assistant pending" id="aiWpPending"><span>SiteGit AI</span><p>자연어 지시와 현재 현장의 장비·작업 대상을 교차 검증하고 있습니다…</p></div>`);
  messages.scrollTop=messages.scrollHeight;
  try{
    const response=await apiFetch('/work-packages/ai/code/interpret',{
      method:'POST',body:JSON.stringify({project_id:PROJECT_ID,message:prompt}),
    });
    const data=await response.json().catch(()=>({}));
    if(!response.ok){
      const detail=data.detail||{};
      const error=new Error(detail.message||`AI_WORK_PACKAGE_${response.status}`);
      error.code=detail.code;throw error;
    }
    aiWorkPackageDraft=data;
    $('#aiWpPending')?.remove();
    const assistantText=data.executable
      ?`${data.plan.summary} 작업 계획과 현장 자원 검증이 완료됐습니다.`
      :data.plan.ready
        ?`${data.plan.summary} Work Package는 저장할 수 있지만 현재 실행 자원이 부족합니다.`
      :(data.plan.clarification_question||'작업지시를 실행하려면 추가 정보가 필요합니다.');
    messages.insertAdjacentHTML('beforeend',`<div class="wp-chat-message assistant"><span>SiteGit Code Agent · ${esc(data.model)}</span><p>${esc(assistantText)}</p></div>`);
    renderAiWorkPackageDraft();
  }catch(error){
    $('#aiWpPending')?.remove();
    const message=error.code==='LLM_NOT_CONFIGURED'
      ?'로컬 Ollama 앱과 qwen3:8b 모델이 실행 가능한지 확인해 주세요.'
      :(error.message||'LLM 요청에 실패했습니다.');
    messages.insertAdjacentHTML('beforeend',`<div class="wp-chat-message assistant error"><span>SiteGit AI</span><p>${esc(message)}</p></div>`);
    toast('Work Package 생성 실패',message,'danger');
  }finally{
    button.disabled=false;button.textContent='작업 해석';
    messages.scrollTop=messages.scrollHeight;
  }
}
function renderAiWorkPackageDraft(){
  const host=$('#aiWpPreview');
  if(!host||!aiWorkPackageDraft)return;
  const draft=aiWorkPackageDraft,plan=draft.plan;
  const executable=Boolean(draft.executable);
  host.classList.remove('hidden');
  host.innerHTML=`<div class="ai-wp-preview-head"><div><span>AI 작업 계획</span><strong>${esc(plan.summary)}</strong></div><span class="badge ${executable?'ready':'warning'}">${executable?'실행 가능':'자원 대기'}</span></div>
    <div class="ai-wp-preview-grid">
      <div><span>장비</span><b>${esc(draft.equipment?.name||'미확정')}</b></div>
      <div><span>작업 종류 / 구역</span><b>${esc(plan.operation)} · Zone ${esc(plan.zone_id||'미지정')}</b></div>
      <div class="full"><span>장비 Prim</span><b class="prim-path-value">${esc(draft.equipment?.path||'미확정')}</b></div>
      <div class="full"><span>작업 대상 / 생성 Prim</span><b class="prim-path-value">${esc(draft.target?.path||draft.execution_target_path||'해당 없음')}</b></div>
    </div>
    <div class="ai-wp-checks">${(draft.checks||[]).map(check=>`<div class="${check.ok?'pass':'fail'}"><span>${check.ok?'✓':'!'}</span><p>${esc(check.message)}</p></div>`).join('')}</div>
    <div class="ai-wp-source">기존 작업 대상은 현장 자원 목록과 일치할 때만 실행되며, 새 작업 대상은 승인된 작업 영역 안에서만 생성됩니다.</div>`;
  $('#dispatchAiWpBtn').disabled=false;
  $('#dispatchAiWpBtn').textContent=executable?'작업 지시 확정 · 현장 전송':'자원 대기 Work Package 저장';
}
function cacheCodeWorkPackageDispatch(data,display={}){
  const record=data.work_package;
  const instruction=data.instruction;
  let workPackage=state.workPackages.find(item=>item.id===record.id);
  const target=Number(display.target)||1;
  const zone=String(display.zone||record.zone_id||'-').replace(/zone\s*/i,'').trim().toUpperCase()||'-';
  const base={
    id:record.id,zone,name:display.title||record.summary,task:display.task||record.operation||'GENERATED_SCRIPT',length:0,
    target,raw:0,qualified:0,remaining:target,status:record.status,version:1,
    eta:record.status==='blocked'?'자원 대기':'작업 대기',risk:record.status==='blocked'?'high':'medium',start:'-',end:'-',x:0,y:0,width:0,
    color:'#d95757',completionThreshold:Number(display.completionThreshold)||100,
    observationThreshold:Number(display.observationThreshold)||100,toleranceMm:Number(display.toleranceMm)||0,assignments:[],
    isaacInstructionId:instruction.id,sourceText:record.source_text,
    equipmentPrimPath:record.equipment?.path||'',targetPrimPath:record.target?.path||record.execution_target_path||'',
    position:record.target?.world_position||display.position||null,
    size:record.target?.bounds_size||display.size||null,
    generatedCode:record.generated_code,segment:display.segment||'',successor:display.successor||'',
  };
  if(workPackage)Object.assign(workPackage,base);
  else{
    workPackage=base;
    state.workPackages.unshift(workPackage);
  }
  const evidence=state.evidence[record.id]||{};
  state.evidence[record.id]={...evidence,
    rule:100,completeness:record.status==='blocked'?10:25,confidence:0,observation:0,workFinished:false,
    resultDeviationMm:0,overcutVolume:0,state:'not-started',
    missing:[...new Set([...(record.missing_resources||[]),'작업 실행 Commit','관리자 승인'])],
    conflicts:evidence.conflicts||[],externalEvidence:evidence.externalEvidence||[],
  };
  if(!state.versions.some(version=>version.code===record.id)){
    state.versions.push({type:'work',code:record.id,title:'AI Code Work Package 발행',desc:record.summary,time:nowTime(),actor:currentUser?.full_name||state.manager.name,state:record.status==='blocked'?'warning':'current',branch:true});
  }
  state.selectedWpId=record.id;
  addEvent(record.status==='blocked'?'warning':'info','AI Work Package 발행',`${record.id} · ${record.status==='blocked'?'자원 대기':'현장 작업 실행 대기'}`);
  return workPackage;
}
async function submitCodeWorkPackageDraft(draft,display={}){
  const response=await apiFetch('/work-packages/ai/code/dispatch',{
    method:'POST',
    body:JSON.stringify({project_id:PROJECT_ID,message:draft.source_text,plan:draft.plan}),
  });
  const data=await response.json().catch(()=>({}));
  if(!response.ok)throw new Error(data.detail?.message||data.detail||`AI_DISPATCH_${response.status}`);
  cacheCodeWorkPackageDispatch(data,display);
  await loadIsaacInstructions();
  return data;
}
async function dispatchAiWorkPackage(){
  if(!aiWorkPackageDraft)return;
  const button=$('#dispatchAiWpBtn');button.disabled=true;button.textContent='Work Package 저장 중...';
  try{
    const data=await submitCodeWorkPackageDraft(aiWorkPackageDraft);
    const record=data.work_package;
    closeModal();
    navigate('dashboard');
    toast(record.status==='blocked'?'Work Package 자원 대기':'Work Package 전송 완료',record.status==='blocked'?(record.missing_resources||[]).join(' · '):'검증된 작업 지시가 현장 작업 실행 대기열에 등록됐습니다.',record.status==='blocked'?'warning':'success');
  }catch(error){
    button.disabled=false;button.textContent='Work Package 다시 저장';
    toast('현장 전송 실패',error.message||'서버 상태를 확인하세요.','danger');
  }
}
function evidenceUrl(storageKey){
  return `/evidence/${String(storageKey||'').split('/').map(encodeURIComponent).join('/')}`;
}
function evidenceImageKey(data){
  const explicit=data?.image?.storage_key;
  if(explicit)return explicit;
  const stageKey=data?.stage?.storage_key||'';
  // Older commits may say image.available=false even though Kit finished
  // writing the asynchronous viewport capture a moment later.  The stage and
  // viewport files share the same evidence directory, so recover that key.
  return /-stage\.json$/i.test(stageKey)?stageKey.replace(/-stage\.json$/i,'-viewport.png'):'';
}
function sensorVector(value){
  if(!Array.isArray(value)||value.length<3)return null;
  const vector=value.slice(0,3).map(Number);
  return vector.every(Number.isFinite)?vector:null;
}
function sensorVectorMagnitude(value){
  const vector=sensorVector(value);
  return vector?Math.sqrt(vector.reduce((sum,item)=>sum+item*item,0)):null;
}
function sensorVectorLabel(value,digits=3){
  const vector=sensorVector(value);
  return vector?vector.map(item=>item.toFixed(digits)).join(' · '):'측정값 없음';
}
function quaternionValue(value){
  if(!Array.isArray(value)||value.length<4)return null;
  const quaternion=value.slice(0,4).map(Number);
  if(!quaternion.every(Number.isFinite))return null;
  const length=Math.sqrt(quaternion.reduce((sum,item)=>sum+item*item,0));
  return length>1e-9?quaternion.map(item=>item/length):null;
}
function quaternionEulerDegrees(value){
  const quaternion=quaternionValue(value);
  if(!quaternion)return null;
  const [w,x,y,z]=quaternion;
  const roll=Math.atan2(2*(w*x+y*z),1-2*(x*x+y*y));
  const pitch=Math.asin(Math.max(-1,Math.min(1,2*(w*y-z*x))));
  const yaw=Math.atan2(2*(w*z+x*y),1-2*(y*y+z*z));
  return [roll,pitch,yaw].map(angle=>angle*180/Math.PI);
}
function quaternionDeltaDegrees(beforeValue,afterValue){
  const before=quaternionValue(beforeValue),after=quaternionValue(afterValue);
  if(!before||!after)return null;
  const dot=Math.min(1,Math.abs(before.reduce((sum,item,index)=>sum+item*after[index],0)));
  return 2*Math.acos(dot)*180/Math.PI;
}
function vectorDistance(beforeValue,afterValue){
  const before=sensorVector(beforeValue),after=sensorVector(afterValue);
  if(!before||!after)return null;
  return Math.sqrt(before.reduce((sum,item,index)=>sum+(after[index]-item)**2,0));
}
function imuReading(data){
  const imu=data?.imu||{};
  const frame=imu.frame||{};
  const acceleration=sensorVector(frame.lin_acc);
  const angularVelocity=sensorVector(frame.ang_vel);
  const orientation=quaternionValue(frame.orientation);
  const physicsStep=Number(frame.physics_step);
  const physicsTime=Number(frame.time);
  return {
    available:Boolean(imu.available&&acceleration&&angularVelocity&&orientation&&Number.isFinite(physicsStep)&&physicsStep>0),
    imu,frame,acceleration,angularVelocity,orientation,physicsStep,physicsTime,
    accelerationMagnitude:sensorVectorMagnitude(acceleration),
    angularSpeed:sensorVectorMagnitude(angularVelocity),
    euler:quaternionEulerDegrees(orientation),
  };
}
function sensorMetric(label,value,unit='',tone=''){
  return `<div class="sensor-metric ${tone}"><span>${esc(label)}</span><strong>${esc(value)}</strong>${unit?`<small>${esc(unit)}</small>`:''}</div>`;
}
function evidencePhaseCard(title,data){
  const image=data?.image||{};
  const stage=data?.stage||{};
  const telemetry=data?.telemetry||{};
  const imageKey=evidenceImageKey(data);
  return `<section class="commit-evidence-phase">
    <h3>${title}</h3>
    <div class="commit-evidence-image">${imageKey
      ?`<img decoding="async" src="${evidenceUrl(imageKey)}" alt="${title} 장비 장착 카메라" data-evidence-image><span hidden data-evidence-image-fallback>장비 카메라 이미지 없음<br><small>${esc(image.reason||'캡처 파일을 찾을 수 없음')}</small></span>`
      :`<span>장비 카메라 이미지 없음<br><small>${esc(image.reason||'캡처되지 않음')}</small></span>`}</div>
    <dl class="camera-evidence-meta">
      <div><dt>카메라</dt><dd class="${image.available?'evidence-ok':'evidence-missing'}">${image.available?'장비 장착 카메라':'이미지 없음'}</dd></div>
      <div><dt>대상 Prim 상태</dt><dd>${stage.target_active===false?'비활성화됨':stage.target_active===true?'활성':'확인 불가'}</dd></div>
      <div><dt>장비 Pose</dt><dd>${telemetry.available&&telemetry.storage_key
        ?`<a href="${evidenceUrl(telemetry.storage_key)}" target="_blank" rel="noopener">위치·자세 열기</a>`
        :esc(telemetry.reason||'데이터 없음')}</dd></div>
    </dl>
  </section>`;
}
function imuPhasePanel(title,data){
  const reading=imuReading(data);
  if(!reading.available){
    return `<div class="imu-phase-card unavailable"><div class="sensor-card-title"><strong>${title}</strong><span class="sensor-state bad">미수집</span></div><p>${esc(reading.imu.reason||'유효한 PhysX IMU 프레임이 없습니다.')}</p></div>`;
  }
  const euler=reading.euler||[];
  return `<div class="imu-phase-card">
    <div class="sensor-card-title"><strong>${title}</strong><span class="sensor-state ok">실측</span></div>
    <div class="imu-primary-value"><strong>${reading.accelerationMagnitude.toFixed(3)}</strong><span>m/s² · 가속도 크기</span></div>
    <div class="imu-data-list">
      <div><span>선형가속도 X · Y · Z</span><b>${sensorVectorLabel(reading.acceleration)} m/s²</b></div>
      <div><span>각속도 X · Y · Z</span><b>${sensorVectorLabel(reading.angularVelocity,4)} rad/s</b></div>
      <div><span>센서축 자세 R · P · Y</span><b>${euler.map(value=>`${value.toFixed(1)}°`).join(' · ')}</b></div>
      <div><span>PhysX 시점</span><b>${Number.isFinite(reading.physicsTime)?reading.physicsTime.toFixed(3):'-'}s · step ${num(reading.physicsStep)}</b></div>
    </div>
    ${reading.imu.storage_key?`<a class="sensor-raw-link" href="${evidenceUrl(reading.imu.storage_key)}" target="_blank" rel="noopener">원본 IMU JSON 열기 ↗</a>`:''}
  </div>`;
}
function imuComparisonPanel(beforeData,afterData){
  const before=imuReading(beforeData),after=imuReading(afterData);
  const orientationDelta=quaternionDeltaDegrees(before.orientation,after.orientation);
  const accelerationDelta=before.accelerationMagnitude!=null&&after.accelerationMagnitude!=null
    ?Math.abs(after.accelerationMagnitude-before.accelerationMagnitude):null;
  const angularSpeedAfter=after.angularSpeed;
  return `<section class="sensor-review-section">
    <div class="sensor-review-heading"><div><span>PHYSICAL IMU</span><h3>굴착기 움직임·자세 비교</h3></div><small>굴착기 RigidBody 장착 센서 · 작업 전/후 정지 프레임</small></div>
    <div class="imu-comparison-grid">${imuPhasePanel('작업 전',beforeData)}${imuPhasePanel('작업 후',afterData)}</div>
    <div class="sensor-delta-strip">
      ${sensorMetric('자세 변화',orientationDelta==null?'-':orientationDelta.toFixed(2),'deg',orientationDelta!=null&&orientationDelta>10?'warn':'')}
      ${sensorMetric('가속도 크기 차이',accelerationDelta==null?'-':accelerationDelta.toFixed(3),'m/s²',accelerationDelta!=null&&accelerationDelta>3?'warn':'')}
      ${sensorMetric('작업 후 각속도',angularSpeedAfter==null?'-':angularSpeedAfter.toFixed(4),'rad/s',angularSpeedAfter!=null&&angularSpeedAfter>.5?'warn':'')}
      ${sensorMetric('프레임 진행',before.available&&after.available?num(after.physicsStep-before.physicsStep):'-','steps',before.available&&after.available&&after.physicsStep<=before.physicsStep?'bad':'')}
    </div>
    <div class="depth-corroboration-option">
      <div class="depth-corroboration-copy">
        <span>OPTIONAL SENSOR FUSION</span>
        <h4>LiDAR + IMU·기구학 깊이 교차검증</h4>
        <p>LiDAR 지형 깊이에 장비 자세와 버킷 팁 최저점 추정값을 함께 대조하는 보조 Evidence 옵션입니다.</p>
      </div>
      <div class="depth-corroboration-example" aria-label="10미터 굴착 깊이 교차검증 예시">
        <div><span>목표 깊이</span><strong>10.00 m</strong></div>
        <div><span>LiDAR 확인</span><strong>10.01 m</strong></div>
        <div><span>IMU·기구학 추정</span><strong>10.02 m</strong></div>
        <div class="depth-corroboration-pass"><span>교차 판정</span><strong>목표 충족</strong></div>
      </div>
      <div class="depth-corroboration-disclaimer"><b>DEMO · 예시값</b><span>센서 융합 확장 가능성을 보여주는 보조 정보이며, 실제 승인 판정에는 아직 사용하지 않습니다.</span></div>
    </div>
  </section>`;
}
function lidarPhasePanel(title,data){
  const lidar=data?.lidar||{};
  if(!lidar.available){
    return `<div class="lidar-phase-card unavailable"><div class="sensor-card-title"><strong>${title}</strong><span class="sensor-state bad">미수집</span></div><p>${esc(lidar.reason||'LiDAR 데이터가 없습니다.')}</p></div>`;
  }
  if(lidar.capture_mode==='declared-only'){
    return `<div class="lidar-phase-card">
      <div class="sensor-card-title"><strong>${title}</strong><span class="sensor-state ok">센서 구성됨</span></div>
      <div class="lidar-data-row"><span>실행 모드</span><b>실시간 스캔 생략</b></div>
      <div class="lidar-data-row"><span>센서 위치 XYZ</span><b>${sensorVectorLabel(lidar.origin_m,2)} m</b></div>
      <div class="lidar-data-row"><span>측정 범위</span><b>${Array.isArray(lidar.range_m)?`${lidar.range_m.map(value=>num(value)).join('–')} m`:'-'}</b></div>
      <p>시연 성능을 위해 포인트 클라우드 계산은 생략하고 LiDAR 구성 정보만 기록합니다.</p>
    </div>`;
  }
  const ratio=Number(lidar.hit_ratio);
  return `<div class="lidar-phase-card">
    <div class="sensor-card-title"><strong>${title}</strong><span class="sensor-state ok">${num(lidar.point_count)} points</span></div>
    <div class="lidar-bar"><span style="width:${Math.max(0,Math.min(100,(Number.isFinite(ratio)?ratio:0)*100))}%"></span></div>
    <div class="lidar-data-row"><span>반환율</span><b>${Number.isFinite(ratio)?`${(ratio*100).toFixed(1)}%`:'-'}</b></div>
    <div class="lidar-data-row"><span>센서 원점 XYZ</span><b>${sensorVectorLabel(lidar.origin_m,2)} m</b></div>
    <div class="lidar-data-row"><span>범위</span><b>${Array.isArray(lidar.range_m)?`${lidar.range_m.map(value=>num(value)).join('–')} m`:'-'}</b></div>
    ${lidar.storage_key?`<a class="sensor-raw-link" href="${evidenceUrl(lidar.storage_key)}" target="_blank" rel="noopener">Point Cloud PLY 열기 ↗</a>`:''}
  </div>`;
}
function lidarComparisonPanel(beforeData,afterData,result){
  const before=beforeData?.lidar||{},after=afterData?.lidar||{};
  const geometry=result.geometry_change||{};
  const originDelta=vectorDistance(before.origin_m,after.origin_m);
  const pointDelta=before.available&&after.available?Number(after.point_count||0)-Number(before.point_count||0):null;
  return `<section class="sensor-review-section">
    <div class="sensor-review-heading"><div><span>3D RAYCAST LIDAR</span><h3>Point Cloud·지형 변화 비교</h3></div><small>동일 작업 위치의 작업 전/후 스캔</small></div>
    <div class="lidar-comparison-grid">${lidarPhasePanel('작업 전',beforeData)}${lidarPhasePanel('작업 후',afterData)}</div>
    <div class="sensor-delta-strip">
      ${sensorMetric('절토',geometry.available?num(geometry.removed_volume_m3||0):'-','㎥')}
      ${sensorMetric('성토',geometry.available?num(geometry.added_volume_m3||0):'-','㎥')}
      ${sensorMetric('변경 격자',geometry.available?num(geometry.changed_cell_count||0):'-','cells')}
      ${sensorMetric('센서 위치 차이',originDelta==null?'-':originDelta.toFixed(3),'m',originDelta!=null&&originDelta>.75?'warn':'')}
      ${sensorMetric('반환점 증감',pointDelta==null?'-':`${pointDelta>=0?'+':''}${num(pointDelta)}`,'points')}
    </div>
  </section>`;
}
function evidenceDiagnostics(evidence,result){
  const before=evidence.before||{},after=evidence.after||{};
  const beforeImu=imuReading(before),afterImu=imuReading(after);
  const quality=evidence.quality||{};
  const warnings=[];
  const lidarMetadataOnly=[before?.lidar,after?.lidar].every(lidar=>lidar?.capture_mode==='declared-only');
  (quality.missing_sensor_types||[]).forEach(sensor=>warnings.push({tone:'bad',message:`필수 센서 미수집: ${sensor}`}));
  if(quality.timestamps_valid===false)warnings.push({tone:'bad',message:'Evidence 시간 순서가 유효하지 않습니다.'});
  for(const [phase,label] of [[before,'작업 전'],[after,'작업 후']]){
    if(!phase?.image?.available)warnings.push({tone:'bad',message:`${label} 카메라 이미지가 없습니다.`});
    if(!phase?.lidar?.available)warnings.push({tone:'bad',message:`${label} LiDAR Point Cloud가 없습니다.`});
    if(!imuReading(phase).available)warnings.push({tone:'bad',message:`${label} IMU 물리 프레임이 없습니다.`});
  }
  if(beforeImu.available&&afterImu.available&&afterImu.physicsStep<=beforeImu.physicsStep){
    warnings.push({tone:'bad',message:'작업 후 IMU 프레임이 작업 전보다 진행되지 않았습니다.'});
  }
  for(const [reading,label] of [[beforeImu,'작업 전'],[afterImu,'작업 후']]){
    if(reading.available&&Math.abs(reading.accelerationMagnitude-9.81)>3){
      warnings.push({tone:'warn',message:`${label} 캡처 시 가속도 크기가 정지 기준과 크게 다릅니다 (${reading.accelerationMagnitude.toFixed(2)} m/s²).`});
    }
    if(reading.available&&reading.angularSpeed>.5){
      warnings.push({tone:'warn',message:`${label} 캡처 시 장비가 회전 중일 수 있습니다 (${reading.angularSpeed.toFixed(3)} rad/s).`});
    }
  }
  const originDelta=vectorDistance(before?.lidar?.origin_m,after?.lidar?.origin_m);
  if(originDelta!=null&&originDelta>.75)warnings.push({tone:'warn',message:`전·후 LiDAR 센서 위치가 ${originDelta.toFixed(2)}m 다릅니다.`});
  if(!lidarMetadataOnly&&!result?.geometry_change?.available)warnings.push({tone:'warn',message:`LiDAR 지형 비교 불가: ${result?.geometry_change?.reason||'비교 결과 없음'}`});
  return `<section class="evidence-diagnostics ${warnings.length?'has-warning':'all-clear'}">
    <div><span class="diagnostic-icon">${warnings.length?'!':'✓'}</span><div><strong>${warnings.length?`검토 필요 ${warnings.length}건`:'센서 Evidence 정상'}</strong><small>${warnings.length?'아래 항목은 자동 승인/반려가 아닌 관리자 확인 정보입니다.':'카메라·LiDAR·IMU 전후 데이터와 시간 순서가 확인됐습니다.'}</small></div></div>
    ${warnings.length?`<ul>${warnings.map(item=>`<li class="${item.tone}">${esc(item.message)}</li>`).join('')}</ul>`:''}
  </section>`;
}
function formatExecutionDuration(seconds){
  const value=Number(seconds);
  if(!Number.isFinite(value))return '-';
  if(value<60)return `${value.toFixed(2)}초`;
  return `${Math.floor(value/60)}분 ${(value%60).toFixed(1)}초`;
}
function executionMetricCards(result,evidence){
  const geometry=result.geometry_change||{};
  const quantity=result.performed_quantity||{};
  const quality=evidence.quality||{};
  const completeness=Number(quality.completeness_ratio);
  const metric=(label,value,note='')=>`<div class="execution-metric"><span>${label}</span><strong>${value}</strong>${note?`<small>${note}</small>`:''}</div>`;
  return `<div class="execution-metrics">
    ${metric('실행 시간',formatExecutionDuration(result.duration_seconds??evidence.duration_seconds),'실제 Adapter 실행 구간')}
    ${metric('작업량',quantity.value!=null?`${num(quantity.value)} ${esc(quantity.unit||'')}`:'산정 안 됨',quantity.method?`${esc(quantity.method)}${quantity.estimated?' · 추정':''}`:'센서 비교 결과 없음')}
    ${metric('절토 / 성토',geometry.available?`${num(geometry.removed_volume_m3||0)} / ${num(geometry.added_volume_m3||0)} ㎥`:'비교 불가',geometry.method?esc(geometry.method):esc(geometry.reason||''))}
    ${metric('Evidence 완결성',Number.isFinite(completeness)?`${Math.round(completeness*100)}%`:'기존 형식',(quality.missing_sensor_types||[]).length?`미수집: ${(quality.missing_sensor_types||[]).map(item=>esc(item)).join(', ')}`:'필수 센서 수집 완료')}
  </div>`;
}
function excavationQualityPanel(result){
  const quality=result?.quality_assessment||{};
  if(!quality.status)return '';
  const needsRemediation=quality.status==='needs_remediation';
  const measured=Math.round(Number(quality.measured_completion_ratio||0)*1000)/10;
  const required=Math.round(Number(quality.required_completion_ratio||0)*1000)/10;
  const planned=Number(quality.planned_volume_m3||0);
  const completed=Number(quality.completed_volume_m3||0);
  const remaining=Number(quality.remaining_volume_m3||0);
  const equipment=String(quality.equipment_prim_path||'').split('/').pop()?.replaceAll('_','-')||'-';
  return `<section class="excavation-quality-panel ${needsRemediation?'needs-remediation':'passed'}">
    <div class="excavation-quality-title">
      <i>${needsRemediation?'!':'✓'}</i>
      <div><span>EXCAVATION QUALITY GATE</span><h3>${needsRemediation?'목표 굴착량 미달 · 검토 필요':'목표 굴착량 충족'}</h3><p>${needsRemediation?'원 지시는 완료로 제출됐지만 센서 실측값이 승인 기준에 미달합니다.':'센서 실측값이 현재 공정의 승인 기준을 충족했습니다.'}</p></div>
      <strong>${measured}% / 기준 ${required}%</strong>
    </div>
    <div class="excavation-quality-metrics">
      <div><span>계획 굴착량</span><b>${num(planned)} ㎥</b></div>
      <div><span>실측 완료량</span><b>${num(completed)} ㎥</b></div>
      <div><span>부족 작업량</span><b>${num(remaining)} ㎥</b></div>
      <div><span>보완 대상 장비</span><b>${esc(equipment)}</b></div>
    </div>
    ${needsRemediation?'<small>카메라·LiDAR 증거를 확인한 뒤 AI 보완 작업 초안을 만들 수 있습니다. 수량과 작업 대상은 LLM이 아니라 센서 실측값으로 고정됩니다.</small>':''}
  </section>`;
}
function executionEventTimeline(evidence){
  const events=evidence.events||[];
  if(!events.length)return '<div class="execution-event-empty">기존 Commit에는 실행 이벤트가 없습니다.</div>';
  return `<div class="execution-event-list">${events.map(event=>`<div class="execution-event-row">
    <span>${Number(event.elapsed_seconds||0).toFixed(2)}s</span>
    <div><strong>${esc(event.event_type||'-')}</strong><small>${esc(event.work_state||'-')}</small></div>
  </div>`).join('')}</div>`;
}
function openIsaacEvidence(instructionId,commitId=''){
  const instruction=isaacInstructions.find(item=>item.id===instructionId);
  const commit=instruction&&((instruction.commits||[]).find(item=>item.id===commitId)||isaacLatestCommit(instruction));
  if(!instruction||!commit)return;
  const evidence=commit.evidence||{};
  const result=commit.result||{};
  const bindings=instruction.params?.resource_bindings||{};
  const equipmentPath=instruction.params?.equipment_prim_path||bindings.equipment||'-';
  const targetPath=instruction.params?.target_prim_path||bindings.target||result.target_prim_path||'-';
  const needsRemediation=result.quality_assessment?.status==='needs_remediation';
  const dateLabel=value=>{
    if(!value)return '-';
    const parsed=new Date(value);
    return Number.isNaN(parsed.getTime())?String(value):parsed.toLocaleString('ko-KR',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
  };
  const reviewLabels={approved:'승인 · Merge',rejected:'반려 · Conflict',pending:'검토 대기'};
  const workPackageId=instruction.params?.work_package_id||instruction.id;
  const workfront=instruction.params?.workfront_id||instruction.params?.label||'-';
  const equipmentName=instruction.params?.equipment_name||primShortName(equipmentPath);
  const parentCommitId=instruction.params?.remediation_parent_commit_id||'';
  const lineage=parentCommitId
    ?`원 Commit ${parentCommitId.slice(0,12)}…의 부족 굴착량을 보완한 재작업 Commit`
    :(needsRemediation?'목표량 미달로 보완 Work Package가 필요한 원 Commit':'독립 실행 Commit');
  const rejectedEvidencePanel=commit.review_status==='rejected'?`<section class="supplemental-evidence-panel" data-rejected-evidence-panel>
      <header>
        <div><span>REJECTED COMMIT · SUPPLEMENTAL EVIDENCE</span><h3>추가 Evidence 제출</h3><p>반려 사유를 보완할 현장 자료와 설명을 추가해 같은 Commit의 재검토를 요청할 수 있습니다.</p></div>
        <em>UI PREVIEW</em>
      </header>
      <div class="supplemental-evidence-reason"><span>반려 사유</span><strong>${esc(commit.review_note||'관리자 검토 기준을 충족하지 못했습니다.')}</strong></div>
      <div class="supplemental-evidence-form">
        <label class="supplemental-file-field">
          <span>보완 파일</span>
          <input id="supplementalEvidenceFiles" type="file" multiple accept=".jpg,.jpeg,.png,.pdf,.csv,.json,.ply,.pcd,.las,.laz">
          <small data-supplemental-file-summary>파일을 선택하세요 · 여러 파일 선택 가능</small>
        </label>
        <label class="supplemental-note-field">
          <span>보완 설명</span>
          <textarea id="supplementalEvidenceNote" rows="3" placeholder="예: 미굴착 구간을 추가 측량했으며 보완 작업 후 목표 깊이를 확인했습니다."></textarea>
        </label>
      </div>
      <div class="supplemental-evidence-types"><span>카메라 이미지</span><span>LiDAR·Point Cloud</span><span>측량 성과</span><span>현장 확인서</span></div>
      <footer><small>화면 예시입니다. 파일 저장과 재검증 API는 아직 연결되지 않았습니다.</small><button class="secondary-button" type="button" data-supplemental-evidence-submit disabled>추가 Evidence 제출 · 재검토 요청</button></footer>
    </section>`:'';
  openModal({
    eyebrow:'FIELD EXECUTION COMMIT',
    title:'작업 전·후 증거 검토',
    modalClass:'evidence-review-modal',
    body:`<div class="commit-evidence-summary">
      <strong>${esc(instruction.params?.label||instruction.kind)}</strong>
      <span>${esc(equipmentPath)} → ${esc(targetPath)}</span>
      <small>실행 환경: ${result.simulator?'현장 작업 시스템':'-'} · 검증: ${result.source?'센서 결과 데이터':'-'}</small>
    </div>
    <section class="commit-provenance">
      <header><div><span>HISTORICAL COMMIT</span><h3>${esc(commit.id)}</h3></div><em class="${esc(commit.review_status||'pending')}">${esc(reviewLabels[commit.review_status]||commit.review_status||'검토 대기')}</em></header>
      <dl>
        <div><dt>Commit 시각</dt><dd>${esc(dateLabel(commit.committed_at||commit.created_at))}</dd></div>
        <div><dt>Work Package</dt><dd>${esc(workPackageId)}</dd></div>
        <div><dt>작업전선 · 장비</dt><dd>${esc(workfront)} · ${esc(equipmentName)}</dd></div>
        <div><dt>관리자 판정</dt><dd>${esc(commit.reviewed_by||'-')} · ${esc(dateLabel(commit.reviewed_at))}</dd></div>
        <div class="wide"><dt>Commit 계보</dt><dd>${esc(lineage)}</dd></div>
        ${commit.review_note?`<div class="wide note"><dt>검토 메모</dt><dd>${esc(commit.review_note)}</dd></div>`:''}
      </dl>
    </section>
    ${rejectedEvidencePanel}
    ${executionMetricCards(result,evidence)}
    ${excavationQualityPanel(result)}
    <section class="sensor-review-section camera-review-section">
      <div class="sensor-review-heading">
        <div><span>EQUIPMENT CAMERA</span><h3>장비 카메라 작업 전·후</h3></div>
        <small>작업 대상에 접근한 뒤 암·버킷 동작 직전과 작업 완료 시점을 비교합니다.</small>
      </div>
      <div class="commit-evidence-grid">
        ${evidencePhaseCard('작업 전',evidence.before)}
        ${evidencePhaseCard('작업 후',evidence.after)}
      </div>
    </section>
    ${evidenceDiagnostics(evidence,result)}
    ${lidarComparisonPanel(evidence.before,evidence.after,result)}
    ${imuComparisonPanel(evidence.before,evidence.after)}
    <section class="execution-events"><div class="execution-events-head"><h3>실행 이벤트</h3><span>${num((evidence.events||[]).length)}건</span></div>${executionEventTimeline(evidence)}</section>`,
    footer:`<button class="ghost-button" data-modal-close>닫기</button>${commit.review_status==='pending'?(needsRemediation?`<button class="secondary-button" data-isaac-remediation="${esc(commit.id)}">AI 보완 작업 초안</button>`:`<button class="ghost-button" data-isaac-reject="${esc(commit.id)}">반려 · Conflict</button><button class="secondary-button" data-isaac-approve="${esc(commit.id)}">증거 확인 · 승인</button>`):''}`,
  });
  $$('[data-evidence-image]',$('#modalBody')).forEach(image=>image.addEventListener('error',()=>{
    image.hidden=true;
    const fallback=image.nextElementSibling;
    if(fallback)fallback.hidden=false;
  },{once:true}));
  const supplementalFiles=$('#supplementalEvidenceFiles');
  const supplementalSummary=$('[data-supplemental-file-summary]');
  const supplementalSubmit=$('[data-supplemental-evidence-submit]');
  supplementalFiles?.addEventListener('change',()=>{
    const files=[...(supplementalFiles.files||[])];
    if(supplementalSummary)supplementalSummary.textContent=files.length
      ?`${files.length}개 선택 · ${files.map(file=>file.name).join(', ')}`
      :'파일을 선택하세요 · 여러 파일 선택 가능';
    if(supplementalSubmit)supplementalSubmit.disabled=!files.length;
  });
  supplementalSubmit?.addEventListener('click',()=>{
    const files=[...(supplementalFiles?.files||[])];
    if(!files.length){toast('보완 파일 필요','재검토에 사용할 Evidence 파일을 선택하세요.','warning');return}
    toast('추가 Evidence 준비 완료',`${files.length}개 파일을 선택했습니다. 현재는 UI 예시이며 서버에는 저장되지 않습니다.`,'success');
  });
}
function openRealWorkPackageDetail(instructionId){
  const instruction=isaacInstructions.find(item=>item.id===instructionId);
  if(!instruction)return;
  const params=instruction.params||{};
  const bindings=params.resource_bindings||{};
  const commit=isaacLatestCommit(instruction);
  const status=realWorkPackageStatus(instruction.status);
  const equipmentPath=params.equipment_prim_path||bindings.equipment||'';
  const targetPath=params.target_prim_path||bindings.target||commit?.result?.target_prim_path||'';
  const missing=params.missing_resources||[];
  const lifecycle=[
    ['생성',instruction.created_at],
    ['작업 지시 수신',instruction.dispatched_at],
    ['최근 변경',instruction.updated_at],
    ['Commit',commit?.committed_at],
    ['관리자 판정',commit?.reviewed_at],
  ];
  openModal({
    eyebrow:'BACKEND WORK PACKAGE',
    title:realWorkPackageId(instruction),
    body:`<div class="real-wp-detail-head"><div><span class="badge ${status.badge}">${esc(status.label)}</span><h3>${esc(params.summary||params.label||instruction.note||realWorkPackageKind(instruction))}</h3><p>${esc(params.source_text||instruction.note||'자연어 원문 미기록')}</p></div><small>Field instruction<br><code>${esc(instruction.id)}</code></small></div>
      <div class="real-wp-detail-grid">
        <div><span>작업 종류</span><strong>${esc(realWorkPackageKind(instruction))}</strong></div>
        <div><span>생성자</span><strong>${esc(instruction.created_by_username||'시스템')}</strong></div>
        <div class="wide"><span>장비 Prim</span><code>${esc(equipmentPath||'미배정')}</code></div>
        <div class="wide"><span>대상 Prim</span><code>${esc(targetPath||'미배정')}</code></div>
      </div>
      ${missing.length?`<div class="real-wp-missing"><strong>현재 부족한 실행 자원</strong>${missing.map(item=>`<span>${esc(item)}</span>`).join('')}</div>`:''}
      <div class="real-wp-lifecycle">${lifecycle.map(([label,value])=>`<div class="${value?'done':''}"><i></i><span>${esc(label)}</span><b>${value?esc(new Date(value).toLocaleString('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})):'-'}</b></div>`).join('')}</div>
      <div class="real-wp-commit-summary"><span>실행 Commit</span><strong>${commit?`${esc(commit.status)} · ${num(commit.attempt||1)}차`:'아직 생성되지 않음'}</strong><small>${commit?`검토 상태: ${esc(commit.review_status||'pending')}`:'현장 작업 시스템이 작업을 완료하면 Evidence와 함께 생성됩니다.'}</small></div>`,
    footer:`<button class="ghost-button" data-modal-close>닫기</button>${commit?`<button class="secondary-button" data-isaac-detail="${esc(instruction.id)}">Evidence 검토</button>`:''}`,
  });
}
function responseDetailMessage(payload,fallback){
  const detail=payload?.detail;
  if(typeof detail==='string')return detail;
  if(detail&&typeof detail.message==='string')return detail.message;
  return fallback;
}
function openRemediationPlan(instruction){
  const params=instruction?.params||{};
  const narrative=params.remediation_narrative||{};
  const facts=params.remediation_facts||{};
  const bindings=params.resource_bindings||{};
  const steps=Array.isArray(narrative.action_steps)?narrative.action_steps:[];
  const equipment=String(bindings.equipment||'').split('/').pop()?.replaceAll('_','-')||'-';
  openModal({
    eyebrow:'AI CORRECTIVE WORK PLAN',
    title:'굴착 부족분 보완 작업',
    modalClass:'remediation-plan-modal',
    body:`<section class="remediation-plan-summary">
      <div><span>${params.llm_assisted?'LLM 보조 계획':'규칙 기반 대체 계획'} · ${esc(params.compiler_model||'-')}</span><h3>${esc(narrative.title||'보완 굴착 작업')}</h3><p>${esc(narrative.summary||'센서 실측 부족분을 보완합니다.')}</p></div>
      <em>관리자 승인 대기</em>
    </section>
    <div class="remediation-fact-grid">
      <div><span>배정 장비</span><b>${esc(equipment)}</b><small>${esc(bindings.equipment||'-')}</small></div>
      <div><span>작업 대상</span><b>${esc(String(bindings.target||'').split('/').pop()||'-')}</b><small>${esc(bindings.target||'-')}</small></div>
      <div><span>원 계획량</span><b>${num(facts.planned_volume_m3||0)} ㎥</b></div>
      <div class="critical"><span>추가 굴착량</span><b>${num(facts.remaining_volume_m3||0)} ㎥</b></div>
    </div>
    <section class="remediation-steps"><h3>보완 작업 흐름</h3>${steps.map((step,index)=>`<div><i>${index+1}</i><span>${esc(step)}</span></div>`).join('')}</section>
    <div class="remediation-manager-note"><strong>관리자 확인</strong><p>${esc(narrative.manager_note||'대상과 부족량을 확인한 뒤 해당 장비 한 대에만 재작업을 하달합니다.')}</p></div>
    <p class="remediation-safety-note">LLM은 설명만 작성합니다. 장비·대상 Prim·부족 작업량은 승인된 원 Commit과 센서 실측값에서 고정되며 임의로 변경되지 않습니다.</p>`,
    footer:`<button class="ghost-button" data-modal-close>취소</button><button class="secondary-button" data-remediation-dispatch="${esc(instruction.id)}">승인 · ${esc(equipment)} 보완 작업 하달</button>`,
  });
}
async function loadRemediationPlan(instructionId){
  try{
    const instruction=(isaacInstructions||[]).find(item=>item.id===instructionId);
    if(!instruction)throw new Error('보완 Work Package를 찾을 수 없습니다. 새로고침 후 다시 시도하세요.');
    openRemediationPlan(instruction);
  }catch(error){toast('보완 계획을 열지 못했습니다',error.message,'danger')}
}
async function createIsaacRemediation(commitId){
  try{
    const response=await apiFetch(`/isaac/commits/${encodeURIComponent(commitId)}/remediation`,{method:'POST',body:'{}'});
    const payload=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(responseDetailMessage(payload,`REMEDIATION_${response.status}`));
    await loadIsaacInstructions();
    openRemediationPlan(payload);
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')toast('보완 계획 생성 실패',String(error.message||error),'danger');
  }
}
async function dispatchIsaacRemediation(instructionId){
  const button=document.querySelector(`[data-remediation-dispatch="${CSS.escape(instructionId)}"]`);
  if(button){button.disabled=true;button.textContent='현장 자원 확인 중…';}
  try{
    const response=await apiFetch(`/isaac/instructions/${encodeURIComponent(instructionId)}/dispatch-remediation`,{method:'POST',body:'{}'});
    const payload=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(responseDetailMessage(payload,`DISPATCH_REMEDIATION_${response.status}`));
    await loadIsaacInstructions();
    closeModal();
    addEvent('warning','굴착 보완 작업 하달',`${payload.params?.equipment_name||'지정 굴착기'} 한 대가 부족 구간만 재작업합니다.`);
    toast('보완 작업 하달 완료','EXC-002가 부족 굴착량을 보완한 뒤 새 Evidence Commit을 제출합니다.','success');
    renderAll();
  }catch(error){
    if(button){button.disabled=false;button.textContent='승인 · 보완 작업 하달';}
    if(error.message!=='AUTH_REQUIRED')toast('보완 작업 하달 실패',String(error.message||error),'danger');
  }
}
async function reviewIsaacCommit(commitId,decision){
  const note=decision==='rejected'?(prompt('반려 사유를 입력하세요.')||'').slice(0,500):null;
  if(decision==='rejected'&&!note){toast('반려 취소','사유를 입력해야 반려할 수 있습니다.','warning');return}
  const reviewedInstruction=(isaacInstructions||[]).find(item=>(item.commits||[]).some(commit=>commit.id===commitId));
  const scenarioRunId=reviewedInstruction?.params?.scenario_run_id||'';
  const scenarioZoneId=reviewedInstruction?.params?.zone_id||'A';
  try{
    const response=await apiFetch(`/isaac/commits/${encodeURIComponent(commitId)}/review`,{
      method:'POST',body:JSON.stringify({decision,note}),
    });
    if(response.status===409){toast('이미 판정된 결과','다른 관리자가 먼저 처리했습니다.','warning');await loadIsaacInstructions();return}
    if(!response.ok){const payload=await response.json().catch(()=>({}));throw new Error(responseDetailMessage(payload,`REVIEW_${response.status}`))}
    await loadIsaacInstructions();
    closeModal();
    if(decision==='approved'){
      reloadIsaacMapObjects();
      addEvent('success','현장 작업 결과 승인','승인된 작업 결과가 Site Work Map에 반영됐습니다.');
      const nextPhaseOpened=typeof wfOpenReadyScenarioPhasePlan==='function'&&wfOpenReadyScenarioPhasePlan(scenarioRunId);
      toast(
        nextPhaseOpened?'선행 공정 승인 완료':'승인 완료',
        nextPhaseOpened?`Zone ${scenarioZoneId}의 다음 공정 단계 작업량·장비·판정 기준을 검토하고 계획 승인해 주세요.`:'맵에 작업 결과가 반영됐습니다.',
        'success',
      );
    }else{
      reloadIsaacMapObjects();
      addEvent('warning','현장 작업 Conflict 등록',`반려 사유: ${note}`);
      toast('Conflict 등록','공식 맵에는 반영되지 않고 Constraint 화면에 남습니다.','warning');
    }
    renderAll();
  }catch(error){
    if(error.message!=='AUTH_REQUIRED')toast('판정 실패',String(error.message||'서버 연결과 권한을 확인하세요.'),'danger');
  }
}

/* Modal helpers */
function normalizedSitePlanDesign(raw){
  const candidate=raw?.design||raw;
  if(candidate?.centerline&&candidate?.phases)return candidate;
  const area=candidate?.work_area;const pipe=area?.pipe;
  if(!area||!pipe||!Array.isArray(candidate?.workflow))throw new Error('SiteGit 도면 JSON 또는 시나리오 도면 JSON이 아닙니다.');
  return {
    plan_id:candidate.plan_id,revision:candidate.revision,title:candidate.title,
    source_map:candidate.source_map,work_area_id:area.id,work_area_label:area.label,
    station_range:area.station_range,total_length_m:area.total_length_m,
    design_depth_m:area.design_depth_m,pipe_diameter_m:pipe.outside_diameter_m,
    centerline:area.centerline,workfronts:area.workfronts||[],phases:candidate.workflow,
    assumptions:candidate.planning_assumptions||[],
  };
}
function drawingRecordMarkup(record){
  const design=record.design||{};const approved=record.status==='approved';
  const updated=Number(new Date(record.updated_at))>0?new Date(record.updated_at).toLocaleString('ko-KR'):'기본 시나리오';
  return `<article class="drawing-record ${approved?'approved':''}"><div><span>${approved?'APPROVED':'DRAFT'}</span><b>${esc(design.plan_id||'-')} · Rev.${esc(design.revision||'-')}</b><small>${esc(design.title||'-')}</small></div><dl><div><dt>구간</dt><dd>${esc(design.station_range||'-')}</dd></div><div><dt>관로</dt><dd>Ø${design.pipe_diameter_m||'-'}m · 깊이 ${design.design_depth_m||'-'}m</dd></div><div><dt>저장</dt><dd>${esc(updated)}</dd></div><div><dt>작성자</dt><dd>${esc(record.updated_by||'-')}</dd></div></dl></article>`;
}
function openDrawingManager(){
  const current=approvedSitePlan?.design;
  openModal({
    eyebrow:'SITE PLAN REGISTRY',title:'현장 도면 관리',modalClass:'drawing-manager-modal',
    body:`<div class="drawing-manager-summary"><div><span>현재 승인 도면</span><b>${current?`${esc(current.plan_id)} · Rev.${esc(current.revision)}`:'등록되지 않음'}</b><small>${current?`${esc(current.station_range)} · 관경 Ø${current.pipe_diameter_m}m · 설계 깊이 ${current.design_depth_m}m`:'도면을 등록하면 메인 맵의 도면 레이어에 표시됩니다.'}</small></div><button class="secondary-button" type="button" data-map-layer="drawing">맵에서 보기</button></div><div class="drawing-registry-list">${sitePlans.map(drawingRecordMarkup).join('')||'<p class="muted">저장된 도면이 없습니다.</p>'}</div><div class="drawing-upload-box"><div><b>새 Revision 등록</b><span>좌표 정합이 끝난 SiteGit JSON 또는 시나리오 JSON을 저장합니다.</span></div><input class="form-control" id="sitePlanFile" type="file" accept="application/json,.json"><label>저장 상태<select class="form-control" id="sitePlanStatus"><option value="draft">초안</option><option value="approved">승인 도면</option></select></label><p class="form-hint">승인 도면만 메인 3D 맵의 지하 관로 X-ray 레이어에 적용됩니다.</p></div>`,
    footer:`<button class="ghost-button" data-modal-close>닫기</button><button class="primary-button" id="saveSitePlanBtn" ${remoteCanEdit?'':'disabled'}>도면 Revision 저장</button>`,
  });
  $('#saveSitePlanBtn')?.addEventListener('click',saveDrawingRevision);
}
async function saveDrawingRevision(){
  const button=$('#saveSitePlanBtn');const file=$('#sitePlanFile')?.files?.[0];
  if(!file){toast('도면 파일 필요','저장할 JSON 도면 파일을 선택해 주세요.','warning');return;}
  button.disabled=true;button.textContent='도면 검증·저장 중…';
  try{
    const raw=JSON.parse(await file.text());const design=normalizedSitePlanDesign(raw);
    const response=await apiFetch('/site-plans',{method:'POST',body:JSON.stringify({project_id:PROJECT_ID,status:$('#sitePlanStatus').value,source_filename:file.name,design})});
    const payload=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(payload.detail?.message||payload.detail||`SITE_PLAN_${response.status}`);
    await loadSitePlans();activeMapLayer=payload.status==='approved'?'drawing':activeMapLayer;
    closeModal();renderAll(true);
    toast('도면 Revision 저장 완료',`${payload.design.plan_id} Rev.${payload.design.revision} · ${payload.status==='approved'?'메인 맵 적용':'초안 저장'}`,'success');
  }catch(error){button.disabled=false;button.textContent='도면 Revision 저장';toast('도면 저장 실패',String(error.message||error),'danger');}
}

function openModal({eyebrow='EDIT',title,body,footer,modalClass=''}){
  const modal=$('#genericModal');
  modal.className=`modal${modalClass?` ${modalClass}`:''}`;
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
  openModal({eyebrow:'PROJECT CONFIGURATION',title:'현장·건설사 기본정보',body:`<div class="form-grid"><div class="form-group full"><label>프로젝트명</label><input class="form-control" id="fProjectName" value="${esc(p.name)}"></div><div class="form-group"><label>건설사 / 시공사</label><input class="form-control" id="fContractor" value="${esc(state.company.contractor)}"></div><div class="form-group"><label>현장관리자</label><input class="form-control" id="fManager" value="${esc(state.manager.name)}"></div><div class="form-group"><label>현장 위치</label><input class="form-control" id="fLocation" value="${esc(p.location)}"></div><div class="form-group"><label>착공일</label><input type="date" class="form-control" id="fStart" value="${p.startDate}"></div><div class="form-group"><label>준공일</label><input type="date" class="form-control" id="fEnd" value="${p.endDate}"></div><div class="form-group"><label>터파기 물량 (㎥)</label><input type="number" class="form-control" id="fVolume" value="${p.excavationVolume}"></div><div class="form-group"><label>도급 총공사비 (원)</label><input type="number" class="form-control" id="fCost" value="${p.contractCost}"></div></div>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveProjectBtn">변경 저장</button>`});
  $('[data-modal-close]').addEventListener('click',closeModal);$('#saveProjectBtn').addEventListener('click',()=>{p.name=$('#fProjectName').value;p.shortName=p.name.replace(/하수관로.*/,'').trim()||p.name;state.company.contractor=$('#fContractor').value;state.manager.name=$('#fManager').value;p.location=$('#fLocation').value;p.startDate=$('#fStart').value;p.endDate=$('#fEnd').value;p.excavationVolume=Number($('#fVolume').value)||p.excavationVolume;p.contractCost=Number($('#fCost').value)||p.contractCost;closeModal();toast('기본정보 저장','현장과 관리자 정보가 로컬 데이터에 반영됐습니다.','success');renderAll()});
}
function openReadinessModal(id){
  const item=id?state.readiness.find(r=>r.id===id):{id:`custom-${Date.now()}`,name:'',category:'현장 데이터',grade:'C',status:'missing',source:'USER INPUT',value:'',action:'경고 후 진행 가능',desc:''};
  openModal({eyebrow:'DATA READINESS',title:id?'데이터 항목 수정':'데이터 항목 추가',body:`<div class="form-grid"><div class="form-group"><label>항목명</label><input class="form-control" id="rName" value="${esc(item.name)}"></div><div class="form-group"><label>카테고리</label><input class="form-control" id="rCategory" value="${esc(item.category)}"></div><div class="form-group"><label>등급</label><select class="form-control" id="rGrade">${['A','B','C','D'].map(x=>`<option ${x===item.grade?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group"><label>상태</label><select class="form-control" id="rStatus">${[['ready','확보'],['simulated','검증용 데이터'],['needs-confirmation','확인 필요'],['missing','미제공']].map(([v,l])=>`<option value="${v}" ${v===item.status?'selected':''}>${l}</option>`).join('')}</select></div><div class="form-group"><label>데이터 출처</label><select class="form-control" id="rSource">${['PUBLIC PROJECT','MANUFACTURER SPEC','STANDARD-BASED','USER INPUT','ASSUMED','FIELD SYSTEM','SENSOR DATA'].map(x=>`<option ${x===item.source?'selected':''}>${x}</option>`).join('')}</select></div><div class="form-group"><label>현재 값</label><input class="form-control" id="rValue" value="${esc(item.value)}"></div><div class="form-group full"><label>설명</label><textarea class="form-control" id="rDesc">${esc(item.desc)}</textarea></div><div class="form-group full"><label>누락·확인 시 시스템 행동</label><input class="form-control" id="rAction" value="${esc(item.action)}"></div><div class="form-group full"><label>관련 파일 (로컬 파일명만 표시)</label><input type="file" class="form-control" id="rFile"><span class="form-hint">등록 여부와 파일명을 관리하며, 지원 형식은 별도 데이터 처리 과정에서 검증합니다.</span></div></div>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="primary-button" id="saveReadinessBtn">저장</button>`});
  $('[data-modal-close]').addEventListener('click',closeModal);$('#saveReadinessBtn').addEventListener('click',()=>{item.name=$('#rName').value;item.category=$('#rCategory').value;item.grade=$('#rGrade').value;item.status=$('#rStatus').value;item.source=$('#rSource').value;item.value=$('#rValue').value;item.desc=$('#rDesc').value;item.action=$('#rAction').value;const f=$('#rFile').files[0];if(f){item.value=`${item.value} · ${f.name}`;item.status='ready';item.source='USER INPUT'}if(!id)state.readiness.push(item);closeModal();toast('데이터 준비도 갱신',`${item.name} 항목이 저장됐습니다.`,'success');renderAll()});
}
function equipmentEditorPreview(e){
  const imageUrl=EQUIPMENT_PHOTOS[e.model];
  const visual=imageUrl
    ?`<img decoding="async" src="${imageUrl}" alt="${esc(e.model)} 장비 전체 사진">`
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
  const w=id?state.workPackages.find(x=>x.id===id):{id:`WP-DEMO-${String.fromCharCode(65+state.workPackages.length)}01`,zone:String.fromCharCode(65+state.workPackages.length),name:'신규 자율화 작업',task:'EXCAVATION',length:0,target:100,raw:0,qualified:0,remaining:100,status:'draft',version:1,eta:'대기',risk:'low',start:'-',end:'-',x:0,y:0,width:0,color:'#3d7fa0',completionThreshold:100,observationThreshold:90,toleranceMm:50,assignments:[]};
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
function showSourcesModal(){openModal({eyebrow:'SOURCE DISCLOSURE',title:'현장 장비 데이터 출처',body:`<div class="source-list"><div class="source-row"><div><strong>승인 작업 도면</strong><small>Zone별 목표량과 공정별 판정 기준</small></div>${sourceBadge('APPROVED DRAWING')}</div><div class="source-row"><div><strong>HD Hyundai HX210AL 장비 제원</strong><small>EXC-001 · EXC-002 · EXC-003 · EXC-004의 제조사 공개 제원</small></div>${sourceBadge('MANUFACTURER SPEC')}</div><div class="source-row"><div><strong>장비 Evidence</strong><small>Camera · LiDAR · IMU · Pose · 작업 이벤트</small></div>${sourceBadge('SENSOR DATA')}</div></div><div class="divider"></div><p class="muted" style="font-size:10px;line-height:1.65">Equipment Registry는 현장 장비 ID와 실제 제조사 모델·제원을 기준으로 표시합니다. 현장 연동에 필요한 내부 연결 정보는 화면에 노출하지 않고 연결 모듈에서만 관리합니다.</p>`,footer:`<button class="primary-button" data-modal-close>확인</button>`});$('[data-modal-close]').addEventListener('click',closeModal)}
function showArchitectureModal(){openModal({eyebrow:'SITEGIT CORE',title:'자율화 운영·검증 아키텍처',body:`<div class="onboard-summary"><div class="onboard-summary-row"><strong>01 · Site Data Onboarding</strong><span>건설사 기존 데이터 → Data Readiness</span></div><div class="onboard-summary-row"><strong>02 · Work Package Compiler</strong><span>작업 대상·목표·제약·종료조건</span></div><div class="onboard-summary-row"><strong>03 · Field Equipment Connector</strong><span>장비 Capability 비교·작업 배포</span></div><div class="onboard-summary-row"><strong>04 · Autonomous Equipment</strong><span>인지·경로·작업기 제어·실제 수행</span></div><div class="onboard-summary-row"><strong>05 · Execution & Evidence</strong><span>장비 이벤트·궤적·작업 결과 귀속</span></div><div class="onboard-summary-row"><strong>06 · Trust & Human Gate</strong><span>Rule·완결성·관측 신뢰도 → 관리자 결정</span></div><div class="onboard-summary-row"><strong>07 · Version Update</strong><span>결정 이력·보완·다음 Plan 연결</span></div></div>`,footer:`<button class="primary-button" data-modal-close>확인</button>`});$('[data-modal-close]').addEventListener('click',closeModal)}

/* Onboarding */
function openOnboarding(){onboardingStep=0;renderOnboarding();$('#onboardingBackdrop').classList.remove('hidden')}
function closeOnboarding(){safeSetItem(ONBOARD_KEY,'1');$('#onboardingBackdrop').classList.add('hidden');renderAll()}
function renderOnboarding(){
  $('#onboardingProgress').style.setProperty('--step-progress',`${(onboardingStep+1)*25}%`);
  const c=$('#onboardingContent');
  if(onboardingStep===0)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 1 / 4 · PROJECT</div><h2>건설사와 현장 기본정보</h2><p class="intro">현재 관로 시공 프로젝트 정보를 기본값으로 채웠습니다. 실제 프로젝트에 맞게 언제든 수정할 수 있습니다.</p><div class="form-grid"><div class="form-group full"><label>프로젝트명</label><input class="form-control" id="oProject" value="${esc(state.project.name)}"></div><div class="form-group"><label>시공사</label><input class="form-control" id="oContractor" value="${esc(state.company.contractor)}"></div><div class="form-group"><label>현장관리자</label><input class="form-control" id="oManager" value="${esc(state.manager.name)}"></div><div class="form-group"><label>현장 위치</label><input class="form-control" id="oLocation" value="${esc(state.project.location)}"></div></div></div>`;
  if(onboardingStep===1)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 2 / 4 · SITE DATA</div><h2>자율화 작업 데이터 준비도</h2><p class="intro">데이터 출처와 검증 상태를 표시하고, 누락 데이터별 시스템 행동을 정의합니다.</p><div class="onboard-summary">${state.readiness.slice(0,8).map(r=>`<div class="onboard-summary-row"><div><strong>${r.grade} · ${esc(r.name)}</strong><div style="margin-top:5px">${sourceBadge(r.source)}</div></div><span class="status-chip ${r.status}">${readinessStatusLabel(r.status)}</span></div>`).join('')}</div></div>`;
  if(onboardingStep===2)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 3 / 4 · EQUIPMENT</div><h2>현장 장비 Capability</h2><p class="intro">관로 공사에 투입되는 HD Hyundai HX210AL 굴착기 3대를 Registry에 등록합니다.</p>${state.equipment.map(e=>`<div class="onboard-equip"><div class="onboard-equip-icon"><img src="${EQUIPMENT_PHOTOS[e.model]||''}" alt="${esc(e.manufacturer)} ${esc(e.model)}"></div><div><strong>${e.id} · ${esc(e.manufacturer)} ${esc(e.model)}</strong><small>${esc(e.type)} · ${esc(e.workfrontId||'작업전선 미배정')}</small></div><div class="spacer"></div>${sourceBadge(e.specSource)}</div>`).join('')}</div>`;
  if(onboardingStep===3)c.innerHTML=`<div class="onboarding-panel-content"><div class="eyebrow">STEP 4 / 4 · COMPLETE</div><h2>현장 설정이 완료되었습니다</h2><p class="intro">입력한 프로젝트 정보와 장비 구성을 확인했습니다. 현장 대시보드에서 작업 계획과 실행 상태를 관리할 수 있습니다.</p><div class="onboard-summary"><div class="onboard-summary-row"><strong>프로젝트</strong><span>${esc(state.project.shortName)}</span></div><div class="onboard-summary-row"><strong>기준 터파기 물량</strong><span>${num(state.project.excavationVolume)}㎥</span></div><div class="onboard-summary-row"><strong>작업 계획</strong><span>${state.workPackages.length}개</span></div><div class="onboard-summary-row"><strong>등록 장비</strong><span>${state.equipment.length}대</span></div></div></div>`;
  $('#onboardingPrevBtn').style.visibility=onboardingStep===0?'hidden':'visible';$('#onboardingNextBtn').textContent=onboardingStep===3?'현장 대시보드 열기':'다음';
}
function saveOnboardingStep(){
  if(onboardingStep===0){state.project.name=$('#oProject')?.value||state.project.name;state.project.shortName=state.project.name.replace(/하수관로.*/,'').trim()||state.project.name;state.company.contractor=$('#oContractor')?.value||state.company.contractor;state.manager.name=$('#oManager')?.value||state.manager.name;state.project.location=$('#oLocation')?.value||state.project.location;}
}
$('#onboardingPrevBtn').addEventListener('click',()=>{saveOnboardingStep();onboardingStep=Math.max(0,onboardingStep-1);renderOnboarding()});
$('#onboardingNextBtn').addEventListener('click',()=>{saveOnboardingStep();if(onboardingStep<3){onboardingStep++;renderOnboarding()}else closeOnboarding()});
$('#quickStartBtn').addEventListener('click',closeOnboarding);

/* Data import/export/reset */
function exportJson(){
  const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='SiteGit_Pipeline_Demo_Data.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('JSON 내보내기','현재 프로젝트·장비·작업·Evidence 데이터가 저장됐습니다.','success')
}
$('#jsonImportInput').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{const parsed=JSON.parse(await file.text());state=mergeDefaults(deepClone(DEFAULT_STATE),parsed);applyCurrentDemoProfile(state);renderAll(true);toast('JSON 불러오기 완료',file.name,'success')}catch(err){toast('불러오기 실패','유효한 SiteGit JSON 파일인지 확인하세요.','danger')}e.target.value=''});
function confirmReset(){openModal({eyebrow:'DANGER ZONE',title:'전체 데모를 초기화할까요?',body:`<p style="font-size:11px;line-height:1.7;color:var(--slate-600)">현장정보, 장비 수정값, Work Package, Evidence와 Version 이력을 관로 시공 통합 데모의 초기 상태로 되돌립니다. 내보내지 않은 변경사항은 복구할 수 없습니다.</p>`,footer:`<button class="ghost-button" data-modal-close>취소</button><button class="danger-button" id="confirmResetBtn">초기화</button>`});$('[data-modal-close]').addEventListener('click',closeModal);$('#confirmResetBtn').addEventListener('click',()=>{if(simTimer)clearInterval(simTimer);state=deepClone(DEFAULT_STATE);applyCurrentDemoProfile(state);safeRemoveItem(STORAGE_KEY);closeModal();toast('데모 초기화 완료','관로 시공 통합 데모의 초기 상태로 돌아갔습니다.','success');renderAll(true)})}
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
    const response=await apiFetch(`/state/${PROJECT_ID}`,{method:'PUT',body:JSON.stringify({payload:sharedStatePayload(),revision:remoteRevision,source:'full-reset'})});
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
renderHeader();
applyPage();
const initialPage=$(`#page-${state.selectedPage}`);
if(initialPage)initialPage.innerHTML='<div class="card"><div class="empty-state">공동 작업 기록을 불러오는 중입니다.</div></div>';
const judgeDemoOnboarding=safeGetSessionItem(JUDGE_DEMO_ONBOARD_SESSION_KEY)==='1';
if(judgeDemoOnboarding)safeRemoveSessionItem(JUDGE_DEMO_ONBOARD_SESSION_KEY);
if(judgeDemoOnboarding||!safeGetItem(ONBOARD_KEY)) openOnboarding();
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
  const allowed=button.matches('.nav-item,#mobileMenuBtn,#logoutBtn,#notificationsBtn,#profileBtn,#closeModalBtn,[data-modal-close],[data-select-wp],[data-wp-id],[data-zone],[data-page-link],[data-review-open],[data-review-back],[data-review-phase],[data-settings-tab],[data-equipment-select],[data-isaac-detail],[data-real-wp-detail],[data-history-event],[data-map-layer],[data-action="fit-map"],[data-action="manage-drawings"],[data-workflow-action="refresh"],[data-isaac-remediation],[data-remediation-dispatch],[data-open-remediation]');
  if(allowed)return;
  event.preventDefault();
  event.stopImmediatePropagation();
  toast('조회 전용 계정','공동 DB를 변경할 권한이 없습니다.','warning');
},true);
