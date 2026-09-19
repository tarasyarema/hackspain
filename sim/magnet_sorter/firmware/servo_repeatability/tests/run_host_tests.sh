#!/usr/bin/env bash
set -euo pipefail

tests_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
build_dir="${TMPDIR:-/tmp}/servo-repeatability-host-tests"
mkdir -p "$build_dir"

common=(
  -std=c++11
  -Wall
  -Wextra
  -Werror
  -pedantic
  -I"$tests_dir"
  "$tests_dir/host_test.cpp"
)

build_and_run() {
  local name="$1"
  shift
  g++ "${common[@]}" "$@" -o "$build_dir/$name"
  "$build_dir/$name"
}

build_and_run unconfirmed
build_and_run positional -DSERVO_REPEATABILITY_MODE=SERVO_MODE_POSITIONAL
build_and_run continuous -DSERVO_REPEATABILITY_MODE=SERVO_MODE_CONTINUOUS
build_and_run invalid \
  -DSERVO_REPEATABILITY_MODE=SERVO_MODE_POSITIONAL \
  -DSERVO_REPEATABILITY_LOW_US=1399 \
  -DTEST_INVALID_CONFIGURATION
