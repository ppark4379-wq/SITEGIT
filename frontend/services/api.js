/** SiteGit FastAPI 호출을 한 곳에 모으기 위한 공통 클라이언트. */
export async function apiRequest(path, options = {}) {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`);
  const type = response.headers.get('content-type') || '';
  return type.includes('application/json') ? response.json() : response.text();
}
