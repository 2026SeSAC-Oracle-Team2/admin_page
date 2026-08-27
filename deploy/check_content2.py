from app import db
# IMAGE_RESOURCE 직접 INSERT 시도 (에러 메시지 확인)
try:
    n = db.execute_dml("INSERT INTO \"SPEECHAPP_CONTENT\".\"IMAGE_RESOURCE\" (\"IMAGE_NAME\",\"BUCKET_PATH\",\"PROBLEM_TYPE\") VALUES ('직접테스트.png','oci://b/p.png','WORD')")
    print("insert ok:", n)
    row = db.fetch_one("SELECT * FROM \"SPEECHAPP_CONTENT\".\"IMAGE_RESOURCE\" WHERE IMAGE_NAME='직접문제.png'")
    print("fetch:", row)
    row2 = db.fetch_one("SELECT IMAGE_ID FROM \"SPEECHAPP_CONTENT\".\"IMAGE_RESOURCE\" WHERE IMAGE_NAME='직접테스트.png'")
    print("fetch2:", row2)
    # 정리
    if row2:
        db.execute_dml(f'DELETE FROM "SPEECHAPP_CONTENT"."IMAGE_RESOURCE" WHERE IMAGE_ID = {row2["IMAGE_ID"]}')
        print("cleaned")
except Exception as e:
    print("ERR:", repr(str(e))[:200])