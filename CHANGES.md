# Revision notes

## Corrected
- **Pytest crash:** models were defined inside `create_app()` and the module also ran `app = create_app()` on import, so the
  tests' second `create_app()` call would redefine the same tables. Models are now module-level; Procfile/Render use
  `gunicorn "app:create_app()"`.
- **Edit UI:** the dashboard now has an Edit form per record (the update route previously had no interface).
- **Tests:** expanded from 3 to 12 per app (login/logout, CRUD, validation, cross-user isolation, CSRF).
- **Validation:** whitelisted choices, safe number/date parsing (no NaN/inf), length limits, basic email check.
- **Health check:** `/health` now verifies the database connection (503 if unreachable).
- **Config:** `.env` is now actually loaded (python-dotenv); `psycopg2-binary` added for PostgreSQL;
  app refuses `COOKIE_SECURE=1` with the default secret; security headers added; table renamed `users`
  (avoids the reserved word `user` in PostgreSQL).
- **Deployment:** root `render.yaml` Blueprint added.

## NOT yet verified (no network in the authoring sandbox)
Dependencies were not installed and pytest was not executed. Python syntax and Jinja template rendering were checked only.
Run `pip install -r requirements.txt && pytest -q` in each folder, then deploy and test each live `/health` URL.
Deployment must not be declared complete until that is done.
