/** 프로젝트 변경 알림용 WebSocket 생성기. */
export function connectProjectRealtime(projectId, onMessage) {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(`${scheme}://${location.host}/api/v1/state/ws/${projectId}`);
  socket.onmessage = event => onMessage?.(JSON.parse(event.data));
  return socket;
}
