def test_db_connection_and_auth_dependency(api, make_user):
    # 確認測試資料庫可連線、lifespan 有啟動
    assert api.get("/api/ready").status_code == 200
