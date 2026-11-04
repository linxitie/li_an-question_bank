"""论坛文档附件上传 P2.5 测试。"""


def test_upload_rar_with_magic(client, auth_headers):
    content = b"Rar!\x1a\x07" + b"0" * 128
    files = {"file": ("a.rar", content, "application/vnd.rar")}
    resp = client.post("/api/forum/upload", headers=auth_headers, files=files)
    assert resp.status_code == 200
    assert resp.json()["type"] == "rar"


def test_upload_7z_with_magic(client, auth_headers):
    content = b"7z\xbc\xaf\x27\x1c" + b"0" * 128
    files = {"file": ("a.7z", content, "application/x-7z-compressed")}
    resp = client.post("/api/forum/upload", headers=auth_headers, files=files)
    assert resp.status_code == 200
    assert resp.json()["type"] == "7z"


def test_reject_executable(client, auth_headers):
    files = {"file": ("a.exe", b"MZ" + b"0" * 128, "application/octet-stream")}
    resp = client.post("/api/forum/upload", headers=auth_headers, files=files)
    assert resp.status_code == 422
