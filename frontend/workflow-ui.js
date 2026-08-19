/* Manager-workflow UI layer. Isaac rendering and execution remain owned by app.js. */
const workflowUI={mode:'compose',messages:[{role:'assistant',text:'현장 작업을 자연어로 설명해 주세요. Zone, 공종, 작업 구간과 목표량을 확인해 작업지시 초안을 만들겠습니다.'}],draft:null,reviewId:null,settingsTab:'criteria',equipmentId:null,historyZone:'ALL',reviewPhase:'excavation',planView:'drawing',publishing:false};
if(state.selectedPage==='readiness')state.selectedPage='dashboard';

function wfInstructionForWork(w){return (isaacInstructions||[]).find(item=>item.id===w?.isaacInstructionId||item.params?.work_package_id===w?.id)||null;}
function wfCommitForWork(w){const instruction=wfInstructionForWork(w);return instruction?isaacLatestCommit(instruction):null;}
function wfStatus(w){
  const instruction=wfInstructionForWork(w);
  const status=instruction?.status||w?.status;
  if(status==='approved'||status==='accepted'||status==='done'||Number(w?.qualified)>=100)return ['승인 완료','done'];
  if(status==='rejected'||status==='paused')return ['반려·Conflict','warning'];
  if(status==='blocked')return ['자원 대기','warning'];
  if(status==='correction'||status==='correction-issued')return ['보완 중','warning'];
  if(status==='committed'||status==='review'||Number(w?.qualified)>0)return ['검토 대기','review'];
  if(status==='dispatched'||status==='executing')return ['Isaac 실행 중','active'];
  if(status==='pending')return ['Isaac 대기','locked'];
  return ['대기','locked'];
}
function wfProgress(w){
  const instruction=wfInstructionForWork(w);
  if(instruction?.status==='approved')return 100;
  if(['committed','rejected'].includes(instruction?.status))return 100;
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
function wfMapFrame({controls=true,planning=false}={}){return `<div class="workflow-map-shell ${planning?'planning':''}">${controls?`<div class="workflow-map-toolbar map-toolbar"><div class="segmented"><button class="${activeMapLayer==='work'?'active':''}" data-map-layer="work">Work</button><button class="${activeMapLayer==='zone'?'active':''}" data-map-layer="zone">Zone</button><button class="${activeMapLayer==='timeline'?'active':''}" data-map-layer="timeline">Timeline</button></div><button class="ghost-button button-sm" data-action="fit-map">화면 맞춤</button></div>`:''}<iframe class="workflow-map" ${planning?'data-planning-map="1"':''} src="/static/isaac-map-viewer.html?v=20260820-front-masks-4" title="${planning?'관로 도면 작업 예정 구간':'Isaac 현장 맵'}"></iframe><div class="workflow-map-caption"><b>${planning?'도면 작업 예정 구간':activeMapLayer==='zone'?'작업 Zone':activeMapLayer==='timeline'?'Commit Timeline':'현재 현장 맵'}</b><span>${planning?'노란 점선 전체는 Zone A, 내부 색상은 장비별 작업전선 1~3입니다.':activeMapLayer==='zone'?'새 작업 지시의 실제 대상 범위를 표시합니다.':activeMapLayer==='timeline'?'새 승인 Commit을 순서대로 재생합니다.':'관리자 승인으로 Merge된 작업 결과를 표시합니다.'}</span></div>${controls?`<div class="map-timeline-shell map-timeline-control ${activeMapLayer==='timeline'?'active':''}">${timelineControlMarkup()}</div>`:''}</div>`;}

renderDashboard=function(){
  const works=state.workPackages||[];const active=works.filter(w=>!['accepted','done'].includes(w.status)).length;const review=works.filter(w=>wfStatus(w)[1]==='review').length;const correction=works.filter(w=>wfStatus(w)[1]==='warning').length;
  $('#page-dashboard').innerHTML=`<div class="workflow-page">
    <div class="workflow-kpis"><button data-page-link="execution"><span>작업 중</span><b>${active}</b><small>지속 관리 필요</small></button><button data-page-link="evidence"><span>검토 대기</span><b>${review}</b><small>검토·승인 필요</small></button><button data-page-link="evidence"><span>보완 필요</span><b>${correction}</b><small>즉시 확인 필요</small></button><button data-page-link="execution"><span>다음 공정 대기</span><b>${Math.max(0,works.length-active)}</b><small>선행 작업 확인</small></button></div>
    <div class="workflow-dashboard-grid"><section class="workflow-panel map-panel"><header><div><h2>현장 맵 <small>Site Work Map</small></h2><p>작업 위치와 문제 Zone을 한눈에 확인합니다.</p></div><span class="workflow-live">${stageInventory?.connected?'LIVE':'OFFLINE'}</span></header>${wfMapFrame()}</section>
    <aside class="workflow-panel action-panel"><header><div><h2>지금 확인할 작업</h2><p>우선순위가 높은 관리자 조치</p></div></header>${works.slice(0,4).map((w,i)=>{const s=wfStatus(w);return `<button class="workflow-action-row" data-page-link="${s[1]==='review'||s[1]==='warning'?'evidence':'execution'}"><i class="${s[1]}"></i><span><b>${esc(w.zone||'-')} · ${esc(w.name)}</b><small>${s[0]} · ${esc(w.id)}</small></span><em>›</em></button>`}).join('')||wfBlank('등록된 작업 없음','작업 지시에서 첫 작업을 작성하세요.')}</aside></div></div>`;
};

renderWorkPackages=function(){
  const page=$('#page-workpackages');const selected=state.workPackages.find(w=>w.id===state.selectedWpId)||state.workPackages[0]||{};const criteria=wfCriteria(selected);
  if(workflowUI.mode==='form'&&workflowUI.draft){page.innerHTML=wfInstructionForm(workflowUI.draft,criteria);requestAnimationFrame(wireIsaacMapFrames);return;}
  page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 지시</h2><p>대화로 계획을 정리하고, 관리자 확인 후 구조화된 작업지시를 발행합니다.</p></div><button class="ghost-button" data-workflow-action="reset-chat">새 대화</button></div>
  <div class="instruction-layout"><section class="workflow-panel chat-panel"><header><div><h3>SiteGit Planning Assistant</h3><p>대화 내용은 작업지시 초안 작성에만 사용됩니다.</p></div><span class="planning-badge">PLAN ONLY</span></header><div class="workflow-chat" id="workflowChat">${workflowUI.messages.map(m=>`<div class="chat-message ${m.role}"><span>${m.role==='assistant'?'S':'나'}</span><p>${esc(m.text)}</p></div>`).join('')}</div><form class="workflow-prompt" id="workflowPrompt"><textarea id="workflowPromptText" placeholder="예: 이 구역 관로 공사 진행하자."></textarea><button class="primary-button" type="submit">초안 만들기</button></form></section>
  <aside class="instruction-context"><section class="workflow-panel zone-panel"><header><div><h3>현재 맵 · Zone</h3><p>명령 대상의 공간 문맥</p></div></header>${wfMapFrame({controls:false})}</section><section class="workflow-panel criteria-panel"><header><div><h3>적용 작업 기준</h3><p>설정의 현재 프로젝트 기준</p></div><button class="text-button" data-page-link="settings">설정에서 관리</button></header><div class="criteria-list"><div><span>Preset</span><b>${criteria.name}</b></div><div><span>바닥 Level</span><b>±${criteria.tolerance}mm</b></div><div><span>완료 판정 기준</span><b>${criteria.completion}%</b></div><div><span>Evidence 완전성</span><b>${criteria.observation}% 이상</b></div></div></section></aside></div></div>`;
  requestAnimationFrame(wireIsaacMapFrames);
};
function wfInstructionForm(d,c){if(d.design)return wfDrawingInstructionForm(d,c);return `<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업지시 초안</h2><p>AI가 대화 내용을 구조화했습니다. 발행 전 관리자가 모든 값을 확인합니다.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div><div class="instruction-form-layout"><section class="workflow-panel structured-form"><div class="form-section"><h3>작업 기본 정보</h3><div class="workflow-form-grid"><label>작업 구역<input id="wfZone" value="${esc(d.zone)}"></label><label>공종<input id="wfTask" value="${esc(d.task)}"></label><label class="wide">작업명<input id="wfTitle" value="${esc(d.title)}"></label><label>목표 작업량<input id="wfTarget" type="number" value="${d.target}"></label><label>단위<input id="wfUnit" value="${esc(d.unit)}"></label><label class="wide">작업 구간<input id="wfSegment" value="${esc(d.segment)}"></label></div></div><div class="form-section"><h3>완료·승인 판정 기준</h3><div class="criteria-inline"><label>바닥 Level 허용오차<input id="wfTolerance" type="number" value="${c.tolerance}"><span>mm</span></label><label>완료 기준<input id="wfCompletion" type="number" value="${c.completion}"><span>%</span></label><label>Evidence 완전성<input id="wfObservation" type="number" value="${c.observation}"><span>%</span></label></div></div><div class="form-section"><h3>장비·후속 작업</h3><div class="workflow-form-grid"><label>장비 제안<input id="wfEquipment" value="${esc(d.equipment)}"></label><label>후속 작업<input id="wfSuccessor" value="${esc(d.successor)}"></label></div></div><footer><span><b>발행 준비 완료</b> · 관리자 확인 시 Stage 자원을 검증하고 Isaac 실행 대기열로 전송합니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'Isaac 검증·전송 중…':'관리자 확인 · 작업 발행'}</button></footer></section><aside class="workflow-panel precheck"><h3>작업 준비 확인</h3>${[['작업 구역',d.zone],['목표 작업량',`${d.target}${d.unit}`],['완료 기준',c.name],['장비 배정',d.equipment]].map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>발행 후 작업 현황에서 실제 Isaac 상태를 추적할 수 있습니다.</p></aside></div></div>`;}

function wfDesignUnit(unit){return unit==='m3'?'㎥':unit==='ea'?'개':'m';}
function wfCurrentPhaseId(draft){const text=`${draft?.task||''} ${draft?.title||''}`;if(/되메우|복토/.test(text))return 'backfill';if(/관로 설치|관매설|배관 설치/.test(text))return 'pipe_installation';return 'excavation';}
function wfPhaseCriteriaPanel(phases,draft=workflowUI.draft){
  const selected=phases.find(phase=>phase.id===wfCurrentPhaseId(draft))||phases[0];
  if(!selected)return '';
  return `<div class="form-section phase-criteria-section"><div class="section-title-row"><div><h3>Zone ${esc(selected.zone_id)} · ${esc(selected.title)} 완료·승인 판정 기준</h3><p>현재 하달할 공정의 도면 검측 기준만 적용됩니다.</p></div><span>현재 공정</span></div><div class="phase-criteria-list">${(selected.acceptance_criteria||[]).map((criterion,index)=>`<div><i>${index+1}</i><span>${esc(criterion)}</span><b>${index===selected.acceptance_criteria.length-1?'Evidence':'검측'}</b></div>`).join('')}</div></div>`;
}
function wfPipelineDrawing(design){
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
  const fronts=(design.workfronts||[]).map((front,index)=>{const segment=source.filter(point=>point.station>=Number(front.station_start_m)-.01&&point.station<=Number(front.station_end_m)+.01);if(segment.length<2)return '';const line=segment.map(point=>{const projected=project(point);return `${projected.x.toFixed(1)},${projected.y.toFixed(1)}`;}).join(' ');const midpoint=project(segment[Math.floor(segment.length/2)]);const color=frontColors[index%frontColors.length];return `<polyline class="pipeline-front" points="${line}" style="--front:${color}"></polyline><g class="pipeline-zone-label" transform="translate(${midpoint.x.toFixed(1)} ${midpoint.y.toFixed(1)})"><rect x="-39" y="-15" width="78" height="30" rx="6"></rect><text text-anchor="middle" y="-1">ZONE A · F${index+1}</text><text class="equipment" text-anchor="middle" y="10">${esc(front.equipment_id)}</text></g>`;}).join('');
  const stations=source.map((point,index)=>{const projected=project(point);const anchor=index%2?'start':'end';const offset=index%2?10:-10;return `<circle class="pipeline-station" cx="${projected.x.toFixed(1)}" cy="${projected.y.toFixed(1)}" r="4"></circle><text class="pipeline-station-label" x="${(projected.x+offset).toFixed(1)}" y="${(projected.y-9).toFixed(1)}" text-anchor="${anchor}">STA ${point.station.toFixed(1)} · W ${point.width.toFixed(1)}m</text>`;}).join('');
  return `<div class="pipeline-drawing"><svg viewBox="0 0 ${canvas.width} ${canvas.height}" role="img" aria-label="${esc(design.title)} 평면도"><defs><pattern id="drawingGrid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M 24 0 L 0 0 0 24" fill="none" stroke="#bfd7dd" stroke-width=".6"></path></pattern><pattern id="soilHatch" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><line x1="0" y1="0" x2="0" y2="12" stroke="#b9994f" stroke-width="2"></line></pattern></defs><rect width="100%" height="100%" fill="#f6fbfc"></rect><rect width="100%" height="100%" fill="url(#drawingGrid)"></rect><polygon class="pipeline-corridor" points="${polygon}"></polygon><polyline class="pipeline-centerline" points="${centerline}"></polyline>${fronts}${stations}<g class="pipeline-north" transform="translate(54 56)"><circle r="25"></circle><path d="M0 -18 L8 8 L0 3 L-8 8 Z"></path><text y="-28" text-anchor="middle">N</text></g><g class="pipeline-section" transform="translate(714 386)"><rect width="176" height="124" rx="8"></rect><text class="title" x="14" y="22">대표 단면</text><path class="ground" d="M14 48 H162"></path><path class="trench" d="M42 48 L58 101 H118 L134 48"></path><circle class="pipe" cx="88" cy="82" r="18"></circle><text x="14" y="116">깊이 ${design.design_depth_m}m · 관경 Ø${design.pipe_diameter_m}m</text></g><g class="pipeline-title"><text x="78" y="30">${esc(design.plan_id)} · REV.${esc(design.revision)}</text><text class="sub" x="78" y="48">${esc(design.station_range)} · L=${design.total_length_m}m · 좌표 단위 m</text></g></svg><div class="pipeline-drawing-legend"><span><i class="zone-a"></i>Zone A · 터파기</span><span><i class="zone-b"></i>Zone B · 관로 설치</span><span><i class="zone-c"></i>Zone C · 되메우기</span><span><i class="soil"></i>작업전선 1~3</span><b>Zone=공정 · Front=장비별 구간</b></div></div>`;
}

function wfSequentialPhaseInstructionForm(d){
  const design=d.design;const phases=design.phases||[];
  const currentIndex=Math.max(0,phases.findIndex(phase=>phase.id===wfCurrentPhaseId(d)));
  const current=phases[currentIndex]||phases[0];
  const flow=phases.map((phase,index)=>{const stateClass=index<currentIndex?'completed':index===currentIndex?'ready':'locked';const stateLabel=index<currentIndex?'승인 완료':index===currentIndex?'하달 대상':'선행 승인 후';return `<div class="scenario-phase ${stateClass}"><span>${esc(phase.zone_id)}</span><div><b>Zone ${esc(phase.zone_id)} · ${esc(phase.title)}</b><small>${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)} · 약 ${phase.estimated_hours}h</small></div><em>${stateLabel}</em></div>${index<phases.length-1?'<i class="scenario-arrow">→</i>':''}`}).join('');
  const resources=(current.equipment||[]).map(item=>`<div class="workfront-row"><span class="zone-token zone-${String(current.zone_id).toLowerCase()}">ZONE ${esc(current.zone_id)}</span><div><b>${esc(item)}</b><small>${esc(current.title)} 계획 장비</small></div><div><b>${num(current.target_amount)}${wfDesignUnit(current.target_unit)}</b><small>${esc(design.station_range)}</small></div><em class="waiting">발행 시 검증</em></div>`).join('');
  const totalHours=phases.reduce((sum,phase)=>sum+Number(phase.estimated_hours||0),0).toFixed(1);
  return `<div class="workflow-page drawing-plan-page"><div class="workflow-page-head"><div><h2>도면 기반 작업 계획</h2><p>선행 공정 승인 후 열린 현재 공정만 검토하고 하달합니다.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div><div class="drawing-plan-layout"><section class="workflow-panel structured-form"><div class="drawing-reference"><div><span>CURRENT PHASE</span><b>Zone ${esc(current.zone_id)} · ${esc(current.title)}</b><small>${esc(design.plan_id)} · Rev.${esc(design.revision)}</small></div><dl><div><dt>작업 구간</dt><dd>${esc(design.station_range)}</dd></div><div><dt>목표 작업량</dt><dd>${num(current.target_amount)}${wfDesignUnit(current.target_unit)}</dd></div><div><dt>예상 시간</dt><dd>${current.estimated_hours}h</dd></div><div><dt>선행 공정</dt><dd>${(current.depends_on||[]).length?'승인 완료':'없음'}</dd></div></dl></div><div class="form-section"><h3>AI 작업 계획</h3><p class="plan-summary">${esc(d.summary)}</p><div class="scenario-flow">${flow}</div></div><div class="form-section"><div class="section-title-row"><div><h3>Zone ${esc(current.zone_id)} · ${esc(current.title)} 작업 자원</h3><p>현재 공정에 필요한 장비만 발행 시점의 Isaac Stage에서 검증합니다.</p></div><span>현재 공정</span></div><div class="workfront-list">${resources}</div></div>${wfPhaseCriteriaPanel(phases,d)}<input id="wfZone" type="hidden" value="${esc(d.zone)}"><input id="wfTask" type="hidden" value="${esc(d.task)}"><input id="wfTitle" type="hidden" value="${esc(d.title)}"><input id="wfTarget" type="hidden" value="${d.target}"><input id="wfUnit" type="hidden" value="${esc(d.unit)}"><input id="wfSegment" type="hidden" value="${esc(d.segment)}"><input id="wfEquipment" type="hidden" value="${esc(d.equipment)}"><input id="wfSuccessor" type="hidden" value="${esc(d.successor)}"><footer><span><b>현재 공정만 하달</b> · Zone ${esc(current.zone_id)} 승인 전에는 다음 공정이 열리지 않습니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'Isaac 자원 검증 중…':`계획 승인 · ${esc(current.title)} 하달`}</button></footer></section><aside class="drawing-plan-aside"><section class="workflow-panel plan-map-panel"><header><div><h3>${workflowUI.planView==='drawing'?'관로 공사 도면':'현재 공정 작업 구간'}</h3><p>Zone ${esc(current.zone_id)} · ${esc(current.title)}</p></div><div class="plan-view-toggle"><button class="${workflowUI.planView==='map'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="map">현장 3D</button><button class="${workflowUI.planView==='drawing'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="drawing">관로 도면</button></div></header>${workflowUI.planView==='drawing'?wfPipelineDrawing(design):wfMapFrame({controls:false,planning:true})}</section><section class="workflow-panel precheck"><h3>현재 공정 요약</h3>${[['Zone',current.zone_id],['공정',current.title],['목표',`${num(current.target_amount)}${wfDesignUnit(current.target_unit)}`],['전체 순 작업시간',`${totalHours}h`]].map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>과거 Zone의 판정 기준은 이 계획 화면에 다시 표시하지 않습니다.</p></section></aside></div></div>`;
}

function wfDrawingInstructionForm(d,c){
  if(wfCurrentPhaseId(d)!=='excavation')return wfSequentialPhaseInstructionForm(d);
  const design=d.design;const phases=design.phases||[];const fronts=design.workfronts||[];
  const currentPhaseIndex=Math.max(0,phases.findIndex(phase=>phase.id===wfCurrentPhaseId(d)));
  const knownEquipment=new Set((stageInventory?.equipment||[]).filter(item=>item.active).map(item=>item.path));
  const knownTargets=new Set((stageInventory?.diggable_targets||[]).filter(item=>item.active).map(item=>item.path));
  const flow=phases.map((phase,index)=>{const stateClass=index<currentPhaseIndex?'completed':index===currentPhaseIndex?'ready':'locked';const stateLabel=index<currentPhaseIndex?'승인 완료':index===currentPhaseIndex?'하달 대상':'선행 승인 후';return `<div class="scenario-phase ${stateClass}"><span>${esc(phase.zone_id)}</span><div><b>Zone ${esc(phase.zone_id)} · ${esc(phase.title)}</b><small>${num(phase.target_amount)}${wfDesignUnit(phase.target_unit)} · 약 ${phase.estimated_hours}h</small></div><em>${stateLabel}</em></div>${index<phases.length-1?'<i class="scenario-arrow">→</i>':''}`}).join('');
  const frontRows=fronts.map((front,index)=>{const equipmentOk=knownEquipment.has(front.equipment_prim_path);const targetsOk=(front.target_prim_paths||[]).every(path=>knownTargets.has(path));const ready=stageInventory?.connected&&equipmentOk&&targetsOk;return `<div class="workfront-row"><span class="zone-token zone-a">ZONE A · F${index+1}</span><div><b>${esc(front.label)}</b><small>STA ${front.station_start_m} ~ ${front.station_end_m}m · ${num(front.target_volume_m3)}㎥</small></div><div><b>${esc(front.equipment_id)}</b><small>${front.target_prim_paths.length}개 굴착 Prim</small></div><em class="${ready?'ready':'waiting'}">${ready?'실행 가능':'자원 대기'}</em></div>`}).join('');
  const totalHours=phases.reduce((sum,phase)=>sum+Number(phase.estimated_hours||0),0).toFixed(1);
  return `<div class="workflow-page drawing-plan-page"><div class="workflow-page-head"><div><h2>도면 기반 작업 계획</h2><p>LLM이 승인 도면을 조회해 수량·장비·선후 공정을 구성했습니다. 아직 Isaac Stage에는 반영되지 않았습니다.</p></div><button class="ghost-button" data-workflow-action="back-chat">← 대화로 돌아가기</button></div><div class="drawing-plan-layout"><section class="workflow-panel structured-form"><div class="drawing-reference"><div><span>APPROVED DRAWING</span><b>${esc(design.plan_id)} · Rev.${esc(design.revision)}</b><small>${esc(design.title)} · ${esc(design.source_map)}</small></div><dl><div><dt>작업 구간</dt><dd>${esc(design.station_range)}</dd></div><div><dt>총 연장</dt><dd>${design.total_length_m}m</dd></div><div><dt>설계 깊이</dt><dd>${design.design_depth_m}m</dd></div><div><dt>관 외경</dt><dd>${design.pipe_diameter_m}m</dd></div></dl></div><div class="form-section"><h3>AI 작업 계획</h3><p class="plan-summary">${esc(d.summary)}</p><div class="scenario-flow">${flow}</div></div><div class="form-section"><div class="section-title-row"><div><h3>1단계 터파기 작업전선</h3><p>3대가 독립 구간을 작업하고 각각 Evidence Commit을 생성합니다.</p></div><span>${fronts.length}개 Work Package</span></div><div class="workfront-list">${frontRows}</div></div>${wfPhaseCriteriaPanel(phases)}<input id="wfZone" type="hidden" value="${esc(d.zone)}"><input id="wfTask" type="hidden" value="${esc(d.task)}"><input id="wfTitle" type="hidden" value="${esc(d.title)}"><input id="wfTarget" type="hidden" value="${d.target}"><input id="wfUnit" type="hidden" value="${esc(d.unit)}"><input id="wfSegment" type="hidden" value="${esc(d.segment)}"><input id="wfEquipment" type="hidden" value="${esc(d.equipment)}"><input id="wfSuccessor" type="hidden" value="${esc(d.successor)}"><footer><span><b>관리자 승인 시 1단계만 하달</b> · 관로 설치와 되메우기는 선행 Evidence 승인 전까지 잠깁니다.</span><button class="primary-button" data-workflow-action="publish-instruction" ${workflowUI.publishing?'disabled':''}>${workflowUI.publishing?'3개 작업전선 검증 중…':'계획 승인 · 터파기 3건 하달'}</button></footer></section><aside class="drawing-plan-aside"><section class="workflow-panel plan-map-panel"><header><div><h3>${workflowUI.planView==='drawing'?'관로 공사 도면':'도면 작업 예정 구간'}</h3><p>${workflowUI.planView==='drawing'?'중심선·STA·굴착 폭·대표 단면':'채움 토사 위의 관로 중심선과 3개 작업전선'}</p></div><div class="plan-view-toggle"><button class="${workflowUI.planView==='map'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="map">현장 3D</button><button class="${workflowUI.planView==='drawing'?'active':''}" data-workflow-action="set-plan-view" data-plan-view="drawing">관로 도면</button></div></header>${workflowUI.planView==='drawing'?wfPipelineDrawing(design):wfMapFrame({controls:false,planning:true})}</section><section class="workflow-panel precheck"><h3>계획 요약</h3>${[['도면',`${design.plan_id} Rev.${design.revision}`],['총 공정','터파기 → 관로 설치 → 되메우기'],['예상 순 작업시간',`${totalHours}h`],['굴착 장비',`${fronts.length}대`]].map(x=>`<div><i>✓</i><span>${x[0]}</span><b>${esc(String(x[1]))}</b></div>`).join('')}<p>자원이 없는 작업전선도 삭제하지 않고 자원 대기 상태로 기록합니다.</p></section></aside></div></div>`;
}

function renderExecution(){const page=$('#page-execution');if(!page)return;const works=state.workPackages||[];const statusKinds=['active','review','warning','done'];page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 현황</h2><p>진행·검토·보완·잠김 상태와 선후 공정 관계를 한 화면에서 확인합니다.</p></div><button class="primary-button" data-page-link="workpackages">+ 새 작업 지시</button></div><div class="workflow-kpis compact">${['진행 중','검토 대기','보완 중','완료'].map((x,i)=>`<div><span>${x}</span><b>${works.filter(w=>wfStatus(w)[1]===statusKinds[i]).length}</b></div>`).join('')}</div><section class="workflow-panel workflow-table"><div class="workflow-table-head"><span>작업 / Zone</span><span>장비</span><span>진척도</span><span>상태</span><span>후속 영향</span></div>${works.map(w=>{const s=wfStatus(w);const progress=wfProgress(w);return `<button class="workflow-table-row" ${wfInstructionForWork(w)?`data-real-wp-detail="${esc(wfInstructionForWork(w).id)}"`:`data-review-open="${esc(w.id)}"`}><span><b>${esc(w.zone)} · ${esc(w.name)}</b><small>${esc(w.id)}</small></span><span>${esc(wfEquipmentLabel(w)||'-')}</span><span><i style="--p:${progress}%"></i>${progress}%</span><span><em class="${s[1]}">${s[0]}</em></span><span>${s[1]==='warning'?'후속 공정 잠김':'영향 없음'} ›</span></button>`}).join('')||wfBlank('작업 없음','작업 지시를 발행하면 여기에 표시됩니다.')}</section></div>`;}

renderEvidence=function(){const page=$('#page-evidence');const works=state.workPackages||[];if(workflowUI.reviewId){const w=works.find(x=>x.id===workflowUI.reviewId);if(w){page.innerHTML=wfReviewDetail(w);return;}workflowUI.reviewId=null;}page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>검토·승인</h2><p>작업 결과의 검토 대상과 우선순위를 확인하고 상세 검토로 이동합니다.</p></div><button class="ghost-button" data-workflow-action="refresh">↻ 새로고침</button></div><div class="review-layout"><section><div class="workflow-kpis compact">${[['검토 필요','review'],['보완 중','warning'],['재검증 대기','locked'],['승인 완료','done']].map(x=>`<div><span>${x[0]}</span><b>${works.filter(w=>wfStatus(w)[1]===x[1]).length}</b></div>`).join('')}</div><div class="workflow-panel review-list">${works.map(w=>{const s=wfStatus(w);return `<button data-review-open="${esc(w.id)}"><span><b>${esc(w.zone)} · ${esc(w.name)}</b><small>${esc(w.id)}</small></span><span>${wfProgress(w)}%</span><em class="${s[1]}">${s[0]}</em><span>${s[1]==='warning'?'후속 작업 LOCKED':'상세 보기'} →</span></button>`}).join('')}</div></section><aside class="workflow-panel review-priority"><h3>우선 검토 작업</h3>${works[0]?`<b>${esc(works[0].zone)} · ${esc(works[0].name)}</b><div><span>진척도</span><strong>${wfProgress(works[0])}%</strong></div><button class="primary-button" data-review-open="${esc(works[0].id)}">상세 검토로 이동 →</button>`:wfBlank('대상 없음','검토할 작업이 없습니다.')}</aside></div></div>`;};
const REVIEW_PHASES={
  excavation:{label:'굴착',image:'/static/assets/review/pipeline-excavation-demo.png',criterion:'굴착 저면 ±50mm',actual:'최대 편차 -82mm',segment:'14.2m ~ 17.6m',shortfall:'32mm 부족'},
  installation:{label:'관로 매설',image:'/static/assets/review/pipeline-installation-demo.png',criterion:'관 중심선 ±100mm',actual:'최대 편차 +136mm',segment:'22.0m ~ 24.5m',shortfall:'36mm 초과'},
  backfill:{label:'되메우기',image:'/static/assets/review/pipeline-backfill-demo.png',criterion:'층별 다짐도 90% 이상',actual:'최저 다짐도 87%',segment:'28.0m ~ 30.0m',shortfall:'3% 부족'}
};
function wfReviewDemoVisual(){const phase=REVIEW_PHASES[workflowUI.reviewPhase]||REVIEW_PHASES.excavation;return `<div class="review-phase-head"><div class="review-phase-tabs">${Object.entries(REVIEW_PHASES).map(([key,value])=>`<button class="${key===workflowUI.reviewPhase?'active':''}" data-review-phase="${key}">${value.label}</button>`).join('')}</div><span class="review-demo-badge">DEMO · 예상 시각자료</span></div><div class="review-diff-toolbar"><div class="profile-legend"><i class="design-shape"></i>설계 형상<i class="actual-shape"></i>실제 형상<i class="deep-diff"></i>차이(깊게 파임)<i class="shallow-diff"></i>차이(얕게 파임)</div><span>작업 범위</span></div><div class="review-diff-scene"><svg viewBox="0 0 1000 400" role="img" aria-label="${phase.label} 설계 형상과 실제 형상 차이 시연"><defs><pattern id="sceneGrid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#26343b" stroke-width="1"/></pattern><pattern id="meshWhite" width="19" height="15" patternUnits="userSpaceOnUse"><path d="M19 0H0V15M0 0L19 15" fill="none" stroke="#d6dfe2" stroke-opacity=".48" stroke-width="1"/></pattern><pattern id="meshGreen" width="18" height="13" patternUnits="userSpaceOnUse"><path d="M18 0H0V13M0 0L18 13" fill="none" stroke="#8dde91" stroke-opacity=".68" stroke-width="1"/></pattern><pattern id="meshRed" width="16" height="12" patternUnits="userSpaceOnUse"><path d="M16 0H0V12M0 0L16 12" fill="none" stroke="#ff8577" stroke-opacity=".75" stroke-width="1"/></pattern></defs><rect width="1000" height="400" fill="#071116"/><path d="M0 305L270 84H1000L1000 400H0Z" fill="url(#sceneGrid)" opacity=".72"/><polygon points="105,267 265,116 885,177 747,329" fill="#0b171c" stroke="#d4a928" stroke-width="3" stroke-dasharray="9 7"/><polygon points="135,254 279,137 848,189 721,305" fill="url(#meshWhite)" stroke="#aebbc0" stroke-opacity=".72" stroke-width="2"/><polygon points="192,251 320,158 658,190 562,278" fill="#295c39" fill-opacity=".72" stroke="#65ba72" stroke-width="2"/><polygon points="192,251 320,158 658,190 562,278" fill="url(#meshGreen)"/><polygon points="528,271 607,178 790,195 718,291" fill="#8d2020" fill-opacity=".88" stroke="#ef493d" stroke-width="3"/><polygon points="528,271 607,178 790,195 718,291" fill="url(#meshRed)"/><path d="M244 242L704 220" stroke="#72c779" stroke-width="5" opacity=".65"/><path d="M522 266L711 239" stroke="#ff4f45" stroke-width="5" opacity=".85"/><g class="scene-label"><rect x="34" y="116" width="92" height="35" rx="5"/><text x="52" y="139">Zone ${esc(String(workflowUI.reviewId||'C').slice(-1))}</text></g><g class="scene-alert"><path d="M680 80V172"/><rect x="590" y="38" width="180" height="57" rx="5"/><text x="617" y="62">문제 구간</text><text x="610" y="84">${phase.segment}</text></g><g class="scene-axis"><path d="M53 334v-42M53 334l34 12M53 334l-24 17"/><text x="50" y="282">Z</text><text x="93" y="352">X</text><text x="15" y="359">Y</text></g><g class="scene-scale"><text x="35" y="385">0m</text><text x="274" y="385">10m</text><text x="486" y="385">14.2m</text><text x="634" y="385">17.6m</text><text x="825" y="385">30m</text></g></svg><div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="review-profile-chart"><header><div><b>${phase.label} Level Profile</b><span>설계 기준과 예상 실측값의 차이를 동일 구간 축으로 비교</span></div><div class="profile-legend"><i class="design"></i>설계 Level<i class="actual"></i>실제 Level<i class="issue"></i>허용 범위</div></header><svg viewBox="0 0 900 190" role="img" aria-label="${phase.label} 공정 프로파일 차이 예시"><defs><linearGradient id="issueFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#c94c32" stop-opacity=".28"/><stop offset="1" stop-color="#c94c32" stop-opacity=".04"/></linearGradient></defs><g class="profile-grid"><path d="M55 35H870M55 70H870M55 105H870M55 140H870"/><path d="M55 20V155M220 20V155M385 20V155M550 20V155M715 20V155M870 20V155"/></g><rect x="55" y="70" width="815" height="45" class="tolerance-band"/><path class="design-line" d="M55 92H870"/><path class="actual-line" d="M55 87 C140 82 180 96 250 90 S360 86 420 92 C470 98 500 133 555 137 S640 112 700 94 S810 89 870 92"/><path class="issue-area" d="M420 92 C470 98 500 133 555 137 S640 112 700 94 L700 92 L420 92Z"/><line x1="420" y1="25" x2="420" y2="150" class="issue-edge"/><line x1="700" y1="25" x2="700" y2="150" class="issue-edge"/><text x="55" y="178">0m</text><text x="210" y="178">10m</text><text x="405" y="178">14.2m</text><text x="680" y="178">17.6m</text><text x="845" y="178">32m</text><text x="505" y="54" class="issue-label">문제 구간 ${phase.segment}</text></svg><div class="profile-metrics"><div><span>판정 기준</span><b>${phase.criterion}</b></div><div><span>예상 실측</span><b>${phase.actual}</b></div><div class="danger"><span>기준 차이</span><b>${phase.shortfall}</b></div></div></div>`;}
function wfReviewPhaseForWork(w){const zone=String(w?.zone||'').replace(/zone\s*/i,'').trim().toUpperCase();if(zone==='B')return {...REVIEW_PHASES.installation,image:'/static/assets/review/zone-b-pipe-installation-diff-v2.png',approvedImage:'/static/assets/review/zone-b-pipe-installation-approved-v2.png',zone};if(zone==='C'||zone==='D')return {...REVIEW_PHASES.backfill,image:'/static/assets/review/zone-c-backfill-diff-v2.png',approvedImage:'/static/assets/review/zone-c-backfill-approved-v2.png',zone};if(zone==='H')return {label:'반출·운반',image:'/static/assets/review/zone-h-haul-route-diff-v1.png',approvedImage:'/static/assets/review/zone-h-haul-route-diff-v1.png',criterion:'계획 반출량 700㎥ · 운반 종료 이벤트',actual:'누적 반출량 231㎥',segment:'현장 출구 연결 구간',shortfall:'469㎥ 잔여',zone};return {...REVIEW_PHASES.excavation,image:'/static/assets/review/zone-a-excavation-diff-v2.png',approvedImage:'/static/assets/review/zone-a-excavation-approved-v2.png',zone:zone||'A'};}
function wfReviewWorkVisual(w){const phase=wfReviewPhaseForWork(w);return `<div class="review-zone-head"><div><span>ZONE ${esc(phase.zone)}</span><b>${phase.label} 결과 비교</b><small>선택한 작업의 설계 형상과 결과 형상을 비교합니다.</small></div><span class="review-demo-badge">DEMO · 예상 시각자료</span></div><div class="review-diff-toolbar"><div class="profile-legend"><i class="design-shape"></i>설계 형상<i class="actual-shape"></i>실제 형상<i class="deep-diff"></i>기준 미달 영역<i class="shallow-diff"></i>작업 범위</div><span>Zone ${esc(phase.zone)} · ${phase.label}</span></div><div class="review-zone-visual"><img src="${phase.image}" alt="Zone ${esc(phase.zone)} ${phase.label} 설계·결과 Diff 시연 이미지"><div class="review-zone-callout"><b>문제 구간</b><span>${phase.segment}</span></div><div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="review-profile-chart"><header><div><b>${phase.label} Level Profile</b><span>Zone ${esc(phase.zone)}의 설계 기준과 결과 값을 동일 구간 축으로 비교</span></div><div class="profile-legend"><i class="design"></i>설계 Level<i class="actual"></i>결과 Level<i class="issue"></i>허용 범위</div></header><svg viewBox="0 0 900 190" role="img" aria-label="Zone ${esc(phase.zone)} ${phase.label} 결과 프로파일"><defs><linearGradient id="issueFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#c94c32" stop-opacity=".28"/><stop offset="1" stop-color="#c94c32" stop-opacity=".04"/></linearGradient></defs><g class="profile-grid"><path d="M55 35H870M55 70H870M55 105H870M55 140H870"/><path d="M55 20V155M220 20V155M385 20V155M550 20V155M715 20V155M870 20V155"/></g><rect x="55" y="70" width="815" height="45" class="tolerance-band"/><path class="design-line" d="M55 92H870"/><path class="actual-line" d="M55 87 C140 82 180 96 250 90 S360 86 420 92 C470 98 500 133 555 137 S640 112 700 94 S810 89 870 92"/><path class="issue-area" d="M420 92 C470 98 500 133 555 137 S640 112 700 94 L700 92 L420 92Z"/><line x1="420" y1="25" x2="420" y2="150" class="issue-edge"/><line x1="700" y1="25" x2="700" y2="150" class="issue-edge"/><text x="55" y="178">0m</text><text x="210" y="178">10m</text><text x="405" y="178">14.2m</text><text x="680" y="178">17.6m</text><text x="845" y="178">32m</text><text x="505" y="54" class="issue-label">문제 구간 ${phase.segment}</text></svg><div class="profile-metrics"><div><span>판정 기준</span><b>${phase.criterion}</b></div><div><span>결과 값</span><b>${phase.actual}</b></div><div class="danger"><span>기준 차이</span><b>${phase.shortfall}</b></div></div></div>`;}
function wfReviewDetail(w){const e=state.evidence?.[w.id]||{};const c=wfCriteria(w);const progress=wfProgress(w);const phase=wfReviewPhaseForWork(w);return `<div class="workflow-page"><button class="workflow-back" data-review-back>← 검토 목록</button><div class="workflow-page-head"><div><h2>Zone ${esc(phase.zone)} · ${phase.label}</h2><p>${esc(w.id)} · ${esc(w.name)} 결과 상세 검토</p></div><span class="status-chip warning">검토 필요</span></div><div class="review-detail"><section><div class="workflow-kpis compact review-progress-summary"><div><span>진척도</span><b>${progress}%</b></div><div><span>보완 대상</span><b>${Math.max(0,100-progress)}%</b></div></div><div class="workflow-panel review-visual">${wfReviewWorkVisual(w)}</div></section><aside class="workflow-panel review-decision"><h3>판정 및 조치</h3><div class="decision-alert"><b>${e.conflicts?.[0]?.title||`${phase.label} 결과 확인 필요`}</b><span>${phase.criterion} · Evidence ${e.completeness||0}%</span></div><div class="decision-box"><span>다음 공정 영향</span><b>${(e.conflicts||[]).length?'시작 불가 · LOCKED':'판정 대기'}</b></div><h4>완료 기준</h4>${[['진척도',progress>=100],[phase.label+' 기준',!(e.conflicts||[]).length],['Evidence',Number(e.completeness||0)>=c.observation]].map(x=>`<div class="decision-rule"><i class="${x[1]?'pass':'fail'}">${x[1]?'✓':'×'}</i><span>${x[0]}</span><b>${x[1]?'PASS':'CHECK'}</b></div>`).join('')}<div class="decision-actions"><button class="ghost-button" data-workflow-action="request-evidence">추가 근거 요청</button><button class="primary-button" data-workflow-action="issue-correction">보완 작업 발행</button></div></aside></div></div>`;}

renderVersions=function(){const works=state.workPackages||[];const zones=[...new Set(works.map(w=>String(w.zone||'')).filter(Boolean))].sort();const visible=workflowUI.historyZone==='ALL'?works:works.filter(w=>String(w.zone)===workflowUI.historyZone);$('#page-versions').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>작업 이력</h2><p>기준 작업과 보완 Work Package의 분기·재검증·승인 병합 흐름을 추적합니다.</p></div><label class="history-zone-filter">Zone<select data-history-zone><option value="ALL">전체 Zone</option>${zones.map(z=>`<option value="${esc(z)}" ${workflowUI.historyZone===z?'selected':''}>Zone ${esc(z)}</option>`).join('')}</select></label></div><div class="git-summary"><div><span>기준 작업</span><b>${visible.length}</b></div><div><span>보완 브랜치</span><b>${visible.filter(w=>w.status==='correction'||(state.evidence?.[w.id]?.conflicts||[]).length).length}</b></div><div><span>승인·병합</span><b>${visible.filter(w=>wfStatus(w)[1]==='done').length}</b></div></div><section class="workflow-panel git-history"><header><div><h3>Work Package Graph</h3><p>보완 작업은 원본 작업에서 분기되고 승인되면 기준 이력으로 병합됩니다.</p></div><span class="git-branch-label">main / Plan v1.0</span></header><div class="git-graph">${visible.map(w=>wfGitBranch(w)).join('')||wfBlank('표시할 이력 없음','다른 Zone을 선택하거나 작업을 발행해 주세요.')}</div></section></div>`;};
function wfGitBranch(w){const e=state.evidence?.[w.id]||{};const hasCorrection=w.status==='correction'||(e.conflicts||[]).length>0;const done=wfStatus(w)[1]==='done';const progress=wfProgress(w);return `<article class="git-lane ${hasCorrection?'has-branch':''}"><div class="git-rail"><i class="commit main"></i>${hasCorrection?'<i class="branch-line"></i>':''}</div><div class="git-commit"><div class="git-commit-head"><span class="git-hash">${esc(w.id)}</span><b>Zone ${esc(w.zone)} · ${esc(w.name)}</b><em>v${w.version||1}</em></div><p>작업 지시 발행 · 진척도 ${progress}%</p><small>main · ${esc(w.start||'계획')}</small></div>${hasCorrection?`<div class="git-correction"><div class="git-rail correction"><i class="commit warning"></i>${done?'<i class="merge-line"></i>':''}</div><div><div class="git-commit-head"><span class="git-hash">CORR-${esc(w.id.split('-').at(-1))}</span><b>보완 Work Package</b><em>branch</em></div><p>${esc(e.conflicts?.[0]?.title||'완료 기준 미충족 구간 보완')}</p><small>correction/zone-${esc(String(w.zone).toLowerCase())}</small></div></div>`:''}${done?`<div class="git-merge"><div class="git-rail"><i class="commit merged">✓</i></div><div><div class="git-commit-head"><span class="git-hash">MERGE</span><b>재검증 통과 · 관리자 승인</b><em>merged</em></div><p>보완 결과를 기준 작업 이력에 병합하고 다음 공정을 Release</p></div></div>`:''}</article>`;}

renderEquipment=function(){const equipment=state.equipment||[];if(!workflowUI.equipmentId||!equipment.some(e=>e.id===workflowUI.equipmentId))workflowUI.equipmentId=equipment[0]?.id;const selected=equipment.find(e=>e.id===workflowUI.equipmentId);const available=equipment.filter(e=>e.status==='available').length;$('#page-equipment').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>장비관리</h2><p>장비 상태, Capability, 현재 작업과 Evidence 반환 능력을 한 화면에서 확인합니다.</p></div><div class="button-row"><button class="ghost-button" data-workflow-action="equipment-filter">필터</button><button class="primary-button" data-workflow-action="add-equipment">+ 장비 등록</button></div></div><div class="equipment-status-strip"><div><span>전체</span><b>${equipment.length}</b></div><div><span>사용 가능</span><b>${available}</b></div><div><span>작업 중</span><b>${equipment.filter(e=>e.status==='working').length}</b></div><div><span>오프라인</span><b>${equipment.filter(e=>e.status==='offline').length}</b></div></div><div class="equipment-master-detail"><section class="workflow-panel equipment-list-panel"><div class="equipment-search">⌕ <input placeholder="장비명 / 모델 검색" data-equipment-search></div><div class="equipment-list">${equipment.map(e=>`<button class="${e.id===workflowUI.equipmentId?'active':''}" data-equipment-select="${esc(e.id)}"><img src="${EQUIPMENT_PHOTOS[e.model]||''}" alt=""><span><b>${esc(e.id)}</b><small>${esc(e.manufacturer)} · ${esc(e.type)}</small></span><em class="${esc(e.status)}">${e.status==='available'?'사용 가능':e.status==='working'?'작업 중':e.status==='offline'?'오프라인':'대기'}</em></button>`).join('')}</div></section>${selected?wfEquipmentDetail(selected):`<section class="workflow-panel">${wfBlank('등록 장비 없음','장비를 등록해 주세요.')}</section>`}</div></div>`;};
function wfEquipmentDetail(e){const image=EQUIPMENT_PHOTOS[e.model];return `<section class="workflow-panel equipment-detail"><div class="equipment-detail-head"><div><h2>${esc(e.id)}</h2><p>${esc(e.manufacturer)} · ${esc(e.type)}</p></div><span class="equipment-state ${esc(e.status)}">${e.status==='available'?'사용 가능':e.status==='working'?'작업 중':e.status==='offline'?'오프라인':'대기'}</span></div><div class="equipment-detail-grid"><div class="equipment-profile">${image?`<img src="${image}" alt="${esc(e.model)}">`:machineSvg(e.icon,e.color)}<dl><div><dt>운전중량</dt><dd>${e.operatingWeight||'-'}t</dd></div><div><dt>버킷</dt><dd>${e.bucketCapacity||'-'}㎥</dd></div><div><dt>최대 굴착 깊이</dt><dd>${e.maxDepth||'-'}m</dd></div><div><dt>정격 출력</dt><dd>${e.power||'-'}kW</dd></div><div><dt>제조사</dt><dd>${esc(e.manufacturer)}</dd></div></dl><button class="ghost-button" data-workflow-action="edit-equipment">장비 수정</button></div><div class="equipment-operations"><h3>운영 연결 정보</h3><div><span>작업 가능 범위</span><p>${(e.supports||[]).map(x=>`<b>${esc(x)}</b>`).join('')}</p></div><div><span>적용 Zone</span><p><b>${esc((e.assigned||'미배정').replace('WP-SASANG-','Zone '))}</b></p></div><div><span>현재 작업</span><p>${esc(e.assigned||'현재 WP 없음')}</p></div><div><span>반환 가능한 작업 근거</span><p>${(e.evidence||[]).map(x=>`<b>✓ ${esc(x)}</b>`).join('')}</p></div><div><span>연결 상태</span><p><b>${e.status==='offline'?'연결 확인 필요':'정상'}</b> · ${esc(e.specSource||'')}</p></div></div></div></section>`;}

renderSettings=function(){const p=state.project;const tab=workflowUI.settingsTab;$('#page-settings').innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>설정</h2><p>작업 기준, 프로젝트 정보와 데이터 연결을 통합 관리합니다.</p></div></div><div class="settings-tabs">${[['criteria','작업 기준'],['project','프로젝트 설정'],['integration','데이터 연동']].map(x=>`<button class="${tab===x[0]?'active':''}" data-settings-tab="${x[0]}">${x[1]}</button>`).join('')}</div>${tab==='criteria'?wfSettingsCriteria():tab==='project'?`<section class="workflow-panel settings-content"><h3>프로젝트 설정</h3><div class="settings-summary"><div><span>프로젝트명</span><b>${esc(p.name)}</b></div><div><span>현장 위치</span><b>${esc(p.location)}</b></div><div><span>Plan</span><b>v1.0</b></div><div><span>좌표계</span><b>${esc(p.coordinateSystem)}</b></div></div><button class="ghost-button" data-workflow-action="open-project">기본정보 수정</button></section>`:`<section class="workflow-panel settings-content"><h3>데이터 연동</h3><div class="integration-grid"><div><b>Isaac Sim</b><span>${stageInventory?.connected?'연결됨':'미연동'}</span><small>실행 결과 데이터</small></div><div><b>Shared Database</b><span>${remoteReady?'정상':'확인 필요'}</span><small>프로젝트 공동 데이터</small></div><div><b>장비 Gateway</b><span>Demo Mode</span><small>실제 장비 API 미연동</small></div></div><p class="settings-note">Isaac 미연동 상태를 임의 데이터로 대체하지 않습니다.</p></section>`}</div>`;};
function wfSettingsCriteria(){const c=wfCriteria(state.workPackages[0]);return `<section class="workflow-panel settings-content"><div class="criteria-settings-head"><div><h3>${c.name}</h3><p>작업 준비 조건과 완료·승인 기준을 프로젝트 단위로 관리합니다.</p></div><span>현재 프로젝트 적용 중</span></div><div class="criteria-settings-grid"><div><h4>작업 준비 조건</h4><p>✓ 작업 구역 Geometry</p><p>✓ 목표 작업량</p><p>△ 보호구역 관리자 확인</p><p>✓ 장비 Capability</p></div><div><h4>완료·승인 판정 기준</h4><p><span>바닥 Level</span><b>±${c.tolerance}mm</b></p><p><span>완료 진척도</span><b>${c.completion}%</b></p><p><span>Evidence 완전성</span><b>${c.observation}% 이상</b></p></div><div><h4>후속 공정 조건</h4><p>모든 기준 충족 → READY</p><p>기준 미충족 → LOCKED</p></div></div></section>`;}

function wfDraftFromText(text){const zone=(text.match(/zone\s*([a-z])/i)||text.match(/([A-D])\s*(?:구역|존)/i)||[])[1]||'C';const nums=[...text.matchAll(/(\d+(?:\.\d+)?)\s*(m³|㎥|m|미터)/gi)];const target=Number(nums.at(-1)?.[1]||20);const seg=text.match(/(\d+(?:\.\d+)?)\s*m?\s*[~～-]\s*(\d+(?:\.\d+)?)\s*m/i);return {zone:`Zone ${String(zone).toUpperCase()}`,task:text.includes('굴착')?'굴착':text.includes('정지')?'정지':'관로 터파기',title:`Zone ${String(zone).toUpperCase()} · ${text.includes('굴착')?'굴착':'관로 터파기'}`,target,unit:nums.at(-1)?.[2]?.includes('³')||nums.at(-1)?.[2]==='㎥'?'㎥':'m',segment:seg?`${seg[1]}m ~ ${seg[2]}m`:'관리자 확인 필요',equipment:'HX210AL-01',successor:'관 설치'};}
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
    workflowUI.messages.push({role:'assistant',text:`도면 ${design.plan_id}의 터파기 작업전선 ${payload.work_packages.length}건을 하달했습니다. 실행 가능 ${pending}건, 자원 대기 ${blocked}건입니다.`});
    workflowUI.mode='compose';workflowUI.draft=null;setIsaacPlanningOverlay(null);
    await loadIsaacInstructions();navigate('execution');renderAll();
    toast('도면 기반 터파기 하달 완료',`실행 가능 ${pending}건 · 자원 대기 ${blocked}건` ,blocked?'warning':'success');
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
    if(!codeDraft.plan?.ready)throw new Error(codeDraft.plan?.clarification_question||'Isaac 실행에 필요한 작업 정보가 부족합니다.');
    const data=await submitCodeWorkPackageDraft(codeDraft,display);
    const record=data.work_package;
    workflowUI.messages.push({role:'assistant',text:`${record.summary} 작업이 ${record.status==='blocked'?'자원 대기 상태로 저장':'Isaac 실행 대기열에 전송'}되었습니다.`});
    workflowUI.mode='compose';
    workflowUI.draft=null;
    navigate('execution');
    renderAll();
    toast(record.status==='blocked'?'Work Package 자원 대기':'Isaac 작업 전송 완료',record.status==='blocked'?(record.missing_resources||[]).join(' · '):'실제 Isaac Adapter 실행 대기열에 등록했습니다.',record.status==='blocked'?'warning':'success');
  }catch(error){
    toast('작업 발행 실패',String(error.message||error),'danger');
  }finally{
    workflowUI.publishing=false;
    if(workflowUI.mode==='form')renderWorkPackages();
  }
}
document.addEventListener('submit',async e=>{if(e.target.id!=='workflowPrompt')return;e.preventDefault();const input=$('#workflowPromptText');const text=input.value.trim();if(!text)return;const submit=e.target.querySelector('button[type="submit"]');submit.disabled=true;submit.textContent='도면·계획 해석 중…';workflowUI.messages.push({role:'user',text});try{const response=await apiFetch('/work-packages/ai/planning/interpret',{method:'POST',body:JSON.stringify({project_id:PROJECT_ID,message:text})});const payload=await response.json();if(!response.ok)throw new Error(payload?.detail?.message||'작업지시 해석에 실패했습니다.');const p=payload.plan;if(!p.ready){workflowUI.messages.push({role:'assistant',text:p.clarification_question||'작업 구역과 목표량을 조금 더 구체적으로 알려주세요.'});renderWorkPackages();return;}workflowUI.messages.push({role:'assistant',text:p.summary});workflowUI.draft={sourceText:payload.source_text||text,summary:p.summary,zone:payload.design?.work_area_label||`Zone ${p.zone_id}`,task:p.work_type,title:p.title,target:p.target_amount,unit:p.target_unit==='m3'?'㎥':p.target_unit==='ea'?'대':'m',segment:p.segment,equipment:p.equipment_hint,successor:p.successor_title,design:payload.design||null};workflowUI.planView=payload.design?'drawing':'map';setIsaacPlanningOverlay(payload.design||null);workflowUI.mode='form';renderWorkPackages();}catch(error){workflowUI.messages.push({role:'assistant',text:`LLM에 연결하지 못했습니다. ${error.message}`});renderWorkPackages();toast('작업지시 초안 생성 실패',error.message,'warning');}finally{if(submit?.isConnected){submit.disabled=false;submit.textContent='초안 만들기';}}});
document.addEventListener('input',e=>{if(!e.target.matches('[data-equipment-search]'))return;const query=e.target.value.trim().toLowerCase();$$('.equipment-list>button').forEach(row=>row.classList.toggle('hidden',!row.textContent.toLowerCase().includes(query)));});
document.addEventListener('change',e=>{if(!e.target.matches('[data-history-zone]'))return;workflowUI.historyZone=e.target.value;renderVersions();});
document.addEventListener('click',e=>{const phase=e.target.closest('[data-review-phase]');if(!phase)return;workflowUI.reviewPhase=phase.dataset.reviewPhase;renderEvidence();});
document.addEventListener('click',async e=>{
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
  if(action==='equipment-filter')toast('상태 필터','목록 상단의 상태별 수치를 기준으로 장비를 탐색할 수 있습니다.','success');
  if(action==='request-evidence'){state.selectedWpId=workflowUI.reviewId;addEvidence();}
  if(action==='issue-correction'){state.selectedWpId=workflowUI.reviewId;createCorrection();}
  if(action==='publish-instruction')await publishWorkflowInstruction();
});

function wfZoneProfile(phase,approved){const zone=phase.zone;if(zone==='B')return approved?{design:'M55 72 C250 78 500 96 870 112',actual:'M55 75 C250 80 500 92 870 109',start:430,end:650,value:'중심선 편차 +32mm'}:{design:'M55 72 C250 78 500 96 870 112',actual:'M55 75 C250 80 420 91 C500 142 580 137 650 102 C730 102 800 108 870 113',start:420,end:650,value:'중심선 편차 +136mm'};if(zone==='C'||zone==='D')return approved?{design:'M55 86 C260 84 520 90 870 87',actual:'M55 90 C260 87 520 94 870 90',start:470,end:690,value:'최저 다짐도 94%'}:{design:'M55 86 C260 84 520 90 870 87',actual:'M55 90 C280 86 430 92 480 101 C540 138 630 132 690 96 C760 89 820 91 870 90',start:470,end:690,value:'최저 다짐도 87%'};return approved?{design:'M55 92H870',actual:'M55 88 C190 83 310 97 430 89 S680 96 870 90',start:420,end:700,value:'최대 편차 +18mm'}:{design:'M55 92H870',actual:'M55 87 C140 82 180 96 250 90 S360 86 420 92 C470 98 500 133 555 137 S640 112 700 94 S810 89 870 92',start:420,end:700,value:'최대 편차 -82mm'};}
wfReviewWorkVisual=function(w){const phase=wfReviewPhaseForWork(w);const approved=wfStatus(w)[1]==='done';const profile=wfZoneProfile(phase,approved);const image=approved?phase.approvedImage:phase.image;const statusText=approved?'기준 충족 · 승인 완료':'기준 미달 영역';return `<div class="review-zone-head"><div><span>ZONE ${esc(phase.zone)}</span><b>${phase.label} 결과 비교</b><small>선택한 작업의 설계 형상과 결과 형상을 비교합니다.</small></div><span class="review-result-badge ${approved?'approved':'warning'}">${statusText}</span></div><div class="review-diff-toolbar"><div class="profile-legend"><i class="design-shape"></i>설계 형상<i class="actual-shape"></i>결과 형상${approved?'':`<i class="deep-diff"></i>기준 미달 영역`}<i class="shallow-diff"></i>작업 범위</div><span>Zone ${esc(phase.zone)} · ${phase.label}</span></div><div class="review-zone-visual ${approved?'approved':''}"><img src="${image}" alt="Zone ${esc(phase.zone)} ${phase.label} 설계·결과 비교 이미지">${approved?'<div class="review-approved-callout"><b>기준 충족</b><span>검토·승인 완료</span></div>':`<div class="review-zone-callout"><b>문제 구간</b><span>${phase.segment}</span></div>`}<div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="review-profile-chart"><header><div><b>${phase.label} ${zoneProfileLabel(phase.zone)}</b><span>Zone ${esc(phase.zone)}의 설계 기준과 결과 값을 동일 구간 축으로 비교</span></div><div class="profile-legend"><i class="design"></i>설계 기준<i class="actual"></i>결과 값${approved?'':`<i class="issue"></i>허용 범위`}</div></header><svg viewBox="0 0 900 190" role="img" aria-label="Zone ${esc(phase.zone)} ${phase.label} 결과 프로파일"><g class="profile-grid"><path d="M55 35H870M55 70H870M55 105H870M55 140H870"/><path d="M55 20V155M220 20V155M385 20V155M550 20V155M715 20V155M870 20V155"/></g><rect x="55" y="70" width="815" height="45" class="tolerance-band"/><path class="design-line" d="${profile.design}"/><path class="actual-line" d="${profile.actual}"/>${approved?'':`<rect x="${profile.start}" y="25" width="${profile.end-profile.start}" height="125" class="profile-issue-zone"/><line x1="${profile.start}" y1="25" x2="${profile.start}" y2="150" class="issue-edge"/><line x1="${profile.end}" y1="25" x2="${profile.end}" y2="150" class="issue-edge"/><text x="${profile.start+28}" y="54" class="issue-label">문제 구간 ${phase.segment}</text>`}<text x="55" y="178">0m</text><text x="210" y="178">10m</text><text x="405" y="178">14.2m</text><text x="680" y="178">17.6m</text><text x="845" y="178">32m</text></svg><div class="profile-metrics"><div><span>판정 기준</span><b>${phase.criterion}</b></div><div><span>결과 값</span><b>${profile.value}</b></div><div class="${approved?'pass':'danger'}"><span>판정</span><b>${approved?'PASS · 기준 충족':phase.shortfall}</b></div></div></div>`;};
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
renderEvidence=function(){const page=$('#page-evidence');const works=wfReviewWorks();if(workflowUI.reviewId){let w=(state.workPackages||[]).find(x=>x.id===workflowUI.reviewId);if(w?.parentWpId)w=(state.workPackages||[]).find(x=>x.id===w.parentWpId)||w;if(w){page.innerHTML=wfReviewDetail(w);return;}workflowUI.reviewId=null;}const priority=works[0];page.innerHTML=`<div class="workflow-page"><div class="workflow-page-head"><div><h2>검토·승인</h2><p>Zone별 작업의 실제 Isaac 실행 상태와 Evidence 검토 우선순위를 확인합니다.</p></div><button class="ghost-button" data-workflow-action="refresh">↻ 새로고침</button></div><div class="review-layout"><section><div class="workflow-kpis compact">${[['검토 필요','review'],['보완 중','warning'],['재검증 대기','locked'],['승인 완료','done']].map(x=>`<div><span>${x[0]}</span><b>${works.filter(w=>wfStatus(w)[1]===x[1]).length}</b></div>`).join('')}</div><div class="workflow-panel review-list">${works.map(w=>{const s=wfStatus(w);return `<button ${wfReviewClickAttributes(w)}><span><b>Zone ${esc(w.zone)} · ${esc(w.name)}</b><small>${esc(w.id)}</small></span><span>${wfProgress(w)}%</span><em class="${s[1]}">${s[0]}</em><span>${s[1]==='warning'?'후속 작업 LOCKED':wfCommitForWork(w)?'Evidence 검토':'상세 보기'} →</span></button>`}).join('')||wfBlank('검토할 작업 없음','작업 지시를 발행하고 Isaac 실행 결과를 기다려 주세요.')}</div></section><aside class="workflow-panel review-priority"><h3>우선 검토 작업</h3>${priority?`<b>Zone ${esc(priority.zone)} · ${esc(priority.name)}</b><div><span>진척도</span><strong>${wfProgress(priority)}%</strong></div><button class="primary-button" ${wfReviewClickAttributes(priority)}>상세 검토로 이동 →</button>`:wfBlank('대상 없음','검토할 작업이 없습니다.')}</aside></div></div>`;};
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
  return `<div class="review-zone-head haul-zone-head"><div><span>ZONE H</span><b>반출·운반 운영 현황</b><small>공간 형상 판정이 아닌 반출 물량과 운반 이벤트를 집계합니다.</small></div><span class="review-result-badge active">운반 진행 중 · ${progress}%</span></div><div class="review-diff-toolbar haul-toolbar"><div class="profile-legend"><i class="actual-shape"></i>운반 완료 경로<i class="design-shape"></i>남은 계획 경로<i class="shallow-diff"></i>운영 경계</div><span>물량·회차 기준</span></div><div class="review-zone-visual haul-progress-visual"><img src="/static/assets/review/zone-h-haul-progress-v3.png" alt="Zone H 가적치장 반출·운반 진행 현황"><div class="review-approved-callout haul-callout"><b>${progress}% 운반 완료</b><span>남은 경로는 결함이 아닌 계획 구간입니다.</span></div><div class="scene-controls"><button>+</button><button>−</button><button>⌖</button></div></div><div class="haul-operation-summary"><div><span>계획 반출량</span><b>${target.toLocaleString()}㎥</b></div><div><span>누적 반출량</span><b>${completed.toLocaleString()}㎥</b></div><div><span>잔여 반출량</span><b>${remaining.toLocaleString()}㎥</b></div><div><span>운반 이벤트</span><b>${(evidence.missing||[]).includes('운반 종료 이벤트')?'수집 중':'정상 수집'}</b></div></div>`;
};

// Work status keeps every actual Isaac Work Package visible while hiding only
// locally generated correction children from the top-level table.
const renderExecutionBase=renderExecution;
renderExecution=function(){
  renderExecutionBase();
  const visibleWorks=(state.workPackages||[]).filter(work=>!work.parentWpId);
  const statusKinds=['active','review','warning','done'];
  document.querySelectorAll('#page-execution .workflow-kpis.compact>div b').forEach((value,index)=>{
    value.textContent=visibleWorks.filter(w=>wfStatus(w)[1]===statusKinds[index]).length;
  });
  document.querySelectorAll('#page-execution [data-review-open]').forEach(row=>{
    const work=(state.workPackages||[]).find(w=>w.id===row.dataset.reviewOpen);
    if(!work)return;
    if(work.parentWpId){row.remove();return;}
    const title=row.querySelector('b');
    if(title)title.textContent=`Zone ${work.zone} · ${wfZoneDisplayName(work)}`;
  });
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
        criterion:'LLM 작업 해석 · Stage 자원 검증',impact:instruction.status==='blocked'?'자원 확인 전 실행 보류':'Isaac 실행 대기열 등록',
        trace:`${work.id} / ${instruction.id}`,
      });
      if(instruction.dispatched_at){
        events.push({
          id:`${instruction.id}:dispatched`,workId:work.id,zone,type:'active',time:wfHistoryTimestamp(instruction.dispatched_at),
          occurredAt:instruction.dispatched_at,title:'Isaac Adapter 수신',desc:`${wfEquipmentLabel(work)} · 실제 Stage 작업 시작`,
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
          occurredAt:commit.committed_at,title:failed?'Isaac 실행 실패':'실행 Commit · Evidence 수신',
          desc:failed?(result.error||'Adapter 실행 오류'):`작업 전·후 센서와 Stage 결과를 Commit했습니다.`,
          status:failed?'조치 필요':'검토 대기',
          actual:failed?(result.error||'실패'):(quantity.value!=null?`${quantity.value} ${quantity.unit||''}`:geometry.available?`절토 ${geometry.removed_volume_m3||0} / 성토 ${geometry.added_volume_m3||0} ㎥`:'Evidence 저장 완료'),
          criterion:Number.isFinite(completeness)?`Evidence 완결성 ${Math.round(completeness*100)}%`:'카메라·LiDAR·IMU Evidence',
          impact:failed?'후속 공정 LOCKED':'관리자 승인 대기',trace:`${commit.id} / attempt ${commit.attempt||1}`,
        });
        if(commit.review_status==='approved'){
          events.push({
            id:`${commit.id}:approved`,workId:work.id,zone,type:'merge',time:wfHistoryTimestamp(commit.reviewed_at),occurredAt:commit.reviewed_at,
            title:'관리자 승인 · Merge',desc:'검토한 Isaac 결과를 공식 Site Work Map에 반영했습니다.',status:'승인 완료',
            actual:'PASS',criterion:'센서 Evidence 관리자 판정',impact:'공식 맵 반영 · 다음 공정 READY',trace:`MERGE / ${commit.id}`,
          });
        }else if(commit.review_status==='rejected'){
          events.push({
            id:`${commit.id}:rejected`,workId:work.id,zone,type:'warning',time:wfHistoryTimestamp(commit.reviewed_at),occurredAt:commit.reviewed_at,
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
  return `<aside class="workflow-panel history-event-detail"><header><div><span class="history-detail-type ${tone}">${event.status}</span><h3>${esc(event.title)}</h3><p>${esc(event.desc)}</p></div></header><div class="history-detail-grid"><div><span>작업</span><b>Zone ${esc(event.zone)} · ${esc(event.workId)}</b></div><div><span>발생 시각</span><b>${esc(event.time)}</b></div><div><span>결과 값</span><b>${esc(event.actual)}</b></div><div><span>판정 기준</span><b>${esc(event.criterion)}</b></div><div class="wide"><span>후속 영향</span><b class="${tone}">${esc(event.impact)}</b></div></div><section class="history-trace"><span>추적 정보</span><code>${esc(event.trace)}</code><small>Plan v1.0 · Shared DB · 불변 이벤트</small></section></aside>`;
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

// app.js booted first; redraw with the workflow renderers now installed.
renderAll();
