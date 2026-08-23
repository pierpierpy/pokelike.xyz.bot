"""This package holds code shared across packages that must not import from each other.

`arena/` (the bot competition) and `utils/refingerprint.py` (outside the
package entirely) both need `fingerprint.py`'s logic; neither imports it from
the other, and both import it from here.
"""
