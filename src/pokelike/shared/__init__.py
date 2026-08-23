"""Code shared across packages that must not import from each other.

`arena/` (the bot competition) and `utils/refingerprint.py` (outside the
package entirely) both need `fingerprint.py`'s logic; neither imports it from
the other, both import it from here.
"""
