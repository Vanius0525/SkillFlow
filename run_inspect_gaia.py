#!/usr/bin/env python3
"""
Run inspect_evals' GAIA eval against the dataset copy this repo already ships.

Why this launcher exists
------------------------
inspect_evals/gaia/dataset.py calls

    snapshot_download(repo_id="gaia-benchmark/GAIA", repo_type="dataset",
                      local_dir=GAIA_DATASET_DIR, revision=revision)

unconditionally -- there is no "already populated, skip it" branch. Because
`local_dir` is set, huggingface_hub cannot take its offline shortcut either: it
has to list the repo tree to know which files belong there, so it reaches the
network before it ever looks at what is on disk. HF_HUB_OFFLINE=1 therefore does
not make it use a local copy, it just makes it fail.

GAIA is a gated dataset, so that network call needs an approved HF account and
a token. This repo already contains the dataset (GAIA/), so the download is
pure ceremony: the bytes are here, only the fetch stands in the way.

Nothing else in the eval needs the network. The step after the download is

    hf_dataset(path=str(GAIA_DATASET_DIR), name=subset, split=split, ...)

and GAIA/README.md carries the `configs:` frontmatter that maps each subset
("2023_all", "2023_level1", ...) to its metadata parquet, so `datasets`
resolves the whole thing from disk.

This launcher replaces `snapshot_download` with a function that returns the
local directory, but ONLY when that directory already holds the dataset. If it
does not, nothing is patched and the normal download runs, so a machine without
the copy behaves exactly as upstream does. Everything after the download --
task construction, the react agent, the scorer -- is untouched upstream code.

State this substitution in any write-up: the eval is upstream's, the dataset is
a local copy of the same gated release rather than a fresh fetch of the pinned
revision.

    python run_inspect_gaia.py eval inspect_evals/gaia_level1 --model ...

Every argument is forwarded to the `inspect` CLI verbatim.
"""

from __future__ import annotations

import os
import pathlib
import sys

REPO_DIR = pathlib.Path(__file__).resolve().parent


def ensure_cache_dir() -> None:
    """
    Default INSPECT_EVALS_CACHE_DIR to the location setup-external.sh populates.

    This has to run before inspect_evals is imported: constants.py resolves the
    variable once, at import, and every eval derives its module-level paths from
    the result. Left unset, inspect_evals falls back to
    platformdirs.user_cache_dir("inspect_evals") -- ~/.cache/inspect_evals on
    Linux -- which is not where setup-external.sh stages the copy, so the copy
    reads as missing and the gated download runs.

    Only experiments-agents.sh used to export this, so running the launcher by
    hand looked in the wrong place. Defaulting it here keeps both entry points
    on the same directory. An explicit value always wins.
    """
    if os.environ.get("INSPECT_EVALS_CACHE_DIR"):
        return
    default = REPO_DIR / ".inspect_cache"
    os.environ["INSPECT_EVALS_CACHE_DIR"] = str(default)
    print(f"[inspect] INSPECT_EVALS_CACHE_DIR unset — defaulting to {default}")


def load_gaia_dataset_module():
    """
    Import the module that owns both the download call and the dataset path.

    The path is read off `GAIA_DATASET_DIR` rather than recomputed here. That
    constant is `INSPECT_EVALS_CACHE_PATH / "gaia_dataset" / "GAIA"`, and
    INSPECT_EVALS_CACHE_PATH is `platformdirs.user_cache_dir("inspect_evals")`
    unless INSPECT_EVALS_CACHE_DIR is set -- a platform-dependent default that
    is resolved once, at import. Reimplementing that here would be one more
    thing to keep in sync with upstream, and it would disagree with upstream on
    any OS where user_cache_dir is not ~/.cache.
    """
    try:
        import inspect_evals.gaia.dataset as gaia_ds
    except ImportError as e:
        print(f"[FATAL] inspect_evals not importable: {e}", file=sys.stderr)
        return None
    return gaia_ds


def is_populated(path: pathlib.Path) -> bool:
    """A copy counts only if the metadata the loader reads is actually there."""
    return (path / "2023" / "validation" / "metadata.parquet").is_file()


def patch_snapshot_download(gaia_ds, path: pathlib.Path) -> bool:
    """
    Point inspect_evals' snapshot_download at the local copy.

    The name is patched in both places it is bound: the utils module that
    defines the wrapper, and the gaia dataset module that imported the name
    into its own namespace (`from inspect_evals.utils.huggingface import
    hf_dataset, snapshot_download`, so rebinding only the source module would
    not affect the caller). gaia_ds is the binding that actually matters; the
    utils one is patched so anything else importing it late sees the same
    behaviour.
    """
    def _use_local(*_args, **kwargs):
        # Upstream's caller ignores the return value; return the same kind of
        # thing the real function does (the local path, as a str) anyway.
        return str(kwargs.get("local_dir", path))

    patched = []
    modules = [gaia_ds]
    try:
        import inspect_evals.utils.huggingface as hf_utils
        modules.append(hf_utils)
    except ImportError:
        pass

    for module in modules:
        if hasattr(module, "snapshot_download"):
            module.snapshot_download = _use_local
            patched.append(module.__name__)

    if not patched:
        print("[WARN] no snapshot_download binding found to patch; upstream may "
              "have restructured. Falling back to the real download.",
              file=sys.stderr)
        return False

    print(f"[inspect] using local GAIA copy at {path}")
    print(f"[inspect] patched snapshot_download in: {', '.join(patched)}")
    return True


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2

    ensure_cache_dir()

    gaia_ds = load_gaia_dataset_module()
    if gaia_ds is None:
        return 1

    path = pathlib.Path(gaia_ds.GAIA_DATASET_DIR)
    patched = is_populated(path) and patch_snapshot_download(gaia_ds, path)

    if not patched:
        print(f"[inspect] no usable local GAIA copy at {path} — falling back to "
              f"the normal download (needs an approved HF account and HF_TOKEN).")
        print(f"[inspect] to stage the copy: ./setup-external.sh --only gaia")
        # The download cannot run offline, and this flag is the one thing that
        # turns a working fetch into a guaranteed failure. Only clear it here:
        # on the patched path no download happens, and leaving it set keeps the
        # local parquet read from touching the network at all.
        if os.environ.pop("HF_HUB_OFFLINE", None) not in (None, "0"):
            print("[inspect] cleared HF_HUB_OFFLINE — it cannot make "
                  "snapshot_download read a local_dir, it only makes it fail")

    try:
        from inspect_ai._cli.main import main as inspect_main
    except ImportError as e:
        print(f"[FATAL] inspect_ai not importable: {e}", file=sys.stderr)
        return 1

    sys.argv = ["inspect"] + args
    try:
        inspect_main()
    except SystemExit as e:
        code = e.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
