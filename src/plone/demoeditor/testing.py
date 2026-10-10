from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import applyProfile
from plone.app.testing import FunctionalTesting
from plone.app.testing import PloneSandboxLayer
from plone.testing.zope import WSGI_SERVER_FIXTURE

import plone.demoeditor
import plone.restapi


class Layer(PloneSandboxLayer):
    defaultBases = (PLONE_APP_CONTENTTYPES_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=plone.restapi)
        self.loadZCML(package=plone.demoeditor)

    def setUpPloneSite(self, portal):
        # plone.restapi's profile adds the JWT plugin that @login signs in with.
        applyProfile(portal, "plone.restapi:default")
        applyProfile(portal, "plone.demoeditor:default")


FIXTURE = Layer()

FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(FIXTURE, WSGI_SERVER_FIXTURE),
    name="plone.demoeditor:FunctionalTesting",
)
