"""The demo editor: every request it makes runs and answers as usual, and
nothing it does commits. A real editor's save on the same site sticks.
"""

from AccessControl.SecurityManagement import noSecurityManager
from plone import api
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.demoeditor.demo import DEMO_LOCAL_ROLES
from plone.demoeditor.demo import DEMO_ROLES
from plone.demoeditor.demo import DEMO_USER_ID
from plone.demoeditor.demo import ensure_demo_editor
from plone.demoeditor.demo import make_demo_editor_at_startup
from plone.keyring.interfaces import IKeyManager
from plone.restapi.testing import RelativeSession
from zope.component import getUtility
from zope.processlifetime import DatabaseOpenedWithRoot

import pytest
import transaction


PASSWORD = "demo-password"  # noqa: S105  a test account's password


@pytest.fixture
def page(functional):
    portal = functional["portal"]
    ensure_demo_editor(portal, PASSWORD, ["/"])
    with api.env.adopt_user(username=SITE_OWNER_NAME):
        doc = api.content.create(
            container=portal, type="Document", id="page", title="Original title"
        )
        # Published, as a demo site's pages are.
        api.content.transition(obj=doc, transition="publish")
    transaction.commit()
    return doc


def session(portal, auth=None, token=None) -> RelativeSession:
    s = RelativeSession(portal.absolute_url())
    s.headers.update({"Accept": "application/json"})
    if auth:
        s.auth = auth
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def demo_token(portal) -> str:
    response = session(portal).post(
        "/@login", json={"login": DEMO_USER_ID, "password": PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["token"]


def test_a_demo_save_answers_but_does_not_stick(functional, page):
    portal = functional["portal"]
    demo = session(portal, auth=(DEMO_USER_ID, PASSWORD))
    response = demo.patch("/page", json={"title": "Changed by a visitor"})
    assert response.status_code == 204
    transaction.begin()
    assert portal["page"].title == "Original title"


def test_a_demo_add_does_not_stick(functional, page):
    portal = functional["portal"]
    demo = session(portal, auth=(DEMO_USER_ID, PASSWORD))
    response = demo.post(
        "/",
        json={"@type": "Document", "id": "visitor-page", "title": "A visitor's page"},
    )
    assert response.status_code == 201
    transaction.begin()
    assert "visitor-page" not in portal.objectIds()


def test_a_demo_delete_does_not_stick(functional, page):
    portal = functional["portal"]
    demo = session(portal, auth=(DEMO_USER_ID, PASSWORD))
    assert demo.delete("/page").status_code == 204
    transaction.begin()
    assert "page" in portal.objectIds()


def test_a_demo_move_does_not_stick(functional, page):
    portal = functional["portal"]
    with api.env.adopt_user(username=SITE_OWNER_NAME):
        api.content.create(
            container=portal, type="Folder", id="folder", title="A section"
        )
    transaction.commit()
    demo = session(portal, auth=(DEMO_USER_ID, PASSWORD))
    response = demo.post(
        "/folder/@move", json={"source": [portal["page"].absolute_url()]}
    )
    assert response.status_code == 200
    # The move itself happened (and answered so); only its commit is thrown away.
    assert response.json()[0]["target"].endswith("/folder/page")
    transaction.begin()
    assert "page" in portal.objectIds()
    assert "page" not in portal["folder"].objectIds()


def test_a_real_editors_save_sticks(functional, page):
    portal = functional["portal"]
    owner = session(portal, auth=(SITE_OWNER_NAME, SITE_OWNER_PASSWORD))
    response = owner.patch("/page", json={"title": "Changed by an editor"})
    assert response.status_code == 204
    transaction.begin()
    assert portal["page"].title == "Changed by an editor"


def test_a_demo_save_with_the_login_token_does_not_stick(functional, page):
    # Inka signs in through @login and acts with the token it returns. On a
    # fresh site the first sign-in rotates the keyring the token is signed
    # with, so a doomed @login would hand out a token signed with a secret
    # that was never saved.
    portal = functional["portal"]
    demo = session(portal, token=demo_token(portal))
    response = demo.patch("/page", json={"title": "Changed by a visitor"})
    assert response.status_code == 204
    transaction.begin()
    assert portal["page"].title == "Original title"


def test_the_demo_token_survives_a_weekly_keyring_rotation(functional, page):
    # A site that is never rebuilt rotates the keyring every week, on whichever
    # sign-in comes first; the demo's must keep its rotation like any other.
    portal = functional["portal"]
    session(portal, auth=(SITE_OWNER_NAME, SITE_OWNER_PASSWORD)).post(
        "/@login", json={"login": SITE_OWNER_NAME, "password": SITE_OWNER_PASSWORD}
    )
    transaction.begin()
    ring = getUtility(IKeyManager)["_system"]
    ring.last_rotation = 0  # a week (and more) ago
    transaction.commit()
    demo = session(portal, token=demo_token(portal))
    user_actions = [a["id"] for a in demo.get("/@actions").json()["user"]]
    assert "logout" in user_actions


def test_a_demo_editor_can_open_and_save_the_published_site_root(functional, page):
    # A "Try editing" button on the homepage opens the site root in the editor.
    portal = functional["portal"]
    demo = session(portal, token=demo_token(portal))
    actions = [a["id"] for a in demo.get("/@actions").json()["object"]]
    assert "edit" in actions
    response = demo.patch("/", json={"title": "Changed by a visitor"})
    assert response.status_code == 204
    transaction.begin()
    assert portal.title != "Changed by a visitor"


def start_zope(functional) -> None:
    db = functional["app"]._p_jar.db()
    transaction.commit()
    try:
        make_demo_editor_at_startup(DatabaseOpenedWithRoot(db))
    finally:
        noSecurityManager()
    transaction.begin()


def test_startup_makes_the_demo_editor_on_the_named_site(functional, monkeypatch):
    portal = functional["portal"]
    monkeypatch.setenv("DEMO_EDITOR_PASSWORD", "boot-password")
    monkeypatch.setenv("DEMO_EDITOR_SITE", portal.getId())
    monkeypatch.setenv("DEMO_EDITOR_PATHS", "/")
    start_zope(functional)
    user = api.user.get(username=DEMO_USER_ID)
    assert user is not None
    assert set(user.getRoles()) == set(DEMO_ROLES) | {"Authenticated"}
    assert set(user.getRolesInContext(portal)) >= set(DEMO_LOCAL_ROLES)
    assert portal.acl_users.authenticate(
        DEMO_USER_ID, "boot-password", functional["request"]
    )


def test_startup_resets_an_existing_demo_editor(functional, monkeypatch):
    # A site that persists across restarts already has the account: the next
    # start sets the current password and roles rather than failing.
    portal = functional["portal"]
    ensure_demo_editor(portal, "old-password", ["/"])
    portal.acl_users.portal_role_manager.assignRolesToPrincipal(
        ["Manager"], DEMO_USER_ID
    )
    monkeypatch.setenv("DEMO_EDITOR_PASSWORD", "new-password")
    monkeypatch.setenv("DEMO_EDITOR_SITE", portal.getId())
    monkeypatch.setenv("DEMO_EDITOR_PATHS", "/")
    start_zope(functional)
    assert set(api.user.get(username=DEMO_USER_ID).getRoles()) == set(DEMO_ROLES) | {
        "Authenticated"
    }
    assert portal.acl_users.authenticate(
        DEMO_USER_ID, "new-password", functional["request"]
    )
    assert not portal.acl_users.authenticate(
        DEMO_USER_ID, "old-password", functional["request"]
    )


def test_startup_makes_no_demo_editor_without_a_password(functional, monkeypatch):
    portal = functional["portal"]
    monkeypatch.delenv("DEMO_EDITOR_PASSWORD", raising=False)
    monkeypatch.setenv("DEMO_EDITOR_SITE", portal.getId())
    monkeypatch.setenv("DEMO_EDITOR_PATHS", "/")
    start_zope(functional)
    assert api.user.get(username=DEMO_USER_ID) is None


def test_startup_refuses_a_password_without_a_site(functional, monkeypatch):
    # The account reads whatever its roles allow: which site gets it is
    # always named, never guessed.
    monkeypatch.setenv("DEMO_EDITOR_PASSWORD", "boot-password")
    monkeypatch.delenv("DEMO_EDITOR_SITE", raising=False)
    with pytest.raises(KeyError, match="DEMO_EDITOR_SITE"):
        start_zope(functional)


def test_startup_refuses_a_password_without_editing_paths(functional, monkeypatch):
    # Where the account may edit (and so read drafts) is named, never guessed.
    monkeypatch.setenv("DEMO_EDITOR_PASSWORD", "boot-password")
    monkeypatch.setenv("DEMO_EDITOR_SITE", functional["portal"].getId())
    monkeypatch.delenv("DEMO_EDITOR_PATHS", raising=False)
    with pytest.raises(KeyError, match="DEMO_EDITOR_PATHS"):
        start_zope(functional)


def test_the_demo_edits_only_inside_its_paths(functional):
    # A site can hold content the public must not read: the demo account gets
    # its editing roles on the paths it is given, and nowhere else.
    portal = functional["portal"]
    with api.env.adopt_user(username=SITE_OWNER_NAME):
        docs = api.content.create(
            container=portal, type="Folder", id="docs", title="Docs"
        )
        api.content.create(
            container=docs, type="Document", id="draft", title="A docs draft"
        )
        api.content.create(
            container=portal, type="Document", id="secret", title="Private elsewhere"
        )
    ensure_demo_editor(portal, PASSWORD, ["/docs"])
    transaction.commit()
    demo = session(portal, token=demo_token(portal))

    inside = demo.get("/docs/draft")
    assert inside.status_code == 200
    assert inside.json()["title"] == "A docs draft"
    assert demo.patch("/docs/draft", json={"title": "x"}).status_code == 204

    outside = demo.get("/secret")
    assert outside.status_code == 401
    assert "Private elsewhere" not in outside.text
    assert demo.patch("/", json={"title": "x"}).status_code == 401
