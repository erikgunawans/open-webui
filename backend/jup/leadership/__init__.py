"""Ruang Pimpinan: the leadership workspace's records, kept apart from the portfolio domain.

Deliberately import-free. Each submodule is a separate boundary (record validation, reading,
policy) and a caller names the one it depends on, so importing the package never drags in a
reader or policy it did not ask for.
"""
