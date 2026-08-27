from app import db
# 1) 부모+자식 생성
db.execute_dml("INSERT INTO \"SPEECHAPP_USER\".\"APP_USER\" (\"UUID\",\"FIREBASE_UID\",\"EMAIL\") VALUES ('fk-probe-u','fk-probe-fb','fk-probe@x.com')")
uid = db.fetch_one("SELECT ID FROM \"SPEECHAPP_USER\".\"APP_USER\" WHERE \"UUID\" = 'fk-probe-u'")["ID"]
db.execute_dml(f"INSERT INTO \"SPEECHAPP_USER\".\"USER_PROFILE\" (\"USER_ID\",\"NICKNAME\") VALUES ({uid}, 'fk-probe-nick')")
print("생성: APP_USER.ID =", uid)

# 2) FK 위반 삭제 시도
try:
    db.execute_dml(f'DELETE FROM "SPEECHAPP_USER"."APP_USER" WHERE "ID" = {uid}')
    print("deleted?! (FK 미동작)")
except Exception as e:
    print(type(e).__name__, "||", repr(str(e))[:250])

# 3) 정리
pid = db.fetch_one(f'SELECT ID FROM "SPEECHAPP_USER"."USER_PROFILE" WHERE "USER_ID" = {uid}')["ID"]
db.execute_dml(f'DELETE FROM "SPEECHAPP_USER"."USER_PROFILE" WHERE "ID" = {pid}')
db.execute_dml(f'DELETE FROM "SPEECHAPP_USER"."APP_USER" WHERE "ID" = {uid}')
print("정리 완료")