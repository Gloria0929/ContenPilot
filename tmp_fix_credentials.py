#!/usr/bin/env python3
"""修正账号 #4 的博客园凭据（补正确用户名与博客名）。"""
import sys

sys.path.insert(0, "/Users/fuhao/AIProjects/ContentPilot/src")

from publisher.database import SessionLocal, init_db
from publisher.models import Account
from publisher.security import encrypt_json

CREDENTIALS = {
    "username": "敖行客Allthinker",
    "token": "6312DD3B908E2728F0B90E82A38E10700971801C0C5A7EDB8EBBCA0B21FC5401",
    "blog_name": "Allthinker",
}

init_db()
s = SessionLocal()
try:
    account = s.query(Account).filter_by(id=4, platform="cnblogs").one()
    account.encrypted_credentials = encrypt_json(CREDENTIALS)
    s.commit()
    print(f"账号 #{account.id} {account.key} 凭据已更新")
finally:
    s.close()
