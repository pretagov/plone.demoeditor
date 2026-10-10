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

Install the package; its ZCML is picked up by `z3c.autoinclude` (or include
`plone.demoeditor` yourself). Then set, on the Plone backend:

| Variable | |
| --- | --- |
| `DEMO_EDITOR_PASSWORD` | The `demo` account's password. Unset, there is no demo account. |
| `DEMO_EDITOR_SITE` | The id of the one site the account is made on. |
| `DEMO_EDITOR_PATHS` | Where on that site it may edit: comma-separated paths relative to the site, `/` for all of it, e.g. `/components,/guides`. |

The site and the paths are required with the password: Zope does not start
without them.

When Zope starts, it makes the `demo` account on that site, or resets its
password and roles if it is already there, and gives it Contributor, Editor
and Reviewer as local roles on each path.

The editor's half is Inka's demo link, `/login?demo&return_url=<page>/edit`,
with `RAZZLE_DEMO_LOGIN=demo` and `RAZZLE_DEMO_PASSWORD` (the same password)
set on the admin. Link a button to it.

## Signing in

`@login` is the one demo request that is not doomed. Its only writes are the
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
