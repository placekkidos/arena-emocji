import http.cookiejar
import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
from auth import password_hash, verify_password, token_hash


class Client:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None

    def call(self, path, data=None, csrf=True, headers=None):
        h = {'Content-Type':'application/json'}
        if csrf and self.csrf:
            h['X-CSRF-Token'] = self.csrf
        h.update(headers or {})
        req = urllib.request.Request(self.base+path, data=json.dumps(data).encode() if data is not None else None, headers=h)
        try:
            response = self.opener.open(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            body = json.loads(raw) if response.headers.get('Content-Type','').startswith('application/json') else raw
            if isinstance(body,dict) and 'csrf_token' in body:
                self.csrf = body['csrf_token']
            return response.status, body, response.headers

    def register(self, name='UczenA', password='Testowa fraza 2026!'):
        return self.call('/api/register', {'username':name,'password':password,'password_confirm':password})


class ArenaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_db = app.DB_PATH
        app.DB_PATH = Path(self.tmp.name)/'test.db'
        app.initialize()
        self.server = app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.client = Client(self.base)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        app.DB_PATH = self.old_db
        self.tmp.cleanup()

    def test_registration_password_hash_and_cookie_flags(self):
        status, body, headers = self.client.register()
        self.assertEqual(status,201)
        self.assertNotIn('password',body)
        self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn('SameSite=Lax',headers['Set-Cookie'])
        with app.database() as db:
            encoded = db.execute('SELECT password_hash FROM users').fetchone()[0]
            self.assertTrue(encoded.startswith('pbkdf2_sha256$600000$'))
            self.assertTrue(verify_password('Testowa fraza 2026!',encoded))
            self.assertNotIn('Testowa fraza',encoded)
            token = next(iter(self.client.jar)).value
            self.assertEqual(db.execute('SELECT token_hash FROM sessions').fetchone()[0],token_hash(token))

    def test_random_salts_for_equal_passwords(self):
        first, second = password_hash('Testowa fraza 2026!'), password_hash('Testowa fraza 2026!')
        self.assertNotEqual(first,second)
        self.assertTrue(verify_password('Testowa fraza 2026!',second))
        self.assertFalse(verify_password('Inne haslo',first))

    def test_server_validation_without_browser(self):
        for data in [
            {'username':'ab','password':'Testowa fraza 2026!','password_confirm':'Testowa fraza 2026!'},
            {'username':'Uczen','password':'short','password_confirm':'short'},
            {'username':'Uczen','password':'Testowa fraza 2026!','password_confirm':'inne'},
            {'username':'<script>','password':'Testowa fraza 2026!','password_confirm':'Testowa fraza 2026!'},
            {'username':['Uczen'],'password':123,'password_confirm':123},
        ]:
            with self.subTest(data=data):
                self.assertEqual(self.client.call('/api/register',data)[0],400)
        with app.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)

    def test_duplicate_username_case_insensitive(self):
        self.assertEqual(self.client.register()[0],201)
        self.assertEqual(Client(self.base).register('uczena')[0],409)

    def test_login_error_success_and_logout_revocation(self):
        self.client.register()
        other = Client(self.base)
        self.assertEqual(other.call('/api/login',{'username':'UczenA','password':'wrong'})[0],401)
        self.assertEqual(other.call('/api/login',{'username':'UczenA','password':'Testowa fraza 2026!'})[0],200)
        token = next(iter(other.jar)).value
        self.assertEqual(other.call('/api/logout',{})[0],200)
        self.assertEqual(Client(self.base).call('/api/me',headers={'Cookie':'arena_session='+token})[0],401)

    def test_private_pages_redirect_and_api_denies_anonymous(self):
        for path in ['/quizy','/dodaj','/historia']:
            status,html,_ = self.client.call(path)
            self.assertEqual(status,200)  # urllib follows the 303 to /login.
            self.assertIn(b'Arena Emocji',html)
            class NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self,*args,**kwargs): return None
            with self.assertRaises(urllib.error.HTTPError) as err:
                urllib.request.build_opener(NoRedirect).open(self.base+path)
            self.assertEqual(err.exception.code,303)
            self.assertEqual(err.exception.headers['Location'],'/login?reason=auth')
        for path in ['/api/me','/api/quizzes','/api/history','/api/quizzes/1']:
            self.assertEqual(self.client.call(path)[0],401)
        self.assertEqual(self.client.call('/api/quizzes',{})[0],401)

    def test_expired_or_forged_session(self):
        self.client.register()
        with app.database() as db:
            db.execute('UPDATE sessions SET expires_at=?',(int(time.time())-1,))
        self.assertEqual(self.client.call('/api/me')[0],401)
        self.assertEqual(Client(self.base).call('/api/me',headers={'Cookie':'arena_session=forged'})[0],401)

    def test_csrf_and_foreign_origin_are_rejected(self):
        self.client.register()
        self.assertEqual(self.client.call('/api/logout',{},csrf=False)[0],403)
        self.assertEqual(self.client.call('/api/logout',{},headers={'Origin':'https://evil.example'})[0],403)
        self.assertEqual(self.client.call('/api/me')[0],200)

    def quiz_data(self):
        return {'title':'Moja wiedza','description':'Test','questions':[{'prompt':'Ile to 2+2?','options':['1','2','3','4'],'correct':3}]}

    def test_create_list_solve_and_persist_history(self):
        self.client.register()
        status,created,_ = self.client.call('/api/quizzes',self.quiz_data())
        self.assertEqual(status,201)
        qid=created['id']
        self.assertIn(qid,[q['id'] for q in self.client.call('/api/quizzes')[1]])
        quiz=self.client.call(f'/api/quizzes/{qid}')[1]
        self.assertNotIn('correct',quiz['questions'][0])
        result=self.client.call(f'/api/quizzes/{qid}/submit',{'answers':[3],'score':999,'user_id':999})[1]
        self.assertEqual((result['score'],result['total']),(1,1))
        self.assertEqual(len(self.client.call('/api/history')[1]),1)
        fresh=Client(self.base)
        fresh.call('/api/login',{'username':'UczenA','password':'Testowa fraza 2026!'})
        self.assertEqual(fresh.call('/api/history')[1][0]['score'],1)

    def test_other_user_cannot_read_or_submit_private_quiz(self):
        self.client.register()
        qid=self.client.call('/api/quizzes',self.quiz_data())[1]['id']
        self.client.call(f'/api/quizzes/{qid}/submit',{'answers':[3]})
        other=Client(self.base);other.register('UczenB')
        self.assertEqual(other.call(f'/api/quizzes/{qid}')[0],404)
        self.assertEqual(other.call(f'/api/quizzes/{qid}/submit',{'answers':[3]})[0],404)
        self.assertNotIn(qid,[q['id'] for q in other.call('/api/quizzes')[1]])
        self.assertEqual(other.call('/api/history?user_id=1')[1],[])

    def test_invalid_quiz_rolls_back_and_invalid_answers_fail(self):
        self.client.register()
        data=self.quiz_data(); data['questions'].append({'prompt':'bad','options':['same']*4,'correct':0})
        self.assertEqual(self.client.call('/api/quizzes',data)[0],400)
        self.assertEqual(len(self.client.call('/api/quizzes')[1]),1)
        for answers in [[],[4,2,3],[True,2,3],['1',2,3],[1,2]]:
            self.assertEqual(self.client.call('/api/quizzes/1/submit',{'answers':answers})[0],400)
        self.assertEqual(self.client.call('/api/history')[1],[])

    def test_sql_and_html_are_stored_as_data(self):
        self.client.register()
        data=self.quiz_data();data['title']="<b>Próba</b> ' OR 1=1 --"
        qid=self.client.call('/api/quizzes',data)[1]['id']
        self.assertEqual(self.client.call(f'/api/quizzes/{qid}')[1]['title'],data['title'])
        with app.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM users').fetchone()[0],1)

    def test_login_rate_limit(self):
        with app.database() as db:
            db.execute('INSERT INTO login_attempts VALUES(?,?,?)',('127.0.0.1',15,int(time.time())+300))
        self.assertEqual(self.client.call('/api/login',{'username':'UczenA','password':'Testowa fraza 2026!'})[0],429)

    def test_private_files_and_security_headers(self):
        for path in ['/data/arena.db','/auth.py','/.git/config','/../app.py']:
            self.assertEqual(self.client.call(path)[0],404)
        _,_,headers=self.client.call('/login')
        self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertIn("script-src 'self'",headers['Content-Security-Policy'])


if __name__=='__main__':
    unittest.main()
