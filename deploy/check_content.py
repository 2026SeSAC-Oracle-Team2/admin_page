from app import db
# IMAGE_RESOURCE 전체 확인
rows = db.fetch_all('SELECT * FROM "SPEECHAPP_CONTENT"."IMAGE_RESOURCE"')
print("IMAGE_RESOURCE rows:", len(rows))
for r in rows[:5]:
    print(r)
rows2 = db.fetch_all('SELECT * FROM "SPEECHAPP_CONTENT"."IMAGE_TAG"')
print("IMAGE_TAG rows:", len(rows2))
for r in rows2[:5]:
    print(r)
rows3 = db.fetch_all('SELECT * FROM "SPEECHAPP_CONTENT"."IMAGE_HINT"')
print("IMAGE_HINT rows:", len(rows3))
for r in rows3[:5]:
    print(r)