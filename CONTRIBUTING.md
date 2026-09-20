# Contributing

## Automatic formatting

Pull requests apply Ruff fixes before the lint check. With the autofix.ci
app installed for this repository, those fixes are committed to the pull
request branch, including forks. Findings Ruff cannot fix still fail CI.
Push builds check the committed files without applying fixes.

Apply the same fixes locally with:

```console
uvx --with tox-uv tox -e ruff-fix
```
