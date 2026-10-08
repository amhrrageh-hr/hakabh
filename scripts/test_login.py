import requests

s = requests.Session()
login = s.post('http://127.0.0.1:8000/login', data={'subscriber_number':'000000000','password':'password123'})
print('login status', login.status_code)
print('login resp', login.text)
resp = s.get('http://127.0.0.1:8000/million-hakbah')
print('dashboard status', resp.status_code)
print(resp.text[:400])
