"""A demo site's admin password comes from DEMO_ADMIN_PASSWORD, set when Zope
starts.

The admin lives in the Zope root's user folder, outside any site, so a demo
that recreates its site on every start keeps whatever password the instance
was made with — on a public URL, that is usually the image's default.
"""

from AccessControl.SecurityManagement import noSecurityManager
from OFS.userfolder import UserFolder
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


def test_startup_sets_it_in_a_classic_root_user_folder(functional, monkeypatch):
    # A fresh database's root has Zope's classic user folder until Plone's
    # setup replaces it, and a demo that recreates its database on every boot
    # starts on exactly that: the admin password step ran then, found no PAS
    # `users` plugin, and stopped Zope from starting.
    app = functional["app"]
    app._delObject("acl_users")
    app._setObject("acl_users", UserFolder())
    app.acl_users.userFolderAddUser(
        SITE_OWNER_NAME, SITE_OWNER_PASSWORD, ["Manager"], []
    )
    transaction.commit()
    monkeypatch.setenv("DEMO_ADMIN_PASSWORD", "a-secret-password")
    start_zope(functional)
    user = app.acl_users.getUser(SITE_OWNER_NAME)
    assert user.authenticate("a-secret-password", functional["request"])
    assert not user.authenticate(SITE_OWNER_PASSWORD, functional["request"])
    assert "Manager" in user.getRoles()
