"""Signing in as the demo editor, without a password.

The account's password is public by design, so asking for it protects
nothing; it only makes every admin that offers "Try editing" hold it, and hand
it to every visitor's browser. Instead the demo is a login option:

- GET @login lists it (ILoginProviders), beside any other way the site signs
  people in, so a login page can offer it as a button;
- POST @login-demo signs the visitor in as the demo account and returns a
  token, as @login does.

Both only where the demo is on: the add-on installed on the site, and the
account there. Its requests are doomed as ever (demo.py); this sign-in, like
@login, is not, so that its own writes (the keyring rotation its token is
signed with) are kept.
"""

from AccessControl.SecurityManagement import newSecurityManager
from plone import api
from plone.demoeditor.demo import DEMO_USER_ID
from plone.demoeditor.demo import is_installed
from plone.restapi.interfaces import ILoginProviders
from plone.restapi.services.auth.login import Login
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from zope.component import adapter
from zope.component import getMultiAdapter
from zope.interface import alsoProvides
from zope.interface import implementer
from zope.interface import Interface

import plone.protect.interfaces


def demo_is_on(site) -> bool:
    """The add-on is installed on `site` and the demo account is there."""
    return (
        is_installed(site) and DEMO_USER_ID in site.acl_users.source_users.getUserIds()
    )


@implementer(ILoginProviders)
@adapter(Interface)
class DemoLoginProvider:
    """The demo, as one of the site's login options (GET @login)."""

    def __init__(self, context):
        self.context = context

    def get_providers(self):
        site = api.portal.get()
        if not demo_is_on(site):
            return []
        return [
            {
                "id": "demo",
                "plugin": "demo",
                "title": "Try it as a demo editor",
                "url": f"{site.absolute_url()}/@login-demo",
            }
        ]


class DemoLogin(Login):
    """POST @login-demo: a token for the demo account, with no password.

    A Login, so that demo.doom_demo_requests lets it through as it does
    @login: the sign-in's own writes are kept.
    """

    def reply(self):
        site = api.portal.get()
        if not demo_is_on(site):
            self.request.response.setStatus(404)
            return {
                "error": {
                    "type": "NotFound",
                    "message": "This site has no demo editor.",
                }
            }

        # Disable CSRF protection, as @login does.
        alsoProvides(self.request, plone.protect.interfaces.IDisableCSRFProtection)

        uf = site.acl_users
        plugin = next(
            (
                p
                for _id, p in uf._getOb("plugins").listPlugins(IAuthenticationPlugin)
                if p.meta_type == "JWT Authentication Plugin"
            ),
            None,
        )
        if plugin is None:
            self.request.response.setStatus(501)
            return {
                "error": {
                    "type": "Login failed",
                    "message": "JWT authentication plugin not installed.",
                }
            }

        # The request is now the demo account's, as @login's is once its
        # credentials are checked; then the same post-login steps (login
        # time, the login event, which rotates the keyring when it is due).
        user = uf.getUserById(DEMO_USER_ID)
        newSecurityManager(self.request, user)
        getMultiAdapter((self.context, self.request), name="login")._post_login()
        return {
            "token": plugin.create_token(
                user.getId(), data={"fullname": user.getProperty("fullname")}
            )
        }
