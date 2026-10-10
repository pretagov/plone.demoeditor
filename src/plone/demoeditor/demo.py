"""The demo editor: a public account whose saves are thrown away.

A demo site's "Try editing" button signs visitors in as this account (Inka's
/login?demo link). Its password reaches every browser, so nothing it does may
stick: once a request is known to be the demo account's, its transaction is
doomed. The request runs and answers as usual, so the editor behaves normally,
and nothing commits. A real editor's requests are untouched.

Doom protects writes, not reads: where it may edit, the account sees private
content too. It edits only on the paths it is given (DEMO_EDITOR_PATHS), and
only on sites that have plone.demoeditor installed.
"""

from AccessControl import getSecurityManager
from persistent.list import PersistentList
from plone.restapi.services.auth.login import Login
from Testing.makerequest import makerequest
from zope.annotation.interfaces import IAnnotations
from zope.processlifetime import IDatabaseOpenedWithRoot
from ZPublisher.interfaces import IPubAfterTraversal

import logging
import os
import transaction


logger = logging.getLogger("plone.demoeditor")

PROFILE = "plone.demoeditor"
# On the site: the paths the account was given its editing roles on, so they
# can be taken back from exactly there.
GRANTED_PATHS_KEY = "plone.demoeditor.granted_paths"
DEMO_USER_ID = "demo"
# Site-wide, the account is only a Member: what anyone signed in may do.
DEMO_ROLES = ["Member"]
# Its editing roles are local, on the paths it is given (DEMO_EDITOR_PATHS),
# so content elsewhere on the site stays out of its sight.
DEMO_LOCAL_ROLES = ["Contributor", "Editor", "Reviewer"]


def doom_demo_requests(event: IPubAfterTraversal) -> None:
    """Doom the transaction of every request the demo account makes.

    After traversal the request's user is known (authentication happens while
    traversing), and nothing has been written yet.

    Signing in (@login) is let through: it is already the demo account's
    request (the JWT plugin reads the login from its body), and its only
    writes are the sign-in's own. One of them is the weekly rotation of the
    keyring its token is signed with, due on a fresh site's first sign-in;
    thrown away, it would leave the token signed with a secret no later
    request knows.
    """
    if isinstance(event.request.get("PUBLISHED"), Login):
        return
    if getSecurityManager().getUser().getId() == DEMO_USER_ID:
        transaction.doom()


def ensure_demo_editor(site, password: str, paths: list[str]) -> None:
    """Make the demo account on `site`, or reset its password and roles.

    `paths` are where it may edit, relative to the site ("/" is the site
    itself): each gets the editing roles as local roles, which its contents
    inherit.
    """
    users = site.acl_users.source_users
    if DEMO_USER_ID in users.getUserIds():
        users.userSetPassword(DEMO_USER_ID, password)
    else:
        users.addUser(DEMO_USER_ID, DEMO_USER_ID, password)
    site.acl_users.portal_role_manager.assignRolesToPrincipal(DEMO_ROLES, DEMO_USER_ID)
    granted = IAnnotations(site).setdefault(GRANTED_PATHS_KEY, PersistentList())
    for path in [p for p in granted if p not in paths]:
        take_back_editing_roles(site, path)
        granted.remove(path)
    for path in paths:
        obj = at_path(site, path)
        if path not in granted:
            granted.append(path)
        if set(obj.get_local_roles_for_userid(DEMO_USER_ID)) == set(DEMO_LOCAL_ROLES):
            continue
        obj.manage_setLocalRoles(DEMO_USER_ID, DEMO_LOCAL_ROLES)
        # The catalog answers listings and search by who may view each item.
        obj.reindexObjectSecurity()


def at_path(site, path: str):
    return site.unrestrictedTraverse(path.strip("/")) if path.strip("/") else site


def take_back_editing_roles(site, path: str) -> None:
    # The path may be gone since; nothing to take back there.
    obj = site.unrestrictedTraverse(path.strip("/"), None) if path.strip("/") else site
    if obj is not None and obj.get_local_roles_for_userid(DEMO_USER_ID):
        obj.manage_delLocalRoles([DEMO_USER_ID])
        obj.reindexObjectSecurity()


def delete_demo_editor(site) -> None:
    """Delete the demo account, and its editing roles, on `site`."""
    for path in IAnnotations(site).pop(GRANTED_PATHS_KEY, []):
        take_back_editing_roles(site, path)
    if DEMO_USER_ID in site.acl_users.source_users.getUserIds():
        site.acl_users._doDelUser(DEMO_USER_ID)


def demo_settings() -> tuple[str, list[str]] | None:
    """The demo's password and editing paths, or None when it is off.

    DEMO_EDITOR_PASSWORD turns the demo on; unset, nothing happens.
    DEMO_EDITOR_PATHS (comma-separated, "/" for the whole site) is where the
    account may edit, and must be set with it: the account reads drafts there,
    so where is a choice, never a default.
    """
    password = os.environ.get("DEMO_EDITOR_PASSWORD", "").strip()
    if not password:
        return None
    paths = [p.strip() for p in os.environ["DEMO_EDITOR_PATHS"].split(",")]
    if not all(paths):
        raise ValueError(f"DEMO_EDITOR_PATHS has an empty path: {paths!r}")
    return password, paths


def is_installed(site) -> bool:
    profile = site.portal_setup.getLastVersionForProfile(f"{PROFILE}:default")
    return profile != "unknown"


def make_demo_editor_at_startup(event: IDatabaseOpenedWithRoot) -> None:
    """Make (or reset) the demo account when Zope starts, on every site that
    has plone.demoeditor installed, from the environment (demo_settings)."""
    settings = demo_settings()
    if settings is None:
        return
    with event.database.transaction() as connection:
        # A stand-in request: changing a password notifies PAS, which updates
        # the request's credentials, and at startup there is no request.
        app = makerequest(connection.root()["Application"])
        for site in app.objectValues("Plone Site"):
            if is_installed(site):
                ensure_demo_editor(site, *settings)
                logger.info(
                    "demo editor %r edits %s on /%s",
                    DEMO_USER_ID,
                    settings[1],
                    site.getId(),
                )
