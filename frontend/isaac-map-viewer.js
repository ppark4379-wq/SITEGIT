(function () {
  "use strict";

  // The Work map is the published branch: an immutable Stage baseline plus
  // manager-approved commit changes. Live Stage inventory is used only for
  // connectivity and must never leak unreviewed work into this viewer.
  var MAP_ROOT = "/isaac-data/site-work-map";
  var MAP_OBJECTS_URL = "/api/v1/isaac/map-objects";
  var STAGE_INVENTORY_URL = "/api/v1/isaac/stage-inventory";
  var CAMERA_STATE_KEY = "sitegit-isaac-camera-v1";

  var root = document.getElementById("viewer");
  var canvas = document.getElementById("mapCanvas");
  var state = document.getElementById("viewerState");
  var zoneLabels = document.getElementById("zoneLabels");
  var designOverlay = document.getElementById("designOverlay");
  var planningOverlay = document.getElementById("planningOverlay");
  var embedded = window.self !== window.top;
  var gl = canvas.getContext("webgl", { antialias: true, alpha: false });
  var groups = [];
  var mapObjectsRaw = [];
  var mapTimelineStepsRaw = [];
  var mapObjects = [];
  var removalObjects = [];
  var diggableTargetsRaw = [];
  var diggableObjects = [];
  var sceneObjectsRaw = [];
  var mapConflictsRaw = [];
  var conflictObjects = [];
  var publishedGeometryBuffers = [];
  var soilTexture = null;
  var soilVolumeTexture = null;
  var stageConnected = false;
  var bounds = null;
  var triangleCount = 0;
  var meshStatus = "loading";
  var yaw = 0.48;
  var pitch = 0.76;
  var distance = 260;
  var target = [0, 0, 0];
  var dragging = false;
  var dragButton = 0;
  var lastX = 0;
  var lastY = 0;
  var zonesVisible = false;
  var zoneDefinitions = [];
  var activeLayer = "work";
  var timelineEnabled = false;
  var timelineApprovedAt = null;
  var timelineCommitId = null;
  var timelineFeatureStartAt = null;
  var timelineInstructionIds = [];
  var timelineBaselineObjectsRaw = [];
  var planningPlan = null;
  var designPlan = null;

  function loadCameraState() {
    try {
      var saved = JSON.parse(sessionStorage.getItem(CAMERA_STATE_KEY) || "null");
      if (!saved || !Array.isArray(saved.target) || saved.target.length !== 3) return null;
      if (![saved.yaw, saved.pitch, saved.distance].every(Number.isFinite)) return null;
      if (!saved.target.every(Number.isFinite)) return null;
      return saved;
    } catch (error) {
      return null;
    }
  }

  function saveCameraState() {
    try {
      sessionStorage.setItem(CAMERA_STATE_KEY, JSON.stringify({
        yaw: yaw,
        pitch: pitch,
        distance: distance,
        target: target
      }));
    } catch (error) {
      // A blocked storage API must not disable the WebGL viewer.
    }
  }

  var restoredCamera = loadCameraState();
  if (restoredCamera) {
    yaw = restoredCamera.yaw;
    pitch = restoredCamera.pitch;
    distance = restoredCamera.distance;
    target = restoredCamera.target.slice();
  }

  function setState(title, detail, isError) {
    state.className = "state" + (isError ? " error" : "");
    state.innerHTML = "<b>" + title + "</b><span>" + detail + "</span>";
    // The parent dashboard already renders its own Work/Zone caption in the
    // same corner. Keep this diagnostic card only for actionable viewer errors
    // when the map is embedded, while retaining it in standalone debug mode.
    state.hidden = embedded && !isError;
  }

  if (embedded) state.hidden = true;

  if (!gl) {
    setState("WebGL을 사용할 수 없습니다", "Chrome 또는 Edge에서 확인하세요.", true);
    return;
  }

  // 카메라 변환은 두 셰이더가 공유합니다. 행렬 대신 eye/right/up/forward를
  // 그대로 넘겨 정점에서 직접 투영합니다.
  var CAMERA_UNIFORMS = [
    "uniform vec3 uEye,uRight,uUp,uForward;",
    "uniform float uTanHalf,uAspect,uNear,uFar;"
  ].join("\n");
  var PROJECT_FN = [
    "vec4 projectWorld(vec3 world){",
    " vec3 r=world-uEye;",
    " float x=dot(r,uRight),y=dot(r,uUp),z=dot(r,uForward);",
    " return vec4(x/(uTanHalf*uAspect),y/uTanHalf,((uFar+uNear)/(uFar-uNear))*z-(2.0*uFar*uNear)/(uFar-uNear),z);",
    "}"
  ].join("\n");

  var meshVertexSource = [
    "attribute vec3 aPosition;",
    "attribute vec2 aUv;",
    CAMERA_UNIFORMS,
    "varying vec2 vUv;",
    "varying float vDepth;",
    "varying vec3 vWorld;",
    PROJECT_FN,
    "void main(){",
    " gl_Position=projectWorld(aPosition);",
    " vUv=aUv;vDepth=gl_Position.w;vWorld=aPosition;",
    "}"
  ].join("\n");
  var meshFragmentSource = [
    "precision mediump float;",
    "uniform sampler2D uTexture;",
    "uniform int uZonesVisible;",
    "uniform int uZoneCount;",
    "uniform vec2 uZoneCenters[16];",
    "uniform vec2 uZoneHalfSizes[16];",
    "uniform vec3 uZoneColors[16];",
    "uniform int uRemovalCount;",
    "uniform vec3 uRemovalCenters[16];",
    "uniform vec3 uRemovalHalfSizes[16];",
    "varying vec2 vUv;",
    "varying float vDepth;",
    "varying vec3 vWorld;",
    "void main(){",
    " for(int i=0;i<16;i++){",
    "  if(i<uRemovalCount){ vec3 d=abs(vWorld-uRemovalCenters[i]); if(all(lessThanEqual(d,uRemovalHalfSizes[i]))) discard; }",
    " }",
    " vec3 c=texture2D(uTexture,vUv).rgb;",
    " if(uZonesVisible==1){",
    "  for(int i=0;i<16;i++){",
    "   if(i<uZoneCount){",
    "    vec2 delta=abs(vWorld.xz-uZoneCenters[i]);",
    "    if(all(lessThanEqual(delta,uZoneHalfSizes[i]))){",
    "     float edge=min(uZoneHalfSizes[i].x-delta.x,uZoneHalfSizes[i].y-delta.y);",
    "     float boundary=1.0-smoothstep(0.0,0.65,edge);",
    "     c=mix(c,uZoneColors[i],0.38);",
    "     c=mix(c,vec3(1.0),boundary*0.72);",
    "    }",
    "   }",
    "  }",
    " }",
    " float fog=clamp((vDepth-120.0)/520.0,0.0,0.34);",
    " gl_FragColor=vec4(mix(c*0.98,vec3(0.07,0.12,0.14),fog),1.0);",
    "}"
  ].join("\n");

  // 승인된 작업 결과를 지형 위에 얹는 셰이더. 단위 큐브를 uCenter/uSize로
  // 옮겨 그리므로 오브젝트마다 버퍼를 새로 만들 필요가 없습니다.
  var cubeVertexSource = [
    "attribute vec3 aPosition;",
    "attribute vec3 aNormal;",
    CAMERA_UNIFORMS,
    "uniform vec3 uCenter,uSize;",
    "varying float vShade;",
    "varying vec3 vWorld;",
    PROJECT_FN,
    "void main(){",
    " vWorld=uCenter+aPosition*uSize;",
    " gl_Position=projectWorld(vWorld);",
    " vShade=0.45+0.55*max(dot(normalize(aNormal),normalize(vec3(0.35,0.9,0.25))),0.0);",
    "}"
  ].join("\n");
  var cubeFragmentSource = [
    "precision mediump float;",
    "uniform vec3 uColor;",
    "uniform float uSoil;",
    "varying float vShade;",
    "varying vec3 vWorld;",
    "float hash(vec2 p){ return fract(sin(dot(floor(p),vec2(127.1,311.7)))*43758.5453); }",
    "void main(){",
    " float grain=mix(1.0,0.88+0.22*hash(vWorld.xz*3.5),uSoil);",
    " gl_FragColor=vec4(uColor*vShade*grain,1.0);",
    "}"
  ].join("\n");

  function createShader(type, source) {
    var shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(shader));
    }
    return shader;
  }

  function createProgram(vertexSource, fragmentSource) {
    var value = gl.createProgram();
    gl.attachShader(value, createShader(gl.VERTEX_SHADER, vertexSource));
    gl.attachShader(value, createShader(gl.FRAGMENT_SHADER, fragmentSource));
    gl.linkProgram(value);
    if (!gl.getProgramParameter(value, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(value));
    }
    return value;
  }

  var meshProgram;
  var cubeProgram;
  try {
    meshProgram = createProgram(meshVertexSource, meshFragmentSource);
    cubeProgram = createProgram(cubeVertexSource, cubeFragmentSource);
  } catch (error) {
    setState("WebGL 초기화 실패", error.message, true);
    return;
  }

  // 유니폼 위치는 프로그램당 한 번만 찾습니다. 큐브는 오브젝트마다 그리므로
  // 매 프레임 조회하면 개수에 비례해 낭비됩니다.
  function cameraUniforms(program) {
    return {
      eye: gl.getUniformLocation(program, "uEye"),
      right: gl.getUniformLocation(program, "uRight"),
      up: gl.getUniformLocation(program, "uUp"),
      forward: gl.getUniformLocation(program, "uForward"),
      tanHalf: gl.getUniformLocation(program, "uTanHalf"),
      aspect: gl.getUniformLocation(program, "uAspect"),
      near: gl.getUniformLocation(program, "uNear"),
      far: gl.getUniformLocation(program, "uFar")
    };
  }
  var meshUniforms = cameraUniforms(meshProgram);
  meshUniforms.texture = gl.getUniformLocation(meshProgram, "uTexture");
  meshUniforms.zonesVisible = gl.getUniformLocation(meshProgram, "uZonesVisible");
  meshUniforms.zoneCount = gl.getUniformLocation(meshProgram, "uZoneCount");
  meshUniforms.zoneCenters = gl.getUniformLocation(meshProgram, "uZoneCenters[0]");
  meshUniforms.zoneHalfSizes = gl.getUniformLocation(meshProgram, "uZoneHalfSizes[0]");
  meshUniforms.zoneColors = gl.getUniformLocation(meshProgram, "uZoneColors[0]");
  meshUniforms.removalCount = gl.getUniformLocation(meshProgram, "uRemovalCount");
  meshUniforms.removalCenters = gl.getUniformLocation(meshProgram, "uRemovalCenters[0]");
  meshUniforms.removalHalfSizes = gl.getUniformLocation(meshProgram, "uRemovalHalfSizes[0]");
  meshUniforms.position = gl.getAttribLocation(meshProgram, "aPosition");
  meshUniforms.uv = gl.getAttribLocation(meshProgram, "aUv");

  var cubeUniforms = cameraUniforms(cubeProgram);
  cubeUniforms.center = gl.getUniformLocation(cubeProgram, "uCenter");
  cubeUniforms.size = gl.getUniformLocation(cubeProgram, "uSize");
  cubeUniforms.color = gl.getUniformLocation(cubeProgram, "uColor");
  cubeUniforms.soil = gl.getUniformLocation(cubeProgram, "uSoil");
  cubeUniforms.position = gl.getAttribLocation(cubeProgram, "aPosition");
  cubeUniforms.normal = gl.getAttribLocation(cubeProgram, "aNormal");

  function buildCubeBuffer() {
    var faces = [
      [[0, 0, 1], [[-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5]]],
      [[0, 0, -1], [[0.5, -0.5, -0.5], [-0.5, -0.5, -0.5], [-0.5, 0.5, -0.5], [0.5, 0.5, -0.5]]],
      [[1, 0, 0], [[0.5, -0.5, 0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [0.5, 0.5, 0.5]]],
      [[-1, 0, 0], [[-0.5, -0.5, -0.5], [-0.5, -0.5, 0.5], [-0.5, 0.5, 0.5], [-0.5, 0.5, -0.5]]],
      [[0, 1, 0], [[-0.5, 0.5, 0.5], [0.5, 0.5, 0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5]]],
      [[0, -1, 0], [[-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, -0.5, 0.5], [-0.5, -0.5, 0.5]]]
    ];
    var data = [];
    faces.forEach(function (face) {
      var normal = face[0];
      var corners = face[1];
      [[0, 1, 2], [0, 2, 3]].forEach(function (triangle) {
        triangle.forEach(function (index) {
          var corner = corners[index];
          data.push(corner[0], corner[1], corner[2], normal[0], normal[1], normal[2]);
        });
      });
    });
    var buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    return buffer;
  }
  var cubeBuffer = buildCubeBuffer();

  function buildMoundBuffer() {
    var segments = 24;
    var rings = [
      { radius: 1.0, height: -0.5 },
      { radius: 0.70, height: -0.16 },
      { radius: 0.34, height: 0.26 }
    ];
    var vertices = [];
    function point(ring, segment) {
      var angle = Math.PI * 2 * segment / segments;
      return [
        Math.cos(angle) * ring.radius * 0.5,
        ring.height,
        Math.sin(angle) * ring.radius * 0.5
      ];
    }
    function triangle(a, b, c) {
      var ab = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      var ac = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      var normal = normalize(cross(ab, ac));
      [a, b, c].forEach(function (value) {
        vertices.push(value[0], value[1], value[2], normal[0], normal[1], normal[2]);
      });
    }
    for (var ringIndex = 0; ringIndex < rings.length - 1; ringIndex += 1) {
      for (var segment = 0; segment < segments; segment += 1) {
        var next = (segment + 1) % segments;
        var outer = point(rings[ringIndex], segment);
        var outerNext = point(rings[ringIndex], next);
        var inner = point(rings[ringIndex + 1], segment);
        var innerNext = point(rings[ringIndex + 1], next);
        triangle(inner, outer, outerNext);
        triangle(inner, outerNext, innerNext);
      }
    }
    var peak = [0, 0.5, 0];
    var topRing = rings[rings.length - 1];
    for (var topSegment = 0; topSegment < segments; topSegment += 1) {
      triangle(
        peak,
        point(topRing, topSegment),
        point(topRing, (topSegment + 1) % segments)
      );
    }
    var buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
    return { buffer: buffer, count: vertices.length / 6 };
  }
  var moundGeometry = buildMoundBuffer();

  function hexToRgb(hex) {
    var value = /^#?([0-9a-f]{6})$/i.exec(String(hex || ""));
    if (!value) return [0.94, 0.71, 0.16];
    var number = parseInt(value[1], 16);
    return [((number >> 16) & 255) / 255, ((number >> 8) & 255) / 255, (number & 255) / 255];
  }

  function normalize(value) {
    var length = Math.hypot(value[0], value[1], value[2]) || 1;
    return [value[0] / length, value[1] / length, value[2] / length];
  }

  function cross(a, b) {
    return [
      a[1] * b[2] - a[2] * b[1],
      a[2] * b[0] - a[0] * b[2],
      a[0] * b[1] - a[1] * b[0]
    ];
  }

  function camera() {
    var cp = Math.cos(pitch);
    var eye = [
      target[0] + Math.sin(yaw) * cp * distance,
      target[1] + Math.sin(pitch) * distance,
      target[2] + Math.cos(yaw) * cp * distance
    ];
    var forward = normalize([target[0] - eye[0], target[1] - eye[1], target[2] - eye[2]]);
    var right = normalize(cross(forward, [0, 1, 0]));
    var up = normalize(cross(right, forward));
    return { eye: eye, forward: forward, right: right, up: up };
  }

  function applyCamera(uniforms, view) {
    gl.uniform3fv(uniforms.eye, view.eye);
    gl.uniform3fv(uniforms.right, view.right);
    gl.uniform3fv(uniforms.up, view.up);
    gl.uniform3fv(uniforms.forward, view.forward);
    gl.uniform1f(uniforms.tanHalf, Math.tan(Math.PI / 6));
    gl.uniform1f(uniforms.aspect, canvas.width / canvas.height);
    gl.uniform1f(uniforms.near, 0.05);
    gl.uniform1f(uniforms.far, 5000);
  }

  function drawMesh(view) {
    gl.useProgram(meshProgram);
    applyCamera(meshUniforms, view);
    gl.enableVertexAttribArray(meshUniforms.position);
    gl.enableVertexAttribArray(meshUniforms.uv);
    gl.uniform1i(meshUniforms.zonesVisible, zonesVisible ? 1 : 0);
    var visibleZones = zoneDefinitions.slice(0, 16);
    gl.uniform1i(meshUniforms.zoneCount, visibleZones.length);
    if (visibleZones.length) {
      gl.uniform2fv(meshUniforms.zoneCenters, new Float32Array(visibleZones.flatMap(function (zone) {
        var center = siteToMesh(zone.position || {});
        return [center[0], center[2]];
      })));
      gl.uniform2fv(meshUniforms.zoneHalfSizes, new Float32Array(visibleZones.flatMap(function (zone) {
        var size = zone.size || {};
        return [Math.max(.25, Math.abs(Number(size.x) || 1) * .5), Math.max(.25, Math.abs(Number(size.y) || 1) * .5)];
      })));
      gl.uniform3fv(meshUniforms.zoneColors, new Float32Array(visibleZones.flatMap(function (zone) {
        return hexToRgb(zone.color || "#2ca66f");
      })));
    }
    var clipped = removalObjects.slice(0, 16);
    gl.uniform1i(meshUniforms.removalCount, clipped.length);
    if (clipped.length) {
      gl.uniform3fv(meshUniforms.removalCenters, new Float32Array(clipped.flatMap(function (item) { return item.center; })));
      gl.uniform3fv(meshUniforms.removalHalfSizes, new Float32Array(clipped.flatMap(function (item) {
        return item.size.map(function (value) { return Math.max(value * 0.5, 0.01); });
      })));
    }
    groups.forEach(function (group) {
      gl.bindBuffer(gl.ARRAY_BUFFER, group.buffer);
      gl.vertexAttribPointer(meshUniforms.position, 3, gl.FLOAT, false, 20, 0);
      gl.vertexAttribPointer(meshUniforms.uv, 2, gl.FLOAT, false, 20, 12);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, group.texture);
      gl.uniform1i(meshUniforms.texture, 0);
      gl.drawArrays(gl.TRIANGLES, 0, group.count);
    });
    mapObjects.concat(diggableObjects)
      .filter(function (item) { return item.customGeometry; })
      .forEach(function (item) {
        function drawPublishedPart(part, texture) {
          if (!part || !part.count) return;
          gl.bindBuffer(gl.ARRAY_BUFFER, part.buffer);
          gl.vertexAttribPointer(meshUniforms.position, 3, gl.FLOAT, false, 20, 0);
          gl.vertexAttribPointer(meshUniforms.uv, 2, gl.FLOAT, false, 20, 12);
          gl.activeTexture(gl.TEXTURE0);
          gl.bindTexture(gl.TEXTURE_2D, texture);
          gl.uniform1i(meshUniforms.texture, 0);
          gl.drawArrays(gl.TRIANGLES, 0, part.count);
        }
        drawPublishedPart(item.customGeometry.volume, soilVolumeTexture);
        drawPublishedPart(item.customGeometry.top, soilTexture);
      });
    gl.disableVertexAttribArray(meshUniforms.uv);
  }

  function drawObjects(view) {
    gl.useProgram(cubeProgram);
    applyCamera(cubeUniforms, view);
    gl.enableVertexAttribArray(cubeUniforms.position);
    gl.enableVertexAttribArray(cubeUniforms.normal);
    function drawSet(items, buffer, count) {
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.vertexAttribPointer(cubeUniforms.position, 3, gl.FLOAT, false, 24, 0);
      gl.vertexAttribPointer(cubeUniforms.normal, 3, gl.FLOAT, false, 24, 12);
      items.forEach(function (item) {
        gl.uniform3fv(cubeUniforms.center, item.center);
        gl.uniform3fv(cubeUniforms.size, item.size);
        gl.uniform3fv(cubeUniforms.color, item.color);
        gl.uniform1f(
          cubeUniforms.soil,
          item.type === "diggable" || item.type === "deformed_soil" ? 1.0 : 0.0
        );
        gl.drawArrays(gl.TRIANGLES, 0, count);
      });
    }
    drawSet(mapObjects.filter(function (item) { return !item.customGeometry; }), cubeBuffer, 36);
    drawSet(
      diggableObjects.filter(function (item) { return !item.customGeometry; }),
      moundGeometry.buffer,
      moundGeometry.count
    );
    if (activeLayer === "constraint") drawSet(conflictObjects, cubeBuffer, 36);
    gl.disableVertexAttribArray(cubeUniforms.normal);
  }

  function draw() {
    if (!bounds) return;
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0.025, 0.066, 0.086, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
    var view = camera();
    if (groups.length) drawMesh(view);
    if (mapObjects.length || diggableObjects.length || (activeLayer === "constraint" && conflictObjects.length)) drawObjects(view);
    updateZoneLabels(view);
    updateDesignOverlay(view);
    updatePlanningOverlay(view);
  }

  function dot(a, b) {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  }

  function projectToScreen(world, view) {
    var relative = [
      world[0] - view.eye[0],
      world[1] - view.eye[1],
      world[2] - view.eye[2]
    ];
    var depth = dot(relative, view.forward);
    if (depth <= 0.05) return null;
    var tanHalf = Math.tan(Math.PI / 6);
    var ndcX = dot(relative, view.right) / (tanHalf * (canvas.width / canvas.height) * depth);
    var ndcY = dot(relative, view.up) / (tanHalf * depth);
    if (Math.abs(ndcX) > 1.2 || Math.abs(ndcY) > 1.2) return null;
    return [
      (ndcX * 0.5 + 0.5) * canvas.clientWidth,
      (0.5 - ndcY * 0.5) * canvas.clientHeight
    ];
  }

  function escapeOverlayText(value) {
    return String(value || "").replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character];
    });
  }

  function planningCorridorSides(centerline) {
    var left = [];
    var right = [];
    centerline.forEach(function (point, index) {
      var previous = centerline[Math.max(0, index - 1)];
      var next = centerline[Math.min(centerline.length - 1, index + 1)];
      var dx = Number(next.x) - Number(previous.x);
      var dy = Number(next.y) - Number(previous.y);
      var length = Math.hypot(dx, dy) || 1;
      var normalX = -dy / length;
      var normalY = dx / length;
      var halfWidth = Math.max(.5, Number(point.width_m) * .5 || .5);
      var base = { x: Number(point.x) || 0, y: Number(point.y) || 0, z: Number(point.z) || .1 };
      left.push({ x: base.x + normalX * halfWidth, y: base.y + normalY * halfWidth, z: base.z });
      right.push({ x: base.x - normalX * halfWidth, y: base.y - normalY * halfWidth, z: base.z });
    });
    return { left: left, right: right };
  }

  function planningCorridorPoints(centerline) {
    var sides = planningCorridorSides(centerline);
    return sides.left.concat(sides.right.slice().reverse());
  }

  function updatePlanningOverlay(view) {
    if (!planningOverlay) return;
    var centerline = Array.isArray(planningPlan && planningPlan.centerline)
      ? planningPlan.centerline
      : [];
    planningOverlay.hidden = centerline.length < 2;
    if (centerline.length < 2) {
      planningOverlay.innerHTML = "";
      return;
    }
    planningOverlay.setAttribute("viewBox", "0 0 " + canvas.clientWidth + " " + canvas.clientHeight);
    var corridor = planningCorridorPoints(centerline).map(function (point) {
      return projectToScreen(siteToMesh(point), view);
    });
    var line = centerline.map(function (point) {
      return projectToScreen(siteToMesh(point), view);
    });
    if (corridor.some(function (point) { return !point; }) || line.some(function (point) { return !point; })) {
      planningOverlay.innerHTML = "";
      return;
    }
    var polygonPoints = corridor.map(function (point) { return point[0].toFixed(1) + "," + point[1].toFixed(1); }).join(" ");
    var linePoints = line.map(function (point) { return point[0].toFixed(1) + "," + point[1].toFixed(1); }).join(" ");
    var fronts = Array.isArray(planningPlan.workfronts) ? planningPlan.workfronts : [];
    var frontColors = ["#2f96bd", "#9b68cc", "#35aa83"];
    var corridorSides = planningCorridorSides(centerline);
    var frontMasks = fronts.map(function (front, index) {
      var startStation = Number(front.station_start_m);
      var endStation = Number(front.station_end_m);
      var startIndex = centerline.findIndex(function (point) { return Number(point.station_m) >= startStation - .01; });
      var endIndex = -1;
      centerline.forEach(function (point, pointIndex) {
        if (Number(point.station_m) <= endStation + .01) endIndex = pointIndex;
      });
      if (startIndex < 0 || endIndex <= startIndex) return "";
      var maskWorld = corridorSides.left.slice(startIndex, endIndex + 1)
        .concat(corridorSides.right.slice(startIndex, endIndex + 1).reverse());
      var mask = maskWorld.map(function (point) { return projectToScreen(siteToMesh(point), view); });
      if (mask.some(function (point) { return !point; })) return "";
      var points = mask.map(function (point) { return point[0].toFixed(1) + "," + point[1].toFixed(1); }).join(" ");
      return '<polygon class="plan-front-area" points="' + points + '" style="--front:' + frontColors[index % frontColors.length] + '"></polygon>';
    }).join("");
    var labels = fronts.map(function (front, index) {
      var box = front.bounds || {};
      var projected = projectToScreen(siteToMesh({
        x: (Number(box.min_x) + Number(box.max_x)) * .5,
        y: (Number(box.min_y) + Number(box.max_y)) * .5,
        z: 2.5
      }), view);
      if (!projected) return "";
      var color = frontColors[index % frontColors.length];
      return '<g class="plan-front"><circle cx="' + projected[0].toFixed(1) + '" cy="' + projected[1].toFixed(1) + '" r="10" fill="' + color + '"></circle><text x="' + (projected[0] + 14).toFixed(1) + '" y="' + (projected[1] + 4).toFixed(1) + '">Zone A · 작업전선 ' + (index + 1) + ' · ' + escapeOverlayText(front.equipment_id) + '</text></g>';
    }).join("");
    planningOverlay.innerHTML = '<polygon class="plan-area" points="' + polygonPoints + '"></polygon>' + frontMasks + '<polyline class="plan-centerline" points="' + linePoints + '"></polyline><g class="plan-zone-title" transform="translate(18 18)"><rect width="168" height="29" rx="7"></rect><text x="12" y="19">ZONE A · 관로 공사</text></g>' + labels;
  }

  function updateDesignOverlay(view) {
    if (!designOverlay) return;
    var centerline = Array.isArray(designPlan && designPlan.centerline)
      ? designPlan.centerline
      : [];
    var visible = activeLayer === "drawing" && centerline.length >= 2;
    designOverlay.hidden = !visible;
    if (!visible) {
      designOverlay.innerHTML = "";
      return;
    }
    designOverlay.setAttribute("viewBox", "0 0 " + canvas.clientWidth + " " + canvas.clientHeight);
    var depth = Math.max(.1, Number(designPlan.design_depth_m) || 0);
    var radius = Math.max(.05, (Number(designPlan.pipe_diameter_m) || .2) * .5);
    var buried = centerline.map(function (point) {
      return {x:Number(point.x)||0,y:Number(point.y)||0,z:(Number(point.z)||0)-depth+radius};
    });
    var corridor = planningCorridorPoints(centerline).map(function (point) {
      return projectToScreen(siteToMesh(point), view);
    });
    var surface = centerline.map(function (point) { return projectToScreen(siteToMesh(point), view); });
    var pipe = buried.map(function (point) { return projectToScreen(siteToMesh(point), view); });
    if (corridor.some(function (point) { return !point; }) || surface.some(function (point) { return !point; }) || pipe.some(function (point) { return !point; })) {
      designOverlay.innerHTML = "";
      return;
    }
    var corridorPoints = corridor.map(function (point) { return point[0].toFixed(1) + "," + point[1].toFixed(1); }).join(" ");
    var pipePoints = pipe.map(function (point) { return point[0].toFixed(1) + "," + point[1].toFixed(1); }).join(" ");
    var depthLinks = pipe.map(function (point, index) {
      if (index !== 0 && index !== pipe.length - 1 && index % 2) return "";
      return '<line class="depth-link" x1="' + surface[index][0].toFixed(1) + '" y1="' + surface[index][1].toFixed(1) + '" x2="' + point[0].toFixed(1) + '" y2="' + point[1].toFixed(1) + '"></line><circle class="surface-point" cx="' + surface[index][0].toFixed(1) + '" cy="' + surface[index][1].toFixed(1) + '" r="3"></circle><circle class="pipe-point" cx="' + point[0].toFixed(1) + '" cy="' + point[1].toFixed(1) + '" r="4"></circle>';
    }).join("");
    var labelX = Math.max(12, Math.min(canvas.clientWidth - 220, pipe[Math.floor(pipe.length * .55)][0] + 15));
    var labelY = Math.max(12, Math.min(canvas.clientHeight - 58, pipe[Math.floor(pipe.length * .55)][1] - 50));
    designOverlay.innerHTML = '<polygon class="design-corridor" points="' + corridorPoints + '"></polygon><polyline class="pipe-shadow" points="' + pipePoints + '"></polyline><polyline class="pipe-body" points="' + pipePoints + '"></polyline><polyline class="pipe-core" points="' + pipePoints + '"></polyline>' + depthLinks + '<g class="design-label" transform="translate(' + labelX.toFixed(1) + ' ' + labelY.toFixed(1) + ')"><rect width="205" height="45" rx="8"></rect><text x="12" y="18">' + escapeOverlayText(designPlan.plan_id) + ' · REV.' + escapeOverlayText(designPlan.revision) + '</text><text class="sub" x="12" y="34">지하 관로 Ø' + Number(designPlan.pipe_diameter_m).toFixed(1) + 'm · 깊이 ' + depth.toFixed(1) + 'm</text></g>';
  }

  function updateZoneLabels(view) {
    if (!zoneLabels) return;
    zoneLabels.hidden = !zonesVisible;
    if (!zonesVisible || !bounds) return;
    Array.prototype.forEach.call(zoneLabels.querySelectorAll("[data-zone]"), function (label) {
      var zone = zoneDefinitions.find(function (item) { return String(item.id) === label.dataset.zone; });
      if (!zone) { label.hidden = true; return; }
      var position = zone.position || {};
      var size = zone.size || {};
      var projected = projectToScreen(siteToMesh({
        x: Number(position.x) || 0,
        y: Number(position.y) || 0,
        z: (Number(position.z) || 0) + Math.max(1.5, (Number(size.z) || 1) * .5 + 1)
      }), view);
      label.hidden = !projected;
      if (!projected) return;
      label.style.left = projected[0] + "px";
      label.style.top = projected[1] + "px";
    });
  }

  function renderZoneLabels() {
    if (!zoneLabels) return;
    zoneLabels.innerHTML = zoneDefinitions.map(function (zone) {
      var color = String(zone.color || "#2ca66f").replace(/[^#a-fA-F0-9]/g, "");
      return '<div class="zone-label" data-zone="' + String(zone.id).replace(/[^A-Za-z0-9_-]/g, "") + '" style="--zone-color:' + color + ';background:' + color + 'd9"><b>' +
        String(zone.label || ("ZONE " + zone.id)).replace(/[<>&]/g, "") + '</b><small>' +
        String(zone.title || "현장 작업").replace(/[<>&]/g, "") + '</small></div>';
    }).join("");
  }

  function resize() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var width = Math.max(1, Math.round(canvas.clientWidth * dpr));
    var height = Math.max(1, Math.round(canvas.clientHeight * dpr));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    draw();
  }

  function resetCamera() {
    if (!bounds) return;
    target = [
      (bounds.min[0] + bounds.max[0]) / 2,
      (bounds.min[1] + bounds.max[1]) / 2,
      (bounds.min[2] + bounds.max[2]) / 2
    ];
    var span = Math.max(
      bounds.max[0] - bounds.min[0],
      bounds.max[2] - bounds.min[2],
      (bounds.max[1] - bounds.min[1]) * 3
    );
    yaw = 0.48;
    pitch = 0.76;
    distance = Math.max(span * 1.18, 5);
    saveCameraState();
    draw();
  }

  function makeTexture(url, fallbackColor) {
    var texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(
      gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE,
      new Uint8Array(fallbackColor || [116, 112, 101, 255])
    );
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    // The source map uses six UDIM-like tiles. UVs intentionally span
    // U 0..3 and V 0..2, so every material texture must repeat.
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
    if (!url) return texture;
    var image = new Image();
    image.onload = function () {
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      var powerOfTwo = function (value) {
        return value > 0 && (value & (value - 1)) === 0;
      };
      if (powerOfTwo(image.width) && powerOfTwo(image.height)) {
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
        gl.generateMipmap(gl.TEXTURE_2D);
      } else {
        // WebGL 1 treats a repeating or mipmapped NPOT texture as incomplete,
        // which samples as solid black. Keep such assets visible and valid.
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      }
      draw();
    };
    image.onerror = function () {
      console.warn("Map texture load failed:", url);
    };
    image.src = url;
    return texture;
  }

  soilTexture = makeTexture(
    MAP_ROOT + "/demolition_soil_tile_diffuse.jpg?v=dirt-only-v8"
  );
  soilVolumeTexture = makeTexture(null, [77, 59, 41, 255]);

  function describeState() {
    var objectPart = stageConnected
      ? " · Isaac Stage 연결됨"
      : " · Isaac Stage 연결 대기";
    objectPart += " · 승인 반영 " + mapObjectsRaw.length + "건";
    if (timelineEnabled) {
      objectPart += timelineApprovedAt
        ? " · Timeline " + String(timelineCommitId || "").slice(0, 8)
        : " · Timeline Baseline";
    }
    if (zonesVisible) objectPart += zoneDefinitions.length ? " · 작업 Zone " + zoneDefinitions.length + "개" : " · 작업 Zone 없음";
    if (activeLayer === "drawing" && designPlan) {
      objectPart += " · 승인 도면 " + String(designPlan.plan_id || "-") + " Rev." + String(designPlan.revision || "-");
    }
    if (mapConflictsRaw.length) objectPart += " · Conflict " + mapConflictsRaw.length + "건";
    if (meshStatus === "ready") {
      setState(
        "Isaac Site Work Map",
        triangleCount.toLocaleString("ko-KR") + " triangles · " + groups.length + " materials" + objectPart,
        false
      );
    } else if (meshStatus === "missing") {
      setState(
        "지형 Mesh가 게시되지 않았습니다",
        "isaac_adapter/map_publisher.py를 실행하세요." + objectPart,
        true
      );
    }
  }

  async function loadGroup(group, index, total) {
    setState("Isaac Map 불러오는 중", "Mesh " + (index + 1) + " / " + total, false);
    var response = await fetch(MAP_ROOT + "/" + group.geometry, { cache: "no-cache" });
    if (!response.ok) throw new Error(group.geometry + " HTTP " + response.status);
    var values = new Float32Array(await response.arrayBuffer());
    if (values.length % 5 !== 0) throw new Error(group.geometry + " 형식이 올바르지 않습니다.");
    var buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, values, gl.STATIC_DRAW);
    return {
      buffer: buffer,
      count: values.length / 5,
      texture: makeTexture(group.texture ? MAP_ROOT + "/" + group.texture : null)
    };
  }

  async function loadMesh() {
    try {
      var response = await fetch(MAP_ROOT + "/manifest.json", { cache: "no-cache" });
      if (!response.ok) throw new Error("manifest HTTP " + response.status);
      var manifest = await response.json();
      if (manifest.format !== "sitegit-web-mesh-v1") {
        throw new Error("지원하지 않는 맵 형식: " + manifest.format);
      }
      bounds = manifest.bounds;
      triangleCount = Number(manifest.triangle_count || 0);
      for (var index = 0; index < manifest.groups.length; index += 1) {
        groups.push(await loadGroup(manifest.groups[index], index, manifest.groups.length));
      }
      meshStatus = "ready";
      // bounds가 이제야 생겼으므로 먼저 도착한 오브젝트를 다시 변환합니다.
      rebuildMapObjects();
      if (restoredCamera) draw();
      else resetCamera();
    } catch (error) {
      meshStatus = "missing";
      console.warn("Isaac mesh load failed:", error);
      // 지형이 없어도 승인된 오브젝트는 볼 수 있도록 카메라를 살려 둡니다.
      if (!bounds) boundsFromObjects();
      draw();
    }
    describeState();
  }

  function boundsFromObjects() {
    if (!mapObjects.length) return;
    var min = [Infinity, Infinity, Infinity];
    var max = [-Infinity, -Infinity, -Infinity];
    mapObjects.forEach(function (item) {
      for (var axis = 0; axis < 3; axis += 1) {
        min[axis] = Math.min(min[axis], item.center[axis] - item.size[axis]);
        max[axis] = Math.max(max[axis], item.center[axis] + item.size[axis]);
      }
    });
    bounds = { min: min, max: max };
    if (restoredCamera) draw();
    else resetCamera();
  }

  // DB에 저장되는 좌표는 Isaac 현장 좌표계입니다: Z가 위, XY 중심이 원점,
  // 지면이 Z=0. 반면 이 뷰어가 그리는 지형 mesh는 원본 OBJ 좌표 그대로라
  // Y가 위이고 원점도 옮겨져 있지 않습니다. 두 계를 잇는 변환입니다.
  //
  //   webX = siteX + centerX      (isaac_adapter/site_stage.py가 XY 중심을 원점으로)
  //   webY = siteZ + minY         (지면을 Z=0으로 내렸으므로 되돌립니다)
  //   webZ = -siteY + centerZ     (Y-up → Z-up 변환이 X축 +90° 회전이었으므로 부호 반전)
  //
  // 상수는 manifest bounds에서 그대로 유도하므로 하드코딩이 없습니다.
  function siteToMesh(position) {
    var x = Number(position.x) || 0;
    var y = Number(position.y) || 0;
    var z = Number(position.z) || 0;
    if (!bounds) return [x, y, z];
    var centerX = (bounds.min[0] + bounds.max[0]) / 2;
    var minY = bounds.min[1];
    var centerZ = (bounds.min[2] + bounds.max[2]) / 2;
    return [x + centerX, z + minY, -y + centerZ];
  }

  function buildPublishedMeshBuffer(geometry) {
    if (!bounds || !geometry || geometry.format !== "sitegit-triangle-mesh-v1") return null;
    var points = geometry.points || [];
    var counts = geometry.face_vertex_counts || [];
    var indices = geometry.face_vertex_indices || [];
    var uvs = geometry.uvs || [];
    var faceUvs = geometry.face_uvs || [];
    if (!points.length || !counts.length || !indices.length) return null;
    var sourceMinX = Math.min.apply(null, points.map(function (point) { return Number(point[0]) || 0; }));
    var sourceMaxX = Math.max.apply(null, points.map(function (point) { return Number(point[0]) || 0; }));
    var sourceMinY = Math.min.apply(null, points.map(function (point) { return Number(point[1]) || 0; }));
    var sourceMaxY = Math.max.apply(null, points.map(function (point) { return Number(point[1]) || 0; }));
    var sourceSpanX = Math.max(sourceMaxX - sourceMinX, 0.001);
    var sourceSpanY = Math.max(sourceMaxY - sourceMinY, 0.001);
    var topVertices = [];
    var volumeVertices = [];
    var topFaceCount = Number.isFinite(Number(geometry.top_face_count))
      ? Math.max(0, Number(geometry.top_face_count))
      : counts.length;
    var offset = 0;
    counts.forEach(function (rawCount, faceNumber) {
      var count = Number(rawCount) || 0;
      var faceOffset = offset;
      var face = indices.slice(offset, offset + count);
      offset += count;
      if (count < 3) return;
      var vertices = faceNumber < topFaceCount ? topVertices : volumeVertices;
      var first = siteToMesh({ x: points[face[0]][0], y: points[face[0]][1], z: points[face[0]][2] });
      for (var triangleIndex = 1; triangleIndex < count - 1; triangleIndex += 1) {
        var secondSource = points[face[triangleIndex]];
        var thirdSource = points[face[triangleIndex + 1]];
        if (!secondSource || !thirdSource) continue;
        var second = siteToMesh({ x: secondSource[0], y: secondSource[1], z: secondSource[2] });
        var third = siteToMesh({ x: thirdSource[0], y: thirdSource[1], z: thirdSource[2] });
        var trianglePointIndices = [face[0], face[triangleIndex], face[triangleIndex + 1]];
        var triangleCornerOffsets = [0, triangleIndex, triangleIndex + 1];
        [first, second, third].forEach(function (point, pointOffset) {
          var sourceIndex = trianglePointIndices[pointOffset];
          var sourcePoint = points[sourceIndex];
          var uv = faceUvs[faceOffset + triangleCornerOffsets[pointOffset]] || uvs[sourceIndex] || [
            0.21 + 0.09 * ((Number(sourcePoint[0]) - sourceMinX) / sourceSpanX),
            0.17 + 0.06 * ((Number(sourcePoint[1]) - sourceMinY) / sourceSpanY)
          ];
          vertices.push(
            point[0], point[1], point[2],
            Number(uv[0]), Number(uv[1])
          );
        });
      }
    });
    function createPart(vertices) {
      if (!vertices.length) return null;
      var buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
      publishedGeometryBuffers.push(buffer);
      return { buffer: buffer, count: vertices.length / 5 };
    }
    var top = createPart(topVertices);
    var volume = createPart(volumeVertices);
    if (!top && !volume) return null;
    return { top: top, volume: volume };
  }

  function toRenderable(item) {
    var position = item.position || {};
    var size = item.size || {};
    var customGeometry = buildPublishedMeshBuffer(item.geometry);
    return {
      center: customGeometry ? [0, 0, 0] : siteToMesh(position),
      // 크기도 축이 바뀝니다. 높이(site Z)가 mesh Y로, 깊이(site Y)가 mesh Z로 갑니다.
      size: customGeometry ? [1, 1, 1] : [
        Math.abs(Number(size.x) || 1),
        Math.abs(Number(size.z) || 1),
        Math.abs(Number(size.y) || 1)
      ],
      color: hexToRgb(item.color)
      ,type: item.type || "cube"
      ,label: item.label || ""
      ,primPath: item.prim_path || null
      ,geometry: item.geometry || null
      ,customGeometry: customGeometry
    };
  }

  // 변환이 manifest bounds에 의존하므로, 지형과 오브젝트 중 무엇이 먼저
  // 도착하든 좌표가 맞도록 원본을 들고 있다가 다시 계산합니다.
  function rebuildMapObjects() {
    publishedGeometryBuffers.forEach(function (buffer) { gl.deleteBuffer(buffer); });
    publishedGeometryBuffers = [];
    var visibleMapObjectsRaw = mapObjectsRaw;
    if (timelineEnabled) {
      var objectsByPrim = {};
      var featureStart = Date.parse(timelineFeatureStartAt || "");
      var selectedTime = Date.parse(timelineApprovedAt || "");
      var allowedInstructions = {};
      timelineInstructionIds.forEach(function (id) { allowedInstructions[id] = true; });
      function applyTimelineObjects(items) {
        (items || []).forEach(function (item) {
          var key = String(item.prim_path || item.id);
          objectsByPrim[key] = item;
        });
      }
      if (mapTimelineStepsRaw.length) {
        mapTimelineStepsRaw.forEach(function (step) {
          var stepTime = Date.parse(step.approved_at || "");
          var isBaselineStep = Number.isFinite(featureStart) && Number.isFinite(stepTime) && stepTime < featureStart;
          if (isBaselineStep) { applyTimelineObjects(step.objects); return; }
          if (!timelineApprovedAt || !allowedInstructions[step.instruction_id]) return;
          if (timelineCommitId) {
            if (Number.isFinite(selectedTime) && stepTime <= selectedTime) applyTimelineObjects(step.objects);
            return;
          }
          if (!Number.isFinite(selectedTime) || stepTime <= selectedTime) applyTimelineObjects(step.objects);
        });
      } else {
        mapObjectsRaw.forEach(function (item) {
          var itemTime = Date.parse(item.approved_at || "");
          var isBaselineItem = Number.isFinite(featureStart) && Number.isFinite(itemTime) && itemTime < featureStart;
          var isSelectedItem = Boolean(timelineApprovedAt && allowedInstructions[item.instruction_id] && (!Number.isFinite(selectedTime) || itemTime <= selectedTime));
          if (isBaselineItem || isSelectedItem) applyTimelineObjects([item]);
        });
      }
      visibleMapObjectsRaw = Object.keys(objectsByPrim).map(function (key) { return objectsByPrim[key]; });
    }
    var rendered = visibleMapObjectsRaw.map(toRenderable);
    var changedPaths = {};
    rendered.forEach(function (item) {
      if (item.primPath) changedPaths[item.primPath] = true;
    });
    // Old approved cube commits remain in the audit trail, but they are not a
    // source of truth for the Work map. Only objects that exist in the current
    // Stage inventory are rendered here.
    mapObjects = sceneObjectsRaw
      .filter(function (item) { return item.active !== false && !changedPaths[item.path]; })
      .map(function (item) {
        return toRenderable({
          position: item.world_position,
          size: item.bounds_size,
          color: item.display_color || "#F0B429",
          type: "scene_object",
          label: item.name,
          prim_path: item.path
        });
      });
    rendered.forEach(function (item) {
      if (item.type !== "removed_prim") mapObjects.push(item);
    });
    // 독립 토사 Prim은 정적 Mud Map의 일부가 아니므로 지형을 잘라내지 않고
    // 해당 overlay만 승인 후 숨깁니다.
    removalObjects = rendered.filter(function (item) {
      return item.type === "terrain_cut";
    });
    var baselineDiggableTargets = diggableTargetsRaw.slice();
    if (timelineEnabled) {
      var knownBaselinePaths = {};
      baselineDiggableTargets.forEach(function (item) {
        if (item.path) knownBaselinePaths[item.path] = true;
      });
      timelineBaselineObjectsRaw.forEach(function (item) {
        if (!item.path || knownBaselinePaths[item.path]) return;
        knownBaselinePaths[item.path] = true;
        baselineDiggableTargets.push(item);
      });
    }
    diggableObjects = baselineDiggableTargets
      .filter(function (item) { return item.active !== false && !changedPaths[item.path]; })
      .map(function (item) {
        return toRenderable({
          position: item.world_position,
          size: item.bounds_size,
          color: item.display_color || "#76502d",
          type: "diggable",
          label: item.name,
          prim_path: item.path,
          geometry: item.geometry || null
        });
      });
    conflictObjects = mapConflictsRaw
      .filter(function (item) { return item.position && item.size; })
      .map(function (item) {
        return toRenderable({
          position: item.position,
          size: item.size,
          color: "#ef4444",
          type: "conflict",
          label: item.label,
          prim_path: item.prim_path
        });
      });
  }

  function publishTimelineData() {
    if (mapTimelineStepsRaw.length) {
      window.parent.postMessage({
        type: "sitegit.isaac-map.timeline-data",
        commits: mapTimelineStepsRaw.map(function (step) {
          return {
            commitId: step.commit_id || null,
            instructionId: step.instruction_id || null,
            approvedAt: step.approved_at || null
          };
        })
      }, window.location.origin);
      return;
    }
    var seen = {};
    var commits = [];
    mapObjectsRaw.forEach(function (item) {
      if (!item.approved_at) return;
      var rawId = String(item.id || "");
      var commitId = rawId.indexOf(":") >= 0 ? rawId.split(":", 1)[0] : rawId;
      var key = commitId || String(item.instruction_id || "") + "@" + item.approved_at;
      if (seen[key]) return;
      seen[key] = true;
      commits.push({
        commitId: commitId || null,
        instructionId: item.instruction_id || null,
        approvedAt: item.approved_at
      });
    });
    window.parent.postMessage({
      type: "sitegit.isaac-map.timeline-data",
      commits: commits
    }, window.location.origin);
  }

  async function loadMapObjects() {
    try {
      var response = await fetch(MAP_OBJECTS_URL, {
        cache: "no-store",
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("map-objects HTTP " + response.status);
      var data = await response.json();
      mapObjectsRaw = data.objects || [];
      mapTimelineStepsRaw = data.timeline || [];
      diggableTargetsRaw = data.baseline_diggable_targets || [];
      sceneObjectsRaw = data.baseline_scene_objects || [];
      mapConflictsRaw = data.conflicts || [];
      publishTimelineData();
      rebuildMapObjects();
      if (!bounds) boundsFromObjects();
      draw();
      describeState();
    } catch (error) {
      console.warn("Map object load failed:", error);
    }
  }

  async function loadStageInventory() {
    try {
      var response = await fetch(STAGE_INVENTORY_URL, {
        cache: "no-store",
        credentials: "same-origin"
      });
      if (!response.ok) throw new Error("stage-inventory HTTP " + response.status);
      var data = await response.json();
      var wasConnected = stageConnected;
      stageConnected = Boolean(data.connected);
      // The judge-demo launcher intentionally opens the dashboard before
      // Isaac Sim. The immutable published baseline is created by the first
      // Stage inventory heartbeat, so an early map request can legitimately
      // contain no initial diggable geometry. Reload only the approved map
      // endpoint when Isaac changes from disconnected to connected; never use
      // the live inventory itself as Work-map geometry.
      if (stageConnected && !wasConnected) loadMapObjects();
      describeState();
    } catch (error) {
      console.warn("Stage inventory load failed:", error);
    }
  }

  canvas.addEventListener("contextmenu", function (event) { event.preventDefault(); });
  canvas.addEventListener("pointerdown", function (event) {
    dragging = true;
    dragButton = event.button;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.classList.add("dragging");
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", function (event) {
    if (!dragging) return;
    var dx = event.clientX - lastX;
    var dy = event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    if (dragButton === 0) {
      yaw -= dx * 0.007;
      pitch = Math.max(0.08, Math.min(1.48, pitch + dy * 0.006));
    } else {
      var view = camera();
      var scale = distance * 0.0016;
      target[0] -= (view.right[0] * dx - view.up[0] * dy) * scale;
      target[1] -= (view.right[1] * dx - view.up[1] * dy) * scale;
      target[2] -= (view.right[2] * dx - view.up[2] * dy) * scale;
    }
    draw();
  });
  function stopDrag() {
    dragging = false;
    canvas.classList.remove("dragging");
    saveCameraState();
  }
  canvas.addEventListener("pointerup", stopDrag);
  canvas.addEventListener("pointercancel", stopDrag);
  canvas.addEventListener("wheel", function (event) {
    event.preventDefault();
    distance *= Math.exp(event.deltaY * 0.001);
    distance = Math.max(1, Math.min(3000, distance));
    saveCameraState();
    draw();
  }, { passive: false });
  canvas.addEventListener("dblclick", resetCamera);
  window.addEventListener("message", function (event) {
    if (event.origin !== window.location.origin || !event.data) return;
    if (event.data.type === "sitegit.isaac-map.fit") resetCamera();
    if (event.data.type === "sitegit.isaac-map.layer") {
      activeLayer = event.data.layer || "work";
      zonesVisible = event.data.layer === "zone";
      timelineEnabled = event.data.layer === "timeline";
      if (!timelineEnabled) {
        timelineApprovedAt = null;
        timelineCommitId = null;
      }
      rebuildMapObjects();
      draw();
      describeState();
    }
    if (event.data.type === "sitegit.isaac-map.zones") {
      zoneDefinitions = Array.isArray(event.data.zones) ? event.data.zones.slice(0, 16) : [];
      if (event.data.featureStartAt) timelineFeatureStartAt = event.data.featureStartAt;
      renderZoneLabels();
      draw();
      describeState();
    }
    if (event.data.type === "sitegit.isaac-map.timeline") {
      timelineEnabled = true;
      activeLayer = "timeline";
      zonesVisible = false;
      timelineApprovedAt = event.data.baseline ? null : (event.data.approvedAt || null);
      timelineCommitId = event.data.baseline ? null : (event.data.commitId || null);
      timelineFeatureStartAt = event.data.featureStartAt || timelineFeatureStartAt;
      timelineInstructionIds = Array.isArray(event.data.instructionIds) ? event.data.instructionIds : [];
      timelineBaselineObjectsRaw = Array.isArray(event.data.baselineObjects)
        ? event.data.baselineObjects
        : [];
      rebuildMapObjects();
      draw();
      describeState();
    }
    if (event.data.type === "sitegit.isaac-map.plan") {
      planningPlan = event.data.plan || null;
      draw();
    }
    if (event.data.type === "sitegit.isaac-map.plan-clear") {
      planningPlan = null;
      draw();
    }
    if (event.data.type === "sitegit.isaac-map.design") {
      designPlan = event.data.plan || null;
      draw();
      describeState();
    }
    if (event.data.type === "sitegit.isaac-map.design-clear") {
      designPlan = null;
      draw();
      describeState();
    }
    // 관리자가 승인하면 부모 창이 이 메시지를 보냅니다.
    if (event.data.type === "sitegit.isaac-map.reload-objects") loadMapObjects();
  });
  new ResizeObserver(resize).observe(root);
  resize();
  // 지형은 60MB라 느립니다. 오브젝트는 기다리지 않고 함께 받습니다.
  loadMesh();
  loadMapObjects();
  loadStageInventory();
  window.setInterval(loadStageInventory, 1000);
}());
