from app import db
# 올바른 값으로 재시도: DESCRIBE / GUESS, CHOSUNG / ASSOCIATION
try:
    db.execute_dml("INSERT INTO \"SPEECHAPP_CONTENT\".\"IMAGE_RESOURCE\" (\"IMAGE_NAME\",\"BUCKET_PATH\",\"PROBLEM_TYPE\") VALUES ('직접테스트.png','oci://b/p.png','DESCRIBE')")
    row2 = db.fetch_one("SELECT IMAGE_ID FROM \"SPEECHAPP_CONTENT\".\"IMAGE_RESOURCE\" WHERE IMAGE_NAME='직접테스트.png'")
    print("insert ok:", row2)
    rid = row2["IMAGE_ID"]
    db.execute_dml(f"INSERT INTO \"SPEECHAPP_CONTENT\".\"IMAGE_TAG\" (\"IMAGE_ID\",\"TAG_TEXT\") VALUES ({rid}, '동물')")
    db.execute_dml(f"INSERT INTO \"SPEECHAPP_CONTENT\".\"IMAGE_HINT\" (\"IMAGE_ID\",\"HINT_TYPE\",\"HINT_TEXT\") VALUES ({rid}, 'CHOSUNG', 'ㅁㅇㅁ')")
    print("tag+hint ok")
    # 정리
    db.execute_dml(f'DELETE FROM "SPEECHAPP_CONTENT"."IMAGE_TAG" WHERE IMAGE_ID = {rid}')
    db.execute_dml(f'DELETE FROM "SPEECHAPP_CONTENT"."IMAGE_HINT" WHERE IMAGE_ID = {rid}')
    db.execute_dml(f'DELETE FROM "SPEECHAPP_CONTENT"."IMAGE_RESOURCE" WHERE IMAGE_ID = {rid}')
    print("cleaned")
except Exception as e:
    print("ERR:", repr(str(e))[:200])