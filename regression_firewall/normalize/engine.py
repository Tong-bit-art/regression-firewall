from __future__ import annotations

import fnmatch
from typing import Optional

from ..config.schema import IgnoreConfig, NormalizationConfig
from . import rules as R

PLACEHOLDERS = ("UUID", "DATETIME", "TIMESTAMP", "REQUEST_ID", "TOKEN", "TEMP_PATH", "DURATION")


class Normalizer:
    """Applies normalization rules to JSON values, header/cookie maps, and text.

    The same normalizer (built from the *current* config) is applied to both
    the baseline and the latest captures at diff time, so identical code never
    produces diffs from volatile data.
    """

    def __init__(self, normalization: NormalizationConfig, ignore: IgnoreConfig):
        self.cfg = normalization
        self.ignore = ignore

    # -- JSON values --------------------------------------------------------

    def normalize_json(self, value, key: Optional[str] = None, path: str = ""):
        if self._path_ignored(path):
            return value
        if isinstance(value, dict):
            return {
                k: self.normalize_json(v, key=k, path=self._child(path, k))
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [
                self.normalize_json(v, key=key, path=f"{path}.{i}" if path else str(i))
                for i, v in enumerate(value)
            ]
        if isinstance(value, str):
            return self.normalize_string(value, key)
        if isinstance(value, bool):
            return value
        if key and self.cfg.durations and R.DURATION_KEY_RE.search(key):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return "<DURATION>"
        if (
            self.cfg.epoch_timestamps
            and key
            and R.TEMPORAL_KEY_RE.search(key)
            and R.looks_like_epoch(value)
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            return "<TIMESTAMP>"
        if isinstance(value, float) and self.cfg.float_precision:
            rounded = round(value, 6)
            return 0.0 if rounded == 0 else rounded
        return value

    def normalize_string(self, value: str, key: Optional[str] = None) -> str:
        if not value:
            return value
        if self.cfg.uuid and R.UUID_RE.match(value):
            return "<UUID>"
        if self.cfg.iso_datetime and R.ISO_RE.match(value):
            return "<DATETIME>"
        if key:
            if (
                self.cfg.epoch_timestamps
                and R.TEMPORAL_KEY_RE.search(key)
                and R.looks_like_epoch(value)
            ):
                return "<TIMESTAMP>"
            if self.cfg.request_ids and R.REQUEST_ID_KEY_RE.search(key):
                return "<REQUEST_ID>"
            if self.cfg.tokens and R.TOKEN_KEY_RE.search(key):
                return "<TOKEN>"
            if (
                self.cfg.durations
                and R.DURATION_KEY_RE.search(key)
                and (value.replace(".", "", 1).isdigit())
            ):
                return "<DURATION>"
        if self.cfg.temp_paths and R.is_temp_path(value):
            return "<TEMP_PATH>"
        return value

    # -- Header / cookie maps ------------------------------------------------

    # Header values that are unordered SETS per spec: Django emits these in
    # nondeterministic order per process, which produced a false positive on
    # every single response in real-world testing (healthchecks).
    SET_SEMANTIC_HEADERS = ("access-control-allow-methods", "access-control-allow-headers")

    def normalize_headers(self, headers: dict) -> dict:
        ignored = {h.lower() for h in self.ignore.headers}
        out = {}
        for name, value in headers.items():
            low = str(name).lower()
            if low in ignored:
                continue
            text = str(value)
            if low in self.SET_SEMANTIC_HEADERS:
                parts = sorted(p.strip() for p in text.split(",") if p.strip())
                text = ", ".join(parts)
            out[low] = self.normalize_string(text, low)
        return out

    def normalize_cookies(self, cookies: dict) -> dict:
        return {name: self.normalize_string(str(v), name) for name, v in cookies.items()}

    # -- Plain text (stdout / stderr / text bodies) ---------------------------

    def normalize_text(self, text: str) -> str:
        if self.cfg.ansi:
            text = R.strip_ansi(text)
        if self.cfg.whitespace:
            text = R.normalize_lines(text)
        if self.cfg.uuid:
            text = R.UUID_INLINE_RE.sub("<UUID>", text)
        if self.cfg.iso_datetime:
            text = R.ISO_INLINE_RE.sub("<DATETIME>", text)
        if self.cfg.temp_paths:
            # Token-level masking first: a pristine temp path (root + random
            # file name) is replaced wholesale, mirroring the JSON rule. The
            # root-level pass afterwards catches any leftovers embedded in
            # larger strings.
            text = self._mask_temp_tokens(text)
            text = self._mask_temp_roots(text)
        return text

    def _mask_temp_tokens(self, text: str) -> str:
        # Whole-path masking mirrors the JSON rule: a whitespace-delimited
        # token that is a temp path becomes <TEMP_PATH>, including any random
        # file name inside it.
        import re

        def replace(match):
            token = match.group(0)
            return "<TEMP_PATH>" if R.is_temp_path(token) else token

        return re.sub(r"\S+", replace, text)

    def _mask_temp_roots(self, text: str) -> str:
        import re

        for root in self._temp_roots():
            # Case-insensitive so C:\Temp\, c:\temp\ and /TMP/ are all caught.
            text = re.sub(re.escape(root), "<TEMP_PATH>", text, flags=re.IGNORECASE)
        return text

    def _temp_roots(self):
        import tempfile

        roots = []
        try:
            roots.append(str(tempfile.gettempdir()))
        except Exception:  # pragma: no cover
            pass
        roots.extend(["/tmp/", "/var/folders/", "\\Temp\\", "Temp\\"])
        # Longest first so e.g. "C:\Users\x\AppData\Local\Temp\" wins over "Temp\".
        roots.sort(key=len, reverse=True)
        return roots

    # -- helpers --------------------------------------------------------------

    def _child(self, path: str, key: str) -> str:
        return f"{path}.{key}" if path else str(key)

    def _path_ignored(self, path: str) -> bool:
        if not path or not self.ignore.json_paths:
            return False
        return any(fnmatch.fnmatchcase(path, pattern) for pattern in self.ignore.json_paths)
