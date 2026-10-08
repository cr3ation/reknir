"""API tests for company archive export/import and backup listing."""

import io
import zipfile

from app.services import archive_import_service, backup_service


def test_export_company_archive_is_verifiable(client, admin_auth_headers, test_company_with_fiscal_year, tmp_path):
    company, _ = test_company_with_fiscal_year
    response = client.get(f"/api/backup/export-company/{company.id}", headers=admin_auth_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/zip")

    out = tmp_path / "company.zip"
    out.write_bytes(response.content)
    archive = archive_import_service.verify_archive(out)
    assert archive.manifest.scope == "company"
    assert archive.manifest.includes_credentials is False
    assert archive.companies[0].company.org_number == company.org_number
    with zipfile.ZipFile(out) as zf:
        assert "schema/company.schema.json" in zf.namelist()


def test_export_company_requires_admin(client, auth_headers, test_company):
    response = client.get(f"/api/backup/export-company/{test_company.id}", headers=auth_headers)
    assert response.status_code == 403


def test_export_unknown_company_is_404(client, admin_auth_headers):
    response = client.get("/api/backup/export-company/9999", headers=admin_auth_headers)
    assert response.status_code == 404


def test_import_company_refuses_duplicate_org_number(client, admin_auth_headers, test_company_with_fiscal_year):
    company, _ = test_company_with_fiscal_year
    exported = client.get(f"/api/backup/export-company/{company.id}", headers=admin_auth_headers).content

    response = client.post(
        "/api/backup/import-company",
        headers=admin_auth_headers,
        files={"file": ("company.zip", io.BytesIO(exported), "application/zip")},
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_import_company_creates_new_company(client, admin_auth_headers, test_company_with_fiscal_year, db_session):
    company, _ = test_company_with_fiscal_year
    exported = client.get(f"/api/backup/export-company/{company.id}", headers=admin_auth_headers).content

    # Change the org number inside the archive (and fix the manifest hashes) to
    # simulate importing a different company.
    import hashlib
    import json

    with zipfile.ZipFile(io.BytesIO(exported)) as src:
        members = {i.filename: src.read(i.filename) for i in src.infolist()}
    manifest = json.loads(members["manifest.json"])
    base = manifest["companies"][0]["path"]
    manifest["companies"][0]["org_number"] = "999999-0001"
    company_json = json.loads(members[f"{base}/company.json"])
    company_json["org_number"] = "999999-0001"
    members[f"{base}/company.json"] = json.dumps(company_json).encode()
    for entry in manifest["files"]:
        if entry["path"] == f"{base}/company.json":
            entry["bytes"] = len(members[entry["path"]])
            entry["sha256"] = hashlib.sha256(members[entry["path"]]).hexdigest()
    members["manifest.json"] = json.dumps(manifest).encode()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as dst:
        for name, data in members.items():
            dst.writestr(name, data)

    response = client.post(
        "/api/backup/import-company",
        headers=admin_auth_headers,
        files={"file": ("other.zip", io.BytesIO(buf.getvalue()), "application/zip")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"]["companies"] == 1
    new_id = body["company_ids"][0]
    assert new_id != company.id

    from app.models.company import Company

    assert db_session.query(Company).filter(Company.org_number == "999999-0001").one().id == new_id


def test_list_backups_reads_json_manifest(
    client, admin_auth_headers, test_company_with_fiscal_year, db_session, tmp_path, monkeypatch
):
    from app.services import archive_export_service

    monkeypatch.setattr(backup_service, "BACKUP_DIR", tmp_path)
    archive_export_service.export_archive(
        db_session, tmp_path / "reknir_backup_2026-01-01_00.00.00.zip", uploads_dir=tmp_path / "nothing"
    )
    (tmp_path / "not_a_backup.zip").write_bytes(b"junk")

    response = client.get("/api/backup/list", headers=admin_auth_headers)
    assert response.status_code == 200
    backups = response.json()
    assert len(backups) == 1
    assert backups[0]["format"] == "json"
    assert backups[0]["scope"] == "instance"
    assert backups[0]["companies"] == ["Test Company AB"]
    assert backups[0]["counts"]["companies"] == 1

    download = client.get(f"/api/backup/download/{backups[0]['filename']}", headers=admin_auth_headers)
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("application/zip")

    bad = client.get("/api/backup/download/not_a_backup.zip", headers=admin_auth_headers)
    assert bad.status_code == 400
