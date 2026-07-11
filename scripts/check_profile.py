import httpx, json
r = httpx.post('http://localhost:7000/api/v1/auth/login', json={'email':'test@test.com','password':'test12345'})
token = r.json()['access_token']
r2 = httpx.get('http://localhost:7000/api/v1/profile/resume-state', headers={'Authorization': f'Bearer {token}'})
data = r2.json()
sp = data.get('structured_profile', {})
ev = sp.get('structured_evidence', [])
for e in ev:
    print(f"{e.get('title')}: skills={e.get('skills')}")
print("---")
print("technologies:", sp.get('technologies'))
print("ai_tools:", sp.get('ai_tools'))
print("automation_tools:", sp.get('automation_tools'))
