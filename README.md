# plone.demoeditor

A public demo editor for a Plone site. A "Try editing" button signs visitors in
as `demo`, and they can add, edit, move and delete anything. Nothing they do is
kept.

Every request the `demo` account makes is **doomed**: it runs and answers as
usual, so the editor behaves normally, and its transaction never commits. A
real editor's requests on the same site are untouched.

## Read this first

Doom protects writes, not reads. Where it may edit, the `demo` account
(Contributor, Editor and Reviewer there) sees **private content too**. Its
password is public by design. Give it only paths whose drafts anyone may see.
Elsewhere on the site it is just a Member, and sees what any signed-in user
sees.

Doom covers the ZODB. Anything an add-on does outside the transaction, such
as calling a webhook or another service, purging a cache or writing a file,
still happens. Check the site's add-ons before turning the demo on. Plone's
mail is queued until commit, so a doomed request sends none.

## Turning it on

Add the package to the Plone backend; its ZCML is picked up by
`z3c.autoinclude` (or include `plone.demoeditor` yourself). Set:

| Variable | |
| --- | --- |
| `DEMO_EDITOR_PASSWORD` | The `demo` account's password. Unset, there is no demo account. |
| `DEMO_EDITOR_PATHS` | Where it may edit: comma-separated paths relative to the site, `/` for all of it, e.g. `/components,/guides`. Required with the password: Zope does not start without it. |
| `DEMO_ADMIN_PASSWORD` | The root `admin` account's password, set at each start (see below). Unset, it is left alone. |

Then **install the add-on on the site** that gets the demo: Site Setup → Add-ons
→ Demo editor, or `plone.demoeditor:default` in a distribution's profiles. Only
sites that have it installed get the account. Others in the same Zope are left
alone.

Installing makes the `demo` account. Each time Zope starts, it is made again,
or its password and roles reset, on every site that has the add-on, with
Contributor, Editor and Reviewer as local roles on each path. A path dropped
from the setting loses them. Uninstalling deletes the account and its roles.

The doom itself is keyed on the `demo` user, not on the add-on being installed:
should the account ever outlive the add-on, its saves are still thrown away.

## Signing in as the demo

The password is public, so nobody needs to type it, and no admin needs to hold
it. Where the demo is on (the add-on installed, the account there):

- `GET @login` lists it among the site's login options, beside any others
  (Google, …):
  `{"id": "demo", "plugin": "demo", "title": "Try it as a demo editor", "url": "<site>/@login-demo"}`.
  A login page shows it as a button.
- `POST @login-demo` signs the visitor in as `demo` with no password, and
  answers `{"token": …}` as `@login` does. Where the demo is off it answers 404.

Inka's login page shows the option, and its demo link,
`/login?demo&return_url=<page>/edit`, presses it for the visitor: one link
opens the editor. Link a "Try editing" button to it.

## The admin password

A demo is public, so its admin password has to be a secret. The admin lives in
the Zope root's user folder, outside every site: a demo that recreates its site
on each start keeps whatever password the instance was made with, which is
usually the image's default.

Set `DEMO_ADMIN_PASSWORD` and each time Zope starts the root `admin` gets that
password; its roles are left alone. Unset, the password is not touched. A root
with no `admin` user stops Zope from starting rather than run unprotected.

This applies to the whole instance, whichever sites have the add-on installed.

## What is not doomed

`@login` and `@login-demo` are the demo requests that are not doomed. Its only writes are the
sign-in's own. One of them is plone.protect's weekly rotation of the keyring
that signs the token. Throwing that rotation away would leave the token signed
with a secret no later request knows, and every request after sign-in would
run as anonymous.

## Tests

```shell
uv venv .venv
uv pip install -p .venv/bin/python -e ".[test]" -c https://dist.plone.org/release/6.2.1/constraints.txt
.venv/bin/pytest
```
