"""Arena Emocji: konta, prywatne quizy i wyniki. Uruchom: python app.py."""
import argparse
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from auth import password_hash, verify_password, token_hash

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('ARENA_DB', ROOT / 'data' / 'arena.db'))
SESSION_SECONDS = 3600
COOKIE_SECURE = os.environ.get('ARENA_COOKIE_SECURE') == '1'
USERNAME = re.compile(r'[A-Za-z0-9_]{3,30}\Z')


class Problem(Exception):
    def __init__(self, message, status=400):
        self.message, self.status = message, status


def require(condition, message, status=400):
    if not condition:
        raise Problem(message, status)


@contextmanager
def database():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            csrf_token TEXT NOT NULL, expires_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS login_attempts (
            key TEXT PRIMARY KEY, count INTEGER NOT NULL, until INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY, owner_id INTEGER REFERENCES users(id),
            title TEXT NOT NULL, description TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY, quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
            prompt TEXT NOT NULL, options TEXT NOT NULL, correct INTEGER NOT NULL CHECK(correct BETWEEN 0 AND 3));
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            quiz_id INTEGER NOT NULL REFERENCES quizzes(id), score INTEGER NOT NULL,
            total INTEGER NOT NULL, created_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS results_user ON results(user_id, created_at);
        ''')
        if not db.execute('SELECT 1 FROM quizzes WHERE owner_id IS NULL').fetchone():
            qid = db.execute('INSERT INTO quizzes(owner_id,title,description,created_at) VALUES(NULL,?,?,?)',
                             ('Bezpieczny start', 'Trzy pytania o bezpieczeństwo aplikacji webowych.', int(time.time()))).lastrowid
            for prompt, options, correct in [
                ('Jak należy przechowywać hasła?', ['Jawnym tekstem', 'Jako hash z losową solą', 'W pliku HTML', 'W nazwie użytkownika'], 1),
                ('Gdzie trzeba sprawdzać dane z formularza?', ['Tylko w CSS', 'Tylko w przeglądarce', 'W przeglądarce i na serwerze', 'Nigdzie'], 2),
                ('Co powinno się stać po wylogowaniu?', ['Sesja pozostaje aktywna', 'Hasło trafia do adresu URL', 'Wyniki są usuwane', 'Token sesji zostaje unieważniony'], 3),
            ]:
                db.execute('INSERT INTO questions(quiz_id,prompt,options,correct) VALUES(?,?,?,?)',
                           (qid, prompt, json.dumps(options, ensure_ascii=False), correct))


def text_field(data, key, minimum, maximum, label):
    value = data.get(key)
    require(isinstance(value, str), f'{label}: wymagany tekst.')
    value = value.strip()
    require(minimum <= len(value) <= maximum, f'{label}: od {minimum} do {maximum} znaków.')
    return value


def credentials(data, registration=False):
    name = text_field(data, 'username', 3, 30, 'Login')
    require(USERNAME.fullmatch(name), 'Login: 3–30 liter bez polskich znaków, cyfr lub znaków _.')
    password = data.get('password')
    require(isinstance(password, str) and 1 <= len(password) <= 128, 'Hasło: od 1 do 128 znaków.')
    if registration:
        require(len(password) >= 12, 'Hasło musi mieć od 12 do 128 znaków.')
        require(password == data.get('password_confirm'), 'Hasła muszą być identyczne.')
    return name, password


class Handler(BaseHTTPRequestHandler):
    server_version = 'ArenaEmocji'

    def log_message(self, fmt, *args):
        logging.info(fmt, *args)

    def send(self, data, status=200, content_type='application/json; charset=utf-8', headers=None):
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        for key, value in {
            'Content-Type': content_type, 'Content-Length': str(len(raw)),
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'same-origin', 'X-Frame-Options': 'DENY',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            **(headers or {}),
        }.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def cookie(self, token, age=SESSION_SECONDS):
        return f'arena_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={age}' + ('; Secure' if COOKIE_SECURE else '')

    def current_session(self, db):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookies.get('arena_session')
            if token:
                return db.execute('''SELECT s.*, u.username FROM sessions s JOIN users u ON u.id=s.user_id
                    WHERE s.token_hash=? AND s.expires_at>?''', (token_hash(token.value), int(time.time()))).fetchone()
        except Exception:
            return None

    def read_json(self):
        require(self.headers.get('Content-Type', '').split(';')[0] == 'application/json', 'Wymagany format JSON.', 415)
        origin = self.headers.get('Origin')
        if origin:
            parsed = urlsplit(origin)
            require(parsed.scheme in ('http', 'https') and parsed.netloc == self.headers.get('Host'), 'Niedozwolone źródło żądania.', 403)
        require(not self.headers.get('Transfer-Encoding'), 'Nieobsługiwany sposób przesyłania danych.', 400)
        length = int(self.headers.get('Content-Length', '0'))
        require(0 < length <= 65536, 'Nieprawidłowy rozmiar żądania.', 413)
        data = json.loads(self.rfile.read(length))
        require(isinstance(data, dict), 'Wymagany obiekt JSON.')
        return data

    def do_GET(self):
        self.handle_request(False)

    def do_POST(self):
        self.handle_request(True)

    def handle_request(self, post):
        try:
            path = urlsplit(self.path).path
            data = self.read_json() if post else {}
            with database() as db:
                session = self.current_session(db)
                if not post and not path.startswith('/api/'):
                    if path == '/':
                        return self.send(b'', 303, headers={'Location': '/quizy' if session else '/login'})
                    assets = {'/style.css': ('style.css', 'text/css'), '/app.js': ('app.js', 'text/javascript')}
                    if path in assets:
                        name, content_type = assets[path]
                        return self.send((ROOT/'static'/name).read_bytes(), content_type=content_type+'; charset=utf-8')
                    require(path in ('/login', '/register', '/quizy', '/dodaj', '/historia'), 'Nie znaleziono strony.', 404)
                    if path in ('/quizy', '/dodaj', '/historia') and not session:
                        return self.send(b'', 303, headers={'Location': '/login?reason=auth'})
                    if path in ('/login', '/register') and session:
                        return self.send(b'', 303, headers={'Location': '/quizy'})
                    return self.send((ROOT/'static/index.html').read_bytes(), content_type='text/html; charset=utf-8')
                if post and path in ('/api/register', '/api/login'):
                    # Limit obejmuje także nieudane próby; oddzielny limit dla każdego IP.
                    key = self.client_address[0]
                    now = int(time.time())
                    db.execute('BEGIN IMMEDIATE')
                    attempt = db.execute('SELECT * FROM login_attempts WHERE key=?', (key,)).fetchone()
                    require(not attempt or attempt['until'] <= now or attempt['count'] < 15, 'Zbyt wiele prób. Spróbuj ponownie za 5 minut.', 429)
                    db.execute('''INSERT INTO login_attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET
                        count=CASE WHEN until<=? THEN 1 ELSE count+1 END,
                        until=CASE WHEN until<=? THEN excluded.until ELSE until END''', (key, now+300, now, now))
                    db.commit()
                    name, password = credentials(data, path == '/api/register')
                    if path == '/api/register':
                        require(not db.execute('SELECT id FROM users WHERE username=?', (name,)).fetchone(), 'Ten login jest już zajęty.', 409)
                        db.execute('INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)', (name, password_hash(password), now))
                    user = db.execute('SELECT * FROM users WHERE username=?', (name,)).fetchone()
                    # Również nieistniejący użytkownik przechodzi kosztowne wyprowadzenie klucza.
                    encoded = user['password_hash'] if user else 'pbkdf2_sha256$600000$'+'00'*16+'$'+'00'*32
                    valid = verify_password(password, encoded)
                    require(user is not None and valid, 'Nieprawidłowy login lub hasło.', 401)
                    if session:
                        db.execute('DELETE FROM sessions WHERE token_hash=?', (session['token_hash'],))
                    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                    db.execute('DELETE FROM sessions WHERE expires_at<=?', (now,))
                    db.execute('INSERT INTO sessions VALUES(?,?,?,?)', (token_hash(token), user['id'], csrf, now+SESSION_SECONDS))
                    db.commit()
                    return self.send({'username': user['username'], 'csrf_token': csrf}, 201 if path == '/api/register' else 200,
                                     headers={'Set-Cookie': self.cookie(token)})
                require(session is not None, 'Zaloguj się, aby uzyskać dostęp.', 401)
                uid = session['user_id']
                if post:
                    require(secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf_token']), 'Nieprawidłowy token CSRF. Odśwież stronę.', 403)
                if not post and path == '/api/me':
                    return self.send({'username': session['username'], 'csrf_token': session['csrf_token']})
                if post and path == '/api/logout':
                    db.execute('DELETE FROM sessions WHERE token_hash=?', (session['token_hash'],))
                    db.commit()
                    return self.send({'ok': True}, headers={'Set-Cookie': self.cookie('', 0)})
                if path == '/api/quizzes' and not post:
                    rows = db.execute('''SELECT q.id,q.title,q.description,q.owner_id,COUNT(p.id) AS count
                        FROM quizzes q JOIN questions p ON p.quiz_id=q.id
                        WHERE q.owner_id IS NULL OR q.owner_id=? GROUP BY q.id ORDER BY q.id DESC''', (uid,)).fetchall()
                    return self.send([dict(r) for r in rows])
                if path == '/api/quizzes' and post:
                    title = text_field(data, 'title', 3, 80, 'Tytuł')
                    description = text_field(data, 'description', 0, 240, 'Opis')
                    questions = data.get('questions')
                    require(isinstance(questions, list) and 1 <= len(questions) <= 10, 'Quiz musi zawierać od 1 do 10 pytań.')
                    validated = []
                    for q in questions:
                        require(isinstance(q, dict), 'Nieprawidłowe pytanie.')
                        prompt = text_field(q, 'prompt', 3, 300, 'Pytanie')
                        options = q.get('options')
                        require(isinstance(options, list) and len(options) == 4, 'Wpisz cztery odpowiedzi.')
                        options = [text_field({'value': v}, 'value', 1, 160, 'Odpowiedź') for v in options]
                        require(len(set(v.casefold() for v in options)) == 4, 'Odpowiedzi muszą się różnić.')
                        require(type(q.get('correct')) is int and 0 <= q['correct'] <= 3, 'Wybierz poprawną odpowiedź A–D.')
                        validated.append((prompt, json.dumps(options, ensure_ascii=False), q['correct']))
                    qid = db.execute('INSERT INTO quizzes(owner_id,title,description,created_at) VALUES(?,?,?,?)',
                                     (uid, title, description, int(time.time()))).lastrowid
                    db.executemany('INSERT INTO questions(quiz_id,prompt,options,correct) VALUES(?,?,?,?)', [(qid,*q) for q in validated])
                    db.commit()
                    return self.send({'id': qid}, 201)
                found = re.fullmatch(r'/api/quizzes/([0-9]+)(/submit)?', path)
                if found:
                    qid = int(found[1])
                    quiz = db.execute('SELECT * FROM quizzes WHERE id=? AND (owner_id IS NULL OR owner_id=?)', (qid,uid)).fetchone()
                    require(quiz is not None, 'Nie znaleziono dostępnego quizu.', 404)
                    questions = db.execute('SELECT * FROM questions WHERE quiz_id=? ORDER BY id', (qid,)).fetchall()
                    if not post and not found[2]:
                        return self.send({'id':qid,'title':quiz['title'],'questions':[
                            {'id':q['id'],'prompt':q['prompt'],'options':json.loads(q['options'])} for q in questions]})
                    if post and found[2]:
                        answers = data.get('answers')
                        require(isinstance(answers, list) and len(answers)==len(questions), 'Odpowiedz na wszystkie pytania.')
                        require(all(type(a) is int and 0 <= a <= 3 for a in answers), 'Nieprawidłowy numer odpowiedzi.')
                        score = sum(a == q['correct'] for a,q in zip(answers,questions))
                        rid = db.execute('INSERT INTO results(user_id,quiz_id,score,total,created_at) VALUES(?,?,?,?,?)',
                                         (uid,qid,score,len(questions),int(time.time()))).lastrowid
                        db.commit()
                        return self.send({'id':rid, 'score':score, 'total':len(questions)})
                if not post and path == '/api/history':
                    return self.send([dict(r) for r in db.execute('''SELECT r.id,q.title,r.score,r.total,r.created_at
                        FROM results r JOIN quizzes q ON q.id=r.quiz_id WHERE r.user_id=? ORDER BY r.id DESC LIMIT 100''', (uid,))])
                raise Problem('Nie znaleziono zasobu.', 404)
        except Problem as e:
            self.send({'error':e.message}, e.status)
        except sqlite3.IntegrityError:
            self.send({'error':'Login jest już zajęty lub dane są nieprawidłowe.'}, 409)
        except (ValueError, TypeError, UnicodeError):
            self.send({'error':'Nieprawidłowe dane żądania.'}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            logging.exception('Błąd serwera')
            self.send({'error':'Wewnętrzny błąd serwera.'}, 500)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Arena Emocji — aplikacja lokalna')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    initialize()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'Arena Emocji: http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
