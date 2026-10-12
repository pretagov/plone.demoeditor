"""A demo site's admin password comes from DEMO_ADMIN_PASSWORD, set when Zope
starts.

The admin lives in the Zope root's user folder, outside any site, so a demo
that recreates its site on every start keeps whatever password the instance
was made with — on a public URL, that is usually the image's default.
"""

from AccessControl.SecurityManagement import noSecurityManager
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.demoeditor.demo import set_admin_password_at_startup
from zope.processlifetime import DatabaseOpenedWithRoot

import pytest
import transaction


def start_zope(functional) -> None:
    db = functional["app"]._p_jar.db()
    transaction.commit()
    try:
        set_admin_password_at_startup(DatabaseOpenedWithRoot(db))
    finally:
        noSecurityManager()
    transaction.begin()


def can_sign_in(functional, password: str) -> bool:
    # The root user folder is a PluggableAuthService, as in a Plone instance;
    # its users live in the ZODBUserManager plugin `users`.
    users = functional["app"].acl_users.users
    return bool(
        users.authenticateCredentials({"login": SITE_OWNER_NAME, "password": password})
    )


def test_startup_sets_the_admin_password(functional, monkeypatch):
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "a-secret-password")
    start_zope(functional)
    assert can_sign_in(functional, "a-secret-password")
    assert not can_sign_in(functional, SITE_OWNER_PASSWORD)


def test_startup_keeps_the_admin_roles(functional, monkeypatch):
    roles = set(functional["app"].acl_users.getUser(SITE_OWNER_NAME).getRoles())
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "a-secret-password")
    start_zope(functional)
    assert set(functional["app"].acl_users.getUser(SITE_OWNER_NAME).getRoles()) == roles


def test_startup_leaves_the_password_alone_without_the_setting(functional, monkeypatch):
    monkeypatch.delenv("DEMO_ADMIN_PASSWORD", raising=False)
    start_zope(functional)
    assert can_sign_in(functional, SITE_OWNER_PASSWORD)


def test_startup_refuses_when_there_is_no_admin(functional, monkeypatch):
    functional["app"].acl_users.users.removeUser(SITE_OWNER_NAME)
    transaction.commit()
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "a-secret-password")
    with pytest.raises(LookupError):
        start_zope(functional)
