import asyncio
from fastapi.templating import Jinja2Templates
from fastapi import Request
import database as db_mod
from main import dashboard, templates

db = db_mod.SessionLocal()
subs = db.query(db_mod.Subscriber).all()
if not subs:
    print("No subscribers")
    import sys
    sys.exit()

class DummyRequest(Request):
    def __init__(self, sub_id):
        self.scope = {"type": "http"}
        self._session = {"sub_id": sub_id}
    @property
    def session(self):
        return self._session

for sub in subs:
    req = DummyRequest(sub.id)
    try:
        res = asyncio.run(dashboard(req, db))
        body = res.body
        print(f"Sub {sub.id}: Successfully rendered template! Length: {len(body)}")
    except Exception as e:
        print(f"Sub {sub.id}: Error rendering template!")
        import traceback
        traceback.print_exc()
