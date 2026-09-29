"""
BridgeWatch: cross-chain bridge exploit detection (draft prototype for SNX-3).

Learns each bridge's normal flow pattern, then raises an alert the moment
withdrawals or escrow movements deviate from it. Runs on synthetic data until
SonarX data access is in place; see prototype/README.md.
"""
