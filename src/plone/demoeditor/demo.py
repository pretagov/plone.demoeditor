"""The demo editor: a public account whose saves are thrown away.

A demo site's "Try editing" button signs visitors in as this account (Inka's
/login?demo link). Its password reaches every browser, so nothing it does may
stick: once a request is known to be the demo account's, its transaction is
doomed. The request runs and answers as usual, so the editor behaves normally,
and nothing commits. A real editor's requests are untouched.

Doom protects writes, not reads: the account sees whatever its roles let it
see, private content included. Enable it only on a site whose content may be
seen by anyone.
"""

from AccessControl import getSecurityManager
from plone.restapi.services.auth.login import Login
from Testing.makerequest import makerequest
from zope.processlifetime import IDatabaseOpenedWithRoot
from ZPublisher.interfaces import IPubAfterTraversal

import logging
import os
import transaction


logger = logging.getLogger("plone.demoeditor")

DEMO_USER_ID = "demo"
DEMO_ROLES = ["Member", "Contributor", "Editor", "Reviewer"]


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


def ensure_demo_editor(site, password: str) -> None:
    """Make the demo account on `site`, or reset its password and roles."""
    users = site.acl_users.source_users
    if DEMO_USER_ID in users.getUserIds():
        users.userSetPassword(DEMO_USER_ID, password)
    else:
        users.addUser(DEMO_USER_ID, DEMO_USER_ID, password)
    site.acl_users.portal_role_manager.assignRolesToPrincipal(DEMO_ROLES, DEMO_USER_ID)


def make_demo_editor_at_startup(event: IDatabaseOpenedWithRoot) -> None:
    """Make the demo account when Zope starts, from the environment.

    DEMO_EDITOR_PASSWORD turns the demo on; unset, nothing happens.
    DEMO_EDITOR_SITE names the one site it is made on, and must be set with it:
    the account can read whatever its roles allow, so which site is a choice,
    never a default.
    """
    password = os.environ.get("DEMO_EDITOR_PASSWORD", "").strip()
    if not password:
        return
    site_id = os.environ["DEMO_EDITOR_SITE"]
    with event.database.transaction() as connection:
        # A stand-in request: changing a password notifies PAS, which updates
        # the request's credentials, and at startup there is no request.
        app = makerequest(connection.root()["Application"])
        ensure_demo_editor(app[site_id], password)
    logger.info("demo editor %r ready on /%s", DEMO_USER_ID, site_id)
