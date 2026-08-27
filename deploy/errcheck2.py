from app import db
# FK 위반 케이스: 존재하는 부모를 자식이 참조 중일 때 삭제
rows = db.fetch_all('SELECT ID FROM "SPEECHAPP_USER"."USER_PROFILE" FETCH FIRST 1 ROWS ONLY')
if rows:
    uid = rows[0]["USER_ID"]
    print("parent USER_ID =", uid)
    try:
        db.execute_dml(f'DELETE FROM "SPEECHAPP_USER"."APP_USER" WHERE "ID" = {uid}')
        print("deleted?! (FK 미동작)")
    except Exception as e:
        print(type(e).__name__, "||", repr(str(e))[:220])
else:
    print("USER_PROFILE 비어있음 - 테스트 불가")