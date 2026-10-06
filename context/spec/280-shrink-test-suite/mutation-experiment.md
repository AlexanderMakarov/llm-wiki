# Mutation experiment — #280 (synth proof batch)

## Line coverage is not mutation score

The CI floor of **87%** is Coverage.py **line** coverage on `llmwiki` (statements that ran). Mutation score is the fraction of tiny synthetic bugs the suite **fails on**. `llmwiki/tag_utils.py` can be **100% line coverage** and still show ~70% kill rate: the lines ran, but asserts did not notice `""` vs `"XXXX"`. Those two numbers must not be mixed.

## mutmut 3 vs `cli.py`

mutmut 3.8 builds a **trampoline** per function (original + every mutant in one generated file). Pointing it at `llmwiki/cli.py` (~4k lines) produced a ~154MB file and stalled. That is the wrong grain. Docs: `only_mutate` one small module; `# pragma: no mutate block` on huge `def`s; pytest via `pytest_add_cli_args_test_selection`. mutmut 3 mutates **inside functions** only.

A custom AST flip script on `cmd_*` is **not** a mutmut score and is not used as verification.

## Proof in this PR: `llmwiki/synth/reporting.py`

**Not a committed mutmut suite.** mutmut was run locally once; CI does not install or invoke it. What ships is stronger pytest. Local recipe (optional; do not add mutmut to `[dev]`):

```bash
python3 -m pip install 'mutmut==3.8.*'
# throwaway setup.cfg with only_mutate = llmwiki/synth/reporting.py — see below
mutmut run
```

Throwaway `setup.cfg` (not committed):

```ini
[mutmut]
source_paths = llmwiki
only_mutate = llmwiki/synth/reporting.py
pytest_add_cli_args_test_selection = tests/synth/test_reporting.py
```

Pre-copy `tests/` into `mutants/tests` (mutmut 3.8 can `copy2` `tests/conftest.py` before that directory exists). Then `mutmut run`.

| Pass | Killed | Survived | Total |
|---|---|---|---|
| First (substring asserts + always-passed kwargs) | 59 | 7 | 66 |
| After exact-string + default-arg tests | **66** | **0** | 66 |

Survivors that the first tests missed (then killed): wrapping user-visible strings in `XX…XX`; flipping default `sessions/docs/stubs/other=0` to `1` when callers always passed kwargs.

CLI handler proof is `tests/cli/test_synth.py`: mutex error on the **handler** (not only argparse), harvest non-zero rc skips the success summary, unavailable backend, `--backend` must not write `config.json`, `--sources-only` skips harvest but still prints `Synthesized:` / `Duration:`.

## Broader mutation

[#314](https://github.com/AlexanderMakarov/llm-wiki/issues/314) is **expansion** (other small modules, never whole `cli.py` until split) — not a substitute for this proof.
