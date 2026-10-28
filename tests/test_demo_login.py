"""Signing in as the demo editor without a password: a login option.

A site with the demo editor lists "Try it as a demo editor" among its login
options (GET @login, beside any others: Google, …), and @login-demo signs a
visitor in as the account with no password at all. Its saves are thrown away
as before; a site without the demo editor offers neither.
"""

from plone import api
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.base.utils import get_installer
from plone.demoeditor.demo import delete_demo_editor
from plone.demoeditor.demo import DEMO_USER_ID
from plone.demoeditor.demo import ensure_demo_editor
from plone.keyring.interfaces import IKeyManager
from plone.restapi.testing import RelativeSession
from zope.component import getUtility

import pytest
import transaction


@pytest.fixture
def page(functional):
    portal = functional["portal"]
    ensure_demo_editor(portal, "a-password-nobody-types", ["/"])
    with api.env.adopt_user(username=SITE_OWNER_NAME):
        doc = api.content.create(
            container=portal, type="Document", id="page", title="Original title"
        )
        api.content.transition(obj=doc, transition="publish")
    transaction.commit()
    return doc


def session(portal, token=None) -> RelativeSession:
    s = RelativeSession(portal.absolute_url())
    s.headers.update({"Accept": "application/json"})
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


def demo_sign_in(portal) -> str:
    response = session(portal).post("/@login-demo")
    assert response.status_code == 200, response.text
    return response.json()["token"]


def test_the_login_options_offer_the_demo(functional, page):
    portal = functional["portal"]
    options = session(portal).get("/@login").json()["options"]
    assert {
        "id": "demo",
        "plugin": "demo",
        "title": "Try it as a demo editor",
        "url": f"{portal.absolute_url()}/@login-demo",
    } in options


def test_the_demo_signs_in_without_a_password(functional, page):
    portal = functional["portal"]
    demo = session(portal, token=demo_sign_in(portal))
    user = demo.get("/@users/demo")
    assert user.status_code == 200
    assert user.json()["id"] == DEMO_USER_ID


def test_a_save_after_a_demo_sign_in_does_not_stick(functional, page):
    portal = functional["portal"]
    demo = session(portal, token=demo_sign_in(portal))
    response = demo.patch("/page", json={"title": "Changed by a visitor"})
    assert response.status_code == 204
    transaction.begin()
    assert portal["page"].title == "Original title"


def test_the_demo_sign_in_keeps_a_weekly_keyring_rotation(functional, page):
    # As with @login: the sign-in that rotates the keyring must keep its
    # rotation, or its token is signed with a secret no later request knows.
    portal = functional["portal"]
    RelativeSession(portal.absolute_url()).post(
        "/@login",
        json={"login": SITE_OWNER_NAME, "password": SITE_OWNER_PASSWORD},
        headers={"Accept": "application/json"},
    )
    transaction.begin()
    getUtility(IKeyManager)["_system"].last_rotation = 0  # a week (and more) ago
    transaction.commit()
    demo = session(portal, token=demo_sign_in(portal))
    assert "logout" in [a["id"] for a in demo.get("/@actions").json()["user"]]


def test_no_demo_account_no_demo_option(functional, page):
    portal = functional["portal"]
    delete_demo_editor(portal)
    transaction.commit()
    options = session(portal).get("/@login").json()["options"]
    assert "demo" not in [o["id"] for o in options]
    assert session(portal).post("/@login-demo").status_code == 404


def test_a_site_without_the_add_on_offers_no_demo(functional, page):
    portal = functional["portal"]
    with api.env.adopt_roles(["Manager"]):
        get_installer(portal, portal.REQUEST).uninstall_product("plone.demoeditor")
    transaction.commit()
    options = session(portal).get("/@login").json()["options"]
    assert "demo" not in [o["id"] for o in options]
    assert session(portal).post("/@login-demo").status_code == 404
