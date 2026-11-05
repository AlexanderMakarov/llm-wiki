# #169 — CI optional-extra coverage

## Delivered

- `lint-and-test` matrix leg `extras-profile: optional` installs editable `[add,graph,dev]` (trafilatura + graphifyy) with pip cache keyed on `pyproject.toml`; `minimal` leg unchanged.
- `test_thin_page_without_renderer_warns` parametrized for stdlib floor vs trafilatura present; `_no_default_renderer` disables Playwright fallback so local e2e installs match CI.
