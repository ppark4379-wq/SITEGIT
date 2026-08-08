(function () {
  "use strict";

  // 지형 mesh는 SSD의 정적 번들, 작업 결과 오브젝트는 DB에서 옵니다.
  // 승인된 Commit만 map-objects에 나타나므로 미승인 결과는 절대 그려지지 않습니다.
  var MAP_ROOT = "/isaac-data/site-work-map";
  var MAP_OBJECTS_URL = "/api/v1/isaac/map-objects";

  var root = document.getElementById("viewer");
  var canvas = document.getElementById("mapCanvas");
  var state = document.getElementById("viewerState");
  var gl = canvas.getContext("webgl", { antialias: true, alpha: false });
  var groups = [];
  var mapObjectsRaw = [];
  var mapObjects = [];
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

  function setState(title, detail, isError) {
    state.className = "state" + (isError ? " error" : "");
    state.innerHTML = "<b>" + title + "</b><span>" + detail + "</span>";
  }

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
    PROJECT_FN,
    "void main(){",
    " gl_Position=projectWorld(aPosition);",
    " vUv=aUv;vDepth=gl_Position.w;",
    "}"
  ].join("\n");
  var meshFragmentSource = [
    "precision mediump float;",
    "uniform sampler2D uTexture;",
    "varying vec2 vUv;",
    "varying float vDepth;",
    "void main(){",
    " vec3 c=texture2D(uTexture,vUv).rgb;",
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
    PROJECT_FN,
    "void main(){",
    " gl_Position=projectWorld(uCenter+aPosition*uSize);",
    " vShade=0.45+0.55*max(dot(normalize(aNormal),normalize(vec3(0.35,0.9,0.25))),0.0);",
    "}"
  ].join("\n");
  var cubeFragmentSource = [
    "precision mediump float;",
    "uniform vec3 uColor;",
    "varying float vShade;",
    "void main(){ gl_FragColor=vec4(uColor*vShade,1.0); }"
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
  meshUniforms.position = gl.getAttribLocation(meshProgram, "aPosition");
  meshUniforms.uv = gl.getAttribLocation(meshProgram, "aUv");

  var cubeUniforms = cameraUniforms(cubeProgram);
  cubeUniforms.center = gl.getUniformLocation(cubeProgram, "uCenter");
  cubeUniforms.size = gl.getUniformLocation(cubeProgram, "uSize");
  cubeUniforms.color = gl.getUniformLocation(cubeProgram, "uColor");
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
    groups.forEach(function (group) {
      gl.bindBuffer(gl.ARRAY_BUFFER, group.buffer);
      gl.vertexAttribPointer(meshUniforms.position, 3, gl.FLOAT, false, 20, 0);
      gl.vertexAttribPointer(meshUniforms.uv, 2, gl.FLOAT, false, 20, 12);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, group.texture);
      gl.uniform1i(meshUniforms.texture, 0);
      gl.drawArrays(gl.TRIANGLES, 0, group.count);
    });
    gl.disableVertexAttribArray(meshUniforms.uv);
  }

  function drawObjects(view) {
    gl.useProgram(cubeProgram);
    applyCamera(cubeUniforms, view);
    gl.bindBuffer(gl.ARRAY_BUFFER, cubeBuffer);
    gl.enableVertexAttribArray(cubeUniforms.position);
    gl.enableVertexAttribArray(cubeUniforms.normal);
    gl.vertexAttribPointer(cubeUniforms.position, 3, gl.FLOAT, false, 24, 0);
    gl.vertexAttribPointer(cubeUniforms.normal, 3, gl.FLOAT, false, 24, 12);
    mapObjects.forEach(function (item) {
      gl.uniform3fv(cubeUniforms.center, item.center);
      gl.uniform3fv(cubeUniforms.size, item.size);
      gl.uniform3fv(cubeUniforms.color, item.color);
      gl.drawArrays(gl.TRIANGLES, 0, 36);
    });
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
    if (mapObjects.length) drawObjects(view);
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
    draw();
  }

  function makeTexture(url) {
    var texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texImage2D(
      gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE,
      new Uint8Array([116, 112, 101, 255])
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
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
      gl.generateMipmap(gl.TEXTURE_2D);
      draw();
    };
    image.onerror = function () {
      console.warn("Map texture load failed:", url);
    };
    image.src = url;
    return texture;
  }

  function describeState() {
    var objectPart = mapObjects.length
      ? " · 승인된 작업 " + mapObjects.length + "건"
      : " · 승인된 작업 없음";
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
      resetCamera();
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
    resetCamera();
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

  function toRenderable(item) {
    var position = item.position || {};
    var size = item.size || {};
    return {
      center: siteToMesh(position),
      // 크기도 축이 바뀝니다. 높이(site Z)가 mesh Y로, 깊이(site Y)가 mesh Z로 갑니다.
      size: [
        Math.abs(Number(size.x) || 1),
        Math.abs(Number(size.z) || 1),
        Math.abs(Number(size.y) || 1)
      ],
      color: hexToRgb(item.color)
    };
  }

  // 변환이 manifest bounds에 의존하므로, 지형과 오브젝트 중 무엇이 먼저
  // 도착하든 좌표가 맞도록 원본을 들고 있다가 다시 계산합니다.
  function rebuildMapObjects() {
    mapObjects = mapObjectsRaw.map(toRenderable);
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
      rebuildMapObjects();
      if (!bounds) boundsFromObjects();
      draw();
      describeState();
    } catch (error) {
      console.warn("Map object load failed:", error);
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
  }
  canvas.addEventListener("pointerup", stopDrag);
  canvas.addEventListener("pointercancel", stopDrag);
  canvas.addEventListener("wheel", function (event) {
    event.preventDefault();
    distance *= Math.exp(event.deltaY * 0.001);
    distance = Math.max(1, Math.min(3000, distance));
    draw();
  }, { passive: false });
  canvas.addEventListener("dblclick", resetCamera);
  window.addEventListener("message", function (event) {
    if (event.origin !== window.location.origin || !event.data) return;
    if (event.data.type === "sitegit.isaac-map.fit") resetCamera();
    // 관리자가 승인하면 부모 창이 이 메시지를 보냅니다.
    if (event.data.type === "sitegit.isaac-map.reload-objects") loadMapObjects();
  });
  new ResizeObserver(resize).observe(root);
  resize();
  // 지형은 60MB라 느립니다. 오브젝트는 기다리지 않고 함께 받습니다.
  loadMesh();
  loadMapObjects();
}());
