# #169 — matrix job names vs branch protection

GitHub matrix jobs default to `{job_id} ({matrix values})`, which produced `lint-and-test (3.12, minimal)` after the optional-extras leg landed. `main` branch protection still requires `lint-and-test (3.12)`.

Fix: explicit `name:` on the `lint-and-test` job so the minimal profile omits the suffix; optional keeps `, optional`.
