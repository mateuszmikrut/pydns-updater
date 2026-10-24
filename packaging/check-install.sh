#!/usr/bin/env bash
set -euo pipefail

pydns-updater --help
test -x /usr/bin/pydns-updater
test -r /usr/share/doc/pydns-updater/README.md
test -r /usr/share/doc/pydns-updater/copyright
test "$(stat -c '%a' /etc/ydns-upater.conf)" = 600
test "$(stat -c '%U:%G' /etc/ydns-upater.conf)" = root:root

# The unconfigured package must stop before making any API requests.
if output=$(pydns-updater 2>&1); then
  echo "Expected the empty package configuration to be rejected" >&2
  exit 1
else
  test "$?" -eq 2
fi
[[ "$output" == *"Missing required settings: username, password, hosts"* ]]

case "$1" in
  deb)
    test "$(dpkg-query --show --showformat='${Architecture}' pydns-updater)" = "$(dpkg --print-architecture)"
    config_files=$(dpkg-query --show --showformat='${Conffiles}' pydns-updater)
    [[ "$config_files" == *" /etc/ydns-upater.conf "* ]]
    ;;
  rpm)
    test "$(rpm -q --queryformat '%{ARCH}' pydns-updater)" = "$(rpm --eval '%{_arch}')"
    config_files=$(rpm -q --queryformat '[%{FILENAMES} %{FILEFLAGS}\n]' pydns-updater)
    # RPM flags 1 (config) + 16 (noreplace) preserve locally edited settings.
    [[ "$config_files" == *"/etc/ydns-upater.conf 17"* ]]
    ;;
  *) exit 2 ;;
esac
