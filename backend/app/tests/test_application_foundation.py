def test_project_metadata_search_and_pagination(foundation_db):
    from app.auth.auth_service import auth_service
    from app.projects.project_service import project_service

    account = auth_service.register("manager@example.com", "StrongPass123")
    user_id = account["user"]["id"]
    project_service.create_project(
        {
            "name": "Harbour Office",
            "project_number": "HBR-001",
            "client_name": "Harbour Holdings",
            "location": "Colombo",
            "description": "Commercial office project",
        },
        user_id,
    )
    project_service.create_project({"name": "School Block"}, user_id)

    projects, total = project_service.search_projects(user_id, search="harbour", limit=10, offset=0)
    assert total == 1
    assert projects[0]["project_number"] == "HBR-001"
    assert projects[0]["organization_name"]


def test_dashboard_summary_uses_owned_projects_and_organization(foundation_db):
    from app.auth.auth_service import auth_service
    from app.platform.platform_service import platform_service
    from app.projects.project_service import project_service

    account = auth_service.register("qs@example.com", "StrongPass123")
    user = account["user"]
    project_service.create_project({"name": "Tower A"}, user["id"])

    summary = platform_service.dashboard_summary(user)
    assert summary["project_count"] == 1
    assert summary["recent_projects"][0]["name"] == "Tower A"
    assert summary["context"]["organization"]["id"] == user["organization_id"]
    assert summary["member_count"] == 1


def test_account_and_organization_settings_merge(foundation_db):
    from app.auth.auth_service import auth_service
    from app.platform.platform_service import platform_service

    account = auth_service.register("admin@example.com", "StrongPass123")
    user = account["user"]
    organization_id = user["organization_id"]

    platform_service.update_account_settings(user["id"], {"email_updates": "enabled"})
    settings = platform_service.update_account_settings(user["id"], {"timezone": "Asia/Colombo"})
    assert settings == {"email_updates": "enabled", "timezone": "Asia/Colombo"}

    platform_service.update_organization_settings(organization_id, {"email_updates": "disabled"}, user["id"])
    organization_settings = platform_service.update_organization_settings(
        organization_id,
        {"default_currency": "LKR"},
        user["id"],
    )
    assert organization_settings == {"email_updates": "disabled", "default_currency": "LKR"}
