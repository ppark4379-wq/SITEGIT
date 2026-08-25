/* Manager-workflow UI layer. Isaac rendering and execution remain owned by app.js. */
const workflowUI={mode:'compose',messages:[{role:'assistant',text:'현장 작업을 자연어로 설명해 주세요. Zone, 공종, 작업 구간과 목표량을 확인해 작업지시 초안을 만들겠습니다.'}],draft:null,reviewId:null,scenarioRunId:null,settingsTab:'criteria',equipmentId:null,equipmentQuery:'',equipmentType:'ALL',equipmentStatus:'ALL',historyZone:'ALL',historyBranchesOpen:new Set(),reviewPhase:'excavation',planView:'drawing',publishing:false};
if(state.selectedPage==='readiness')state.selectedPage='dashboard';

function wfInstructionForWork(w){return (isaacInstructions||[]).find(item=>item.id===w?.isaacInstructionId||item.params?.work_package_id===w?.id)||null;}
function wfCommitForWork(w){const instruction=wfInstructionForWork(w);return instruction?isaacLatestCommit(instruction):null;}
function wfCommitNeedsRemediation(instruction){
  const commit=isaacLatestCommit(instruction);
  return commit?.review_status==='pending'&&commit?.result?.quality_assessment?.status==='needs_remediation';
}
function wfRemediationInstruction(instructions=[]){
  return instructions.find(item=>item.params?.remediation_mode&&item.status!=='approved')||instructions.find(item=>item.params?.remediation_mode)||null;
}
function wfStatus(w){
  const instruction=wfInstructionForWork(w);
  const status=instruction?.status||w?.status;
  if(wfCommitNeedsRemediation(instruction))return ['목표량 미달 · 검토 필요','warning'];
  if(instruction?.params?.remediation_mode&&status!=='approved')return ['보완 작업 중','warning'];
  if(status==='approved'||status==='accepted'||status==='done'||Number(w?.qualified)>=100)return ['승인 완료','done'];
  if(status==='rejected'||status==='paused')return ['반려·Conflict','warning'];
  if(status==='blocked'&&instruction?.params?.phase_approval_ready)return ['다음 공정 계획 승인','review'];
  if(status==='blocked')return ['선행 공정 승인 대기','locked'];
  if(status==='correction'||status==='correction-issued')return ['보완 중','warning'];
  if(status==='dispatched'||status==='executing')return ['현장 작업 중','active'];
  if(status==='pending')return ['작업 대기','active'];
  if(status==='committed'||status==='review'||Number(w?.qualified)>0)return ['검토 대기','review'];
  return ['대기','locked'];
}
function wfProgress(w){
  const instruction=wfInstructionForWork(w);
  if(instruction?.status==='approved')return 100;
  if(['committed','rejected'].includes(instruction?.status))return 100;
  if(instruction?.status==='dispatched'||['dispatched','executing'].includes(w?.status)){
    return Math.max(0,Math.min(100,Number(w?.raw??0)));
  }
  return Math.max(0,Math.min(100,Number(w?.qualified??w?.raw??0)));
}
function wfEquipmentLabel(w){
  const instruction=wfInstructionForWork(w);
  const params=instruction?.params||{};
  const path=params.equipment_prim_path||params.resource_bindings?.equipment||w?.equipmentPrimPath||'';
  const assigned=typeof assignmentRoleSummary==='function'?assignmentRoleSummary(w):'-';
  return params.equipment_name||path.split('/').filter(Boolean).at(-1)||assigned;
}
function wfReviewClickAttributes(w){
  const instruction=wfInstructionForWork(w);
  if(!instruction)return `data-review-open="${esc(w.id)}"`;
  return wfCommitForWork(w)?`data-isaac-detail="${esc(instruction.id)}"`:`data-real-wp-detail="${esc(instruction.id)}"`;
}
function wfCriteria(w={}){return {name:'Pipe Trench v1.2',tolerance:Number(w.toleranceMm??50),completion:Number(w.completionThreshold??100),observation:Number(w.observationThreshold??90)};}
function wfBlank(title,desc){return `<div class="workflow-blank"><div class="workflow-blank-mark">◇</div><strong>${esc(title)}</strong><span>${esc(desc)}</span></div>`;}
function wfMapFrame({controls=true,planning=false}={}){
  const captionTitle=planning?'도면 작업 예정 구간':activeMapLayer==='zone'?'작업 Zone':activeMapLayer==='timeline'?'Commit Timeline':activeMapLayer==='drawing'?'승인 도면 · 지하 관로':'현재 현장 맵';
  const captionDetail=planning?'노란 점선 전체는 Zone A, 내부 색상은 장비별 작업전선 1~3입니다.':activeMapLayer==='zone'?'새 작업 지시의 실제 대상 범위를 표시합니다.':activeMapLayer==='timeline'?'새 승인 Commit을 순서대로 재생합니다.':activeMapLayer==='drawing'?(approvedSitePlan?`${wfPlanLabel(approvedSitePlan.design.plan_id)} Rev.${approvedSitePlan.design.revision} · X-ray 설계 관로`:'승인 도면을 등록해 주세요.'):'관리자 승인으로 Merge된 작업 결과를 표시합니다.';
  const toolbar=controls?`<div class="workflow-map-toolbar map-toolbar"><div class="segmented"><button class="${activeMapLayer==='work'?'active':''}" data-map-layer="work">Work</button><button class="${activeMapLayer==='zone'?'active':''}" data-map-layer="zone">Zone</button><button class="${activeMapLayer==='timeline'?'active':''}" data-map-layer="timeline">Timeline</button><button class="${activeMapLayer==='drawing'?'active':''}" data-map-layer="drawing">도면</button></div><button class="ghost-button button-sm" data-action="manage-drawings">도면 관리</button><button class="ghost-button button-sm" data-action="fit-map">화면 맞춤</button></div>`:'';
  return `<div class="workflow-map-shell ${planning?'planning':''}">${toolbar}<iframe class="workflow-map" ${planning?'data-planning-map="1"':''} src="/static/isaac-map-viewer.html?v=20260825-soil-candidate-1" title="${planning?'관로 도면 작업 예정 구간':'현장 작업 맵'}"></iframe><div class="workflow-map-caption"><b>${captionTitle}</b><span>${captionDetail}</span></div>${controls?`<div class="map-timeline-shell map-timeline-control ${activeMapLayer==='timeline'?'active':''}">${timelineControlMarkup()}</div>`:''}</div>`;
}

renderDashboard=function(){
  const works=state.workPackages||[];const active=works.filter(w=>!['accepted','done'].includes(w.status)).length;const review=works.filter(w=>wfStatus(w)[1]==='review').length;const correction=works.filter(w=>wfStatus(w)[1]==='warning').length;
  $('#page-dashboard').innerHTML=`<div class="workflow-page">
    <div class="workflow-kpis"><button data-page-link="execution"><span>작업 중</span><b>${active}</b><small>지속 관리 필요</small></button><button data-page-link="evidence"><span>검토 대기</span><b>${review}</b><small>검토·승인 필요</small></button><button data-page-link="evidence"><span>보완 필요</span><b>${correction}</b><small>즉시 확인 필요</small></button><button data-page-link="execution"><span>다음 공정 대기</span><b>${Math.max(0,works.length-active)}</b><small>선행 작업 확인</small></button></div>
    <div class="workflow-dashboard-grid"><section class="workflow-panel map-panel"><header><div><h2>현장 맵 <small>Site Work Map</small></h2><p>작업 위치와 문제 Zone을 한눈에 확인합니다.</p></div><span class="workflow-live">${stageInventory?.connected?'LIVE':'OFFLINE'}</span></header>${wfMapFrame()}</section>
    <aside class="workflow-panel action-panel"><header><div><h2>지금 확인할 작업</h2><p>우선순위가 높은 관리자 조치</p></div></header>${works.slice(0,4).map((w,i)=>{const s=wfStatus(w);return `<button class="workflow-action-row" data-page-link="${s[1]==='review'||s[1]==='warning'?'evidence':'execution'}"><i class="${s[1]}"></i><span><b>${esc(w.zone||'-')} · ${esc(w.name)}</b><small>${s[0]} · ${esc(w.id)}</small></span><em>›</em></button>`}).join('')||wfBlank('등록된 작업 없음','작업 지시에서 첫 작업을 작성하세요.')}</aside></div></div>`;
};

renderWorkPackages=function(){
  const page=$('#page-workpackages');const selected=state.workPackages.find(w=>w.id===state.selectedWpId)||state.workPackages[0]||{};const criteria=wfCriteria(selected);
  if(workflowUI.mode==='form'&&workflowUI.draft){page.innerHTML=wfInstructionForm(workflowUI.draft,criteria);wfAnnotateStationRanges(page);requestAnimationFrame(wireIsaacMapFrames);return;}
  page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 지시</h2><p>대화로 계획을 정리하고, 관리자 확인 후 구조화된 작업지시를 발행합니다.</p></div><button class="ghost-button" data-workflow-action="reset-chat">새 대화</button></div>
  <div class="instruction-layout"><section class="workflow-panel chat-panel"><header><div><h3>SiteGit Planning Assistant</h3><p>대화 내용은 작업지시 초안 작성에만 사용됩니다.</p></div><span class="planning-badge">PLAN ONLY</span></header><div class="workflow-chat" id="workflowChat">${workflowUI.messages.map(m=>`<div class="chat-message ${m.role}"><span>${m.role==='assistant'?'S':'나'}</span><p>${esc(m.text)}</p></div>`).join('')}</div><form class="workflow-prompt" id="workflowPrompt"><textarea id="workflowPromptText" placeholder="예: 이 구역 관로 공사 진행하자."></textarea><button class="primary-button" type="submit">초안 만들기</button></form></section>
  <aside class="instruction-context"><section class="workflow-panel zone-panel"><header><div><h3>현재 맵 · Zone</h3><p>명령 대상의 공간 문맥</p></div></header>${wfMapFrame({controls:false})}</section><section class="workflow-panel criteria-panel"><header><div><h3>적용 작업 기준</h3><p>설정의 현재 프로젝트 기준</p></div><button class="text-button" data-page-link="settings">설정에서 관리</button></header><div class="criteria-list"><div><span>Preset</span><b>${criteria.name}</b></div><div><span>바닥 Level</span><b>±${criteria.tolerance}mm</b></div><div><span>완료 판정 기준</span><b>${criteria.completion}%</b></div><div><span>Evidence 완전성</span><b>${criteria.observation}% 이상</b></div></div></section></aside></div></div>`;
  requestAnimationFrame(wireIsaacMapFrames);
};
function wfInstructionForm(d,c){if(d.design)return wfDrawingInstructionForm(d,c);return `<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업지시 초안</h2><p>AI가 대화 내용을 구조화했습니다. 발행 전 관리자가 모든 값을 확인합니다.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div><div class="instruction-form-layout"><section class="workflow-panel structured-form"><div class="form-section"><h3>작업 기본 정보</h3><div class="workflow-form-grid"><label>작업 구역<input id="wfZone" value="${esc(d.zone)}"></label><label>공종<input id="wfTask" value="${esc(d.task)}"></label><label class="wide">작업명<input id="wfTitle" value="${esc(d.title)}"></label><label>목표 작업량<input id="wfTarget" type="number" value="${d.target}"></label><label>단위<input id="wfUnit" value="${esc(d.unit)}"></label><label class="wide">작업 구간<input id="wfSegment" value="${esc(d.segment)}"></label></div></div><div class="form-section"><h3>완료·승인 판정 기준</h3><div class="criteria-inline"><label>바닥 Level 허용오차<input id="wfTolerance" type="number" value="${c.tolerance}"><span>mm</span></label><label>완료 기준<input id="wfCompletion" type="number" value="${c.completion}"><span>%</span></label><label>Evidence 완전성<input id="wfObservation" type="number" value="${c.observation}"><span>%</span></label></div></div><div class="form-section"><h3>장비·후속 작업</h3><div class="workflow-form-grid"><label>장비 제안<input id="wfEquipment" value="${esc(d.equipment)}"></label><label>후속 작업<input id="wfSuccessor" value="${esc(d.successor)}"></label></div></div><footer><span><b>발행 준비 완료</b> · 관리자 확인 시 현장 자원을 검증하고 작업 실행 대기열로 전송합니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'현장 자원 검증 중…':'관리자 확인 · 작업 발행'}</button></footer></section><aside class="workflow-panel precheck"><h3>작업 준비 확인</h3>${[['작업 구역',d.zone],['목표 작업량',`${d.target}${d.unit}`],['완료 기준',c.name],['장비 배정',d.equipment]].map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>발행 후 작업 현황에서 현장 작업 상태를 추적할 수 있습니다.</p></aside></div></div>`;}

function wfDesignUnit(unit){return unit==='m3'?'㎥':unit==='ea'?'개':'m';}
function wfPlanLabel(planId){return String(planId||'-').replace(/^SASANG-PIPE-/i,'PIPELINE-').replace(/^SASANG-/i,'');}
function wfStationPoint(value){
  const meters=Number(value);
  if(!Number.isFinite(meters))return String(value??'-');
  const sign=meters<0?'-':'';
  const absolute=Math.abs(meters);
  const kilometer=Math.floor(absolute/1000);
  const remainder=absolute-kilometer*1000;
  const decimals=Number.isInteger(remainder)?0:1;
  const [whole,fraction]=remainder.toFixed(decimals).split('.');
  return `${sign}${kilometer}+${whole.padStart(3,'0')}${fraction?`.${fraction}`:''}`;
}
function wfAnnotateStationRanges(root=document){
  const noteText='기준점 STA 0+000 = 관로 중심선 시작점 · 단위 m · 중심선 누적거리';
  root.querySelectorAll('.drawing-reference dt,.scenario-current-panel dt').forEach(label=>{
    if(label.textContent.trim()!=='작업 구간'&&!label.classList.contains('station-label'))return;
    label.textContent='작업 구간 · 측점(STA)';
    label.classList.add('station-label');
    const value=label.nextElementSibling;
    if(!value||value.querySelector('.station-basis'))return;
    const range=value.textContent.trim();
    value.textContent='';
    const rangeNode=document.createElement('span');
    rangeNode.className='station-range-value';
    rangeNode.textContent=range;
    const note=document.createElement('small');
    note.className='station-basis';
    note.textContent=noteText;
    value.append(rangeNode,note);
    value.title=noteText;
  });
  root.querySelectorAll('.workfront-row small').forEach(label=>{
    const match=label.textContent.trim().match(/^STA\s+([\d.]+)\s*~\s*([\d.]+)m(\s*·.*)?$/);
    if(!match)return;
    label.textContent=`STA ${wfStationPoint(match[1])} ~ ${wfStationPoint(match[2])} · 단위 m${match[3]||''}`;
  });
  root.querySelectorAll('.pipeline-station-label').forEach(label=>{
    const match=label.textContent.match(/^STA\s+([\d.]+)(.*)$/);
    if(match)label.textContent=`STA ${wfStationPoint(match[1])}${match[2]}`;
  });
  const drawingSubtitle=root.querySelector('.pipeline-title .sub');
  if(drawingSubtitle&&drawingSubtitle.textContent.includes('좌표 단위 m'))drawingSubtitle.textContent=drawingSubtitle.textContent.replace('좌표 단위 m','STA 기준: 중심선 시작점 · 단위 m');
}
function wfScenarioZoneId(design=approvedSitePlan?.design){return String(design?.zone_id||design?.phases?.[0]?.zone_id||'A');}
function wfScenarioZoneTitle(design=approvedSitePlan?.design){return String(design?.zone_title||'관로 공사');}
function wfPhaseStep(phase,index=-1){const order=Number(phase?.order);return Number.isFinite(order)&&order>0?order:index+1;}
function wfPhaseBadge(phase,index=-1){return `${wfPhaseStep(phase,index)}단계`;}
function wfPhaseCss(phase,index=-1){return `zone-${['a','b','c'][Math.max(0,wfPhaseStep(phase,index)-1)]||'a'}`;}
function wfCurrentPhaseId(draft){if(draft?.design?.scenario_type==='soil_relocation')return 'soil_relocation';const text=`${draft?.task||''} ${draft?.title||''}`;if(/되메우|복토/.test(text))return 'backfill';if(/관로 설치|관매설|배관 설치/.test(text))return 'pipe_installation';return 'excavation';}
function wfReadyScenarioPhaseInstruction(scenarioRunId=''){
  return [...(isaacInstructions||[])]
    .filter(item=>item.status==='blocked'&&item.params?.phase_approval_ready&&item.params?.scenario_plan_id&&(!scenarioRunId||item.params?.scenario_run_id===scenarioRunId))
    .sort((left,right)=>(Date.parse(right.params?.ready_at||right.updated_at||0)||0)-(Date.parse(left.params?.ready_at||left.updated_at||0)||0))[0]||null;
}
function wfOpenReadyScenarioPhasePlan(scenarioRunId=''){
  const instruction=wfReadyScenarioPhaseInstruction(scenarioRunId);
  const design=approvedSitePlan?.design;
  if(!instruction||!design||design.plan_id!==instruction.params?.scenario_plan_id)return false;
  const phase=(design.phases||[]).find(item=>item.id===instruction.params?.scenario_phase_id);
  if(!phase)return false;
  const nextPhase=(design.phases||[]).find(item=>Number(item.order)===Number(phase.order)+1);
  workflowUI.draft={
    sourceText:instruction.params?.source_text||`${design.title} ${phase.title}`,
    summary:`Zone ${wfScenarioZoneId(design)} 관로 공사의 ${wfPhaseBadge(phase)} ${phase.title} 계획이 열렸습니다. 선행 공정 Evidence 승인 결과를 기준으로 장비·작업량·판정 기준을 확인한 뒤 하달합니다.`,
    zone:`Zone ${wfScenarioZoneId(design)}`,
    task:phase.title,
    title:`${design.work_area_label} ${phase.title}`,
    target:Number(phase.target_amount||0),
    unit:phase.target_unit,
    segment:design.station_range,
    equipment:(phase.equipment||[]).join(' + '),
    successor:nextPhase?.title||'관로 공사 완료',
    scenarioRunId:instruction.params?.scenario_run_id||'',
    design,
  };
  workflowUI.mode='form';
  workflowUI.planView='drawing';
  setIsaacPlanningOverlay(design);
  navigate('workpackages');
  renderAll();
  window.scrollTo({top:0,behavior:'smooth'});
  return true;
}
function wfPhaseCriteriaPanel(phases,draft=workflowUI.draft){
  const selected=phases.find(phase=>phase.id===wfCurrentPhaseId(draft))||phases[0];
  if(!selected)return '';
  const zoneLabel=draft?.design?.zone_assignment_mode==='create_on_approval'
    ?`승인 후 생성될 Zone ${wfScenarioZoneId(draft?.design)}`
    :`Zone ${wfScenarioZoneId(draft?.design)}`;
  return `<div class="form-section phase-criteria-section"><div class="section-title-row"><div><h3>${wfPhaseBadge(selected)} ${esc(selected.title)} 완료·승인 판정 기준</h3><p>${esc(zoneLabel)}에 현재 하달할 공정의 도면 검측 기준만 적용됩니다.</p></div><span>현재 공정</span></div><div class="phase-criteria-list">${(selected.acceptance_criteria||[]).map((criterion,index)=>`<div><i>${index+1}</i><span>${esc(criterion)}</span><b>${index===selected.acceptance_criteria.length-1?'Evidence':'검측'}</b></div>`).join('')}</div></div>`;
}
function wfSoilRelocationDrawing(design){
  const move=design?.relocation||{};
  const src=move.source_position||{};const dst=move.destination_position||{};const eq=move.equipment_position||{};
  const points=[src,dst,eq].filter(Boolean);const minX=Math.min(...points.map(p=>Number(p.x)||0))-6;const maxX=Math.max(...points.map(p=>Number(p.x)||0))+6;const minY=Math.min(...points.map(p=>Number(p.y)||0))-6;const maxY=Math.max(...points.map(p=>Number(p.y)||0))+6;
  const project=p=>({x:100+((Number(p.y)-minY)/(maxY-minY||1))*720,y:470-((Number(p.x)-minX)/(maxX-minX||1))*370});
  const a=project(src),b=project(dst),m=project(eq);const label=(p,title,sub,color)=>`<g transform="translate(${p.x.toFixed(1)} ${p.y.toFixed(1)})"><circle r="18" fill="${color}" stroke="#fff" stroke-width="4"></circle><rect x="25" y="-24" width="210" height="48" rx="8" fill="#0d2d3c"></rect><text x="38" y="-5" fill="#fff" font-size="15" font-weight="800">${esc(title)}</text><text x="38" y="13" fill="#b8d9df" font-size="11">${esc(sub)}</text></g>`;
  return `<div class="pipeline-drawing"><svg viewBox="0 0 920 540" role="img" aria-label="토사 이동 후보 구역 도면"><defs><pattern id="relocationGrid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#c8dce0" stroke-width=".7"></path></pattern><marker id="relocationArrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#8056a3"></path></marker></defs><rect width="920" height="540" fill="#f6fbfc"></rect><rect width="920" height="540" fill="url(#relocationGrid)"></rect><rect x="42" y="62" width="836" height="424" rx="24" fill="rgba(128,86,163,.08)" stroke="#8056a3" stroke-width="3" stroke-dasharray="11 8"></rect><text x="64" y="95" fill="#593575" font-size="18" font-weight="900">작업 후보 구역 · 승인 시 새 Zone B 생성</text><path d="M${a.x.toFixed(1)} ${a.y.toFixed(1)} Q${m.x.toFixed(1)} ${(m.y-85).toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}" fill="none" stroke="#8056a3" stroke-width="8" stroke-dasharray="12 8" marker-end="url(#relocationArrow)"></path>${label(a,'기존 흙더미','5회 분할 굴착','#bd7b25')}${label(m,move.equipment_id||'EXC-004','궤도 고정 · 상부체만 선회','#2f96bd')}${label(b,'지정 적치 위치',`${Number(move.swing_degrees||90)}° 선회 후 적치`,'#35aa83')}<text x="64" y="516" fill="#4a6570" font-size="13">현장 도면이 찾은 후보 위치 · 관리자가 확인·승인하면 이 구역이 Zone B가 됩니다.</text></svg></div>`;
}

function wfPipelineDrawing(design){
  if(design?.scenario_type==='soil_relocation')return wfSoilRelocationDrawing(design);
  design={...design,plan_id:wfPlanLabel(design?.plan_id)};
  const source=(design.centerline||[]).map(point=>({station:Number(point.station_m),x:Number(point.x),y:Number(point.y),width:Number(point.width_m)})).filter(point=>Object.values(point).every(Number.isFinite));
  if(source.length<2)return wfBlank('도면 좌표 없음','승인 도면의 중심선 좌표를 확인해 주세요.');
  const canvas={width:920,height:540,padX:78,padY:72};
  const maxWidth=Math.max(...source.map(point=>point.width));
  const minX=Math.min(...source.map(point=>point.x))-maxWidth/2;const maxX=Math.max(...source.map(point=>point.x))+maxWidth/2;
  const minY=Math.min(...source.map(point=>point.y))-maxWidth/2;const maxY=Math.max(...source.map(point=>point.y))+maxWidth/2;
  const scale=Math.min((canvas.width-canvas.padX*2)/(maxY-minY||1),(canvas.height-canvas.padY*2)/(maxX-minX||1));
  const centerX=(minX+maxX)/2;const centerY=(minY+maxY)/2;
  const project=point=>({x:canvas.width/2+(point.y-centerY)*scale,y:canvas.height/2-(point.x-centerX)*scale});
  const edge=(point,index,side)=>{const previous=source[Math.max(0,index-1)];const next=source[Math.min(source.length-1,index+1)];const dx=next.x-previous.x;const dy=next.y-previous.y;const length=Math.hypot(dx,dy)||1;return project({x:point.x+(-dy/length)*(point.width/2)*side,y:point.y+(dx/length)*(point.width/2)*side});};
  const left=source.map((point,index)=>edge(point,index,1));const right=source.map((point,index)=>edge(point,index,-1)).reverse();
  const polygon=[...left,...right].map(point=>`${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(' ');
  const centerline=source.map(point=>{const projected=project(point);return `${projected.x.toFixed(1)},${projected.y.toFixed(1)}`;}).join(' ');
  const frontColors=['#2f96bd','#9b68cc','#35aa83'];
  const fronts=(design.workfronts||[]).map((front,index)=>{const segment=source.filter(point=>point.station>=Number(front.station_start_m)-.01&&point.station<=Number(front.station_end_m)+.01);if(segment.length<2)return '';const line=segment.map(point=>{const projected=project(point);return `${projected.x.toFixed(1)},${projected.y.toFixed(1)}`;}).join(' ');const midpoint=project(segment[Math.floor(segment.length/2)]);const color=frontColors[index%frontColors.length];return `<polyline class="pipeline-front" points="${line}" style="--front:${color}"></polyline><g class="pipeline-zone-label" transform="translate(${midpoint.x.toFixed(1)} ${midpoint.y.toFixed(1)})"><rect x="-39" y="-15" width="78" height="30" rx="6"></rect><text text-anchor="middle" y="-1">FRONT F${index+1}</text><text class="equipment" text-anchor="middle" y="10">${esc(front.equipment_id)}</text></g>`;}).join('');
  const stations=source.map((point,index)=>{const projected=project(point);const anchor=index%2?'start':'end';const offset=index%2?10:-10;return `<circle class="pipeline-station" cx="${projected.x.toFixed(1)}" cy="${projected.y.toFixed(1)}" r="4"></circle><text class="pipeline-station-label" x="${(projected.x+offset).toFixed(1)}" y="${(projected.y-9).toFixed(1)}" text-anchor="${anchor}">STA ${point.station.toFixed(1)} · W ${point.width.toFixed(1)}m</text>`;}).join('');
  return `<div class="pipeline-drawing"><svg viewBox="0 0 ${canvas.width} ${canvas.height}" role="img" aria-label="${esc(design.title)} 평면도"><defs><pattern id="drawingGrid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M 24 0 L 0 0 0 24" fill="none" stroke="#bfd7dd" stroke-width=".6"></path></pattern><pattern id="soilHatch" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><line x1="0" y1="0" x2="0" y2="12" stroke="#b9994f" stroke-width="2"></line></pattern></defs><rect width="100%" height="100%" fill="#f6fbfc"></rect><rect width="100%" height="100%" fill="url(#drawingGrid)"></rect><polygon class="pipeline-corridor" points="${polygon}"></polygon><polyline class="pipeline-centerline" points="${centerline}"></polyline>${fronts}${stations}<g class="pipeline-north" transform="translate(54 56)"><circle r="25"></circle><path d="M0 -18 L8 8 L0 3 L-8 8 Z"></path><text y="-28" text-anchor="middle">N</text></g><g class="pipeline-section" transform="translate(714 386)"><rect width="176" height="124" rx="8"></rect><text class="title" x="14" y="22">대표 단면</text><path class="ground" d="M14 48 H162"></path><path class="trench" d="M42 48 L58 101 H118 L134 48"></path><circle class="pipe" cx="88" cy="82" r="18"></circle><text x="14" y="116">깊이 ${design.design_depth_m}m · 관경 Ø${design.pipe_diameter_m}m</text></g><g class="pipeline-title"><text x="78" y="30">${esc(design.plan_id)} · REV.${esc(design.revision)}</text><text class="sub" x="78" y="48">${esc(design.station_range)} · L=${design.total_length_m}m · 좌표 단위 m</text></g></svg><div class="pipeline-drawing-legend"><span><i class="zone-a"></i>Zone ${esc(wfScenarioZoneId(design))} · ${esc(wfScenarioZoneTitle(design))}</span><span><i class="zone-b"></i>1단계 터파기</span><span><i class="zone-c"></i>2단계 관로 설치 → 3단계 되메우기</span><span><i class="soil"></i>작업전선 1~3</span><b>Zone=대형 공사 구역 · Phase=내부 공정 · Front=장비별 구간</b></div></div>`;
}

function wfSequentialPhaseInstructionForm(d){
  const design={...d.design,plan_id:wfPlanLabel(d.design?.plan_id)};const phases=design.phases||[];
  const currentIndex=Math.max(0,phases.findIndex(phase=>phase.id===wfCurrentPhaseId(d)));
  const current=phases[currentIndex]||phases[0];
  const flow=phases.map((phase,index)=>{const stateClass=index<currentIndex?'completed':index===currentIndex?'ready':'locked';const stateLabel=index<currentIndex?'승인 완료':index===currentIndex?'하달 대상':'선행 승인 후';return `<div class="scenario-phase ${stateClass}"><span>${wfPhaseStep(phase,index)}</span><div><b>${wfPhaseBadge(phase,index)} · ${esc(phase.title)}</b><small>Zone ${esc(wfScenarioZoneId(design))} · ${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)} · 약 ${phase.estimated_hours}h</small></div><em>${stateLabel}</em></div>${index<phases.length-1?'<i class="scenario-arrow">→</i>':''}`}).join('');
  const registered=(isaacInstructions||[]).filter(item=>item.params?.scenario_run_id===d.scenarioRunId&&item.params?.scenario_phase_id===current.id);
  const resources=registered.length
    ?registered.map((item,index)=>{const params=item.params||{};const quantity=params.planned_quantity||{};return `<div class="workfront-row"><span class="zone-token ${wfPhaseCss(current,currentIndex)}">${esc(params.workfront_id||`F${index+1}`)}</span><div><b>${esc(params.equipment_name||'장비 미정')}</b><small>${esc(params.target_name||current.title)}</small></div><div><b>${num(quantity.value||0)}${wfDesignUnit(quantity.unit||current.target_unit)}</b><small>${esc(params.station_range||design.station_range)}</small></div><em class="ready">Stage 확인 완료</em></div>`;}).join('')
    :(current.equipment||[]).map((item,index)=>`<div class="workfront-row"><span class="zone-token ${wfPhaseCss(current,currentIndex)}">F${index+1}</span><div><b>${esc(item)}</b><small>${esc(current.title)} 계획 장비</small></div><div><b>${num(current.target_amount)}${wfDesignUnit(current.target_unit)}</b><small>${esc(design.station_range)}</small></div><em class="waiting">발행 시 검증</em></div>`).join('');
  const totalHours=phases.reduce((sum,phase)=>sum+Number(phase.estimated_hours||0),0).toFixed(1);
  return `<div class="workflow-page drawing-plan-page"><div class="workflow-page-head"><div><h2>도면 기반 작업 계획</h2><p>Zone ${esc(wfScenarioZoneId(design))} 관로 공사에서 선행 단계가 승인된 현재 공정만 검토하고 하달합니다.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div><div class="drawing-plan-layout"><section class="workflow-panel structured-form"><div class="drawing-reference"><div><span>CURRENT PHASE</span><b>${wfPhaseBadge(current,currentIndex)} · ${esc(current.title)}</b><small>Zone ${esc(wfScenarioZoneId(design))} · ${esc(wfScenarioZoneTitle(design))} · ${esc(design.plan_id)} Rev.${esc(design.revision)}</small></div><dl><div><dt>작업 구간</dt><dd>${esc(design.station_range)}</dd></div><div><dt>목표 작업량</dt><dd>${num(current.target_amount)}${wfDesignUnit(current.target_unit)}</dd></div><div><dt>예상 시간</dt><dd>${current.estimated_hours}h</dd></div><div><dt>선행 공정</dt><dd>${(current.depends_on||[]).length?'승인 완료':'없음'}</dd></div></dl></div><div class="form-section"><h3>AI 작업 계획</h3><p class="plan-summary">${esc(d.summary)}</p><div class="scenario-flow">${flow}</div></div><div class="form-section"><div class="section-title-row"><div><h3>${wfPhaseBadge(current,currentIndex)} · ${esc(current.title)} 작업 자원</h3><p>현재 공정에 필요한 장비만 발행 시점의 현장 자원 정보로 검증합니다.</p></div><span>Zone ${esc(wfScenarioZoneId(design))}</span></div><div class="workfront-list">${resources}</div></div>${wfPhaseCriteriaPanel(phases,d)}<input id="wfZone" type="hidden" value="${esc(d.zone)}"><input id="wfTask" type="hidden" value="${esc(d.task)}"><input id="wfTitle" type="hidden" value="${esc(d.title)}"><input id="wfTarget" type="hidden" value="${d.target}"><input id="wfUnit" type="hidden" value="${esc(d.unit)}"><input id="wfSegment" type="hidden" value="${esc(d.segment)}"><input id="wfEquipment" type="hidden" value="${esc(d.equipment)}"><input id="wfSuccessor" type="hidden" value="${esc(d.successor)}"><footer><span><b>현재 단계만 하달</b> · ${wfPhaseBadge(current,currentIndex)} 승인 전에는 다음 단계가 열리지 않습니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'현장 자원 검증 중…':`계획 승인 · ${wfPhaseBadge(current,currentIndex)} 하달`}</button></footer></section><aside class="drawing-plan-aside"><section class="workflow-panel plan-map-panel"><header><div><h3>${workflowUI.planView==='drawing'?'관로 공사 도면':'현재 공정 작업 구간'}</h3><p>Zone ${esc(wfScenarioZoneId(design))} · ${wfPhaseBadge(current,currentIndex)} ${esc(current.title)}</p></div><div class="plan-view-toggle"><button class="${workflowUI.planView==='map'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="map">현장 3D</button><button class="${workflowUI.planView==='drawing'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="drawing">관로 도면</button></div></header>${workflowUI.planView==='drawing'?wfPipelineDrawing(design):wfMapFrame({controls:false,planning:true})}</section><section class="workflow-panel precheck"><h3>현재 공정 요약</h3>${[['Zone',`${wfScenarioZoneId(design)} · ${wfScenarioZoneTitle(design)}`],['공정 단계',`${wfPhaseBadge(current,currentIndex)} · ${current.title}`],['목표',`${num(current.target_amount)}${wfDesignUnit(current.target_unit)}`],['전체 순 작업시간',`${totalHours}h`]].map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>완료된 단계의 판정 기준은 현재 계획 화면에 반복 표시하지 않습니다.</p></section></aside></div></div>`;
}

function wfLegacySoilRelocationInstructionForm(d){
  const design={...d.design,plan_id:wfPlanLabel(d.design?.plan_id)};const phase=design.phases?.[0]||{};const move=design.relocation||{};
  const equipmentOk=(stageInventory?.equipment||[]).some(item=>item.active&&item.path===move.equipment_prim_path);
  const targetOk=(stageInventory?.diggable_targets||[]).some(item=>item.active&&item.path===move.source_prim_path);
  const ready=Boolean(stageInventory?.connected&&equipmentOk&&targetOk);
  const source=`(${num(move.source_position?.x)}m, ${num(move.source_position?.y)}m)`;const destination=`(${num(move.destination_position?.x)}m, ${num(move.destination_position?.y)}m)`;
  return `<div class="workflow-page drawing-plan-page"><div class="workflow-page-head"><div><h2>Zone B 토사 이동 계획</h2><p>Zone A 관로 공사와 독립적으로 실행할 수 있는 동측 토사 적치 위치 변경 작업입니다.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div><div class="drawing-plan-layout"><section class="workflow-panel structured-form"><div class="drawing-reference"><div><span>APPROVED WORK PLAN</span><b>${esc(design.plan_id)} · Rev.${esc(design.revision)}</b><small>${esc(design.title)} · ${esc(design.source_map)}</small></div><dl><div><dt>작업 구역</dt><dd>Zone B · 현장 동측</dd></div><div><dt>목표 이동량</dt><dd>${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)}</dd></div><div><dt>작업 장비</dt><dd>${esc(move.equipment_id||'EXC-004')}</dd></div><div><dt>예상 시간</dt><dd>${num(phase.estimated_hours)}h</dd></div></dl></div><div class="form-section"><h3>작업 방식</h3><p class="plan-summary">${esc(d.summary)}</p><div class="scenario-flow"><div class="scenario-phase ready"><span>1</span><div><b>기존 흙더미 굴착</b><small>${source} · ${move.scoop_count||5}회 분할</small></div><em>시작 위치</em></div><i class="scenario-arrow">→</i><div class="scenario-phase ready"><span>2</span><div><b>상부체 선회</b><small>궤도 고정 · ${num(move.swing_degrees||90)}° 선회</small></div><em>차체 이동 없음</em></div><i class="scenario-arrow">→</i><div class="scenario-phase ready"><span>3</span><div><b>지정 위치 적치</b><small>${destination}</small></div><em>반복 적치</em></div></div></div><div class="form-section"><div class="section-title-row"><div><h3>배정 장비·자원</h3><p>도면의 장비, 원토 Prim, 적치 좌표를 현장 Stage에서 확인합니다.</p></div><span>1개 Work Package</span></div><div class="workfront-list"><div class="workfront-row"><span class="zone-token zone-b">ZONE B</span><div><b>${esc(move.equipment_id||'EXC-004')}</b><small>굴착기 궤도 고정</small></div><div><b>${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)}</b><small>${esc(design.station_range)}</small></div><em class="${ready?'ready':'waiting'}">${ready?'실행 가능':'자원 대기'}</em></div></div></div>${wfPhaseCriteriaPanel([phase],d)}<input id="wfZone" type="hidden" value="Zone B"><input id="wfTask" type="hidden" value="토사 이동"><input id="wfTitle" type="hidden" value="${esc(d.title)}"><input id="wfTarget" type="hidden" value="${Number(d.target)||0}"><input id="wfUnit" type="hidden" value="${esc(d.unit)}"><input id="wfSegment" type="hidden" value="${esc(d.segment)}"><input id="wfEquipment" type="hidden" value="${esc(move.equipment_id||d.equipment)}"><input id="wfSuccessor" type="hidden" value="${esc(d.successor)}"><footer><span><b>독립 작업 하달</b> · Zone A와 병렬 실행할 수 있습니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'현장 자원 검증 중…':'계획 승인 · Zone B 하달'}</button></footer></section><aside class="drawing-plan-aside"><section class="workflow-panel plan-map-panel"><header><div><h3>${workflowUI.planView==='drawing'?'토사 이동 계획도':'현재 현장 위치'}</h3><p>Zone B · 동측 토사 적치 위치 변경</p></div><div class="plan-view-toggle"><button class="${workflowUI.planView==='map'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="map">현장 3D</button><button class="${workflowUI.planView==='drawing'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="drawing">이동 도면</button></div></header>${workflowUI.planView==='drawing'?wfSoilRelocationDrawing(design):wfMapFrame({controls:false,planning:true})}</section><section class="workflow-panel precheck"><h3>실행 전 확인</h3>${[['Zone','B · 독립 작업구역'],['장비',move.equipment_id||'EXC-004'],['궤도','고정'],['굴착·적치',`${move.scoop_count||5}회`]].map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>좌표가 맞지 않으면 첫 시연 전에 도면 좌표만 조정하면 됩니다.</p></section></aside></div></div>`;
}

function wfSoilRelocationInstructionForm(d){
  const design={...d.design,plan_id:wfPlanLabel(d.design?.plan_id)};
  const phase=design.phases?.[0]||{};
  const move=design.relocation||{};
  const equipmentOk=(stageInventory?.equipment||[]).some(item=>item.active&&item.path===move.equipment_prim_path);
  const targetOk=(stageInventory?.diggable_targets||[]).some(item=>item.active&&item.path===move.source_prim_path);
  const ready=Boolean(stageInventory?.connected&&equipmentOk&&targetOk);
  const source=`(${num(move.source_position?.x)}m, ${num(move.source_position?.y)}m)`;
  const destination=`(${num(move.destination_position?.x)}m, ${num(move.destination_position?.y)}m)`;
  const confirmation=design.location_confirmation_prompt||'표시된 원토와 적치 위치를 말씀하신 것이 맞습니까?';
  const checks=[
    ['후보 위치',confirmation],
    ['승인 후 Zone','새 Zone B 생성'],
    ['장비',move.equipment_id||'EXC-004'],
    ['굴착·적치',`${move.scoop_count||5}회`],
  ];
  return `<div class="workflow-page drawing-plan-page">
    <div class="workflow-page-head"><div><h2>토사 이동 후보 위치 확인</h2><p>자연어 지시와 현장 도면을 대조해 가장 가까운 작업 후보를 찾았습니다. 아래 위치가 맞는지 확인해 주세요.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div>
    <div class="drawing-plan-layout">
      <section class="workflow-panel structured-form">
        <div class="drawing-reference"><div><span>PROPOSED WORK AREA</span><b>${esc(design.plan_id)} · Rev.${esc(design.revision)}</b><small>${esc(design.title)} · ${esc(design.source_map)}</small></div><dl><div><dt>현재 상태</dt><dd>후보 위치 · Zone 미생성</dd></div><div><dt>목표 이동량</dt><dd>${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)}</dd></div><div><dt>작업 장비</dt><dd>${esc(move.equipment_id||'EXC-004')}</dd></div><div><dt>예상 시간</dt><dd>${num(phase.estimated_hours)}h</dd></div></dl></div>
        <div class="form-section"><div class="section-title-row"><div><h3>도면 위치 확인</h3><p>${esc(confirmation)}</p></div><span>관리자 확인 필요</span></div><p class="plan-summary">${esc(d.summary)}</p></div>
        <div class="form-section"><h3>승인 후 작업 방식</h3><div class="scenario-flow"><div class="scenario-phase ready"><span>1</span><div><b>기존 흙더미 굴착</b><small>${source} · ${move.scoop_count||5}회 분할</small></div><em>원토</em></div><i class="scenario-arrow">→</i><div class="scenario-phase ready"><span>2</span><div><b>상부체 선회</b><small>궤도 고정 · ${num(move.swing_degrees||90)}° 선회</small></div><em>차체 이동 없음</em></div><i class="scenario-arrow">→</i><div class="scenario-phase ready"><span>3</span><div><b>지정 위치 적치</b><small>${destination}</small></div><em>반복 적치</em></div></div></div>
        <div class="form-section"><div class="section-title-row"><div><h3>배정 장비·자원</h3><p>도면의 후보 흙더미, 장비, 적치 좌표가 현재 현장 자원과 일치하는지 확인합니다.</p></div><span>승인 시 1개 Work Package</span></div><div class="workfront-list"><div class="workfront-row"><span class="zone-token zone-b">후보 구역</span><div><b>${esc(move.equipment_id||'EXC-004')}</b><small>굴착기 궤도 고정</small></div><div><b>${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)}</b><small>${esc(design.station_range)}</small></div><em class="${ready?'ready':'waiting'}">${ready?'위치 확인 가능':'자원 대기'}</em></div></div></div>
        ${wfPhaseCriteriaPanel([phase],d)}
        <input id="wfZone" type="hidden" value="Zone B"><input id="wfTask" type="hidden" value="토사 이동"><input id="wfTitle" type="hidden" value="${esc(d.title)}"><input id="wfTarget" type="hidden" value="${Number(d.target)||0}"><input id="wfUnit" type="hidden" value="${esc(d.unit)}"><input id="wfSegment" type="hidden" value="${esc(d.segment)}"><input id="wfEquipment" type="hidden" value="${esc(move.equipment_id||d.equipment)}"><input id="wfSuccessor" type="hidden" value="${esc(d.successor)}">
        <footer><span><b>위치 확인 후 Zone 생성</b> · 승인 전에는 Zone B가 현장 맵과 작업 현황에 나타나지 않습니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'현장 자원 검증 중…':'위치 확인 · 작업 승인 · Zone B 생성'}</button></footer>
      </section>
      <aside class="drawing-plan-aside"><section class="workflow-panel plan-map-panel"><header><div><h3>${workflowUI.planView==='drawing'?'후보 토사 이동 계획도':'도면 후보 위치'}</h3><p>승인 전 · 아직 Zone이 생성되지 않은 위치 후보입니다.</p></div><div class="plan-view-toggle"><button class="${workflowUI.planView==='map'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="map">현장 3D</button><button class="${workflowUI.planView==='drawing'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="drawing">이동 도면</button></div></header>${workflowUI.planView==='drawing'?wfSoilRelocationDrawing(design):wfMapFrame({controls:false,planning:true})}</section><section class="workflow-panel precheck"><h3>승인 전 확인</h3>${checks.map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>위치가 다르면 대화로 돌아가 방향이나 현장 기준물을 추가로 설명해 주세요.</p></section></aside>
    </div>
  </div>`;
}

function wfDrawingInstructionForm(d,c){
  if(d?.design?.scenario_type==='soil_relocation')return wfSoilRelocationInstructionForm(d);
  if(wfCurrentPhaseId(d)!=='excavation')return wfSequentialPhaseInstructionForm(d);
  const design={...d.design,plan_id:wfPlanLabel(d.design?.plan_id)};const phases=design.phases||[];const fronts=design.workfronts||[];
  const currentPhaseIndex=Math.max(0,phases.findIndex(phase=>phase.id===wfCurrentPhaseId(d)));
  const knownEquipment=new Set((stageInventory?.equipment||[]).filter(item=>item.active).map(item=>item.path));
  const knownTargets=new Set((stageInventory?.diggable_targets||[]).filter(item=>item.active).map(item=>item.path));
  const flow=phases.map((phase,index)=>{const stateClass=index<currentPhaseIndex?'completed':index===currentPhaseIndex?'ready':'locked';const stateLabel=index<currentPhaseIndex?'승인 완료':index===currentPhaseIndex?'하달 대상':'선행 승인 후';return `<div class="scenario-phase ${stateClass}"><span>${wfPhaseStep(phase,index)}</span><div><b>${wfPhaseBadge(phase,index)} · ${esc(phase.title)}</b><small>Zone ${esc(wfScenarioZoneId(design))} · ${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)} · 약 ${phase.estimated_hours}h</small></div><em>${stateLabel}</em></div>${index<phases.length-1?'<i class="scenario-arrow">→</i>':''}`}).join('');
  const frontRows=fronts.map((front,index)=>{const equipmentOk=knownEquipment.has(front.equipment_prim_path);const targetsOk=(front.target_prim_paths||[]).every(path=>knownTargets.has(path));const ready=stageInventory?.connected&&equipmentOk&&targetsOk;return `<div class="workfront-row"><span class="zone-token zone-a">작업전선 F${index+1}</span><div><b>${esc(front.label)}</b><small>STA ${front.station_start_m} ~ ${front.station_end_m}m · ${num(front.target_volume_m3)}㎥</small></div><div><b>${esc(front.equipment_id)}</b><small>${front.target_prim_paths.length}개 굴착 Prim</small></div><em class="${ready?'ready':'waiting'}">${ready?'실행 가능':'자원 대기'}</em></div>`}).join('');
  const totalHours=phases.reduce((sum,phase)=>sum+Number(phase.estimated_hours||0),0).toFixed(1);
  return `<div class="workflow-page drawing-plan-page"><div class="workflow-page-head"><div><h2>도면 기반 작업 계획</h2><p>LLM이 승인 도면을 조회해 수량·장비·선후 공정을 구성했습니다. 아직 현장 작업 시스템에는 하달되지 않았습니다.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div><div class="drawing-plan-layout"><section class="workflow-panel structured-form"><div class="drawing-reference"><div><span>APPROVED DRAWING</span><b>${esc(design.plan_id)} · Rev.${esc(design.revision)}</b><small>${esc(design.title)} · ${esc(design.source_map)}</small></div><dl><div><dt>작업 구간</dt><dd>${esc(design.station_range)}</dd></div><div><dt>총 연장</dt><dd>${design.total_length_m}m</dd></div><div><dt>설계 깊이</dt><dd>${design.design_depth_m}m</dd></div><div><dt>관 외경</dt><dd>${design.pipe_diameter_m}m</dd></div></dl></div><div class="form-section"><h3>AI 작업 계획</h3><p class="plan-summary">${esc(d.summary)}</p><div class="scenario-flow">${flow}</div></div><div class="form-section"><div class="section-title-row"><div><h3>1단계 터파기 작업전선</h3><p>3대가 독립 구간을 작업하고 각각 Evidence Commit을 생성합니다.</p></div><span>${fronts.length}개 Work Package</span></div><div class="workfront-list">${frontRows}</div></div>${wfPhaseCriteriaPanel(phases)}<input id="wfZone" type="hidden" value="${esc(d.zone)}"><input id="wfTask" type="hidden" value="${esc(d.task)}"><input id="wfTitle" type="hidden" value="${esc(d.title)}"><input id="wfTarget" type="hidden" value="${d.target}"><input id="wfUnit" type="hidden" value="${esc(d.unit)}"><input id="wfSegment" type="hidden" value="${esc(d.segment)}"><input id="wfEquipment" type="hidden" value="${esc(d.equipment)}"><input id="wfSuccessor" type="hidden" value="${esc(d.successor)}"><footer><span><b>관리자 승인 시 1단계만 하달</b> · 관로 설치와 되메우기는 선행 Evidence 승인 전까지 잠깁니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'3개 작업전선 검증 중…':'계획 승인 · 터파기 3건 하달'}</button></footer></section><aside class="drawing-plan-aside"><section class="workflow-panel plan-map-panel"><header><div><h3>${workflowUI.planView==='drawing'?'관로 공사 도면':'도면 작업 예정 구간'}</h3><p>${workflowUI.planView==='drawing'?'중심선·STA·굴착 폭·대표 단면':'채움 토사 위의 관로 중심선과 3개 작업전선'}</p></div><div class="plan-view-toggle"><button class="${workflowUI.planView==='map'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="map">현장 3D</button><button class="${workflowUI.planView==='drawing'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="drawing">관로 도면</button></div></header>${workflowUI.planView==='drawing'?wfPipelineDrawing(design):wfMapFrame({controls:false,planning:true})}</section><section class="workflow-panel precheck"><h3>계획 요약</h3>${[['도면',`${design.plan_id} Rev.${design.revision}`],['총 공정','터파기 → 관로 설치 → 되메우기'],['예상 순 작업시간',`${totalHours}h`],['굴착 장비',`${fronts.length}대`]].map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>자원이 없는 작업전선도 삭제하지 않고 자원 대기 상태로 기록합니다.</p></section></aside></div></div>`;
}

function renderExecution(){const page=$('#page-execution');if(!page)return;const works=state.workPackages||[];const statusKinds=['active','review','warning','done'];page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 현황</h2><p>공사별 진행 단계와 승인 상태를 확인합니다.</p></div><button class="primary-button" data-page-link="workpackages">+ 새 작업 지시</button></div><div class="workflow-kpis compact">${['진행 중','검토 대기','보완 중','완료'].map((x,i)=>`<div><span>${x}</span><b>${works.filter(w=>wfStatus(w)[1]===statusKinds[i]).length}</b></div>`).join('')}</div><section class="workflow-panel workflow-table"><div class="workflow-table-head"><span>작업 / Zone</span><span>장비</span><span>진척도</span><span>상태</span><span>후속 영향</span></div>${works.map(w=>{const s=wfStatus(w);const progress=wfProgress(w);return `<button class="workflow-table-row" ${wfInstructionForWork(w)?`data-real-wp-detail="${esc(wfInstructionForWork(w).id)}"`:`data-review-open="${esc(w.id)}"`}><span><b>${esc(w.zone)} · ${esc(w.name)}</b><small>${esc(w.id)}</small></span><span>${esc(wfEquipmentLabel(w)||'-')}</span><span><i style="--p:${progress}%"></i>${progress}%</span><span><em class="${s[1]}">${s[0]}</em></span><span>${s[1]==='warning'?'후속 공정 잠김':'영향 없음'} ›</span></button>`}).join('')||wfBlank('작업 없음','작업 지시를 발행하면 여기에 표시됩니다.')}</section></div>`;}

renderEvidence=function(){const page=$('#page-evidence');const works=state.workPackages||[];if(workflowUI.reviewId){const w=works.find(x=>x.id===workflowUI.reviewId);if(w){page.innerHTML=wfReviewDetail(w);return;}workflowUI.reviewId=null;}page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>검토·승인</h2><p>작업 결과의 검토 대상과 우선순위를 확인하고 상세 검토로 이동합니다.</p></div><button class="ghost-button" data-workflow-action="refresh">↻ 새로고침</button></div><div class="review-layout"><section><div class="workflow-kpis compact">${[['검토 필요','review'],['보완 중','warning'],['재검증 대기','locked'],['승인 완료','done']].map(x=>`<div><span>${x[0]}</span><b>${works.filter(w=>wfStatus(w)[1]===x[1]).length}</b></div>`).join('')}</div><div class="workflow-panel review-list">${works.map(w=>{const s=wfStatus(w);return `<button data-review-open="${esc(w.id)}"><span><b>${esc(w.zone)} · ${esc(w.name)}</b><small>${esc(w.id)}</small></span><span>${wfProgress(w)}%</span><em class="${s[1]}">${s[0]}</em><span>${s[1]==='warning'?'후속 작업 LOCKED':'상세 보기'} →</span></button>`}).join('')}</div></section><aside class="workflow-panel review-priority"><h3>우선 검토 작업</h3>${works[0]?`<b>${esc(works[0].zone)} · ${esc(works[0].name)}</b><div><span>진척도</span><strong>${wfProgress(works[0])}%</strong></div><button class="primary-button" data-review-open="${esc(works[0].id)}">상세 검토로 이동 →</button>`:wfBlank('대상 없음','검토할 작업이 없습니다.')}</aside></div></div>`;};
const REVIEW_PHASES={
  excavation:{label:'굴착',image:'/static/assets/review/pipeline-excavation-demo.png',criterion:'굴착 저면 ±50mm',actual:'최대 편차 -82mm',segment:'14.2m ~ 17.6m',shortfall:'32mm 부족'},
  installation:{label:'관로 매설',image:'/static/assets/review/pipeline-installation-demo.png',criterion:'관 중심선 ±100mm',actual:'최대 편차 +136mm',segment:'22.0m ~ 24.5m',shortfall:'36mm 초과'},
  backfill:{label:'되메우기',image:'/static/assets/review/pipeline-backfill-demo.png',criterion:'층별 다짐도 90% 이상',actual:'최저 다짐도 87%',segment:'28.0m ~ 30.0m',shortfall:'3% 부족'}
};
function wfReviewDemoVisual(){const phase=REVIEW_PHASES[workflowUI.reviewPhase]||REVIEW_PHASES.excavation;return `<div class="review-phase-head"><div class="review-phase-tabs">${Object.entries(REVIEW_PHASES).map(([key,value])=>`<button class="${key===workflowUI.reviewPhase?'active':''}" data-review-phase="${key}">${value.label}</button>`).join('')}</div><span class="review-demo-badge">DEMO · 예상 시각자료</span></div><div class="review-diff-toolbar"><div class="profile-legend"><i class="design-shape"></i>설계 형상<i class="actual-shape"></i>실제 형상<i class="deep-diff"></i>차이(깊게 파임)<i class="shallow-diff"></i>차이(얕게 파임)</div><span>작업 범위</span></div><div class="review-diff-scene"><svg viewBox="0 0 1000 400" role="img" aria-label="${phase.label} 설계 형상과 실제 형상 차이 시연"><defs><pattern id="sceneGrid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#26343b" stroke-width="1"/></pattern><pattern id="meshWhite" width="19" height="15" patternUnits="userSpaceOnUse"><path d="M19 0H0V15M0 0L19 15" fill="none" stroke="#d6dfe2" stroke-opacity=".48" stroke-width="1"/></pattern><pattern id="meshGreen" width="18" height="13" patternUnits="userSpaceOnUse"><path d="M18 0H0V13M0 0L18 13" fill="none" stroke="#8dde91" stroke-opacity=".68" stroke-width="1"/></pattern><pattern id="meshRed" width="16" height="12" patternUnits="userSpaceOnUse"><path d="M16 0H0V12M0 0L16 12" fill="none" stroke="#ff8577" stroke-opacity=".75" stroke-width="1"/></pattern></defs><rect width="1000" height="400" fill="#071116"/><path d="M0 305L270 84H1000L1000 400H0Z" fill="url(#sceneGrid)" opacity=".72"/><polygon points="105,267 265,116 885,177 747,329" fill="#0b171c" stroke="#d4a928" stroke-width="3" stroke-dasharray="9 7"/><polygon points="135,254 279,137 848,189 721,305" fill="url(#meshWhite)" stroke="#aebbc0" stroke-opacity=".72" stroke-width="2"/><polygon points="192,251 320,158 658,190 562,278" fill="#295c39" fill-opacity=".72" stroke="#65ba72" stroke-width="2"/><polygon points="192,251 320,158 658,190 562,278" fill="url(#meshGreen)"/><polygon points="528,271 607,178 790,195 718,291" fill="#8d2020" fill-opacity=".88" stroke="#ef493d" stroke-width="3"/><polygon points="528,271 607,178 790,195 718,291" fill="url(#meshRed)"/><path d="M244 242L704 220" stroke="#72c779" stroke-width="5" opacity=".65"/><path d="M522 266L711 239" stroke="#ff4f45" stroke-width="5" opacity=".85"/><g class="scene-label"><rect x="34" y="116" width="92" height="35" rx="5"/><text x="52" y="139">Zone ${esc(String(workflowUI.reviewId||'C').slice(-1))}</text></g><g class="scene-alert"><path d="M680 80V172"/><rect x="590" y="38" width="180" height="57" rx="5"/><text x="617" y="62">문제 구간</text><text x="610" y="84">${phase.segment}</text></g><g class="scene-axis"><path d="M53 334v-42M53 334l34 12M53 334l-24 17"/><text x="50" y="282">Z</text><text x="93" y="352">X</text><text x="15" y="359">Y</text></g><g class="scene-scale"><text x="35" y="385">0m</text><text x="274" y="385">10m</text><text x="486" y="385">14.2m</text><text x="634" y="385">17.6m</text><text x="825" y="385">30m</text></g></svg><div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="review-profile-chart"><header><div><b>${phase.label} Level Profile</b><span>설계 기준과 예상 실측값의 차이를 동일 구간 축으로 비교</span></div><div class="profile-legend"><i class="design"></i>설계 Level<i class="actual"></i>실제 Level<i class="issue"></i>허용 범위</div></header><svg viewBox="0 0 900 190" role="img" aria-label="${phase.label} 공정 프로파일 차이 예시"><defs><linearGradient id="issueFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#c94c32" stop-opacity=".28"/><stop offset="1" stop-color="#c94c32" stop-opacity=".04"/></linearGradient></defs><g class="profile-grid"><path d="M55 35H870M55 70H870M55 105H870M55 140H870"/><path d="M55 20V155M220 20V155M385 20V155M550 20V155M715 20V155M870 20V155"/></g><rect x="55" y="70" width="815" height="45" class="tolerance-band"/><path class="design-line" d="M55 92H870"/><path class="actual-line" d="M55 87 C140 82 180 96 250 90 S360 86 420 92 C470 98 500 133 555 137 S640 112 700 94 S810 89 870 92"/><path class="issue-area" d="M420 92 C470 98 500 133 555 137 S640 112 700 94 L700 92 L420 92Z"/><line x1="420" y1="25" x2="420" y2="150" class="issue-edge"/><line x1="700" y1="25" x2="700" y2="150" class="issue-edge"/><text x="55" y="178">0m</text><text x="210" y="178">10m</text><text x="405" y="178">14.2m</text><text x="680" y="178">17.6m</text><text x="845" y="178">32m</text><text x="505" y="54" class="issue-label">문제 구간 ${phase.segment}</text></svg><div class="profile-metrics"><div><span>판정 기준</span><b>${phase.criterion}</b></div><div><span>예상 실측</span><b>${phase.actual}</b></div><div class="danger"><span>기준 차이</span><b>${phase.shortfall}</b></div></div></div>`;}
function wfReviewPhaseForWork(w){const zone=String(w?.zone||'').replace(/zone\s*/i,'').trim().toUpperCase();if(zone==='B')return {...REVIEW_PHASES.installation,image:'/static/assets/review/zone-b-pipe-installation-diff-v2.png',approvedImage:'/static/assets/review/zone-b-pipe-installation-approved-v2.png',zone};if(zone==='C'||zone==='D')return {...REVIEW_PHASES.backfill,image:'/static/assets/review/zone-c-backfill-diff-v2.png',approvedImage:'/static/assets/review/zone-c-backfill-approved-v2.png',zone};if(zone==='H')return {label:'반출·운반',image:'/static/assets/review/zone-h-haul-route-diff-v1.png',approvedImage:'/static/assets/review/zone-h-haul-route-diff-v1.png',criterion:'계획 반출량 700㎥ · 운반 종료 이벤트',actual:'누적 반출량 231㎥',segment:'현장 출구 연결 구간',shortfall:'469㎥ 잔여',zone};return {...REVIEW_PHASES.excavation,image:'/static/assets/review/zone-a-excavation-diff-v2.png',approvedImage:'/static/assets/review/zone-a-excavation-approved-v2.png',zone:zone||'A'};}
function wfReviewWorkVisual(w){const phase=wfReviewPhaseForWork(w);return `<div class="review-zone-head"><div><span>ZONE ${esc(phase.zone)}</span><b>${phase.label} 결과 비교</b><small>선택한 작업의 설계 형상과 결과 형상을 비교합니다.</small></div><span class="review-demo-badge">DEMO · 예상 시각자료</span></div><div class="review-diff-toolbar"><div class="profile-legend"><i class="design-shape"></i>설계 형상<i class="actual-shape"></i>실제 형상<i class="deep-diff"></i>기준 미달 영역<i class="shallow-diff"></i>작업 범위</div><span>Zone ${esc(phase.zone)} · ${phase.label}</span></div><div class="review-zone-visual"><img loading="lazy" decoding="async" src="${phase.image}" alt="Zone ${esc(phase.zone)} ${phase.label} 설계·결과 Diff 시연 이미지"><div class="review-zone-callout"><b>문제 구간</b><span>${phase.segment}</span></div><div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="review-profile-chart"><header><div><b>${phase.label} Level Profile</b><span>Zone ${esc(phase.zone)}의 설계 기준과 결과 값을 동일 구간 축으로 비교</span></div><div class="profile-legend"><i class="design"></i>설계 Level<i class="actual"></i>결과 Level<i class="issue"></i>허용 범위</div></header><svg viewBox="0 0 900 190" role="img" aria-label="Zone ${esc(phase.zone)} ${phase.label} 결과 프로파일"><defs><linearGradient id="issueFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#c94c32" stop-opacity=".28"/><stop offset="1" stop-color="#c94c32" stop-opacity=".04"/></linearGradient></defs><g class="profile-grid"><path d="M55 35H870M55 70H870M55 105H870M55 140H870"/><path d="M55 20V155M220 20V155M385 20V155M550 20V155M715 20V155M870 20V155"/></g><rect x="55" y="70" width="815" height="45" class="tolerance-band"/><path class="design-line" d="M55 92H870"/><path class="actual-line" d="M55 87 C140 82 180 96 250 90 S360 86 420 92 C470 98 500 133 555 137 S640 112 700 94 S810 89 870 92"/><path class="issue-area" d="M420 92 C470 98 500 133 555 137 S640 112 700 94 L700 92 L420 92Z"/><line x1="420" y1="25" x2="420" y2="150" class="issue-edge"/><line x1="700" y1="25" x2="700" y2="150" class="issue-edge"/><text x="55" y="178">0m</text><text x="210" y="178">10m</text><text x="405" y="178">14.2m</text><text x="680" y="178">17.6m</text><text x="845" y="178">32m</text><text x="505" y="54" class="issue-label">문제 구간 ${phase.segment}</text></svg><div class="profile-metrics"><div><span>판정 기준</span><b>${phase.criterion}</b></div><div><span>결과 값</span><b>${phase.actual}</b></div><div class="danger"><span>기준 차이</span><b>${phase.shortfall}</b></div></div></div>`;}
function wfReviewDetail(w){const e=state.evidence?.[w.id]||{};const c=wfCriteria(w);const progress=wfProgress(w);const phase=wfReviewPhaseForWork(w);return `<div class="workflow-page"><button class="workflow-back" data-review-back>← 검토 목록</button><div class="workflow-page-head"><div><h2>Zone ${esc(phase.zone)} · ${phase.label}</h2><p>${esc(w.id)} · ${esc(w.name)} 결과 상세 검토</p></div><span class="status-chip warning">검토 필요</span></div><div class="review-detail"><section><div class="workflow-kpis compact review-progress-summary"><div><span>진척도</span><b>${progress}%</b></div><div><span>보완 대상</span><b>${Math.max(0,100-progress)}%</b></div></div><div class="workflow-panel review-visual">${wfReviewWorkVisual(w)}</div></section><aside class="workflow-panel review-decision"><h3>판정 및 조치</h3><div class="decision-alert"><b>${e.conflicts?.[0]?.title||`${phase.label} 결과 확인 필요`}</b><span>${phase.criterion} · Evidence ${e.completeness||0}%</span></div><div class="decision-box"><span>다음 공정 영향</span><b>${(e.conflicts||[]).length?'시작 불가 · LOCKED':'판정 대기'}</b></div><h4>완료 기준</h4>${[['진척도',progress>=100],[phase.label+' 기준',!(e.conflicts||[]).length],['Evidence',Number(e.completeness||0)>=c.observation]].map(x=>`<div class="decision-rule"><i class="${x[1]?'pass':'fail'}">${x[1]?'✓':'×'}</i><span>${x[0]}</span><b>${x[1]?'PASS':'CHECK'}</b></div>`).join('')}<div class="decision-actions"><button class="ghost-button" data-workflow-action="request-evidence">추가 근거 요청</button><button class="primary-button" data-workflow-action="issue-correction">보완 작업 발행</button></div></aside></div></div>`;}

renderVersions=function(){const works=state.workPackages||[];const zones=[...new Set(works.map(w=>String(w.zone||'')).filter(Boolean))].sort();const visible=workflowUI.historyZone==='ALL'?works:works.filter(w=>String(w.zone)===workflowUI.historyZone);$('#page-versions').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 이력</h2><p>기준 작업과 보완 Work Package의 분기·재검증·승인 병합 흐름을 추적합니다.</p></div><label class="history-zone-filter">Zone<select data-history-zone><option value="ALL">전체 Zone</option>${zones.map(z=>`<option value="${esc(z)}" ${workflowUI.historyZone===z?'selected':''}>Zone ${esc(z)}</option>`).join('')}</select></label></div><div class="git-summary"><div><span>기준 작업</span><b>${visible.length}</b></div><div><span>보완 브랜치</span><b>${visible.filter(w=>w.status==='correction'||(state.evidence?.[w.id]?.conflicts||[]).length).length}</b></div><div><span>승인·병합</span><b>${visible.filter(w=>wfStatus(w)[1]==='done').length}</b></div></div><section class="workflow-panel git-history"><header><div><h3>Work Package Graph</h3><p>보완 작업은 원본 작업에서 분기되고 승인되면 기준 이력으로 병합됩니다.</p></div><span class="git-branch-label">main / Plan v1.0</span></header><div class="git-graph">${visible.map(w=>wfGitBranch(w)).join('')||wfBlank('표시할 이력 없음','다른 Zone을 선택하거나 작업을 발행해 주세요.')}</div></section></div>`;};
function wfGitBranch(w){const e=state.evidence?.[w.id]||{};const hasCorrection=w.status==='correction'||(e.conflicts||[]).length>0;const done=wfStatus(w)[1]==='done';const progress=wfProgress(w);return `<article class="git-lane ${hasCorrection?'has-branch':''}"><div class="git-rail"><i class="commit main"></i>${hasCorrection?'<i class="branch-line"></i>':''}</div><div class="git-commit"><div class="git-commit-head"><span class="git-hash">${esc(w.id)}</span><b>Zone ${esc(w.zone)} · ${esc(w.name)}</b><em>v${w.version||1}</em></div><p>작업 지시 발행 · 진척도 ${progress}%</p><small>main · ${esc(w.start||'계획')}</small></div>${hasCorrection?`<div class="git-correction"><div class="git-rail correction"><i class="commit warning"></i>${done?'<i class="merge-line"></i>':''}</div><div><div class="git-commit-head"><span class="git-hash">CORR-${esc(w.id.split('-').at(-1))}</span><b>보완 Work Package</b><em>branch</em></div><p>${esc(e.conflicts?.[0]?.title||'완료 기준 미충족 구간 보완')}</p><small>correction/zone-${esc(String(w.zone).toLowerCase())}</small></div></div>`:''}${done?`<div class="git-merge"><div class="git-rail"><i class="commit merged">✓</i></div><div><div class="git-commit-head"><span class="git-hash">MERGE</span><b>재검증 통과 · 관리자 승인</b><em>merged</em></div><p>보완 결과를 기준 작업 이력에 병합하고 다음 공정을 Release</p></div></div>`:''}</article>`;}

function wfEquipmentThumb(e){const image=EQUIPMENT_PHOTOS[e.model];return image?`<img loading="lazy" decoding="async" src="${image}" alt="${esc(e.manufacturer)} ${esc(e.model)}">`:`<span class="equipment-list-svg">${miniMachineSvg(e.icon,e.color)}</span>`;}
function wfEquipmentStatusLabel(status){return status==='available'?'사용 가능':status==='working'?'작업 중':status==='offline'?'오프라인':'대기';}
function wfFilteredEquipment(equipment){
  const query=workflowUI.equipmentQuery.trim().toLowerCase();
  return equipment.filter(item=>{
    const matchesType=workflowUI.equipmentType==='ALL'||item.type===workflowUI.equipmentType;
    const matchesStatus=workflowUI.equipmentStatus==='ALL'||item.status===workflowUI.equipmentStatus;
    const haystack=`${item.id||''} ${item.manufacturer||''} ${item.model||''} ${item.type||''} ${(item.supports||[]).join(' ')}`.toLowerCase();
    return matchesType&&matchesStatus&&(!query||haystack.includes(query));
  });
}
renderEquipment=function(){
  const equipment=state.equipment||[];
  const types=[...new Set(equipment.map(item=>item.type).filter(Boolean))].sort((left,right)=>left.localeCompare(right,'ko'));
  const filtered=wfFilteredEquipment(equipment);
  if(!workflowUI.equipmentId||!filtered.some(item=>item.id===workflowUI.equipmentId))workflowUI.equipmentId=filtered[0]?.id||null;
  const selected=equipment.find(item=>item.id===workflowUI.equipmentId);
  const available=equipment.filter(item=>item.status==='available').length;
  const activeFilterCount=Number(workflowUI.equipmentType!=='ALL')+Number(workflowUI.equipmentStatus!=='ALL')+Number(Boolean(workflowUI.equipmentQuery.trim()));
  const filterPanel=`<section class="equipment-filter-panel" aria-label="장비 목록 필터">
    <label><span>장비 유형</span><select data-equipment-filter="type"><option value="ALL">전체 유형</option>${types.map(type=>`<option value="${esc(type)}" ${workflowUI.equipmentType===type?'selected':''}>${esc(type)}</option>`).join('')}</select></label>
    <label><span>운영 상태</span><select data-equipment-filter="status"><option value="ALL">전체 상태</option>${[['available','사용 가능'],['working','작업 중'],['standby','대기'],['offline','오프라인']].map(([value,label])=>`<option value="${value}" ${workflowUI.equipmentStatus===value?'selected':''}>${label}</option>`).join('')}</select></label>
    <div class="equipment-filter-result"><span>검색 결과</span><b data-equipment-result-count>${filtered.length} / ${equipment.length}대</b></div>
    <button class="ghost-button button-sm" data-workflow-action="equipment-filter-reset" ${activeFilterCount?'':'disabled'}>필터 초기화</button>
  </section>`;
  const rows=filtered.map(item=>`<button class="${item.id===workflowUI.equipmentId?'active':''}" data-equipment-select="${esc(item.id)}" data-equipment-row>${wfEquipmentThumb(item)}<span><b>${esc(item.id)}</b><small>${esc(item.manufacturer)} ${esc(item.model)} · ${esc(item.type)}</small></span><em class="${esc(item.status)}">${wfEquipmentStatusLabel(item.status)}</em></button>`).join('');
  $('#page-equipment').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>장비 Registry</h2><p>현장에 등록된 장비의 제원, 작업 가능 범위와 운영 상태를 통합 관리합니다.</p></div><button class="primary-button" data-workflow-action="add-equipment">+ 장비 등록</button></div>${filterPanel}<div class="equipment-status-strip"><div><span>전체</span><b>${equipment.length}</b></div><div><span>사용 가능</span><b>${available}</b></div><div><span>작업 중</span><b>${equipment.filter(item=>item.status==='working').length}</b></div><div><span>오프라인</span><b>${equipment.filter(item=>item.status==='offline').length}</b></div></div><div class="equipment-master-detail"><section class="workflow-panel equipment-list-panel"><div class="equipment-search">⌕ <input placeholder="장비 ID / 모델 / 유형 검색" value="${esc(workflowUI.equipmentQuery)}" data-equipment-search></div><div class="equipment-list">${rows}<div class="equipment-filter-empty" data-equipment-live-empty ${rows?'hidden':''}><b>조건에 맞는 장비가 없습니다.</b><span>검색어나 필터 조건을 변경해 주세요.</span><button class="text-button" data-workflow-action="equipment-filter-reset">전체 장비 보기</button></div></div></section>${selected?wfEquipmentDetail(selected):`<section class="workflow-panel">${wfBlank('선택 가능한 장비 없음','필터 조건을 초기화하거나 장비를 등록해 주세요.')}</section>`}</div></div>`;
};
function wfEquipmentDetail(e){const image=EQUIPMENT_PHOTOS[e.model];return `<section class="workflow-panel equipment-detail"><div class="equipment-detail-head"><div><h2>${esc(e.id)}</h2><p>${esc(e.manufacturer)} · ${esc(e.model)} · ${esc(e.type)}</p></div><span class="equipment-state ${esc(e.status)}">${e.status==='available'?'사용 가능':e.status==='working'?'작업 중':e.status==='offline'?'오프라인':'대기'}</span></div><div class="equipment-detail-grid"><div class="equipment-profile">${image?`<img decoding="async" src="${image}" alt="${esc(e.manufacturer)} ${esc(e.model)}">`:machineSvg(e.icon,e.color)}<dl><div><dt>운전 중량</dt><dd>${num(e.operatingWeight)} t</dd></div><div><dt>표준 버킷</dt><dd>${num(e.bucketCapacity)} ㎥</dd></div><div><dt>작업 버킷</dt><dd>${num(e.workBucket)} ㎥</dd></div><div><dt>엔진 출력</dt><dd>${num(e.power)} kW</dd></div><div><dt>최대 굴착 깊이</dt><dd>${num(e.maxDepth)} m</dd></div><div><dt>주행 속도</dt><dd>${num(e.travelSpeed)} km/h</dd></div></dl>${e.sourceUrl?`<a class="ghost-button" href="${esc(e.sourceUrl)}" target="_blank" rel="noreferrer">제조사 제원 보기</a>`:''}<button class="ghost-button" data-workflow-action="edit-equipment">장비 수정</button></div><div class="equipment-operations"><h3>현장 운용 정보</h3><div><span>작업 가능 범위</span><p>${(e.supports||[]).map(x=>`<b>${esc(x)}</b>`).join('')}</p></div><div><span>배정 구역</span><p><b>${esc(e.assigned||'미배정')}</b></p></div><div><span>작업전선</span><p><b>${esc(e.workfrontId||'미배정')}</b></p></div><div><span>수집 가능한 작업 근거</span><p>${(e.evidence||[]).map(x=>`<b>✓ ${esc(x)}</b>`).join('')}</p></div><div><span>장비 상태</span><p><b>${e.status==='offline'?'점검 필요':'운용 가능'}</b> · 제조사 제원 등록</p></div></div></div></section>`;}

renderSettings=function(){const p=state.project;const tab=workflowUI.settingsTab;$('#page-settings').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>설정</h2><p>작업 기준, 프로젝트 정보와 데이터 연결을 통합 관리합니다.</p></div></div><div class="settings-tabs">${[['criteria','작업 기준'],['project','프로젝트 설정'],['integration','데이터 연동']].map(x=>`<button class="${tab===x[0]?'active':''}" data-settings-tab="${x[0]}">${x[1]}</button>`).join('')}</div>${tab==='criteria'?wfSettingsCriteria():tab==='project'?`<section class="workflow-panel settings-content"><h3>프로젝트 설정</h3><div class="settings-summary"><div><span>프로젝트명</span><b>${esc(p.name)}</b></div><div><span>현장 위치</span><b>${esc(p.location)}</b></div><div><span>Plan</span><b>v1.0</b></div><div><span>좌표 기준</span><b>${esc(p.coordinateSystem)}</b></div></div><button class="ghost-button" data-workflow-action="open-project">기본정보 수정</button></section>`:`<section class="workflow-panel settings-content"><h3>데이터 연동</h3><div class="integration-grid"><div><b>현장 작업 시스템</b><span>${stageInventory?.connected?'연결됨':'미연동'}</span><small>작업·센서 결과 데이터</small></div><div><b>Shared Database</b><span>${remoteReady?'정상':'확인 필요'}</span><small>프로젝트 공동 데이터</small></div><div><b>장비 Gateway</b><span>검증 환경</span><small>실제 장비 API 연결 전</small></div></div><p class="settings-note">현장 시스템 미연동 상태를 임의 데이터로 대체하지 않습니다.</p></section>`}</div>`;};
function wfSettingsCriteria(){
  const c=wfCriteria(state.workPackages[0]);
  const phases=wfScenarioPhases();
  const phaseCards=phases.map((phase,index)=>{
    const criteria=phase.acceptance_criteria||[];
    return `<article class="criteria-phase-card ${wfPhaseCss(phase,index)}"><header><span>${wfPhaseBadge(phase,index)}</span><div><h4>${esc(phase.title)}</h4><p>${esc(phase.description||'')}</p></div><em>${criteria.length}개 기준</em></header><ol>${criteria.map((criterion,criterionIndex)=>`<li><i>${criterionIndex+1}</i><span>${esc(criterion)}</span></li>`).join('')}</ol><footer><span>Conflict 판정</span><b>기준 1건 이상 미충족 시 검토 필요</b></footer></article>`;
  }).join('');
  return `<section class="workflow-panel settings-content criteria-settings-content"><div class="criteria-settings-head"><div><h3>관로 공사 전체 완료·승인 판정 기준</h3><p>하나의 Zone 안에서 터파기 → 관로 설치 → 되메우기 공정별 기준을 적용하고, 각 공정의 Evidence 승인 후 다음 공정을 엽니다.</p></div><span>${esc(c.name)} · 현재 적용 중</span></div><div class="criteria-common-gate"><div><span>공정 완료 진척도</span><b>${c.completion}%</b></div><div><span>Evidence 완전성</span><b>${c.observation}% 이상</b></div><div><span>공통 Conflict 규칙</span><b>공정 기준 미충족 또는 필수 Evidence 누락</b></div></div><div class="criteria-phase-grid">${phaseCards}</div><div class="criteria-release-rule"><div><span>공정 승인 흐름</span><b>터파기 승인 → 관로 설치 승인 → 되메우기 승인 → 관로 공사 완료</b></div><p>기준 미충족 시 해당 공정은 Conflict·검토 필요 상태가 되며, 보완 Work Package와 재검증 Commit을 거쳐야 다음 공정으로 진행할 수 있습니다.</p></div></section>`;
}

function wfDraftFromText(text){const zone=(text.match(/zone\s*([a-z])/i)||text.match(/([A-D])\s*(?:구역|존)/i)||[])[1]||'A';const nums=[...text.matchAll(/(\d+(?:\.\d+)?)\s*(m³|㎥|m|미터)/gi)];const target=Number(nums.at(-1)?.[1]||20);const seg=text.match(/(\d+(?:\.\d+)?)\s*m?\s*[~～-]\s*(\d+(?:\.\d+)?)\s*m/i);return {zone:`Zone ${String(zone).toUpperCase()}`,task:text.includes('굴착')?'굴착':text.includes('정지')?'정지':'관로 터파기',title:`Zone ${String(zone).toUpperCase()} · ${text.includes('굴착')?'굴착':'관로 터파기'}`,target,unit:nums.at(-1)?.[2]?.includes('³')||nums.at(-1)?.[2]==='㎥'?'㎥':'m',segment:seg?`${seg[1]}m ~ ${seg[2]}m`:'관리자 확인 필요',equipment:'EXC-001',successor:'관로 설치'};}
function wfReadInstructionForm(){
  const draft=workflowUI.draft||{};
  return {
    sourceText:draft.sourceText||draft.summary||draft.title||'',
    zone:$('#wfZone')?.value.trim()||draft.zone||'',task:$('#wfTask')?.value.trim()||draft.task||'',
    title:$('#wfTitle')?.value.trim()||draft.title||'',target:Number($('#wfTarget')?.value)||0,
    unit:$('#wfUnit')?.value.trim()||draft.unit||'',segment:$('#wfSegment')?.value.trim()||draft.segment||'',
    equipment:$('#wfEquipment')?.value.trim()||draft.equipment||'',successor:$('#wfSuccessor')?.value.trim()||draft.successor||'',
    toleranceMm:Number($('#wfTolerance')?.value)||0,completionThreshold:Number($('#wfCompletion')?.value)||100,
    observationThreshold:Number($('#wfObservation')?.value)||100,
  };
}
function wfExecutionInstruction(display){
  const confirmed=[
    `관리자 확정 작업: ${display.title}`,
    `작업 구역: ${display.zone}`,
    `공종: ${display.task}`,
    `작업 구간: ${display.segment}`,
    `목표 작업량: ${display.target}${display.unit}`,
    display.equipment&&!/관리자.*필요/.test(display.equipment)?`사용 장비: ${display.equipment}`:'',
  ].filter(Boolean).join('\n');
  return `${display.sourceText}\n\n${confirmed}`.trim().slice(0,1500);
}
async function publishDrawingScenario(){
  if(workflowUI.publishing||!workflowUI.draft?.design)return;
  const draft=workflowUI.draft;const design=draft.design;
  workflowUI.publishing=true;renderWorkPackages();
  try{
    const response=await apiFetch('/work-packages/ai/planning/dispatch',{method:'POST',body:JSON.stringify({project_id:PROJECT_ID,source_text:draft.sourceText,plan_id:design.plan_id,phase_id:wfCurrentPhaseId(draft)})});
    const payload=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(payload.detail?.message||payload.detail||`SCENARIO_${response.status}`);
    const pending=(payload.work_packages||[]).filter(item=>item.status==='pending').length;
    const blocked=(payload.work_packages||[]).filter(item=>item.status==='blocked').length;
    const phaseId=wfCurrentPhaseId(draft);
    const phase=(design.phases||[]).find(item=>item.id===phaseId);
    const excavation=(payload.work_packages||[]).filter(item=>item.phase_id==='excavation').length;
    const installation=(payload.work_packages||[]).filter(item=>item.phase_id==='pipe_installation').length;
    workflowUI.messages.push({role:'assistant',text:phaseId==='excavation'
      ?`도면 ${design.plan_id}의 Zone ${wfScenarioZoneId(design)} 관로 공사 1건을 등록했습니다. 1단계 터파기 ${excavation}건만 실행하며 2단계 관로 설치 ${installation}건은 Evidence 승인과 별도 계획 승인 전까지 잠깁니다.`
      :`Zone ${phase?.zone_id||'-'} ${phase?.title||phaseId} 계획을 승인했습니다. 현재 공정 ${pending}건을 작업 실행 대기열로 하달했습니다.`});
    workflowUI.mode='compose';workflowUI.draft=null;setIsaacPlanningOverlay(null);
    await loadIsaacInstructions();navigate('execution');
    toast(phaseId==='excavation'?'관로 공사 계획 등록 완료':`Zone ${phase?.zone_id||'-'} ${phase?.title||''} 계획 승인 완료`,`작업 실행 ${pending}건 · 선행 승인 대기 ${blocked}건`,pending?'success':'warning');
  }catch(error){toast('관로 계획 하달 실패',String(error.message||error),'danger');}
  finally{workflowUI.publishing=false;if(workflowUI.mode==='form')renderWorkPackages();}
}
async function publishWorkflowInstruction(){
  if(workflowUI.publishing||!workflowUI.draft)return;
  if(workflowUI.draft.design){await publishDrawingScenario();return;}
  const display=wfReadInstructionForm();
  const message=wfExecutionInstruction(display);
  workflowUI.publishing=true;
  renderWorkPackages();
  try{
    const response=await apiFetch('/work-packages/ai/code/interpret',{
      method:'POST',body:JSON.stringify({project_id:PROJECT_ID,message}),
    });
    const codeDraft=await response.json().catch(()=>({}));
    if(!response.ok)throw new Error(codeDraft.detail?.message||codeDraft.detail||`AI_CODE_${response.status}`);
    if(!codeDraft.plan?.ready)throw new Error(codeDraft.plan?.clarification_question||'현장 작업에 필요한 작업 정보가 부족합니다.');
    const data=await submitCodeWorkPackageDraft(codeDraft,display);
    const record=data.work_package;
    workflowUI.messages.push({role:'assistant',text:`${record.summary} 작업이 ${record.status==='blocked'?'자원 대기 상태로 저장':'작업 실행 대기열에 전송'}되었습니다.`});
    workflowUI.mode='compose';
    workflowUI.draft=null;
    navigate('execution');
    toast(record.status==='blocked'?'Work Package 자원 대기':'현장 작업 전송 완료',record.status==='blocked'?(record.missing_resources||[]).join(' · '):'현장 작업 실행 대기열에 등록했습니다.',record.status==='blocked'?'warning':'success');
  }catch(error){
    toast('작업 발행 실패',String(error.message||error),'danger');
  }finally{
    workflowUI.publishing=false;
    if(workflowUI.mode==='form')renderWorkPackages();
  }
}
document.addEventListener('submit',async e=>{if(e.target.id!=='workflowPrompt')return;e.preventDefault();const input=$('#workflowPromptText');const text=input.value.trim();if(!text)return;const submit=e.target.querySelector('button[type="submit"]');submit.disabled=true;submit.textContent='도면·계획 해석 중…';workflowUI.messages.push({role:'user',text});try{const response=await apiFetch('/work-packages/ai/planning/interpret',{method:'POST',body:JSON.stringify({project_id:PROJECT_ID,message:text})});const payload=await response.json();if(!response.ok)throw new Error(payload?.detail?.message||'작업지시 해석에 실패했습니다.');const p=payload.plan;if(!p.ready){workflowUI.messages.push({role:'assistant',text:p.clarification_question||'작업 구역과 목표량을 조금 더 구체적으로 알려주세요.'});renderWorkPackages();return;}workflowUI.messages.push({role:'assistant',text:p.summary});workflowUI.draft={sourceText:payload.source_text||text,summary:p.summary,zone:payload.design?.work_area_label||`Zone ${p.zone_id}`,task:p.work_type,title:p.title,target:p.target_amount,unit:p.target_unit==='m3'?'㎥':p.target_unit==='ea'?'대':'m',segment:p.segment,equipment:p.equipment_hint,successor:p.successor_title,design:payload.design||null};workflowUI.planView=payload.design?'drawing':'map';setIsaacPlanningOverlay(payload.design||null);workflowUI.mode='form';renderWorkPackages();}catch(error){workflowUI.messages.push({role:'assistant',text:`LLM에 연결하지 못했습니다. ${error.message}`});renderWorkPackages();toast('작업지시 초안 생성 실패',error.message,'warning');}finally{if(submit?.isConnected){submit.disabled=false;submit.textContent='초안 만들기';}}});
document.addEventListener('input',e=>{
  if(!e.target.matches('[data-equipment-search]'))return;
  workflowUI.equipmentQuery=e.target.value;
  const query=workflowUI.equipmentQuery.trim().toLowerCase();
  let visible=0;
  $$('[data-equipment-row]').forEach(row=>{const show=!query||row.textContent.toLowerCase().includes(query);row.classList.toggle('hidden',!show);if(show)visible+=1;});
  const counter=$('[data-equipment-result-count]');
  if(counter)counter.textContent=`${visible} / ${(state.equipment||[]).length}대`;
  const empty=$('[data-equipment-live-empty]');
  if(empty)empty.hidden=visible>0;
});
document.addEventListener('change',e=>{
  if(e.target.matches('[data-equipment-filter="type"]')){workflowUI.equipmentType=e.target.value;renderEquipment();return;}
  if(e.target.matches('[data-equipment-filter="status"]')){workflowUI.equipmentStatus=e.target.value;renderEquipment();return;}
  if(!e.target.matches('[data-history-zone]'))return;
  workflowUI.historyZone=e.target.value;
  renderVersions();
});
document.addEventListener('click',e=>{const phase=e.target.closest('[data-review-phase]');if(!phase)return;workflowUI.reviewPhase=phase.dataset.reviewPhase;renderEvidence();});
document.addEventListener('click',async e=>{
  const scenarioRun=e.target.closest('[data-open-scenario-run]');
  if(scenarioRun){workflowUI.scenarioRunId=scenarioRun.dataset.openScenarioRun||null;renderExecution();window.scrollTo({top:0,behavior:'smooth'});return;}
  if(e.target.closest('[data-scenario-back]')){workflowUI.scenarioRunId=null;renderExecution();window.scrollTo({top:0,behavior:'smooth'});return;}
  const scenarioPhase=e.target.closest('[data-open-scenario-phase]');
  if(scenarioPhase){
    const opened=wfOpenReadyScenarioPhasePlan(scenarioPhase.dataset.openScenarioPhase||'');
    if(!opened)toast('다음 공정 계획을 열 수 없습니다.','선행 공정 Evidence 승인 상태와 도면 연결을 새로고침해 주세요.','warning');
    return;
  }
  const equipment=e.target.closest('[data-equipment-select]');
  if(equipment){workflowUI.equipmentId=equipment.dataset.equipmentSelect;renderEquipment();return;}
  const review=e.target.closest('[data-review-open]');
  if(review){workflowUI.reviewId=review.dataset.reviewOpen;state.selectedWpId=workflowUI.reviewId;if(state.selectedPage!=='evidence')navigate('evidence');renderEvidence();window.scrollTo({top:0,behavior:'smooth'});return;}
  if(e.target.closest('[data-review-back]')){workflowUI.reviewId=null;renderEvidence();window.scrollTo({top:0,behavior:'smooth'});return;}
  const tab=e.target.closest('[data-settings-tab]');
  if(tab){workflowUI.settingsTab=tab.dataset.settingsTab;renderSettings();return;}
  const action=e.target.closest('[data-workflow-action]')?.dataset.workflowAction;
  if(!action)return;
  if(action==='set-plan-view'){workflowUI.planView=e.target.closest('[data-plan-view]')?.dataset.planView==='map'?'map':'drawing';renderWorkPackages();return;}
  if(action==='reset-chat'){workflowUI.mode='compose';workflowUI.draft=null;workflowUI.publishing=false;workflowUI.messages=workflowUI.messages.slice(0,1);setIsaacPlanningOverlay(null);renderWorkPackages();}
  if(action==='back-chat'){workflowUI.mode='compose';workflowUI.publishing=false;setIsaacPlanningOverlay(null);renderWorkPackages();}
  if(action==='refresh'){await Promise.all([loadStageInventory(),loadIsaacInstructions()]);renderEvidence();}
  if(action==='open-project')openProjectModal();
  if(action==='add-equipment')openEquipmentModal(null);
  if(action==='edit-equipment')openEquipmentModal(workflowUI.equipmentId);
  if(action==='equipment-filter-reset'){workflowUI.equipmentQuery='';workflowUI.equipmentType='ALL';workflowUI.equipmentStatus='ALL';renderEquipment();}
  if(action==='request-evidence'){state.selectedWpId=workflowUI.reviewId;addEvidence();}
  if(action==='issue-correction'){state.selectedWpId=workflowUI.reviewId;createCorrection();}
  if(action==='publish-instruction')await publishWorkflowInstruction();
});

function wfZoneProfile(phase,approved){const zone=phase.zone;if(zone==='B')return approved?{design:'M55 72 C250 78 500 96 870 112',actual:'M55 75 C250 80 500 92 870 109',start:430,end:650,value:'중심선 편차 +32mm'}:{design:'M55 72 C250 78 500 96 870 112',actual:'M55 75 C250 80 420 91 C500 142 580 137 650 102 C730 102 800 108 870 113',start:420,end:650,value:'중심선 편차 +136mm'};if(zone==='C'||zone==='D')return approved?{design:'M55 86 C260 84 520 90 870 87',actual:'M55 90 C260 87 520 94 870 90',start:470,end:690,value:'최저 다짐도 94%'}:{design:'M55 86 C260 84 520 90 870 87',actual:'M55 90 C280 86 430 92 480 101 C540 138 630 132 690 96 C760 89 820 91 870 90',start:470,end:690,value:'최저 다짐도 87%'};return approved?{design:'M55 92H870',actual:'M55 88 C190 83 310 97 430 89 S680 96 870 90',start:420,end:700,value:'최대 편차 +18mm'}:{design:'M55 92H870',actual:'M55 87 C140 82 180 96 250 90 S360 86 420 92 C470 98 500 133 555 137 S640 112 700 94 S810 89 870 92',start:420,end:700,value:'최대 편차 -82mm'};}
wfReviewWorkVisual=function(w){const phase=wfReviewPhaseForWork(w);const approved=wfStatus(w)[1]==='done';const profile=wfZoneProfile(phase,approved);const image=approved?phase.approvedImage:phase.image;const statusText=approved?'기준 충족 · 승인 완료':'기준 미달 영역';return `<div class="review-zone-head"><div><span>ZONE ${esc(phase.zone)}</span><b>${phase.label} 결과 비교</b><small>선택한 작업의 설계 형상과 결과 형상을 비교합니다.</small></div><span class="review-result-badge ${approved?'approved':'warning'}">${statusText}</span></div><div class="review-diff-toolbar"><div class="profile-legend"><i class="design-shape"></i>설계 형상<i class="actual-shape"></i>결과 형상${approved?'':`<i class="deep-diff"></i>기준 미달 영역`}<i class="shallow-diff"></i>작업 범위</div><span>Zone ${esc(phase.zone)} · ${phase.label}</span></div><div class="review-zone-visual ${approved?'approved':''}"><img loading="lazy" decoding="async" src="${image}" alt="Zone ${esc(phase.zone)} ${phase.label} 설계·결과 비교 이미지">${approved?'<div class="review-approved-callout"><b>기준 충족</b><span>검토·승인 완료</span></div>':`<div class="review-zone-callout"><b>문제 구간</b><span>${phase.segment}</span></div>`}<div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="review-profile-chart"><header><div><b>${phase.label} ${zoneProfileLabel(phase.zone)}</b><span>Zone ${esc(phase.zone)}의 설계 기준과 결과 값을 동일 구간 축으로 비교</span></div><div class="profile-legend"><i class="design"></i>설계 기준<i class="actual"></i>결과 값${approved?'':`<i class="issue"></i>허용 범위`}</div></header><svg viewBox="0 0 900 190" role="img" aria-label="Zone ${esc(phase.zone)} ${phase.label} 결과 프로파일"><g class="profile-grid"><path d="M55 35H870M55 70H870M55 105H870M55 140H870"/><path d="M55 20V155M220 20V155M385 20V155M550 20V155M715 20V155M870 20V155"/></g><rect x="55" y="70" width="815" height="45" class="tolerance-band"/><path class="design-line" d="${profile.design}"/><path class="actual-line" d="${profile.actual}"/>${approved?'':`<rect x="${profile.start}" y="25" width="${profile.end-profile.start}" height="125" class="profile-issue-zone"/><line x1="${profile.start}" y1="25" x2="${profile.start}" y2="150" class="issue-edge"/><line x1="${profile.end}" y1="25" x2="${profile.end}" y2="150" class="issue-edge"/><text x="${profile.start+28}" y="54" class="issue-label">문제 구간 ${phase.segment}</text>`}<text x="55" y="178">0m</text><text x="210" y="178">10m</text><text x="405" y="178">14.2m</text><text x="680" y="178">17.6m</text><text x="845" y="178">32m</text></svg><div class="profile-metrics"><div><span>판정 기준</span><b>${phase.criterion}</b></div><div><span>결과 값</span><b>${profile.value}</b></div><div class="${approved?'pass':'danger'}"><span>판정</span><b>${approved?'PASS · 기준 충족':phase.shortfall}</b></div></div></div>`;};
function zoneProfileLabel(zone){return zone==='B'?'Alignment Profile':zone==='C'||zone==='D'?'Compaction Profile':'Level Profile';}
wfReviewDetail=function(w){const e=state.evidence?.[w.id]||{};const c=wfCriteria(w);const progress=wfProgress(w);const phase=wfReviewPhaseForWork(w);const approved=wfStatus(w)[1]==='done';return `<div class="workflow-page"><button class="workflow-back" data-review-back>← 검토 목록</button><div class="workflow-page-head"><div><h2>Zone ${esc(phase.zone)} · ${phase.label}</h2><p>${esc(w.id)} · ${esc(w.name)} 결과 상세 검토</p></div><span class="status-chip ${approved?'accepted':'warning'}">${approved?'승인 완료':'검토 필요'}</span></div><div class="review-detail"><section><div class="workflow-kpis compact review-progress-summary"><div><span>진척도</span><b>${progress}%</b></div><div><span>${approved?'판정 결과':'보완 대상'}</span><b>${approved?'PASS':Math.max(0,100-progress)+'%'}</b></div></div><div class="workflow-panel review-visual">${wfReviewWorkVisual(w)}</div></section><aside class="workflow-panel review-decision"><h3>판정 및 조치</h3><div class="decision-alert ${approved?'approved':''}"><b>${approved?`${phase.label} 기준 충족`:e.conflicts?.[0]?.title||`${phase.label} 결과 확인 필요`}</b><span>${phase.criterion} · Evidence ${e.completeness||0}%</span></div><div class="decision-box"><span>다음 공정 영향</span><b>${approved?'시작 가능 · READY':(e.conflicts||[]).length?'시작 불가 · LOCKED':'판정 대기'}</b></div><h4>완료 기준</h4>${[['진척도',approved||progress>=100],[phase.label+' 기준',approved||!(e.conflicts||[]).length],['Evidence',approved||Number(e.completeness||0)>=c.observation]].map(x=>`<div class="decision-rule"><i class="${x[1]?'pass':'fail'}">${x[1]?'✓':'×'}</i><span>${x[0]}</span><b>${x[1]?'PASS':'CHECK'}</b></div>`).join('')}${approved?'<div class="review-release-note"><b>승인된 결과입니다.</b><span>보완 대상과 문제 구간이 없으며 다음 공정을 시작할 수 있습니다.</span></div>':`<div class="decision-actions"><button class="ghost-button" data-workflow-action="request-evidence">추가 근거 요청</button><button class="primary-button" data-workflow-action="issue-correction">보완 작업 발행</button></div>`}</aside></div></div>`;};

renderDashboard=function(){const all=state.workPackages||[];const works=all.filter(w=>['A','B','C','D'].includes(String(w.zone||'').toUpperCase()));const totalWeight=works.reduce((sum,w)=>sum+Math.max(1,Number(w.target)||1),0);const overall=Math.round(works.reduce((sum,w)=>sum+Math.max(1,Number(w.target)||1)*wfProgress(w),0)/Math.max(1,totalWeight));const active=works.filter(w=>!['accepted','done'].includes(w.status)).length;const review=works.filter(w=>wfStatus(w)[1]==='review').length;const correction=works.filter(w=>wfStatus(w)[1]==='warning').length;const dateLabel=new Intl.DateTimeFormat('ko-KR',{month:'2-digit',day:'2-digit'}).format(new Date());$('#page-dashboard').innerHTML=`<div class="workflow-page"><div class="workflow-kpis"><button data-page-link="execution"><span>오늘 작업</span><b>${active}</b><small>지속 관리 필요</small></button><button data-page-link="evidence"><span>검토 대기</span><b>${review}</b><small>검토·승인 필요</small></button><button data-page-link="evidence"><span>보완 필요</span><b>${correction}</b><small>즉시 확인 필요</small></button><button data-page-link="execution"><span>완료 Zone</span><b>${works.filter(w=>wfStatus(w)[1]==='done').length}</b><small>오늘 승인 완료</small></button></div><div class="workflow-dashboard-grid"><section class="workflow-panel map-panel"><header><div><h2>현장 맵 <small>Site Work Map</small></h2><p>오늘 작업 위치와 문제 Zone을 한눈에 확인합니다.</p></div><span class="workflow-live">${stageInventory?.connected?'LIVE':'OFFLINE'}</span></header>${wfMapFrame()}</section><aside class="workflow-panel action-panel daily-progress-panel"><header><div><h2>오늘 작업 진척도</h2><p>${dateLabel} · 일일 작업계획 기준</p></div><b class="daily-overall-value">${overall}%</b></header><div class="daily-overall"><div><span>전체 진척도</span><b>${overall}%</b></div><i style="--p:${overall}%"></i><small>Zone별 목표 작업량을 반영한 가중 진척도</small></div><div class="daily-zone-list">${works.map(w=>wfDailyZoneRow(w)).join('')||wfBlank('오늘 작업 없음','작업 지시에서 오늘 작업을 등록해 주세요.')}</div></aside></div></div>`;};
function wfDailyState(w){const status=wfStatus(w);if(status[1]==='done')return ['승인 완료','done'];if(status[1]==='warning')return [status[0],'warning'];if(status[1]==='review')return ['검토 대기','review'];if(status[1]==='active')return ['작업 중','active'];return [status[0],'locked'];}
function wfDailyZoneRow(w){const progress=wfProgress(w);const status=wfDailyState(w);const targetPage=['review','warning','done'].includes(status[1])?'evidence':'execution';return `<button class="daily-zone-row ${status[1]}" data-page-link="${targetPage}"><div class="daily-zone-title"><span>Zone ${esc(w.zone)}</span><div><b>${esc(w.name)}</b><small>${status[0]} · ${esc(w.id)}</small></div><strong>${progress}%</strong></div><div class="daily-zone-progress"><i style="--p:${progress}%"></i></div></button>`;}

function wfZoneDisplayName(w){const zone=String(w?.zone||'').toUpperCase();if(zone==='A')return '관로 터파기 — 전체 구간';if(zone==='B')return '관로 설치 — 전체 구간';if(zone==='C')return '되메우기 — 전체 구간';if(zone==='D')return '추가 공정';return w?.name||'작업';}
function wfPrimaryZoneWorks(items=state.workPackages||[]){
  const roots=items.filter(w=>!w.parentWpId);
  const byZone=new Map();
  for(const work of roots){
    const zone=String(work.zone||'').toUpperCase();
    const current=byZone.get(zone);
    const actual=Boolean(wfInstructionForWork(work));
    const currentActual=Boolean(wfInstructionForWork(current));
    if(!current||(actual&&!currentActual))byZone.set(zone,work);
    else if(actual&&currentActual){
      const nextTime=Date.parse(wfInstructionForWork(work)?.updated_at||0)||0;
      const currentTime=Date.parse(wfInstructionForWork(current)?.updated_at||0)||0;
      if(nextTime>=currentTime)byZone.set(zone,work);
    }else if(!currentActual&&/^WP-SASANG-[A-Z]\d+$/i.test(work.id||''))byZone.set(zone,work);
  }
  return [...byZone.values()].map(work=>({...work,name:wfInstructionForWork(work)?work.name:wfZoneDisplayName(work)}));
}
function wfReviewWorks(){
  const all=state.workPackages||[];
  const actual=all.filter(work=>Boolean(wfInstructionForWork(work))).sort((a,b)=>{
    const priority={committed:0,rejected:1,dispatched:2,pending:3,blocked:4,approved:5};
    const ai=wfInstructionForWork(a),bi=wfInstructionForWork(b);
    return (priority[ai?.status]??9)-(priority[bi?.status]??9)||(Date.parse(bi?.updated_at||0)||0)-(Date.parse(ai?.updated_at||0)||0);
  });
  const actualZones=new Set(actual.map(work=>String(work.zone||'').toUpperCase()));
  const conceptual=wfPrimaryZoneWorks(all).filter(work=>!wfInstructionForWork(work)&&!actualZones.has(String(work.zone||'').toUpperCase()));
  return [...actual,...conceptual];
}
renderDashboard=function(){const works=wfPrimaryZoneWorks().filter(w=>['A','B','C','D'].includes(String(w.zone||'').toUpperCase()));const totalWeight=works.reduce((sum,w)=>sum+Math.max(1,Number(w.target)||1),0);const overall=Math.round(works.reduce((sum,w)=>sum+Math.max(1,Number(w.target)||1)*wfProgress(w),0)/Math.max(1,totalWeight));const active=works.filter(w=>!['accepted','done'].includes(w.status)).length;const review=works.filter(w=>w.status==='review').length;const correction=works.filter(w=>['correction','correction-issued'].includes(w.status)).length;const dateLabel=new Intl.DateTimeFormat('ko-KR',{month:'2-digit',day:'2-digit'}).format(new Date());$('#page-dashboard').innerHTML=`<div class="workflow-page"><div class="workflow-kpis"><button data-page-link="execution"><span>오늘 작업</span><b>${active}</b><small>지속 관리 필요</small></button><button data-page-link="evidence"><span>검토 대기</span><b>${review}</b><small>검토·승인 필요</small></button><button data-page-link="evidence"><span>보완 필요</span><b>${correction}</b><small>즉시 확인 필요</small></button><button data-page-link="execution"><span>완료 Zone</span><b>${works.filter(w=>wfDailyState(w)[1]==='done').length}</b><small>오늘 승인 완료</small></button></div><div class="workflow-dashboard-grid"><section class="workflow-panel map-panel"><header><div><h2>현장 맵 <small>Site Work Map</small></h2><p>오늘 작업 위치와 문제 Zone을 한눈에 확인합니다.</p></div><span class="workflow-live">${stageInventory?.connected?'LIVE':'OFFLINE'}</span></header>${wfMapFrame()}</section><aside class="workflow-panel action-panel daily-progress-panel"><header><div><h2>오늘 작업 진척도</h2><p>${dateLabel} · 일일 작업계획 기준</p></div><b class="daily-overall-value">${overall}%</b></header><div class="daily-overall"><div><span>전체 진척도</span><b>${overall}%</b></div><i style="--p:${overall}%"></i><small>Zone별 목표 작업량을 반영한 가중 진척도</small></div><div class="daily-zone-list">${works.map(w=>wfDailyZoneRow(w)).join('')||wfBlank('오늘 작업 없음','작업 지시에서 오늘 작업을 등록해 주세요.')}</div></aside></div></div>`;};
renderEvidence=function(){const page=$('#page-evidence');const works=wfReviewWorks();if(workflowUI.reviewId){let w=(state.workPackages||[]).find(x=>x.id===workflowUI.reviewId);if(w?.parentWpId)w=(state.workPackages||[]).find(x=>x.id===w.parentWpId)||w;if(w){page.innerHTML=wfReviewDetail(w);return;}workflowUI.reviewId=null;}const priority=works[0];page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>검토·승인</h2><p>Zone별 작업의 현장 작업 실행 상태와 Evidence 검토 우선순위를 확인합니다.</p></div><button class="ghost-button" data-workflow-action="refresh">↻ 새로고침</button></div><div class="review-layout"><section><div class="workflow-kpis compact">${[['검토 필요','review'],['보완 중','warning'],['재검증 대기','locked'],['승인 완료','done']].map(x=>`<div><span>${x[0]}</span><b>${works.filter(w=>wfStatus(w)[1]===x[1]).length}</b></div>`).join('')}</div><div class="workflow-panel review-list">${works.map(w=>{const s=wfStatus(w);return `<button ${wfReviewClickAttributes(w)}><span><b>Zone ${esc(w.zone)} · ${esc(w.name)}</b><small>${esc(w.id)}</small></span><span>${wfProgress(w)}%</span><em class="${s[1]}">${s[0]}</em><span>${s[1]==='warning'?'후속 작업 LOCKED':wfCommitForWork(w)?'Evidence 검토':'상세 보기'} →</span></button>`}).join('')||wfBlank('검토할 작업 없음','작업 지시를 발행하고 현장 작업 결과를 기다려 주세요.')}</div></section><aside class="workflow-panel review-priority"><h3>우선 검토 작업</h3>${priority?`<b>Zone ${esc(priority.zone)} · ${esc(priority.name)}</b><div><span>진척도</span><strong>${wfProgress(priority)}%</strong></div><button class="primary-button" ${wfReviewClickAttributes(priority)}>상세 검토로 이동 →</button>`:wfBlank('대상 없음','검토할 작업이 없습니다.')}</aside></div></div>`;};
const wfReviewDetailBase=wfReviewDetail;
wfReviewDetail=function(w){return wfReviewDetailBase({...w,name:wfZoneDisplayName(w)});};

// Zone H is a haul operation, not a terrain-shaping operation.
const wfStatusBase=wfStatus;
wfStatus=function(w){
  if(String(w?.zone||'').toUpperCase()==='H'&&w?.status==='executing')return ['운반 중','active'];
  return wfStatusBase(w);
};
const wfZoneProfileBase=wfZoneProfile;
wfZoneProfile=function(phase,approved){
  if(phase.zone==='H')return approved
    ?{design:'M55 140 C250 118 500 76 870 34',actual:'M55 141 C250 120 500 79 870 38',start:700,end:850,value:'누적 반출량 700㎥'}
    :{design:'M55 140 C250 118 500 76 870 34',actual:'M55 142 C250 134 500 121 870 105',start:650,end:870,value:'누적 반출량 231㎥'};
  return wfZoneProfileBase(phase,approved);
};
const zoneProfileLabelBase=zoneProfileLabel;
zoneProfileLabel=function(zone){return zone==='H'?'Haul Progress':zoneProfileLabelBase(zone);};
const wfZoneDisplayNameBase=wfZoneDisplayName;
wfZoneDisplayName=function(w){return String(w?.zone||'').toUpperCase()==='H'?'가적치장 반출·운반':wfZoneDisplayNameBase(w);};

// The daily dashboard originally showed only terrain Zones A-D. Include the
// separately managed haul operation and recalculate the weighted daily total.
const renderDashboardBase=renderDashboard;
renderDashboard=function(){
  renderDashboardBase();
  const works=wfPrimaryZoneWorks();
  const haul=works.find(w=>String(w.zone||'').toUpperCase()==='H');
  const list=document.querySelector('.daily-zone-list');
  if(haul&&list&&!list.querySelector('[data-zone-haul]')){
    const holder=document.createElement('div');
    holder.dataset.zoneHaul='H';
    holder.innerHTML=wfDailyZoneRow(haul);
    list.append(...holder.childNodes);
  }
  const included=works.filter(w=>['A','B','C','D','H'].includes(String(w.zone||'').toUpperCase()));
  const weight=included.reduce((sum,w)=>sum+Math.max(1,Number(w.target)||1),0);
  const overall=Math.round(included.reduce((sum,w)=>sum+Math.max(1,Number(w.target)||1)*wfProgress(w),0)/Math.max(1,weight));
  document.querySelectorAll('.daily-overall-value,.daily-overall b').forEach(el=>{el.textContent=`${overall}%`;});
  document.querySelector('.daily-overall>i')?.style.setProperty('--p',`${overall}%`);
  const statusKinds=[null,'review','warning','done'];
  document.querySelectorAll('#page-dashboard .workflow-kpis>button b').forEach((value,index)=>{
    value.textContent=index===0
      ?included.filter(work=>wfStatus(work)[1]!=='done').length
      :included.filter(work=>wfStatus(work)[1]===statusKinds[index]).length;
  });
};

// Keep the haul review visual in the same photogrammetry language as A-D.
const wfReviewPhaseForWorkBase=wfReviewPhaseForWork;
wfReviewPhaseForWork=function(w){
  const phase=wfReviewPhaseForWorkBase(w);
  if(String(w?.zone||'').toUpperCase()==='H'){
    phase.image='/static/assets/review/zone-h-haul-progress-v3.png';
    phase.approvedImage=phase.image;
  }
  return phase;
};

const wfReviewWorkVisualBase=wfReviewWorkVisual;
wfReviewWorkVisual=function(w){
  if(String(w?.zone||'').toUpperCase()!=='H')return wfReviewWorkVisualBase(w);
  const progress=wfProgress(w);
  const target=Number(w.target||700);
  const completed=Math.round(target*progress/100);
  const remaining=Math.max(0,target-completed);
  const evidence=state.evidence?.[w.id]||{};
  return `<div class="review-zone-head haul-zone-head"><div><span>ZONE H</span><b>반출·운반 운영 현황</b><small>공간 형상 판정이 아닌 반출 물량과 운반 이벤트를 집계합니다.</small></div><span class="review-result-badge active">운반 진행 중 · ${progress}%</span></div><div class="review-diff-toolbar haul-toolbar"><div class="profile-legend"><i class="actual-shape"></i>운반 완료 경로<i class="design-shape"></i>남은 계획 경로<i class="shallow-diff"></i>운영 경계</div><span>물량·회차 기준</span></div><div class="review-zone-visual haul-progress-visual"><img loading="lazy" decoding="async" src="/static/assets/review/zone-h-haul-progress-v3.png" alt="Zone H 가적치장 반출·운반 진행 현황"><div class="review-approved-callout haul-callout"><b>${progress}% 운반 완료</b><span>남은 경로는 결함이 아닌 계획 구간입니다.</span></div><div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="haul-operation-summary"><div><span>계획 반출량</span><b>${target.toLocaleString()}㎥</b></div><div><span>누적 반출량</span><b>${completed.toLocaleString()}㎥</b></div><div><span>잔여 반출량</span><b>${remaining.toLocaleString()}㎥</b></div><div><span>운반 이벤트</span><b>${(evidence.missing||[]).includes('운반 종료 이벤트')?'수집 중':'정상 수집'}</b></div></div>`;
};

function wfScenarioRuns(){
  const grouped=new Map();
  for(const instruction of isaacInstructions||[]){
    const params=instruction.params||{};
    if(!params.scenario_run_id)continue;
    if(!grouped.has(params.scenario_run_id))grouped.set(params.scenario_run_id,[]);
    grouped.get(params.scenario_run_id).push(instruction);
  }
  return [...grouped.entries()].map(([id,instructions])=>({id,instructions})).sort((left,right)=>{
    const newest=run=>Math.max(...run.instructions.map(item=>Date.parse(item.created_at||item.updated_at||0)||0));
    return newest(right)-newest(left);
  });
}
function wfScenarioPhaseState(members){
  if(!members.length)return {label:'선행 공정 승인 후',kind:'locked',progress:0};
  const statuses=members.map(item=>item.status);
  const works=members.map(item=>(state.workPackages||[]).find(work=>work.id===item.params?.work_package_id)).filter(Boolean);
  const progress=works.length?Math.round(works.reduce((sum,work)=>sum+wfProgress(work),0)/works.length):0;
  if(statuses.every(value=>value==='approved'))return {label:'승인 완료',kind:'done',progress:100};
  if(statuses.some(value=>value==='rejected'))return {label:'반려 · 보완 필요',kind:'warning',progress:100};
  const remediation=wfRemediationInstruction(members);
  if(remediation&&remediation.status!=='approved'){
    const label=remediation.status==='blocked'?'보완 계획 승인 대기':remediation.status==='committed'?'보완 Evidence 재검증':remediation.status==='dispatched'?'보완 굴착 실행 중':'보완 굴착 대기';
    return {label,kind:'warning',progress};
  }
  if(members.some(wfCommitNeedsRemediation))return {label:'목표량 미달 · 검토 필요',kind:'warning',progress:100};
  if(statuses.some(value=>value==='committed'))return {label:'Evidence 검토 대기',kind:'review',progress:100};
  if(statuses.some(value=>value==='dispatched'))return {label:'현장 작업 중',kind:'active',progress};
  if(statuses.some(value=>value==='pending'))return {label:'작업 실행 대기',kind:'active',progress};
  if(members.some(item=>item.params?.phase_approval_ready))return {label:'계획 승인 대기',kind:'review',progress:0};
  return {label:'선행 공정 승인 대기',kind:'locked',progress:0};
}
function wfScenarioPhases(){
  return approvedSitePlan?.design?.phases||[
    {id:'excavation',order:1,zone_id:'A',title:'터파기',description:'굴착기 3대가 작업전선별 채움 토사를 제거합니다.',target_amount:1826.9,target_unit:'m3',estimated_hours:10.2,equipment:['EXC-001','EXC-002','EXC-003'],acceptance_criteria:['설계 굴착 저면 대비 ±50mm','미굴착 토사 체적 2% 이하','카메라·LiDAR·IMU Evidence 완전성 90% 이상']},
    {id:'pipe_installation',order:2,zone_id:'A',title:'관로 설치',description:'승인된 굴착 저면의 설계 중심선에 관로를 설치합니다.',target_amount:79.2,target_unit:'m',estimated_hours:7.9,equipment:['EXC-001','EXC-002','EXC-003'],acceptance_criteria:['관 중심선 수평 편차 ±100mm','관저고 설계 편차 ±50mm','이음부 누락 0건']},
    {id:'backfill',order:3,zone_id:'A',title:'되메우기',description:'관로 승인 후 굴착부를 층별 되메우고 다짐합니다.',target_amount:1737.4,target_unit:'m3',estimated_hours:9.7,equipment:['EXC-001','EXC-002','EXC-003'],acceptance_criteria:['층별 다짐도 90% 이상','최종 표면 편차 ±50mm','관로 보호층 최소 두께 300mm']},
  ];
}
function wfScenarioPhasesForRun(run){
  const instructions=run?.instructions||[];
  const first=instructions[0]||{};
  const planId=String(first.params?.scenario_plan_id||'');
  const savedPlan=(sitePlans||[]).find(item=>String(item?.design?.plan_id||'')===planId);
  if(Array.isArray(savedPlan?.design?.phases)&&savedPlan.design.phases.length)return savedPlan.design.phases;
  if(String(approvedSitePlan?.design?.plan_id||'')===planId&&Array.isArray(approvedSitePlan?.design?.phases))return approvedSitePlan.design.phases;
  const ids=[...new Set(instructions.map(item=>item.params?.scenario_phase_id).filter(Boolean))]
    .sort((left,right)=>{
      const leftOrder=Number(instructions.find(item=>item.params?.scenario_phase_id===left)?.params?.scenario_phase_order||999);
      const rightOrder=Number(instructions.find(item=>item.params?.scenario_phase_id===right)?.params?.scenario_phase_order||999);
      return leftOrder-rightOrder;
    });
  const phaseMeta={
    excavation:{title:'터파기',target_unit:'m³',acceptance_criteria:['설계 굴착 저면 대비 ±50mm','미굴착 토사 체적 2% 이하','센서 Evidence 완전성 90% 이상']},
    pipe_installation:{title:'관로 설치',target_unit:'m',acceptance_criteria:['관 중심선 수평 편차 ±100mm','관로 설계 고도 편차 ±50mm','이음부 누락 0건']},
    backfill:{title:'되메우기',target_unit:'m³',acceptance_criteria:['층별 다짐도 90% 이상','최종 표면 편차 ±50mm','관로 보호층 최소 두께 300mm']},
    soil_relocation:{title:'토사 이동',target_unit:'m³',acceptance_criteria:['이동 토사량 목표 대비 95% 이상','최종 적치 중심 위치 오차 0.5m 이하','센서 Evidence 완전성 90% 이상']},
  };
  return ids.map((id,index)=>{
    const members=instructions.filter(item=>item.params?.scenario_phase_id===id);
    const params=members[0]?.params||{};
    const quantity=params.planned_quantity||{};
    const meta=phaseMeta[id]||{title:params.summary||id,target_unit:quantity.unit||'',acceptance_criteria:[]};
    return {
      id,order:Number(params.scenario_phase_order||index+1),zone_id:String(params.zone_id||'A'),
      title:meta.title,description:params.summary||meta.title,
      target_amount:Number(quantity.value||0),target_unit:quantity.unit||meta.target_unit,
      estimated_hours:0,equipment:[...new Set(members.map(item=>item.params?.equipment_name).filter(Boolean))],
      acceptance_criteria:meta.acceptance_criteria,
    };
  });
}
function wfScenarioDesignForRun(run){
  const first=run?.instructions?.[0]||{};
  const params=first.params||{};
  const planId=String(params.scenario_plan_id||'');
  const savedPlan=(sitePlans||[]).find(item=>String(item?.design?.plan_id||'')===planId);
  const persisted=savedPlan?.design||(String(approvedSitePlan?.design?.plan_id||'')===planId?approvedSitePlan.design:null);
  if(persisted)return persisted;
  const phases=wfScenarioPhasesForRun(run);
  const zoneId=String(params.zone_id||phases[0]?.zone_id||'A');
  const scenarioTitle=String(params.scenario_title||'').replace(/^Zone\s+[A-Z]\s*/i,'').trim();
  return {
    plan_id:planId||run?.id||'현장 작업',revision:'',zone_id:zoneId,
    zone_title:scenarioTitle||(phases[0]?.id==='soil_relocation'?'토사 이동':'관로 공사'),
    title:scenarioTitle||'현장 작업',phases,
  };
}
function wfScenarioDate(value){
  const date=new Date(value||0);
  return Number.isNaN(date.getTime())?'-':new Intl.DateTimeFormat('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(date);
}
function wfScenarioInstructionWork(instruction){
  return (state.workPackages||[]).find(work=>work.id===instruction?.params?.work_package_id)||null;
}
function wfScenarioDetailMarkup(run){
  const rawDesign=wfScenarioDesignForRun(run);
  const design={...rawDesign,plan_id:wfPlanLabel(rawDesign.plan_id)};
  const phases=wfScenarioPhasesForRun(run);
  const phaseGroups=phases.map(phase=>{
    const members=run.instructions.filter(item=>item.params?.scenario_phase_id===phase.id);
    return {phase,members,state:wfScenarioPhaseState(members)};
  });
  const completed=phaseGroups.filter(group=>group.state.kind==='done').length;
  const allDone=completed===phaseGroups.length;
  const current=phaseGroups.find(group=>group.state.kind!=='done')||phaseGroups.at(-1);
  const overall=allDone?100:Math.round(((completed+(current?.state.progress||0)/100)/Math.max(1,phaseGroups.length))*100);
  const parentId=run.instructions[0]?.params?.scenario_parent_work_package_id||run.id;
  const approvedCommits=run.instructions.filter(item=>item.status==='approved').length;
  const totalCommits=run.instructions.length;
  const phaseFlow=phaseGroups.map((group,index)=>`<div class="scenario-detail-phase ${group.state.kind} ${group===current?'current':''}"><span>${wfPhaseBadge(group.phase,index)}</span><div><b>${esc(group.phase.title)}</b><small>Zone ${esc(wfScenarioZoneId(design))} · ${esc(group.state.label)} · ${group.members.filter(item=>item.status==='approved').length}/${group.members.length||3} Commit</small></div><strong>${group.state.progress}%</strong></div>${index<phaseGroups.length-1?'<i class="scenario-detail-arrow">→</i>':''}`).join('');
  const members=current?.members||[];
  const workfrontRows=members.map((instruction,index)=>{
    const params=instruction.params||{};
    const work=wfScenarioInstructionWork(instruction);
    const progress=work?wfProgress(work):['committed','approved','rejected'].includes(instruction.status)?100:0;
    const stateInfo=wfScenarioPhaseState([instruction]);
    const quantity=params.planned_quantity||{};
    const commit=isaacLatestCommit(instruction);
    const detail=commit
      ?`<button class="ghost-button button-sm" data-isaac-detail="${esc(instruction.id)}">Evidence 보기</button>`
      :`<span class="scenario-workfront-note">${esc(params.station_range||'실행 대기')}</span>`;
    return `<div class="scenario-detail-workfront"><span class="zone-token ${wfPhaseCss(current.phase,phaseGroups.indexOf(current))}">${esc(params.workfront_id||`F${index+1}`)}</span><div><b>${esc(params.target_name||params.summary||`작업전선 ${index+1}`)}</b><small>${esc(params.station_range||'-')}</small></div><div><span>배정 장비</span><b>${esc(params.equipment_name||'-')}</b></div><div><span>계획량</span><b>${num(quantity.value||0)}${wfDesignUnit(quantity.unit||current.phase.target_unit)}</b></div><div><i class="scenario-progress" style="--p:${progress}%"></i><b>${progress}%</b></div><em class="${stateInfo.kind}">${esc(stateInfo.label)}</em>${detail}</div>`;
  }).join('')||wfBlank('작업전선 미등록','현재 공정의 Work Package가 아직 생성되지 않았습니다.');
  const missing=[...new Set(members.flatMap(item=>item.params?.missing_resources||[]).filter(Boolean))];
  const rejected=members.filter(item=>item.status==='rejected').length;
  const review=members.filter(item=>item.status==='committed').length;
  const deficient=members.filter(wfCommitNeedsRemediation);
  const remediation=wfRemediationInstruction(members);
  const issues=[
    ...missing.map(message=>({tone:'warning',title:'자원 확인 필요',message})),
    ...(rejected?[{tone:'danger',title:`반려된 Commit ${rejected}건`,message:'보완 Work Package 발행 후 재검토가 필요합니다.'}]:[]),
    ...deficient.map(item=>{const quality=isaacLatestCommit(item)?.result?.quality_assessment||{};return {tone:'danger',title:`${item.params?.equipment_name||'굴착 장비'} 목표 굴착량 미달`,message:`완료 ${num(quality.completed_volume_m3||0)}㎥ · 부족 ${num(quality.remaining_volume_m3||0)}㎥ · 다음 공정 LOCKED`};}),
    ...(remediation&&remediation.status!=='approved'?[{tone:'warning',title:'보완 Work Package 진행 중',message:`${remediation.params?.equipment_name||'해당 장비'}만 부족량을 추가 굴착하고 Evidence를 재수집합니다.`}]:[]),
    ...(review?[{tone:'review',title:`Evidence 검토 대기 ${review}건`,message:'모든 작업전선의 결과 승인 후 다음 공정이 열립니다.'}]:[]),
  ];
  if(!issues.length)issues.push({tone:'ok',title:'현재 차단 문제 없음',message:current?.state.kind==='done'?'전체 공정이 승인 완료되었습니다.':'현재 공정이 정상 순서로 진행 중입니다.'});
  const issueMarkup=issues.map(issue=>`<div class="scenario-issue ${issue.tone}"><i>${issue.tone==='ok'?'✓':'!'}</i><div><b>${esc(issue.title)}</b><span>${esc(issue.message)}</span></div></div>`).join('');
  const criteria=(current?.phase.acceptance_criteria||[]).map((criterion,index)=>`<div><i>${index+1}</i><span>${esc(criterion)}</span></div>`).join('');
  const timeline=[];
  phaseGroups.forEach(group=>{
    const created=group.members.map(item=>item.created_at).filter(Boolean).sort()[0];
    if(created)timeline.push({time:created,title:`${wfPhaseBadge(group.phase)} ${group.phase.title} 계획 등록`,kind:'plan'});
    group.members.forEach(item=>{
      const params=item.params||{};
      (item.commits||[]).forEach(commit=>timeline.push({time:commit.created_at||item.updated_at,title:`${params.equipment_name||params.workfront_id||'작업전선'} Evidence Commit`,kind:item.status==='approved'?'done':'evidence'}));
    });
    if(group.state.kind==='done'){
      const completedAt=group.members.map(item=>item.updated_at).filter(Boolean).sort().at(-1);
      timeline.push({time:completedAt,title:`${wfPhaseBadge(group.phase)} ${group.phase.title} 승인 완료`,kind:'done'});
    }
  });
  timeline.sort((a,b)=>(Date.parse(b.time)||0)-(Date.parse(a.time)||0));
  const timelineMarkup=timeline.slice(0,10).map(item=>`<div class="scenario-activity ${item.kind}"><i></i><div><b>${esc(item.title)}</b><span>${wfScenarioDate(item.time)}</span></div></div>`).join('')||wfBlank('이력 없음','공정이 하달되면 실행 이력이 기록됩니다.');
  const ready=members.some(item=>item.status==='blocked'&&item.params?.phase_approval_ready);
  const committed=members.find(item=>item.status==='committed');
  const deficientInstruction=members.find(wfCommitNeedsRemediation);
  const remediationDraft=members.find(item=>item.params?.remediation_mode&&item.status==='blocked');
  const remediationCommitted=members.find(item=>item.params?.remediation_mode&&item.status==='committed');
  const remediationActive=members.find(item=>item.params?.remediation_mode&&['pending','dispatched'].includes(item.status));
  const managerAction=ready
    ?`<button class="primary-button" data-open-scenario-phase="${esc(run.id)}">${wfPhaseBadge(current.phase,phaseGroups.indexOf(current))} 계획 검토·승인</button>`
    :remediationDraft
      ?`<button class="primary-button" data-open-remediation="${esc(remediationDraft.id)}">AI 보완 계획 다시 열기</button>`
      :remediationCommitted
        ?`<button class="primary-button" data-isaac-detail="${esc(remediationCommitted.id)}">보완 Evidence 재검증</button>`
        :remediationActive
          ?`<button class="ghost-button" disabled>${esc(remediationActive.params?.equipment_name||'해당 장비')} 보완 굴착 실행 중</button>`
          :deficientInstruction
            ?`<button class="primary-button" data-isaac-detail="${esc(deficientInstruction.id)}">부족량 Evidence 검토</button>`
            :committed
      ?`<button class="primary-button" data-isaac-detail="${esc(committed.id)}">Evidence 검토 시작</button>`
      :`<button class="ghost-button" disabled>${allDone?'전체 공정 승인 완료':current?.state.label||'대기'}</button>`;
  return `<div class="workflow-page scenario-detail-page"><button class="workflow-back" data-scenario-back>← 작업 현황</button><div class="scenario-detail-heading"><div><span>PIPELINE CONSTRUCTION · ZONE ${esc(wfScenarioZoneId(design))}</span><h2>Zone ${esc(wfScenarioZoneId(design))} · ${esc(wfScenarioZoneTitle(design))} 상세</h2><p>${esc(parentId)} · ${esc(design.plan_id||run.instructions[0]?.params?.scenario_plan_id||'-')} Rev.${esc(design.revision||'-')}</p></div><em class="${current?.state.kind||'locked'}">${esc(allDone?'전체 공정 완료':current?.state.label||'대기')}</em></div><div class="workflow-kpis compact scenario-detail-kpis"><div><span>전체 공정</span><b>${overall}%</b><small>${completed}/${phases.length} 승인 완료</small></div><div><span>현재 공정 실행률</span><b>${current?.state.progress||0}%</b><small>${wfPhaseBadge(current?.phase,phaseGroups.indexOf(current))} · ${esc(current?.phase.title||'-')}</small></div><div><span>Evidence Commit</span><b>${approvedCommits}/${totalCommits}</b><small>승인 / 전체 작업전선</small></div><div><span>현장 연결</span><b>${stageInventory?.connected?'LIVE':'OFFLINE'}</b><small>${stageInventory?.connected?'작업 데이터 동기화 중':'현장 데이터 연결 대기'}</small></div></div><section class="workflow-panel scenario-detail-flow-panel"><header><div><h3>Zone ${esc(wfScenarioZoneId(design))} 내부 공정 흐름</h3><p>터파기·관로 설치·되메우기는 하나의 Zone에서 선행 Evidence 승인 후 순차적으로 열립니다.</p></div><span>${allDone?'COMPLETED':`CURRENT · ${wfPhaseBadge(current?.phase,phaseGroups.indexOf(current))}`}</span></header><div class="scenario-detail-flow">${phaseFlow}</div></section><div class="scenario-detail-layout"><main><section class="workflow-panel scenario-current-panel"><header><div><span>CURRENT PHASE</span><h3>${wfPhaseBadge(current?.phase,phaseGroups.indexOf(current))} · ${esc(current?.phase.title||'-')}</h3><p>${esc(current?.phase.description||'현재 공정 정보를 확인합니다.')}</p></div><dl><div><dt>목표량</dt><dd>${num(current?.phase.target_amount||0)}${wfDesignUnit(current?.phase.target_unit||'')}</dd></div><div><dt>예상시간</dt><dd>${num(current?.phase.estimated_hours||0)}h</dd></div><div><dt>작업 구간</dt><dd>${esc(design.station_range||'STA 0+000 ~ 0+079.2')}</dd></div></dl></header><div class="scenario-detail-workfront-head"><h4>작업전선·장비 상태</h4><span>${members.length}개 Work Package</span></div><div class="scenario-detail-workfronts">${workfrontRows}</div><div class="scenario-criteria"><h4>${wfPhaseBadge(current?.phase,phaseGroups.indexOf(current))} 완료·승인 판정 기준</h4><div>${criteria}</div></div></section><section class="workflow-panel scenario-activity-panel"><header><h3>공사 타임라인</h3><span>최근 ${Math.min(10,timeline.length)}건</span></header><div>${timelineMarkup}</div></section></main><aside><section class="workflow-panel scenario-map-panel"><header><div><h3>현재 작업 위치</h3><p>Zone ${esc(wfScenarioZoneId(design))} 경계와 작업전선을 현장 맵에서 확인합니다.</p></div></header>${wfMapFrame({controls:false})}</section><section class="workflow-panel scenario-gate-panel"><header><h3>관리자 게이트</h3><span class="${current?.state.kind||'locked'}">${esc(current?.state.label||'대기')}</span></header><div class="scenario-gate-summary"><div><span>현재 공정</span><b>${wfPhaseBadge(current?.phase,phaseGroups.indexOf(current))} · ${esc(current?.phase.title||'-')}</b></div><div><span>다음 공정</span><b>${allDone?'관로 공사 완료':esc(phaseGroups[phaseGroups.indexOf(current)+1]?.phase.title||'최종 승인')}</b></div></div>${managerAction}</section><section class="workflow-panel scenario-issue-panel"><header><h3>문제·차단 항목</h3><span>${issues.filter(issue=>issue.tone!=='ok').length}건</span></header><div>${issueMarkup}</div></section></aside></div></div>`;
}

function wfScenarioCompletionSummaryMarkup(run,groups){
  const rawDesign=wfScenarioDesignForRun(run);
  const design={...rawDesign,plan_id:wfPlanLabel(rawDesign.plan_id)};
  const instructions=run?.instructions||[];
  const commits=instructions.flatMap(instruction=>(instruction.commits||[]).map(commit=>({instruction,commit})));
  const approvedCommits=commits.filter(({instruction,commit})=>commit.review_status==='approved'||instruction.status==='approved');
  const remediation=instructions.filter(wfIsRemediationInstruction);
  const primary=instructions.filter(instruction=>!wfIsRemediationInstruction(instruction));
  const equipment=[...new Set(instructions.map(instruction=>instruction.params?.equipment_name).filter(Boolean))];
  const completenessValues=groups.map(group=>group.completeness).filter(value=>Number.isFinite(value)&&value>0);
  const completeness=completenessValues.length
    ?Math.round(completenessValues.reduce((sum,value)=>sum+value,0)/completenessValues.length)
    :(approvedCommits.length===commits.length&&commits.length?100:0);
  const completionTimes=[
    ...approvedCommits.map(({commit})=>commit.reviewed_at||commit.committed_at||commit.created_at),
    ...instructions.map(instruction=>instruction.updated_at),
  ].filter(Boolean).sort((left,right)=>(Date.parse(left)||0)-(Date.parse(right)||0));
  const completedAt=completionTimes.at(-1)||'';
  const zoneId=wfScenarioZoneId(design);
  const phaseResults=groups.map((group,index)=>{
    const approved=group.members.filter(instruction=>instruction.status==='approved').length;
    const target=`${num(group.phase.target_amount||0)}${wfDesignUnit(group.phase.target_unit||'')}`;
    return `<div class="scenario-completion-phase"><i>${index+1}</i><div><span>${wfPhaseBadge(group.phase,index)} · ${esc(group.phase.title)}</span><b>${target} 작업 · ${approved}/${group.members.length} Commit 승인</b></div>${group.remediationMembers.length?`<em>보완 ${group.remediationMembers.length}건 포함</em>`:'<em class="done">기준 충족</em>'}</div>`;
  }).join('');
  return `<section class="workflow-panel scenario-completion-panel"><div class="scenario-completion-hero"><i>✓</i><div><span>CONSTRUCTION RELEASE · MAIN MERGED</span><h3>Zone ${esc(zoneId)} 관로 공사가 완료되었습니다</h3><p>터파기 → 관로 설치 → 되메우기 결과와 Evidence가 모두 관리자 승인을 통과해 최종 현장 상태로 반영되었습니다.</p></div><em>공사 완료</em></div><div class="scenario-completion-summary-grid"><div><span>완료 공정</span><b>${groups.length}/${groups.length}</b><small>모든 선행 게이트 승인</small></div><div><span>승인 Commit</span><b>${approvedCommits.length}/${commits.length}</b><small>기본 ${primary.length} · 보완 ${remediation.length}</small></div><div><span>사용 장비</span><b>${equipment.length}대</b><small>${esc(equipment.join(' · ')||'-')}</small></div><div><span>Evidence 완결성</span><b>${completeness}%</b><small>카메라 · LiDAR · IMU</small></div><div><span>완료 구간</span><b>${esc(design.station_range||'STA 0+000 ~ 0+079.2')}</b><small>${num(design.total_length_m||79.2)}m 관로 공사</small></div><div><span>완료 시각</span><b>${wfScenarioDate(completedAt)}</b><small>Main Merge · Release</small></div></div><div class="scenario-completion-phase-list"><header><h4>공정별 완료 요약</h4><span>${remediation.length?`재작업 ${remediation.length}건 추적 완료`:'보완 작업 없음'}</span></header>${phaseResults}</div></section>`;
}

function wfDecorateCompletedScenarioDetail(page,run){
  if(!page||!run)return;
  const groups=wfConstructionPhaseGroups(run);
  if(!groups.length||!groups.every(group=>group.state.kind==='done'))return;
  const main=page.querySelector('.scenario-detail-layout>main');
  if(main&&!main.querySelector('.scenario-completion-panel'))main.insertAdjacentHTML('afterbegin',wfScenarioCompletionSummaryMarkup(run,groups));

  const kpis=page.querySelectorAll('.scenario-detail-kpis>div');
  if(kpis[1])kpis[1].innerHTML=`<span>완료 공정</span><b>${groups.length}/${groups.length}</b><small>터파기 · 관로 설치 · 되메우기</small>`;
  const completionTimes=(run.instructions||[]).map(instruction=>instruction.updated_at).filter(Boolean).sort((left,right)=>(Date.parse(left)||0)-(Date.parse(right)||0));
  if(kpis[3])kpis[3].innerHTML=`<span>최종 상태</span><b>RELEASED</b><small>${wfScenarioDate(completionTimes.at(-1))} · Main Merge 완료</small>`;

  const phasePanel=page.querySelector('.scenario-current-panel');
  if(phasePanel){
    phasePanel.classList.add('scenario-final-phase-panel');
    const eyebrow=phasePanel.querySelector('header>div>span');
    const title=phasePanel.querySelector('header h3');
    const description=phasePanel.querySelector('header p');
    if(eyebrow)eyebrow.textContent='FINAL PHASE RECORD';
    if(title)title.textContent=`최종 공정 기록 · ${groups.at(-1)?.phase.title||'되메우기'}`;
    if(description)description.textContent='전체 공사 완료 전 마지막 공정의 작업전선과 승인 Evidence를 기록으로 보존합니다.';
  }

  const mapTitle=page.querySelector('.scenario-map-panel header h3');
  const mapDescription=page.querySelector('.scenario-map-panel header p');
  if(mapTitle)mapTitle.textContent='완료 구간';
  if(mapDescription)mapDescription.textContent=`승인되어 Main에 반영된 Zone ${wfScenarioZoneId(wfScenarioDesignForRun(run))} 최종 현장 상태입니다.`;

  const gateTitle=page.querySelector('.scenario-gate-panel header h3');
  const gateStatus=page.querySelector('.scenario-gate-panel header span');
  const gateFacts=page.querySelectorAll('.scenario-gate-summary>div');
  if(gateTitle)gateTitle.textContent='최종 Release';
  if(gateStatus){gateStatus.textContent='승인 완료';gateStatus.className='done';}
  if(gateFacts[0])gateFacts[0].innerHTML='<span>공정 상태</span><b>3단계 전체 승인 완료</b>';
  if(gateFacts[1])gateFacts[1].innerHTML='<span>게시 상태</span><b>Main Merge · Release 완료</b>';
  const issueTitle=page.querySelector('.scenario-issue-panel header h3');
  if(issueTitle)issueTitle.textContent='완료 점검';
}

function wfScenarioExecutionMarkup(run){
  const rawDesign=wfScenarioDesignForRun(run);
  const design={...rawDesign,plan_id:wfPlanLabel(rawDesign.plan_id)};
  const phases=wfScenarioPhasesForRun(run);
  const phaseRows=phases.map(phase=>{
    const members=run.instructions.filter(item=>item.params?.scenario_phase_id===phase.id);
    const phaseState=wfScenarioPhaseState(members);
    const ready=members.some(item=>item.status==='blocked'&&item.params?.phase_approval_ready);
    const equipment=[...new Set(members.map(item=>item.params?.equipment_name).filter(Boolean))];
    const approvedCount=members.filter(item=>item.status==='approved').length;
    const detail=ready
      ?`<button class="secondary-button button-sm" data-open-scenario-phase="${esc(run.id)}">계획 검토·승인</button>`
      :members.some(item=>item.status==='committed')
        ?'<button class="ghost-button button-sm" data-page-link="evidence">Evidence 검토</button>'
        :`<span>${members.length?`${approvedCount}/${members.length} Commit 승인`:'아직 미발행'}</span>`;
    return `<div class="scenario-phase-row"><span><i class="zone-token ${wfPhaseCss(phase,phases.indexOf(phase))}">${wfPhaseBadge(phase,phases.indexOf(phase))}</i><b>${esc(phase.title)}</b></span><span>${esc((equipment.length?equipment:phase.equipment||[]).join(' · ')||'-')}</span><span><i class="scenario-progress" style="--p:${phaseState.progress}%"></i>${phaseState.progress}%</span><span><em class="${phaseState.kind}">${phaseState.label}</em></span><span>${detail}</span></div>`;
  }).join('');
  const phaseStates=phases.map(phase=>wfScenarioPhaseState(run.instructions.filter(item=>item.params?.scenario_phase_id===phase.id)));
  const completed=phaseStates.filter(item=>item.kind==='done').length;
  const allDone=completed===phases.length;
  const current=phaseStates.find(item=>item.kind!=='done')||phaseStates.at(-1);
  const currentIndex=Math.max(0,phaseStates.indexOf(current));
  const overall=allDone?100:Math.round(((completed+(current?.progress||0)/100)/Math.max(1,phases.length))*100);
  const parentId=run.instructions[0]?.params?.scenario_parent_work_package_id||run.id;
  const currentPhase=phases[currentIndex]||phases[0];
  const parentPhaseLabel=allDone?'전체 공정 완료':`현재: ${wfPhaseBadge(currentPhase,currentIndex)} · ${currentPhase?.title||'-'}`;
  return `<article class="workflow-scenario-block"><button type="button" class="scenario-parent-row scenario-parent-button" data-open-scenario-run="${esc(run.id)}"><span><b>Zone ${esc(wfScenarioZoneId(design))} · ${esc(wfScenarioZoneTitle(design))}</b><small>${esc(parentId)} · ${esc(design?.plan_id||run.instructions[0]?.params?.scenario_plan_id||'-')}</small></span><span>${esc(parentPhaseLabel)}</span><span><i class="scenario-progress" style="--p:${overall}%"></i>${overall}%</span><span><em class="${current?.kind||'locked'}">${esc(current?.label||'대기')}</em></span><span>${completed}/${phases.length} 공정 완료<strong>상세 ›</strong></span></button><div class="scenario-phase-stack">${phaseRows}</div></article>`;
}

// A pipeline request is one construction job.  Its equipment-level Isaac
// instructions remain available in Evidence, but Work Status groups them by
// internal phase under one Zone parent instead of presenting unrelated jobs.
renderExecution=function(){
  const page=$('#page-execution');if(!page)return;
  const runs=wfScenarioRuns();
  if(workflowUI.scenarioRunId){
    const selectedRun=runs.find(run=>run.id===workflowUI.scenarioRunId);
    if(selectedRun){page.innerHTML=wfScenarioDetailMarkup(selectedRun);wfDecorateCompletedScenarioDetail(page,selectedRun);wfAnnotateStationRanges(page);return;}
    workflowUI.scenarioRunId=null;
  }
  const scenarioWorkIds=new Set(runs.flatMap(run=>run.instructions.map(item=>item.params?.work_package_id).filter(Boolean)));
  const ordinary=(state.workPackages||[]).filter(work=>!work.parentWpId&&!scenarioWorkIds.has(work.id));
  const scenarioStates=runs.map(run=>{
    const members=run.instructions;
    const phases=wfScenarioPhasesForRun(run);
    const states=phases.map(phase=>wfScenarioPhaseState(members.filter(item=>item.params?.scenario_phase_id===phase.id)));
    return states.find(item=>item.kind!=='done')||states.at(-1);
  });
  const statusKinds=['active','review','warning','done'];
  const allKinds=[...scenarioStates.map(item=>item?.kind||'locked'),...ordinary.map(work=>wfStatus(work)[1])];
  const ordinaryRows=ordinary.map(work=>{const status=wfStatus(work);const progress=wfProgress(work);return `<button class="workflow-table-row" ${wfInstructionForWork(work)?`data-real-wp-detail="${esc(wfInstructionForWork(work).id)}"`:`data-review-open="${esc(work.id)}"`}><span><b>Zone ${esc(work.zone)} · ${esc(wfZoneDisplayName(work))}</b><small>${esc(work.id)}</small></span><span>${esc(wfEquipmentLabel(work)||'-')}</span><span><i style="--p:${progress}%"></i>${progress}%</span><span><em class="${status[1]}">${status[0]}</em></span><span>${status[1]==='warning'?'후속 공정 잠김':'영향 없음'} ›</span></button>`;}).join('');
  page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 현황</h2><p>공사별 진행 단계와 승인 상태를 확인합니다.</p></div><button class="primary-button" data-page-link="workpackages">+ 새 작업 지시</button></div><div class="workflow-kpis compact">${['진행 중','검토 대기','보완 중','완료'].map((label,index)=>`<div><span>${label}</span><b>${allKinds.filter(kind=>kind===statusKinds[index]).length}</b></div>`).join('')}</div><section class="workflow-panel workflow-table"><div class="workflow-table-head"><span>Zone / 공사</span><span>장비</span><span>진척도</span><span>상태</span><span>후속 영향</span></div>${runs.map(wfScenarioExecutionMarkup).join('')}${ordinaryRows||(!runs.length?wfBlank('작업 없음','작업 지시를 발행하면 여기에 표시됩니다.'):'')}</section></div>`;
};

// Make the meaning of the percentage explicit in the review list.
const renderEvidenceBase=renderEvidence;
renderEvidence=function(){
  renderEvidenceBase();
  if(workflowUI.reviewId){
    const selected=(state.workPackages||[]).find(w=>w.id===workflowUI.reviewId);
    if(String(selected?.zone||'').toUpperCase()==='H'){
      const reviewVisual=document.querySelector('#page-evidence .review-visual');
      reviewVisual?.classList.add('haul-review-visual');
      const target=Number(selected.target||700);
      const progress=wfProgress(selected);
      const completed=Math.round(target*progress/100);
      const remaining=Math.max(0,target-completed);
      const eventState=(state.evidence?.[selected.id]?.missing||[]).includes('운반 종료 이벤트')?'수집 중':'정상 수집';
      const summary=document.querySelector('#page-evidence .haul-operation-summary');
      if(summary)summary.innerHTML=`<header><div><span>오늘 운반 실적</span><b>${progress}%</b></div><i style="--p:${progress}%"></i><small>계획 반출량 대비 누적 운반 실적</small></header><div class="haul-metric-grid"><div><span>계획 반출량</span><b>${target.toLocaleString()}<small>㎥</small></b></div><div><span>누적 반출량</span><b>${completed.toLocaleString()}<small>㎥</small></b></div><div><span>잔여 반출량</span><b>${remaining.toLocaleString()}<small>㎥</small></b></div><div><span>운반 이벤트</span><b class="event-state">${eventState}</b><small>Trip Event · Payload</small></div></div>`;
      const status=document.querySelector('#page-evidence .status-chip');
      if(status){status.textContent='운반 진행 중';status.className='status-chip review';}
      const decisionTitle=document.querySelector('#page-evidence .decision-alert b');
      if(decisionTitle)decisionTitle.textContent='계획 물량 반출 진행 중';
      const impactLabel=document.querySelector('#page-evidence .decision-box span');
      const impactValue=document.querySelector('#page-evidence .decision-box b');
      if(impactLabel)impactLabel.textContent='운반 완료 조건';
      if(impactValue)impactValue.textContent='목표 물량·종료 이벤트 충족 후 완료';
    }
    return;
  }
  document.querySelectorAll('#page-evidence .review-list>button').forEach(row=>{
    const progress=row.children[1];
    if(progress&&!progress.querySelector('small')){
      const value=progress.textContent.trim();
      progress.innerHTML=`<small>진척도</small><strong>${value}</strong>`;
    }
  });
};

function wfHistoryEvents(works){
  const events=[];
  for(const work of works){
    const zone=String(work.zone||'').toUpperCase();
    const evidence=state.evidence?.[work.id]||{};
    const instruction=wfInstructionForWork(work);
    const name=instruction?work.name:wfZoneDisplayName(work);
    const progress=wfProgress(work);
    const isHaul=zone==='H';
    if(instruction){
      const operation=instruction.params?.operation||instruction.kind;
      const missing=instruction.params?.missing_resources||[];
      events.push({
        id:`${instruction.id}:issued`,workId:work.id,zone,type:instruction.status==='blocked'?'warning':'main',
        time:wfHistoryTimestamp(instruction.created_at),occurredAt:instruction.created_at,title:'작업 지시 발행',
        desc:`Zone ${zone} · ${name}`,status:instruction.status==='blocked'?'자원 대기':'작업 발행',
        actual:instruction.status==='blocked'?(missing.join(' · ')||'실행 자원 미확정'):`${operation} · Backend 저장 완료`,
        criterion:'LLM 작업 해석 · 현장 자원 검증',impact:instruction.status==='blocked'?'자원 확인 전 실행 보류':'작업 실행 대기열 등록',
        trace:`${work.id} / ${instruction.id}`,
      });
      if(instruction.dispatched_at){
        events.push({
          id:`${instruction.id}:dispatched`,workId:work.id,zone,type:'active',time:wfHistoryTimestamp(instruction.dispatched_at),
          occurredAt:instruction.dispatched_at,title:'현장 작업 시스템 수신',desc:`${wfEquipmentLabel(work)} · 현장 작업 시작`,
          status:'실행 중',actual:instruction.params?.resource_bindings?.target||work.targetPrimPath||operation,
          criterion:'검증된 generated_script',impact:'실행 Commit 대기',trace:`${instruction.id} / dispatched`,
        });
      }
      for(const commit of instruction.commits||[]){
        const result=commit.result||{};
        const commitEvidence=commit.evidence||{};
        const quantity=result.performed_quantity||{};
        const geometry=result.geometry_change||{};
        const failed=commit.status!=='succeeded';
        const completeness=Number(commitEvidence.quality?.completeness_ratio);
        events.push({
          id:`${commit.id}:commit`,workId:work.id,zone,type:failed?'warning':'main',time:wfHistoryTimestamp(commit.committed_at),
          instructionId:instruction.id,commitId:commit.id,
          occurredAt:commit.committed_at,title:failed?'현장 작업 실행 실패':'실행 Commit · Evidence 수신',
          desc:failed?(result.error||'현장 작업 시스템 오류'):`작업 전·후 센서와 작업 결과를 Commit했습니다.`,
          status:failed?'조치 필요':'검토 대기',
          actual:failed?(result.error||'실패'):(quantity.value!=null?`${quantity.value} ${quantity.unit||''}`:geometry.available?`절토 ${geometry.removed_volume_m3||0} / 성토 ${geometry.added_volume_m3||0} ㎥`:'Evidence 저장 완료'),
          criterion:Number.isFinite(completeness)?`Evidence 완결성 ${Math.round(completeness*100)}%`:'카메라·LiDAR·IMU Evidence',
          impact:failed?'후속 공정 LOCKED':'관리자 승인 대기',trace:`${commit.id} / attempt ${commit.attempt||1}`,
        });
        if(commit.review_status==='approved'){
          events.push({
            id:`${commit.id}:approved`,workId:work.id,zone,type:'merge',time:wfHistoryTimestamp(commit.reviewed_at),occurredAt:commit.reviewed_at,
            instructionId:instruction.id,commitId:commit.id,
            title:'관리자 승인 · Merge',desc:'검토한 현장 작업 결과를 공식 Site Work Map에 반영했습니다.',status:'승인 완료',
            actual:'PASS',criterion:'센서 Evidence 관리자 판정',impact:'공식 맵 반영 · 다음 공정 READY',trace:`MERGE / ${commit.id}`,
          });
        }else if(commit.review_status==='rejected'){
          events.push({
            id:`${commit.id}:rejected`,workId:work.id,zone,type:'warning',time:wfHistoryTimestamp(commit.reviewed_at),occurredAt:commit.reviewed_at,
            instructionId:instruction.id,commitId:commit.id,
            title:'관리자 반려 · Conflict',desc:commit.review_note||'실행 결과가 반려되었습니다.',status:'반려',
            actual:commit.review_note||'Conflict',criterion:'센서 Evidence 관리자 판정',impact:'공식 맵 미반영 · 후속 공정 LOCKED',trace:`REJECT / ${commit.id}`,
          });
        }
      }
      continue;
    }
    events.push({id:`${work.id}:start`,workId:work.id,zone,type:'main',time:work.start&&work.start!=='-'?work.start:'계획',title:isHaul?'반출·운반 시작':'작업 시작',desc:`Zone ${zone} · ${name}`,status:isHaul?'운반 중':'작업 발행',actual:isHaul?'상차·운반 장비 배차 완료':`목표 ${Number(work.target||0).toLocaleString()}㎥`,criterion:isHaul?'배차 명령·Trip Event 수신':'작업 지시 및 장비 배정 완료',impact:'작업 실행 가능',trace:`${work.id} / v${work.version||1}`});
    if(progress>0){
      events.push({id:`${work.id}:result`,workId:work.id,zone,type:isHaul?'active':'main',time:work.end&&work.end!=='-'?work.end:'현재',title:isHaul?'운반 실적 업데이트':'작업 결과 제출',desc:isHaul?`누적 반출 ${Math.round(Number(work.target||0)*progress/100).toLocaleString()}㎥ · 진척도 ${progress}%`:`진척도 ${progress}% · 결과 검토 요청`,status:isHaul?'운반 진행 중':'결과 수신',actual:isHaul?`${progress}% · ${Math.round(Number(work.target||0)*progress/100).toLocaleString()}㎥`:`Qualified ${progress}%`,criterion:isHaul?`계획 반출량 ${Number(work.target||0).toLocaleString()}㎥`:`완료 진척도 ${work.completionThreshold??100}%`,impact:isHaul?'목표 물량까지 운반 지속':'완료 기준 판정 대기',trace:`EV-${zone}-${String(work.id).split('-').at(-1)}-RESULT`});
    }
    if((evidence.conflicts||[]).length){
      const conflict=evidence.conflicts[0];
      events.push({id:`${work.id}:conflict`,workId:work.id,zone,type:'warning',time:conflict.time||work.end||'현재',title:conflict.title||'완료 기준 미달',desc:'완료 기준과 결과값의 차이를 확인했습니다.',status:'조치 필요',actual:conflict.actual||evidence.actual||'기준 미달',criterion:conflict.criterion||`허용오차 ±${work.toleranceMm??50}mm`,impact:'후속 공정 LOCKED',trace:`CF-${zone}-${String(work.id).split('-').at(-1)}`});
    }
    if(work.status==='correction'||work.parentWpId){
      events.push({id:`${work.id}:correction`,workId:work.id,zone,type:'branch',time:work.start||'현재',title:'보완 Work Package 발행',desc:`${name} 보완 브랜치 생성`,status:'보완 수행',actual:`잔여 ${Number(work.remaining||0).toLocaleString()}㎥`,criterion:'원본 작업 완료 기준 재적용',impact:'재검증 후 병합',trace:`correction/zone-${zone.toLowerCase()}`});
    }
    if(wfStatus(work)[1]==='done'){
      events.push({id:`${work.id}:merge`,workId:work.id,zone,type:'merge',time:work.end&&work.end!=='-'?work.end:'승인',title:'재검증 통과 · 관리자 승인',desc:'결과를 기준 이력에 병합하고 다음 공정을 Release했습니다.',status:'승인 완료',actual:'PASS',criterion:'완료 기준·Evidence 충족',impact:'다음 공정 READY',trace:`MERGE-${work.id}-v${work.version||1}`});
    }
  }
  return events;
}

function wfHistoryTimestamp(value){
  if(!value)return '-';
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return String(value);
  const today=new Date();
  const sameDay=date.getFullYear()===today.getFullYear()&&date.getMonth()===today.getMonth()&&date.getDate()===today.getDate();
  return new Intl.DateTimeFormat('ko-KR',sameDay?{hour:'2-digit',minute:'2-digit',hour12:false}:{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(date);
}

function wfHistoryWorks(){
  const all=state.workPackages||[];
  const actual=all.filter(work=>!work.parentWpId&&wfInstructionForWork(work));
  const actualZones=new Set(actual.map(work=>String(work.zone||'').toUpperCase()));
  const conceptual=wfPrimaryZoneWorks(all).filter(work=>!wfInstructionForWork(work)&&!actualZones.has(String(work.zone||'').toUpperCase()));
  return [...actual,...conceptual];
}

function wfHistoryDetail(event){
  if(!event)return `<aside class="workflow-panel history-event-detail">${wfBlank('이벤트를 선택하세요','왼쪽 작업 이력에서 확인할 이벤트를 선택해 주세요.')}</aside>`;
  const tone=['warning','branch'].includes(event.type)?'warning':event.type==='merge'?'done':event.type==='active'?'active':'main';
  const evidenceAction=event.instructionId&&event.commitId
    ?`<section class="history-evidence-entry"><div><span>COMMIT EVIDENCE</span><b>센서 원본과 작업 전·후 결과</b><small>카메라 · 3D LiDAR · IMU · 실행 이벤트 · 판정값</small></div><button class="primary-button" data-isaac-detail="${esc(event.instructionId)}" data-isaac-commit="${esc(event.commitId)}">Commit 상세·Evidence 열기 →</button></section>`
    :'';
  return `<aside class="workflow-panel history-event-detail"><header><div><span class="history-detail-type ${tone}">${event.status}</span><h3>${esc(event.title)}</h3><p>${esc(event.desc)}</p></div></header><div class="history-detail-grid"><div><span>작업</span><b>Zone ${esc(event.zone)} · ${esc(event.workId)}</b></div><div><span>발생 시각</span><b>${esc(event.time)}</b></div><div><span>결과 값</span><b>${esc(event.actual)}</b></div><div><span>판정 기준</span><b>${esc(event.criterion)}</b></div><div class="wide"><span>후속 영향</span><b class="${tone}">${esc(event.impact)}</b></div></div>${evidenceAction}<section class="history-trace"><span>추적 정보</span><code>${esc(event.trace)}</code><small>Plan v1.0 · Shared DB · 불변 이벤트</small></section></aside>`;
}

renderVersions=function(){
  const works=wfPrimaryZoneWorks();
  const zones=[...new Set(works.map(w=>String(w.zone||'')).filter(Boolean))].sort();
  const visible=workflowUI.historyZone==='ALL'?works:works.filter(w=>String(w.zone)===workflowUI.historyZone);
  const events=wfHistoryEvents(visible);
  if(!events.some(event=>event.id===workflowUI.historyEventId))workflowUI.historyEventId=events[0]?.id||null;
  const selected=events.find(event=>event.id===workflowUI.historyEventId);
  $('#page-versions').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 이력</h2><p>작업 지시부터 실행·검토·보완·승인·Release까지 이벤트 단위로 추적합니다.</p></div><label class="history-zone-filter">Zone<select data-history-zone><option value="ALL">전체 Zone</option>${zones.map(zone=>`<option value="${esc(zone)}" ${workflowUI.historyZone===zone?'selected':''}>Zone ${esc(zone)}</option>`).join('')}</select></label></div><div class="git-summary"><div><span>추적 이벤트</span><b>${events.length}</b></div><div><span>보완 브랜치</span><b>${events.filter(event=>event.type==='branch'||event.type==='warning').length}</b></div><div><span>승인·병합</span><b>${events.filter(event=>event.type==='merge').length}</b></div></div><div class="history-master-detail"><section class="workflow-panel history-event-list"><header><div><h3>Event Graph</h3><p>이벤트를 선택하면 판정 근거와 후속 영향을 확인할 수 있습니다.</p></div><span class="git-branch-label">main / Plan v1.0</span></header><div class="history-event-stream">${events.map(event=>`<button class="history-event-row ${event.type} ${event.id===workflowUI.historyEventId?'selected':''}" data-history-event="${esc(event.id)}"><i></i><time>${esc(event.time)}</time><span><b>${esc(event.title)}</b><small>Zone ${esc(event.zone)} · ${esc(event.workId)}</small></span><em>${esc(event.status)}</em></button>`).join('')||wfBlank('표시할 이력 없음','다른 Zone을 선택해 주세요.')}</div></section>${wfHistoryDetail(selected)}</div></div>`;
};

function wfHistoryTimeValue(event,index){
  const timestamp=Date.parse(event.occurredAt||'');
  if(Number.isFinite(timestamp))return timestamp+index/1000;
  const match=String(event.time||'').match(/^(\d{1,2}):(\d{2})$/);
  if(match)return Number(match[1])*60+Number(match[2])+index/1000;
  if(event.time==='현재')return 23*60+58+index/1000;
  if(event.time==='승인')return 23*60+59+index/1000;
  return 24*60+index/1000;
}

renderVersions=function(){
  workflowUI.historyDate=workflowUI.historyDate||'TODAY';
  workflowUI.historyStatus=workflowUI.historyStatus||'ALL';
  workflowUI.historyQuery=workflowUI.historyQuery||'';
  const works=wfHistoryWorks();
  const zones=[...new Set(works.map(w=>String(w.zone||'')).filter(Boolean))].sort();
  let events=wfHistoryEvents(works).map((event,index)=>({...event,sortTime:wfHistoryTimeValue(event,index)})).sort((a,b)=>a.sortTime-b.sortTime);
  if(workflowUI.historyDate==='TODAY'){
    const now=new Date();
    events=events.filter(event=>{
      if(!event.occurredAt)return true;
      const date=new Date(event.occurredAt);
      return !Number.isNaN(date.getTime())&&date.getFullYear()===now.getFullYear()&&date.getMonth()===now.getMonth()&&date.getDate()===now.getDate();
    });
  }
  if(workflowUI.historyZone!=='ALL')events=events.filter(event=>event.zone===workflowUI.historyZone);
  if(workflowUI.historyStatus==='ACTIVE')events=events.filter(event=>['main','active'].includes(event.type));
  if(workflowUI.historyStatus==='ACTION')events=events.filter(event=>['warning','branch'].includes(event.type));
  if(workflowUI.historyStatus==='DONE')events=events.filter(event=>event.type==='merge');
  const query=workflowUI.historyQuery.trim().toLowerCase();
  if(query)events=events.filter(event=>`${event.title} ${event.desc} ${event.zone} ${event.workId} ${event.trace}`.toLowerCase().includes(query));
  if(!events.some(event=>event.id===workflowUI.historyEventId))workflowUI.historyEventId=events[0]?.id||null;
  const selected=events.find(event=>event.id===workflowUI.historyEventId);
  $('#page-versions').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 이력</h2><p>모든 Zone의 작업 이벤트를 발생 시각 순서로 확인합니다.</p></div></div><div class="history-filter-bar"><label><span>기간</span><select data-history-date><option value="TODAY" ${workflowUI.historyDate==='TODAY'?'selected':''}>오늘</option><option value="ALL" ${workflowUI.historyDate==='ALL'?'selected':''}>전체 기간</option></select></label><label><span>Zone</span><select data-history-zone><option value="ALL">전체 Zone</option>${zones.map(zone=>`<option value="${esc(zone)}" ${workflowUI.historyZone===zone?'selected':''}>Zone ${esc(zone)}</option>`).join('')}</select></label><label><span>상태</span><select data-history-status><option value="ALL" ${workflowUI.historyStatus==='ALL'?'selected':''}>전체 상태</option><option value="ACTIVE" ${workflowUI.historyStatus==='ACTIVE'?'selected':''}>진행 이벤트</option><option value="ACTION" ${workflowUI.historyStatus==='ACTION'?'selected':''}>검토·보완</option><option value="DONE" ${workflowUI.historyStatus==='DONE'?'selected':''}>승인·Release</option></select></label><form data-history-search-form><span>검색</span><input data-history-search value="${esc(workflowUI.historyQuery)}" placeholder="작업명, WP, Zone 검색"><button type="submit">검색</button></form></div><div class="git-summary"><div><span>표시 이벤트</span><b>${events.length}</b></div><div><span>조치 이벤트</span><b>${events.filter(event=>event.type==='branch'||event.type==='warning').length}</b></div><div><span>승인·Release</span><b>${events.filter(event=>event.type==='merge').length}</b></div></div><div class="history-master-detail"><section class="workflow-panel history-event-list"><header><div><h3>Time-ordered Event Graph</h3><p>Zone 구분 없이 실제 발생 시각 순서로 정렬됩니다.</p></div><span class="git-branch-label">main / Plan v1.0</span></header><div class="history-event-stream">${events.map(event=>`<button class="history-event-row ${event.type} ${event.id===workflowUI.historyEventId?'selected':''}" data-history-event="${esc(event.id)}"><i></i><time>${esc(event.time)}</time><span><b>${esc(event.title)}</b><small>Zone ${esc(event.zone)} · ${esc(event.workId)}</small></span><em>${esc(event.status)}</em></button>`).join('')||wfBlank('검색 결과 없음','필터나 검색어를 변경해 주세요.')}</div></section>${wfHistoryDetail(selected)}</div></div>`;
};

document.addEventListener('click',event=>{
  const target=event.target.closest('[data-history-event]');
  if(!target)return;
  workflowUI.historyEventId=target.dataset.historyEvent;
  renderVersions();
});
document.addEventListener('change',event=>{
  if(event.target.matches('[data-history-date]')){workflowUI.historyDate=event.target.value;renderVersions();}
  if(event.target.matches('[data-history-status]')){workflowUI.historyStatus=event.target.value;renderVersions();}
});
document.addEventListener('submit',event=>{
  if(!event.target.matches('[data-history-search-form]'))return;
  event.preventDefault();
  workflowUI.historyQuery=event.target.querySelector('[data-history-search]').value;
  renderVersions();
});

// ---------------------------------------------------------------------------
// Construction-centric review and history
// ---------------------------------------------------------------------------
// Review and History intentionally use the scenario hierarchy already shown in
// Work Status.  Equipment instructions remain traceable evidence, but they are
// no longer presented as unrelated top-level jobs.
function wfConstructionLabel(run){
  const first=run?.instructions?.[0];
  const design=wfScenarioDesignForRun(run);
  const planId=first?.params?.scenario_plan_id||design?.plan_id||'현장 작업';
  const revision=design?.revision;
  return revision?`${planId} · Rev.${revision}`:planId;
}

function wfIsRemediationInstruction(instruction){
  return Boolean(instruction?.params?.remediation_mode);
}

function wfCompactTraceId(value){
  const text=String(value||'');
  return text?text.slice(0,8):'-';
}

function wfRemediationForInstruction(group,instruction){
  const direct=(group?.remediationMembers||[]).find(item=>item.params?.remediation_parent_instruction_id===instruction?.id);
  if(direct)return direct;
  const params=instruction?.params||{};
  return (group?.remediationMembers||[]).find(item=>{
    const candidate=item.params||{};
    return candidate.equipment_name===params.equipment_name&&candidate.workfront_id===params.workfront_id;
  })||null;
}

function wfRemediationFacts(remediation,parentCommit){
  const facts=remediation?.params?.remediation_facts||{};
  const quality=parentCommit?.result?.quality_assessment||{};
  return {
    planned:Number(facts.planned_volume_m3??quality.planned_volume_m3??0),
    completed:Number(facts.completed_volume_m3??quality.initial_completed_volume_m3??quality.completed_volume_m3??0),
    remaining:Number(facts.remaining_volume_m3??quality.initial_remaining_volume_m3??quality.remaining_volume_m3??0),
    measured:Number(facts.measured_completion_ratio??quality.initial_measured_completion_ratio??quality.measured_completion_ratio??0),
    required:Number(facts.required_completion_ratio??quality.required_completion_ratio??0.98),
  };
}

function wfRemediationResolved(remediation){
  const commit=isaacLatestCommit(remediation);
  return Boolean(remediation&&(remediation.status==='approved'||commit?.review_status==='approved'));
}

function wfRemediationLineageMarkup(group,instruction,parentCommit){
  const remediation=wfRemediationForInstruction(group,instruction);
  if(!remediation)return '';
  const correctionCommit=isaacLatestCommit(remediation);
  const facts=wfRemediationFacts(remediation,parentCommit);
  const resolved=wfRemediationResolved(remediation);
  const measured=Math.round(facts.measured*100);
  const required=Math.round(facts.required*100);
  const correctionTitle=correctionCommit
    ?resolved?'재작업 Commit · 기준 충족':'재작업 Commit · 재검증 대기'
    :'재작업 Commit 대기';
  const correctionState=correctionCommit?(resolved?'승인 완료':'검토 대기'):'실행 대기';
  const correctionKind=resolved?'resolved':correctionCommit?'review':'waiting';
  return `<div class="remediation-lineage"><div class="remediation-lineage-head"><div><b>재작업 연결 이력</b><span>최초 결과의 부족 원인부터 보완 승인까지 한 작업전선으로 추적합니다.</span></div><em class="${resolved?'done':'warning'}">${resolved?'보완 완료':'보완 진행'}</em></div><div class="remediation-lineage-flow"><div class="remediation-step issue"><i>1</i><div><b>최초 Commit · 목표량 미달</b><small>${wfCompactTraceId(remediation.params?.remediation_parent_commit_id||parentCommit?.id)} · 완료 ${num(facts.completed)}㎥ / 목표 ${num(facts.planned)}㎥</small><span>부족 ${num(facts.remaining)}㎥ · 달성률 ${measured}% / 기준 ${required}%</span></div><em>검토 필요</em></div><i class="remediation-arrow">→</i><div class="remediation-step correction"><i>2</i><div><b>보완 Work Package 하달</b><small>${esc(remediation.params?.equipment_name||instruction.params?.equipment_name||'해당 장비')} · ${esc(remediation.params?.workfront_id||instruction.params?.workfront_id||'동일 작업전선')}</small><span>부족량 ${num(facts.remaining)}㎥만 추가 굴착</span></div><em>재작업 지시</em></div><i class="remediation-arrow">→</i><div class="remediation-step ${correctionKind}"><i>3</i><div><b>${correctionTitle}</b><small>${wfCompactTraceId(correctionCommit?.id)} · 원 Commit과 연결</small><span>${resolved?'재검증 통과 · 공정 완료 처리':'카메라·LiDAR·IMU Evidence 재검증'}</span></div><em>${correctionState}</em></div></div></div>`;
}

function wfConstructionPhaseGroups(run){
  return wfScenarioPhasesForRun(run).map(phase=>{
    const members=(run?.instructions||[]).filter(item=>item.params?.scenario_phase_id===phase.id);
    const primaryMembers=members.filter(item=>!wfIsRemediationInstruction(item));
    const remediationMembers=members.filter(wfIsRemediationInstruction);
    const works=members.map(wfScenarioInstructionWork).filter(Boolean);
    const commits=members.flatMap(item=>item.commits||[]);
    const latestCommits=members.map(isaacLatestCommit).filter(Boolean);
    const approved=primaryMembers.filter(item=>item.status==='approved').length;
    const committed=members.filter(item=>item.status==='committed').length;
    const rejected=members.filter(item=>item.status==='rejected'||wfCommitNeedsRemediation(item)).length;
    const completenessValues=latestCommits.map(commit=>{
      const value=Number(commit?.evidence?.quality?.completeness_ratio);
      if(Number.isFinite(value))return value<=1?value*100:value;
      return null;
    }).filter(value=>value!=null);
    const completeness=completenessValues.length
      ?Math.round(completenessValues.reduce((sum,value)=>sum+value,0)/completenessValues.length)
      :0;
    return {
      key:`${run.id}::${phase.id}`,run,phase,members,primaryMembers,remediationMembers,works,commits,latestCommits,
      approved,committed,rejected,completeness,state:wfScenarioPhaseState(members),
    };
  });
}

function wfSelectedConstructionRun(scopeKey){
  const runs=wfScenarioRuns();
  if(!runs.length)return null;
  return runs.find(run=>run.id===scopeKey)||runs[0];
}

function wfPhaseReviewTone(group){
  if(group.rejected)return {label:'보완 필요',kind:'warning'};
  if(group.committed)return {label:'검토 대기',kind:'review'};
  if(group.state.kind==='done')return {label:'승인 완료',kind:'done'};
  if(group.state.kind==='active')return {label:'실행 중',kind:'active'};
  return {label:group.state.label||'선행 공정 대기',kind:group.state.kind||'locked'};
}

function wfPhaseReviewPriority(groups){
  const order={warning:0,review:1,active:2,locked:3,done:4};
  return [...groups].sort((left,right)=>(order[wfPhaseReviewTone(left).kind]??9)-(order[wfPhaseReviewTone(right).kind]??9))[0]||null;
}

function wfPhaseReviewDetail(group){
  const phase=group.phase;
  const tone=wfPhaseReviewTone(group);
  const workfronts=group.primaryMembers||group.members.filter(item=>!wfIsRemediationInstruction(item));
  const total=Math.max(workfronts.length,phase.equipment?.length||0,1);
  const runPhases=wfScenarioPhasesForRun(group.run);
  const next=runPhases[runPhases.findIndex(item=>item.id===phase.id)+1];
  const rows=workfronts.map((instruction,index)=>{
    const params=instruction.params||{};
    const work=wfScenarioInstructionWork(instruction);
    const commit=isaacLatestCommit(instruction);
    const remediation=wfRemediationForInstruction(group,instruction);
    const correctionCommit=isaacLatestCommit(remediation);
    const resolved=wfRemediationResolved(remediation);
    const memberState=remediation
      ?wfScenarioPhaseState([instruction,remediation])
      :wfScenarioPhaseState([instruction]);
    const progress=work?wfProgress(work):['committed','approved','rejected'].includes(instruction.status)?100:0;
    const quality=Number(commit?.evidence?.quality?.completeness_ratio);
    const evidencePct=Number.isFinite(quality)?Math.round(quality<=1?quality*100:quality):0;
    const action=commit&&remediation
      ?`<div class="phase-review-actions"><button class="ghost-button button-sm" data-isaac-detail="${esc(instruction.id)}">최초 Evidence</button>${correctionCommit?`<button class="ghost-button button-sm" data-isaac-detail="${esc(remediation.id)}">재작업 Evidence</button>`:''}</div>`
      :commit
        ?`<button class="ghost-button button-sm" data-isaac-detail="${esc(instruction.id)}">Evidence 검토</button>`
      :`<span class="phase-review-wait">${instruction.status==='blocked'?'계획 승인 전':'Commit 대기'}</span>`;
    const stateLabel=resolved?'보완 완료 · 승인':memberState.label;
    return `<article class="phase-review-workfront ${remediation?'has-remediation':''}"><div class="phase-review-member"><span class="zone-token ${wfPhaseCss(phase)}">${esc(params.workfront_id||`F${index+1}`)}</span><div><b>${esc(params.equipment_name||`작업 장비 ${index+1}`)}</b><small>${esc(params.station_range||params.target_name||'-')}</small></div><div><span>실행률</span><b>${progress}%</b></div><div><span>Evidence</span><b>${evidencePct?`${evidencePct}%`:'대기'}</b></div><em class="${memberState.kind}">${esc(stateLabel)}</em>${action}</div>${wfRemediationLineageMarkup(group,instruction,commit)}</article>`;
  }).join('')||wfBlank('아직 하달되지 않은 공정','선행 공정 승인 후 Work Package와 장비 Evidence가 생성됩니다.');
  const criteria=(phase.acceptance_criteria||[]).map((criterion,index)=>`<div><i>${index+1}</i><span>${esc(criterion)}</span></div>`).join('');
  const pending=group.members.filter(item=>item.status==='committed');
  const firstPending=pending[0];
  const gateAction=firstPending
    ?`<button class="primary-button" data-isaac-detail="${esc(firstPending.id)}">검토 대기 Evidence 열기</button>`
    :group.rejected
      ?'<button class="ghost-button" data-page-link="execution">보완 작업 상태 확인</button>'
      :`<button class="ghost-button" disabled>${tone.kind==='done'?'공정 승인 완료':esc(tone.label)}</button>`;
  const commitBreakdown=group.remediationMembers.length
    ?`원 작업 ${workfronts.length} + 보완 ${group.remediationMembers.length}`
    :`원 작업 ${workfronts.length}`;
  return `<div class="workflow-page phase-review-detail"><button class="workflow-back" data-review-group-back>← 공정 검토 목록</button><div class="workflow-page-head"><div><span class="page-eyebrow">CONSTRUCTION REVIEW GATE · ZONE ${esc(wfScenarioZoneId())}</span><h2>${wfPhaseBadge(phase)} · ${esc(phase.title)} 검토</h2><p>Zone ${esc(wfScenarioZoneId())} ${esc(wfScenarioZoneTitle())} · 장비별 결과를 하나의 공정 단계 승인 단위로 묶어 검토합니다.</p></div><span class="status-chip ${tone.kind}">${esc(tone.label)}</span></div><div class="workflow-kpis compact phase-review-kpis"><div><span>작업전선</span><b>${workfronts.length}/${total}</b><small>원 작업 기준</small></div><div><span>승인 작업전선</span><b>${group.approved}/${total}</b><small>보완 완료 포함</small></div><div><span>Evidence 완전성</span><b>${group.completeness}%</b><small>카메라·LiDAR·IMU</small></div><div><span>다음 공정</span><b>${next?wfPhaseBadge(next):'완료'}</b><small>${next?esc(next.title):'관로 공사 Release'}</small></div></div><div class="phase-review-layout"><main><section class="workflow-panel phase-review-members"><header><div><h3>작업전선 Evidence</h3><p>원 작업과 보완 작업을 분리하지 않고 동일 작업전선의 재작업 이력으로 연결합니다.</p></div><span>${group.commits.length} Commit · ${commitBreakdown}</span></header><div>${rows}</div></section><section class="workflow-panel phase-review-criteria"><header><h3>${wfPhaseBadge(phase)} 완료·승인 판정 기준</h3><span>${criteria?`${(phase.acceptance_criteria||[]).length}개 기준`:'기준 대기'}</span></header><div>${criteria||wfBlank('판정 기준 없음','공정 계획에서 승인 기준을 먼저 등록해 주세요.')}</div></section></main><aside><section class="workflow-panel phase-review-gate"><header><div><span>PHASE MERGE GATE</span><h3>${esc(phase.title)} 공정 판정</h3></div><em class="${tone.kind}">${esc(tone.label)}</em></header><dl><div><dt>실행 상태</dt><dd>${esc(group.state.label)}</dd></div><div><dt>검토 대기</dt><dd>${group.committed}건</dd></div><div><dt>보완 이력</dt><dd>${group.remediationMembers.length}건</dd></div><div><dt>후속 공정</dt><dd>${tone.kind==='done'?'READY':'LOCKED'}</dd></div></dl>${gateAction}</section><section class="workflow-panel phase-review-flow"><h3>Zone A 공사 흐름</h3>${wfConstructionPhaseGroups(group.run).map((item,index)=>{const itemTone=wfPhaseReviewTone(item);return `<div class="${item.key===group.key?'current':''}"><span class="zone-token ${wfPhaseCss(item.phase,index)}">${wfPhaseBadge(item.phase,index)}</span><b>${esc(item.phase.title)}</b><em class="${itemTone.kind}">${esc(itemTone.label)}</em></div>`;}).join('')}</section></aside></div></div>`;
}

function wfPhaseReviewList(run){
  const groups=wfConstructionPhaseGroups(run);
  const priority=wfPhaseReviewPriority(groups);
  const counts={review:0,warning:0,active:0,done:0,locked:0};
  groups.forEach(group=>{const kind=wfPhaseReviewTone(group).kind;counts[kind]=(counts[kind]||0)+1;});
  const overall=Math.round(groups.reduce((sum,group)=>sum+group.state.progress,0)/Math.max(1,groups.length));
  return `<div class="workflow-page construction-review-page"><div class="workflow-page-head"><div><h2>검토·승인</h2><p>선택한 Zone의 장비별 Commit을 공정 단계로 모아 검토·승인하고 다음 공정으로 연결합니다.</p></div><label class="construction-run-select"><span>공사 선택</span><select data-review-run>${wfScenarioRuns().map(item=>`<option value="${esc(item.id)}" ${item.id===run.id?'selected':''}>${esc(wfConstructionLabel(item))}</option>`).join('')}</select></label></div><div class="workflow-kpis compact"><div><span>검토 대기 공정</span><b>${counts.review||0}</b><small>관리자 판정 필요</small></div><div><span>보완 필요 공정</span><b>${counts.warning||0}</b><small>Conflict / 부족량</small></div><div><span>진행 중 공정</span><b>${counts.active||0}</b><small>현장 작업·수집</small></div><div><span>승인 완료 공정</span><b>${counts.done||0}/${groups.length}</b><small>전체 공정 ${overall}%</small></div></div><div class="construction-review-layout"><section class="workflow-panel construction-review-card"><header><div><span>ZONE ${esc(wfScenarioZoneId())} · PIPELINE CONSTRUCTION</span><h3>${esc(wfScenarioZoneTitle())}</h3><p>${esc(wfConstructionLabel(run))} · 1단계 터파기 → 2단계 관로 설치 → 3단계 되메우기</p></div><strong>${overall}%</strong></header><div class="phase-review-list">${groups.map((group,index)=>{const tone=wfPhaseReviewTone(group);const workfronts=group.primaryMembers||[];const total=Math.max(workfronts.length,group.phase.equipment?.length||0,1);const correction=group.remediationMembers.length?` · 보완 ${group.remediationMembers.length}건 연결`:'';return `<button class="phase-review-row ${tone.kind}" data-review-group="${esc(group.key)}"><span class="zone-token ${wfPhaseCss(group.phase,index)}">${wfPhaseBadge(group.phase,index)}</span><div><b>${esc(group.phase.title)}</b><small>${esc(group.state.label)} · ${group.approved}/${total} 작업전선 승인${correction}</small></div><div><span>Evidence</span><b>${group.completeness||0}%</b></div><div><i style="--p:${group.state.progress}%"></i><b>${group.state.progress}%</b></div><em class="${tone.kind}">${esc(tone.label)}</em><strong>상세 ›</strong></button>`;}).join('')}</div></section><aside class="workflow-panel construction-review-priority"><header><span>NEXT REVIEW</span><h3>우선 검토 공정</h3></header>${priority?`<div class="priority-zone"><span class="zone-token ${wfPhaseCss(priority.phase)}">${wfPhaseBadge(priority.phase)}</span><div><b>${esc(priority.phase.title)}</b><small>${esc(wfPhaseReviewTone(priority).label)}</small></div></div><dl><div><dt>검토 대기</dt><dd>${priority.committed} Commit</dd></div><div><dt>보완 이력</dt><dd>${priority.remediationMembers.length}건</dd></div><div><dt>Evidence</dt><dd>${priority.completeness}%</dd></div></dl><button class="primary-button" data-review-group="${esc(priority.key)}">공정 검토 열기 →</button>`:wfBlank('검토 대상 없음','현재 공사의 모든 공정이 승인되었습니다.')}</aside></div><p class="construction-scope-note">이 화면은 선택한 Zone의 작업과 공정만 표시합니다. 다른 위치의 독립 작업은 별도 Zone으로 분리됩니다.</p></div>`;
}

renderEvidence=function(){
  const page=$('#page-evidence');if(!page)return;
  const run=wfSelectedConstructionRun(workflowUI.reviewRunId);
  if(!run){page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>검토·승인</h2><p>공사 단위 Evidence 검토를 준비합니다.</p></div></div>${wfBlank('진행 중인 공사 없음','관로 공사 계획을 하달하면 Zone별 검토 게이트가 생성됩니다.')}</div>`;return;}
  workflowUI.reviewRunId=run.id;
  const groups=wfConstructionPhaseGroups(run);
  const selected=groups.find(group=>group.key===workflowUI.reviewGroupKey);
  page.innerHTML=selected?wfPhaseReviewDetail(selected):wfPhaseReviewList(run);
};

function wfConstructionHistoryEvents(run){
  const uniqueWorks=[];
  const seen=new Set();
  const phaseByWorkId=new Map();
  const instructionByWorkId=new Map();
  const remediationByParentId=new Map();
  (run?.instructions||[]).forEach(instruction=>{
    const work=wfScenarioInstructionWork(instruction);
    if(work)phaseByWorkId.set(work.id,String(instruction.params?.scenario_phase_id||''));
    if(work)instructionByWorkId.set(work.id,instruction);
    if(wfIsRemediationInstruction(instruction)&&instruction.params?.remediation_parent_instruction_id){
      remediationByParentId.set(instruction.params.remediation_parent_instruction_id,instruction);
    }
    if(work&&!seen.has(work.id)){seen.add(work.id);uniqueWorks.push(work);}
  });
  return wfHistoryEvents(uniqueWorks).map((event,index)=>{
    const instruction=instructionByWorkId.get(event.workId);
    const remediation=instruction?remediationByParentId.get(instruction.id):null;
    let enriched={...event};
    if(remediation&&event.id.endsWith(':commit')){
      const parentCommit=(instruction.commits||[]).find(commit=>commit.id===remediation.params?.remediation_parent_commit_id)||isaacLatestCommit(instruction);
      const facts=wfRemediationFacts(remediation,parentCommit);
      enriched={
        ...enriched,
        type:'warning',
        title:'최초 Commit · 목표 굴착량 미달',
        desc:`${instruction.params?.equipment_name||'해당 장비'} 작업 결과가 완료 기준에 미달하여 보완 Work Package가 생성되었습니다.`,
        status:'검토 필요',
        actual:`완료 ${num(facts.completed)}㎥ / 목표 ${num(facts.planned)}㎥ · 부족 ${num(facts.remaining)}㎥`,
        criterion:`굴착 달성률 ${Math.round(facts.measured*100)}% / 기준 ${Math.round(facts.required*100)}%`,
        impact:'보완 Work Package 하달 · 다음 공정 LOCKED',
        trace:`DEFICIT / ${parentCommit?.id||instruction.id}`,
      };
    }else if(remediation&&event.id.endsWith(':approved')){
      const correctionCommit=isaacLatestCommit(remediation);
      enriched={
        ...enriched,
        title:'원 Commit 완료 처리',
        desc:'연결된 재작업 Commit이 재검증을 통과하여 최초 미달 Commit을 완료 상태로 닫았습니다.',
        status:'보완 연계 완료',
        actual:`재작업 Commit ${wfCompactTraceId(correctionCommit?.id)}`,
        criterion:'부족량 추가 굴착 · Evidence 재검증 통과',
        impact:'원 작업과 보완 작업을 하나의 작업전선 이력으로 병합',
        trace:`REMEDIATED / ${event.trace}`,
      };
    }else if(wfIsRemediationInstruction(instruction)){
      const parentInstruction=(run?.instructions||[]).find(item=>item.id===instruction.params?.remediation_parent_instruction_id);
      const parentCommit=(parentInstruction?.commits||[]).find(commit=>commit.id===instruction.params?.remediation_parent_commit_id)||isaacLatestCommit(parentInstruction);
      const facts=wfRemediationFacts(instruction,parentCommit);
      if(event.id.endsWith(':issued')){
        enriched={
          ...enriched,type:'branch',title:'보완 Work Package 하달',status:'재작업 지시',
          desc:`${instruction.params?.equipment_name||'해당 장비'}만 동일 작업전선의 부족량을 추가 굴착하도록 하달했습니다.`,
          actual:`부족량 ${num(facts.remaining)}㎥`,criterion:'최초 Commit 목표량 미달',impact:'재굴착 후 센서 Evidence 재수집',
          trace:`CORRECTION / ${instruction.id} ← ${instruction.params?.remediation_parent_commit_id}`,
        };
      }else if(event.id.endsWith(':dispatched')){
        enriched={...enriched,title:'보완 굴착 실행',desc:'보완 Work Package를 원 장비에 재하달하여 부족 구간만 굴착했습니다.',status:'재작업 실행'};
      }else if(event.id.endsWith(':commit')){
        enriched={
          ...enriched,type:'active',title:'재작업 Commit · 기준 충족',status:event.status==='조치 필요'?'재검증 필요':'재검증 대기',
          desc:'부족량 굴착 결과와 카메라·LiDAR·IMU Evidence를 원 Commit에 연결해 재커밋했습니다.',
          actual:`추가 굴착 ${num(facts.remaining)}㎥`,criterion:'원 완료 기준 재적용',impact:'관리자 재검증 후 원 작업 완료 처리',
          trace:`RECOMMIT / ${event.trace} ← ${instruction.params?.remediation_parent_commit_id}`,
        };
      }else if(event.id.endsWith(':approved')){
        enriched={
          ...enriched,title:'재검증 통과 · 보완 Merge',desc:'추가 굴착 결과가 기준을 충족하여 보완 브랜치를 원 작업전선에 병합했습니다.',
          status:'보완 승인',actual:'부족량 0㎥ · PASS',criterion:'목표 굴착량·Evidence 완전성 충족',impact:'터파기 작업전선 완료 · 다음 공정 READY',
          trace:`MERGE CORRECTION / ${event.trace}`,
        };
      }
    }
    return {...enriched,phaseId:phaseByWorkId.get(event.workId)||'',sortTime:wfHistoryTimeValue(enriched,index)};
  }).sort((a,b)=>a.sortTime-b.sortTime);
}

function wfHistoryEventButton(event,label){
  if(!event)return '<span class="git-node empty">Commit 대기</span>';
  const selected=event.id===workflowUI.historyEventId?'selected':'';
  const evidenceClass=event.instructionId&&event.commitId?'has-evidence':'';
  const evidenceAttributes=event.instructionId&&event.commitId
    ?` data-isaac-detail="${esc(event.instructionId)}" data-isaac-commit="${esc(event.commitId)}" title="Commit 상세 Evidence 열기"`
    :'';
  return `<button class="git-node ${event.type} ${selected} ${evidenceClass}" data-history-event="${esc(event.id)}"${evidenceAttributes}><i></i><span><b>${esc(label||event.title)}</b><small>${esc(event.time)} · ${esc(event.status)}</small></span>${evidenceAttributes?'<em>Evidence ›</em>':''}</button>`;
}

function wfConstructionGitGraph(run,groups,events){
  const visibleGroups=workflowUI.historyZone==='ALL'?groups:groups.filter(group=>group.phase.id===workflowUI.historyZone);
  return `<div class="construction-git-root"><div class="git-main-node"><i></i><div><span>main</span><b>${esc(wfScenarioZoneTitle())} 계획 승인</b><small>${esc(wfConstructionLabel(run))}</small></div></div>${visibleGroups.map(group=>{
    const tone=wfPhaseReviewTone(group);
    const memberBranches=group.primaryMembers.map((instruction,index)=>{
      const params=instruction.params||{};
      const work=wfScenarioInstructionWork(instruction);
      const memberEvents=events.filter(event=>event.workId===work?.id);
      const commitEvent=[...memberEvents].reverse().find(event=>event.id.endsWith(':commit'));
      const decisionEvent=[...memberEvents].reverse().find(event=>event.id.endsWith(':approved')||event.id.endsWith(':rejected'));
      const fallback=[...memberEvents].reverse().find(event=>event.id.endsWith(':dispatched')||event.id.endsWith(':issued'));
      const remediation=wfRemediationForInstruction(group,instruction);
      if(remediation){
        const remediationWork=wfScenarioInstructionWork(remediation);
        const remediationEvents=events.filter(event=>event.workId===remediationWork?.id);
        const remediationIssued=remediationEvents.find(event=>event.id.endsWith(':issued'));
        const remediationCommit=[...remediationEvents].reverse().find(event=>event.id.endsWith(':commit'));
        const remediationDecision=[...remediationEvents].reverse().find(event=>event.id.endsWith(':approved')||event.id.endsWith(':rejected'));
        return `<div class="equipment-git-branch has-remediation"><div class="equipment-git-label"><span>${esc(params.workfront_id||`F${index+1}`)}</span><b>${esc(params.equipment_name||'장비 미배정')}</b><small>재작업 1회 · 원인 연결</small></div><div class="equipment-git-line remediation-path">${wfHistoryEventButton(commitEvent||fallback,'최초 Commit · 목표량 미달')}${wfHistoryEventButton(remediationIssued,'보완 Work Package 하달')}${wfHistoryEventButton(remediationCommit,remediationCommit?'재작업 Commit · 기준 충족':'재작업 Commit 대기')}${remediationDecision?wfHistoryEventButton(remediationDecision,'재검증 승인 · Merge'):''}</div></div>`;
      }
      return `<div class="equipment-git-branch"><div class="equipment-git-label"><span>${esc(params.workfront_id||`F${index+1}`)}</span><b>${esc(params.equipment_name||'장비 미배정')}</b></div><div class="equipment-git-line">${wfHistoryEventButton(commitEvent||fallback,commitEvent?'Evidence Commit':'작업 하달')}${decisionEvent?wfHistoryEventButton(decisionEvent,decisionEvent.type==='merge'?'승인':'반려'):''}</div></div>`;
    }).join('')||`<div class="equipment-git-branch empty"><span>선행 공정 승인 후 Work Package가 생성됩니다.</span></div>`;
    const mergeEvent=[...events].reverse().find(event=>event.phaseId===group.phase.id&&event.type==='merge');
    const phaseIndex=groups.indexOf(group);
    const branchKey=`${run.id}:${group.phase.id}`;
    const expanded=workflowUI.historyBranchesOpen.has(branchKey);
    const branchBodyId=`history-branch-${String(run.id).replace(/[^a-zA-Z0-9_-]/g,'-')}-${String(group.phase.id).replace(/[^a-zA-Z0-9_-]/g,'-')}`;
    return `<section class="phase-git-block ${wfPhaseCss(group.phase,phaseIndex)} ${tone.kind} ${expanded?'expanded':'collapsed'}"><header><button type="button" class="phase-git-toggle" data-history-branch-toggle="${esc(branchKey)}" aria-expanded="${expanded}" aria-controls="${esc(branchBodyId)}"><span class="zone-token ${wfPhaseCss(group.phase,phaseIndex)}">${wfPhaseBadge(group.phase,phaseIndex)}</span><div><b>${esc(group.phase.title)} 브랜치</b><small>Zone ${esc(wfScenarioZoneId())} · ${esc(group.state.label)} · 장비 Commit ${group.commits.length}건</small></div><em class="${tone.kind}">${esc(tone.label)}</em><i class="phase-git-chevron" aria-hidden="true"></i></button></header><div class="phase-git-content" id="${esc(branchBodyId)}" ${expanded?'':'hidden'}><div class="equipment-git-branches">${memberBranches}</div><div class="phase-git-merge"><i></i>${mergeEvent?wfHistoryEventButton(mergeEvent,`${wfPhaseBadge(group.phase,phaseIndex)} Merge`):`<span class="git-node empty">${tone.kind==='locked'?'선행 공정 승인 대기':'관리자 Merge 대기'}</span>`}</div></div></section>`;
  }).join('')}<div class="git-release-node ${groups.every(group=>group.state.kind==='done')?'done':''}"><i></i><div><span>release</span><b>${esc(wfScenarioZoneTitle())} 최종 완료</b><small>${groups.filter(group=>group.state.kind==='done').length}/${groups.length} 공정 Merge</small></div></div></div>`;
}

renderVersions=function(){
  workflowUI.historyStatus=workflowUI.historyStatus||'ALL';
  const runs=wfScenarioRuns();
  const run=wfSelectedConstructionRun(workflowUI.historyRunId);
  const page=$('#page-versions');if(!page)return;
  if(!run){page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 이력</h2><p>Zone별 작업의 Commit과 승인 Merge 흐름을 추적합니다.</p></div></div>${wfBlank('기록된 작업 없음','작업 계획을 하달하면 Git graph 이력이 생성됩니다.')}</div>`;return;}
  workflowUI.historyRunId=run.id;
  const groups=wfConstructionPhaseGroups(run);
  if(workflowUI.historyZone!=='ALL'&&!groups.some(group=>group.phase.id===workflowUI.historyZone))workflowUI.historyZone='ALL';
  const allEvents=wfConstructionHistoryEvents(run);
  let events=workflowUI.historyZone==='ALL'?allEvents:allEvents.filter(event=>event.phaseId===workflowUI.historyZone);
  if(workflowUI.historyStatus==='ACTION')events=events.filter(event=>['warning','branch'].includes(event.type));
  if(workflowUI.historyStatus==='DONE')events=events.filter(event=>event.type==='merge');
  if(workflowUI.historyStatus==='ACTIVE')events=events.filter(event=>['main','active'].includes(event.type));
  const commitCount=run.instructions.reduce((sum,item)=>sum+(item.commits||[]).length,0);
  const mergeCount=allEvents.filter(event=>event.type==='merge').length;
  const conflictCount=allEvents.filter(event=>['warning','branch'].includes(event.type)).length;
  page.innerHTML=`<div class="workflow-page construction-history-page"><div class="workflow-page-head"><div><h2>작업 이력</h2><p>선택한 Zone의 공정 브랜치, 장비별 Evidence Commit과 관리자 Merge 흐름을 한 그래프로 추적합니다.</p></div><label class="construction-run-select"><span>작업 선택</span><select data-history-run>${runs.map(item=>`<option value="${esc(item.id)}" ${item.id===run.id?'selected':''}>${esc(wfConstructionLabel(item))}</option>`).join('')}</select></label></div><div class="history-filter-bar construction-history-filter"><label><span>공정 단계</span><select data-history-zone><option value="ALL">전체 공정</option>${groups.map((group,index)=>`<option value="${esc(group.phase.id)}" ${workflowUI.historyZone===group.phase.id?'selected':''}>${wfPhaseBadge(group.phase,index)} · ${esc(group.phase.title)}</option>`).join('')}</select></label><label><span>이벤트</span><select data-history-status><option value="ALL" ${workflowUI.historyStatus==='ALL'?'selected':''}>전체 이벤트</option><option value="ACTIVE" ${workflowUI.historyStatus==='ACTIVE'?'selected':''}>작업·Commit</option><option value="ACTION" ${workflowUI.historyStatus==='ACTION'?'selected':''}>Conflict·보완</option><option value="DONE" ${workflowUI.historyStatus==='DONE'?'selected':''}>승인·Merge</option></select></label><div class="history-scope-explain"><b>Zone ${esc(wfScenarioZoneId())} · ${esc(wfScenarioZoneTitle())}</b><span>다른 위치의 독립 작업은 별도 Zone으로 분리 관리됩니다.</span></div></div><div class="git-summary"><div><span>Evidence Commit</span><b>${commitCount}</b></div><div><span>Conflict·보완</span><b>${conflictCount}</b></div><div><span>승인 Merge</span><b>${mergeCount}</b></div><div><span>완료 공정</span><b>${groups.filter(group=>group.state.kind==='done').length}/${groups.length}</b></div></div><div class="construction-history-layout"><section class="workflow-panel construction-git-panel"><header><div><span>GIT-LIKE CONSTRUCTION GRAPH · ZONE ${esc(wfScenarioZoneId())}</span><h3>${esc(wfScenarioZoneTitle())} · main</h3><p>Evidence Commit을 누르면 해당 시점의 카메라·LiDAR·IMU Evidence 상세가 열립니다.</p></div><code>${esc(run.id.slice(0,18))}</code></header>${wfConstructionGitGraph(run,groups,events)}</section></div></div>`;
};

document.addEventListener('click',event=>{
  const branchToggle=event.target.closest('[data-history-branch-toggle]');
  if(branchToggle){
    const branchKey=branchToggle.dataset.historyBranchToggle;
    if(workflowUI.historyBranchesOpen.has(branchKey))workflowUI.historyBranchesOpen.delete(branchKey);
    else workflowUI.historyBranchesOpen.add(branchKey);
    renderVersions();
    return;
  }
  const phase=event.target.closest('[data-review-group]');
  if(phase){workflowUI.reviewGroupKey=phase.dataset.reviewGroup;renderEvidence();window.scrollTo({top:0,behavior:'smooth'});return;}
  if(event.target.closest('[data-review-group-back]')){workflowUI.reviewGroupKey=null;renderEvidence();window.scrollTo({top:0,behavior:'smooth'});}
});

document.addEventListener('change',event=>{
  if(event.target.matches('[data-review-run]')){
    workflowUI.reviewRunId=event.target.value;
    workflowUI.reviewGroupKey=null;
    renderEvidence();
  }
  if(event.target.matches('[data-history-run]')){
    workflowUI.historyRunId=event.target.value;
    workflowUI.historyEventId=null;
    workflowUI.historyZone='ALL';
    renderVersions();
  }
});

// app.js booted first; redraw with the workflow renderers now installed.
renderAll(true);
