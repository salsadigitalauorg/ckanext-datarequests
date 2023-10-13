#!/usr/bin/env bash
##
# Run tests in CI.
#
set -ex

ahoy lint

echo "==> Run Unit tests"
ahoy test-unit

echo "==> Run BDD tests"
ahoy test-bdd
