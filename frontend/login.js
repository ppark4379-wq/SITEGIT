const form=document.querySelector('#loginForm');
const button=document.querySelector('#loginButton');
const errorBox=document.querySelector('#loginError');
const LAST_USERNAME_KEY='sitegit-last-username';
try{form.username.value=localStorage.getItem(LAST_USERNAME_KEY)||''}catch(error){form.username.value=''}
function clearPassword(){form.password.value=''}
clearPassword();
window.addEventListener('pageshow',clearPassword);
form.addEventListener('submit',async event=>{
  event.preventDefault();
  errorBox.classList.add('hidden');
  button.disabled=true;
  button.textContent='인증 중...';
  try{
    const response=await fetch('/api/v1/auth/login',{
      method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({username:form.username.value.trim(),password:form.password.value}),
    });
    if(!response.ok){
      const body=await response.json().catch(()=>({detail:'로그인에 실패했습니다.'}));
      throw new Error(typeof body.detail==='string'?body.detail:'로그인에 실패했습니다.');
    }
    try{localStorage.setItem(LAST_USERNAME_KEY,form.username.value.trim())}catch(error){}
    clearPassword();
    location.href='/';
  }catch(error){
    errorBox.textContent=error.message;
    errorBox.classList.remove('hidden');
  }finally{
    if(!errorBox.classList.contains('hidden'))clearPassword();
    button.disabled=false;
    button.textContent='로그인';
  }
});
