'use strict';
const main = document.querySelector('#main');
const nav = document.querySelector('#nav');
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let me = null;
async function api(path, data) {
  const headers = data === undefined ? {} : {'Content-Type':'application/json'};
  if (data !== undefined && me) headers['X-CSRF-Token'] = me.csrf_token;
  const response = await fetch(path, {method:data === undefined ? 'GET':'POST', headers, credentials:'same-origin', body:data === undefined ? undefined:JSON.stringify(data)});
  const body = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !['/api/login','/api/register'].includes(path)) location.replace('/login?reason=auth');
    throw new Error(body.error || 'Nie udało się wykonać operacji.');
  }
  return body;
}
function heading(label,title,description) {
  return `<div class="page-heading"><div><span class="eyebrow">${label}</span><h1>${title}</h1><p class="muted">${description}</p></div></div>`;
}
function authPage(register) {
  document.title = (register ? 'Rejestracja' : 'Logowanie') + ' · Arena Emocji';
  nav.innerHTML = `<a href="/login">Logowanie</a><a href="/register">Rejestracja</a>`;
  main.innerHTML = `<div class="auth-layout"><section class="auth-intro"><span class="eyebrow">Wiedza w małych krokach</span><h1>Twój kolejny<br>dobry wynik.</h1><p class="muted">Twórz własne quizy, sprawdzaj wiedzę<br>i śledź swoje postępy.</p><ul><li>Własna biblioteka pytań</li><li>Wynik od razu po rozwiązaniu</li><li>Historia dostępna tylko dla Ciebie</li></ul></section><section class="panel"><span class="eyebrow">${register?'Nowe konto':'Witaj ponownie'}</span><h1>${register?'Utwórz konto':'Zaloguj się'}</h1><p class="muted">${register?'Zacznij od swojego loginu i hasła.':'Wróć do swoich quizów i wyników.'}</p>${!register && new URLSearchParams(location.search).get('reason')==='auth'?'<p class="notice">Ta strona wymaga zalogowania.</p>':''}<form id="auth" novalidate><label class="form-field">Login<input name="username" required minlength="3" maxlength="30" pattern="[A-Za-z0-9_]{3,30}" autocomplete="username" placeholder="np. uczen_arek"></label><p class="help">3–30 liter bez polskich znaków, cyfr lub znaków _.</p><label class="form-field">Hasło<input name="password" type="password" required minlength="${register?12:1}" maxlength="128" autocomplete="${register?'new-password':'current-password'}"></label>${register?'<p class="help">Od 12 do 128 znaków. Możesz użyć długiej frazy.</p><label class="form-field">Powtórz hasło<input name="password_confirm" type="password" required minlength="12" maxlength="128" autocomplete="new-password"></label>':''}<p class="error" id="error" role="alert"></p><button class="wide" type="submit">${register?'Utwórz konto':'Zaloguj się'}</button></form><p class="auth-switch">${register?'Masz już konto? <a href="/login">Zaloguj się</a>':'Nie masz konta? <a href="/register">Zarejestruj się</a>'}</p></section></div>`;
  document.querySelector('#auth').onsubmit = async e => {
    e.preventDefault();
    const form=e.currentTarget, error=document.querySelector('#error'), button=form.querySelector('button');
    const data=Object.fromEntries(new FormData(form));
    error.textContent='';
    if (!/^[A-Za-z0-9_]{3,30}$/.test(data.username)) {error.textContent='Login: 3–30 liter bez polskich znaków, cyfr lub znaków _.'; return;}
    if (data.password.length < (register?12:1) || data.password.length > 128) {error.textContent=register?'Hasło musi mieć od 12 do 128 znaków.':'Wpisz hasło (maksymalnie 128 znaków).';return;}
    if (register && data.password !== data.password_confirm) {error.textContent='Hasła muszą być identyczne.';return;}
    button.disabled=true;
    try {await api(register?'/api/register':'/api/login',data); location.assign('/quizy');}
    catch(err) {error.textContent=err.message;}
    finally {button.disabled=false;}
  };
}
async function listQuizzes() {
  const quizzes=await api('/api/quizzes');
  main.innerHTML=heading('Twoja przestrzeń','Biblioteka quizów','Rozwiąż quiz startowy lub dodaj własny zestaw pytań.')+`<div class="actions"><a class="button" href="/dodaj">+ Dodaj quiz</a><span class="muted">Zalogowano jako ${esc(me.username)}</span></div><br><div class="grid">${quizzes.map(q=>`<article class="quiz-card"><span class="badge">${q.owner_id===null?'QUIZ STARTOWY':'TWÓJ PRYWATNY QUIZ'}</span><h2>${esc(q.title)}</h2><p class="muted">${esc(q.description)}</p><span class="meta">Liczba pytań: ${q.count} · ABCD</span><button data-quiz="${q.id}">Rozwiąż quiz →</button></article>`).join('')}</div>`;
  main.querySelectorAll('[data-quiz]').forEach(button=>button.onclick=()=>solveQuiz(Number(button.dataset.quiz)).catch(showError));
}
function showError(error) {
  const p=document.createElement('p');p.className='error';p.setAttribute('role','alert');p.textContent=error.message;main.prepend(p);
}
function questionFields(index) {
  return `<fieldset data-question><legend>Pytanie ${index}</legend><label class="form-field">Treść pytania<input name="prompt" required minlength="3" maxlength="300"></label><div class="two-col">${['A','B','C','D'].map((letter,i)=>`<label class="form-field">Odpowiedź ${letter}<input name="option${i}" required maxlength="160"></label>`).join('')}</div><label class="form-field">Poprawna odpowiedź<select name="correct"><option value="0">A</option><option value="1">B</option><option value="2">C</option><option value="3">D</option></select></label></fieldset>`;
}
function createQuiz() {
  main.innerHTML=heading('Własne materiały','Dodaj quiz','Quiz będzie widoczny tylko na Twoim koncie. Możesz dodać od 1 do 10 pytań.')+`<form class="panel narrow" id="quiz-form"><label class="form-field">Tytuł quizu<input name="title" required minlength="3" maxlength="80" placeholder="np. Podstawy sieci komputerowych"></label><label class="form-field">Opis<textarea name="description" maxlength="240" placeholder="Czego dotyczy ten quiz?"></textarea></label><div id="questions">${questionFields(1)}</div><p class="error" id="error" role="alert"></p><div class="actions"><button type="button" class="secondary" id="add-question">+ Kolejne pytanie</button><button type="submit">Zapisz quiz</button></div></form>`;
  document.querySelector('#add-question').onclick=e=>{
    const container=document.querySelector('#questions'), count=container.children.length;
    if(count<10) container.insertAdjacentHTML('beforeend', questionFields(count+1));
    if(count+1>=10)e.currentTarget.disabled=true;
  };
  document.querySelector('#quiz-form').onsubmit=async e=>{
    e.preventDefault(); const form=e.currentTarget, error=document.querySelector('#error'), button=form.querySelector('[type=submit]');error.textContent='';
    const data={title:form.elements.title.value.trim(),description:form.elements.description.value.trim(),questions:[...form.querySelectorAll('[data-question]')].map(q=>({prompt:q.querySelector('[name=prompt]').value.trim(),options:[0,1,2,3].map(i=>q.querySelector(`[name=option${i}]`).value.trim()),correct:Number(q.querySelector('[name=correct]').value)}))};
    if(data.title.length<3 || data.questions.some(q=>q.prompt.length<3 || q.options.some(o=>!o) || new Set(q.options.map(o=>o.toLowerCase())).size!==4)){error.textContent='Uzupełnij tytuł, pytania i cztery różne odpowiedzi.';return;}
    button.disabled=true;
    try{await api('/api/quizzes',data);location.assign('/quizy');}catch(err){error.textContent=err.message;}finally{button.disabled=false;}
  };
}
async function solveQuiz(id) {
  const quiz=await api(`/api/quizzes/${id}`);
  main.innerHTML=heading('Sprawdź swoją wiedzę',esc(quiz.title),'Zaznacz jedną odpowiedź w każdym pytaniu. Wynik obliczy serwer.')+`<form id="answers" class="panel narrow">${quiz.questions.map((q,i)=>`<fieldset><legend>${i+1}. ${esc(q.prompt)}</legend>${q.options.map((option,j)=>`<label class="option"><input type="radio" name="q${i}" value="${j}" required>${String.fromCharCode(65+j)}. ${esc(option)}</label>`).join('')}</fieldset>`).join('')}<p class="error" id="error" role="alert"></p><button type="submit">Sprawdź odpowiedzi</button></form>`;
  document.querySelector('#answers').onsubmit=async e=>{
    e.preventDefault();const form=e.currentTarget, button=form.querySelector('button'), data=new FormData(form);button.disabled=true;
    try{
      const result=await api(`/api/quizzes/${id}/submit`,{answers:quiz.questions.map((_,i)=>Number(data.get('q'+i)))});
      main.innerHTML=heading('Ukończono quiz',esc(quiz.title),'Twój wynik został zapisany na koncie.')+`<section class="panel narrow"><span class="eyebrow">Poprawne odpowiedzi</span><p class="score">${result.score} / ${result.total}</p><p class="success" role="status">Wynik: ${Math.round(100*result.score/result.total)}%. Możesz go sprawdzić w historii.</p><div class="actions"><a class="button" href="/historia">Zobacz moje wyniki</a><a class="button secondary" href="/quizy">Wróć do quizów</a></div></section>`;
    }catch(err){document.querySelector('#error').textContent=err.message;button.disabled=false;}
  };
}
async function historyPage() {
  const results=await api('/api/history');
  main.innerHTML=heading('Twoje postępy','Moje wyniki','Historia ostatnich 100 rozwiązań. Tylko Ty masz dostęp do swoich wyników.')+`<section class="panel table-wrap">${results.length?`<table><thead><tr><th>Quiz</th><th>Poprawne odpowiedzi</th><th>Wynik</th><th>Data</th></tr></thead><tbody>${results.map(r=>`<tr><td>${esc(r.title)}</td><td>${r.score} / ${r.total}</td><td>${Math.round(100*r.score/r.total)}%</td><td>${esc(new Date(r.created_at*1000).toLocaleString('pl-PL'))}</td></tr>`).join('')}</tbody></table>`:'<p class="muted">Nie masz jeszcze wyników. Rozwiąż swój pierwszy quiz.</p><a class="button" href="/quizy">Przejdź do quizów</a>'}</section>`;
}
async function start() {
  const path=location.pathname;
  if(['/login','/register'].includes(path)){authPage(path==='/register');return;}
  me=await api('/api/me');
  nav.innerHTML=[['/quizy','Quizy'],['/dodaj','Dodaj quiz'],['/historia','Moje wyniki']].map(([href,label])=>`<a href="${href}" ${href===path?'aria-current="page"':''}>${label}</a>`).join('')+'<button class="secondary" id="logout">Wyloguj się</button>';
  document.querySelector('#logout').onclick=async()=>{try{await api('/api/logout',{});location.replace('/login');}catch(err){showError(err);}};
  document.title=({'/quizy':'Biblioteka quizów','/dodaj':'Dodaj quiz','/historia':'Moje wyniki'}[path]||'Quizy')+' · Arena Emocji';
  if(path==='/dodaj')createQuiz();else if(path==='/historia')await historyPage();else await listQuizzes();
}
window.addEventListener('pageshow',event=>{if(event.persisted)location.reload();});
start().catch(showError);
