# pydns-updater

Update YDNS hosts using your external IP address, retrieved through the YDNS API.

## Installation

### Linux packages

Download a package matching your 64-bit Linux system from [GitHub Releases](https://github.com/mateuszmikrut/pydns-updater/releases/latest):

| Architecture | Debian / Ubuntu | Rocky Linux / Fedora |
| --- | --- | --- |
| x86-64 | [DEB (amd64)](https://github.com/mateuszmikrut/pydns-updater/releases/latest/download/pydns-updater_amd64.deb) | [RPM (x86_64)](https://github.com/mateuszmikrut/pydns-updater/releases/latest/download/pydns-updater.x86_64.rpm) |
| ARM64 | [DEB (arm64)](https://github.com/mateuszmikrut/pydns-updater/releases/latest/download/pydns-updater_arm64.deb) | [RPM (aarch64)](https://github.com/mateuszmikrut/pydns-updater/releases/latest/download/pydns-updater.aarch64.rpm) |

These commands select the package for your system automatically:

Debian / Ubuntu:

```bash
(
  set -e
  pydns_arch=$(dpkg --print-architecture)
  pydns_tmp=$(mktemp -d /tmp/pydns-updater.XXXXXX)
  trap 'rm -rf -- "$pydns_tmp"' EXIT
  chmod 755 "$pydns_tmp"
  curl -fL "https://github.com/mateuszmikrut/pydns-updater/releases/latest/download/pydns-updater_${pydns_arch}.deb" \
    -o "$pydns_tmp/pydns-updater.deb"
  chmod 644 "$pydns_tmp/pydns-updater.deb"
  sudo apt install "$pydns_tmp/pydns-updater.deb"
)
```

The temporary directory and package are readable by APT's `_apt` user and are removed afterward.

Rocky Linux / Fedora:

```bash
pydns_arch=$(rpm --eval '%{_arch}')
curl -fLO "https://github.com/mateuszmikrut/pydns-updater/releases/latest/download/pydns-updater.${pydns_arch}.rpm" &&
sudo dnf install "./pydns-updater.${pydns_arch}.rpm"
```

The package installs the `pydns-updater` command and an empty `/etc/ydns-upater.conf`. Edit that file with your YDNS API credentials and hosts before running. Local config changes are preserved during upgrades.

### Manual install via Python script

Install Python 3.9 or newer and download `pydns-updater.py`. No third-party Python packages are needed.

```bash
python3 pydns-updater.py --help
```

To install it as a command on Linux:

```bash
sudo install -m 755 pydns-updater.py /usr/local/bin/pydns-updater
```

## Help

```bash
pydns-updater --help
```

| Option | Purpose |
| --- | --- |
| `-H`, `--host`, `--hosts HOST` | Hostname to update; repeat for multiple hosts. |
| `-u`, `--username USERNAME` | YDNS API username. |
| `-p`, `--password PASSWORD` | YDNS API password. |
| `-v` | Show the current IP, server responses, and results. |
| `-vv` | Also show config sources, cache comparisons, and update decisions. |
| `-vvv` | Also show HTTP URLs, status codes, and response bodies. |
| `--no-cache` | Force an API update without reading or writing the IP cache. |

`--verbose` is equivalent to `-v` and can be repeated. When no verbosity flag is supplied, the config's `verbose` setting is used; the default is `0` (quiet). Command-line flags replace the configured level: `-v` selects `1`, `-vv` selects `2`, and `-vvv` selects `3`. Passwords and authorization headers are not logged.

## Examples

### Use a config file

Create or edit `/etc/ydns-upater.conf`:

```ini
[ydns]
username = user@example.com
password = your-api-password
hosts = first.ydns.eu second.ydns.eu
verbose = 1
```

Set `verbose` to `0` for quiet operation, `1` for results, `2` for decisions, or `3` for HTTP details.

Use fully qualified hostnames separated by whitespace and values without surrounding quotes. Keep the file readable only by the account running the updater. Packages use root ownership and mode `600`:

```bash
sudo chmod 600 /etc/ydns-upater.conf
sudo pydns-updater -v
```

### Supply settings as arguments

```bash
pydns-updater \
  -u user@example.com -p your-api-password \
  -H first.ydns.eu -H second.ydns.eu -v
```

Arguments override the corresponding config settings. Supplying hosts replaces the entire configured host list. The config file is optional when all settings are supplied as arguments.

### Run every X minutes

Add this entry with `sudo crontab -e` when using the package's root-owned config:

```cron
*/15 * * * * /usr/bin/pydns-updater -v 2>&1 | /usr/bin/logger -t pydns-updater
```

To check last runs

```bash
sudo journalctl -t pydns-updater
```
