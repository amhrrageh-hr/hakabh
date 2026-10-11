import sys
# from fastapi.testclient import TestClient
from main import app
import database as db_mod

db = db_mod.SessionLocal()
sub = db.query(db_mod.Subscriber).first()
if not sub:
    print("No subscribers")
    sys.exit()

try:
    from fastapi import Request
    class DummyRequest:
        def __init__(self):
            self.session = {"sub_id": sub.id}
    req = DummyRequest()
    
    import asyncio
    from main import dashboard
    
    res = asyncio.run(dashboard(req, db))
    print("Dashboard rendered successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()
