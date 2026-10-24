# pydns-updater

Update YDNS hosts using your external IP address, retrieved through the YDNS API.

## Installation

### Linux packages

Download and extract the package artifact for a version tag from the repository's GitHub Actions page. Install the package for your distribution:

```bash
# Debian / Ubuntu
sudo apt install ./pydns-updater_*.deb

# Rocky Linux / Fedora
sudo dnf install ./pydns-updater-*.rpm
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

`--verbose` is equivalent to `-v` and can be repeated. Without verbosity options, normal execution is quiet. Passwords and authorization headers are not logged.

## Examples

### Use a config file

Create or edit `/etc/ydns-upater.conf`:

```ini
[ydns]
username = user@example.com
password = your-api-password
hosts = first.ydns.eu second.ydns.eu
```

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
*/15 * * * * /usr/bin/pydns-updater
```
