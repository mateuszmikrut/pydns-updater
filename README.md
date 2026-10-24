# YDNS Python Updater Script

This repository contains a Python updater script for dynamic DNS hosts on *NIX-like environments. Run it periodically with cron (preferably every 15 minutes).

The script uses the YDNS API v1 (dyn-compatible) and retrieves the current external IP address through the API.

## Installation

Python 3 is required. There are no third-party dependencies.

1. Check out the source code (`updater.py`).
2. Place it into the desired location and make it executable (`chmod +x updater.py`).
3. Configure the username, password, and hosts as described below.
4. Run the script (either by single call or set up a cronjob to run it periodically)

## Configuration

Settings come from command-line arguments or `/etc/ydns-upater.conf`. Each argument takes precedence over the corresponding file setting. There are no built-in credential or host defaults.

Create `/etc/ydns-upater.conf` using this INI format:

```ini
[ydns]
username = user@example.com
password = your-api-password
hosts = first.ydns.eu second.ydns.eu
```

Separate hosts with whitespace. Write values without surrounding quotes; password characters such as `%`, `#`, and `;` are treated literally. Keep the file readable only by the account running the updater (for example, mode `600`).

Hosts supplied with `-H`, `--host`, `--hosts`, or the config file must be fully qualified DNS hostnames. Hostnames are lowercased, international names are converted to IDNA ASCII, and a final DNS dot is removed. Duplicate hosts are updated once. Paths, URLs, ports, IP addresses, whitespace within a hostname, and invalid or oversized DNS labels are rejected before any API or cache access.

Run with the file settings:

```bash
python3 updater.py -v
```

Or supply settings as arguments:

```bash
python3 updater.py -u user@example.com -p your-api-password -H first.ydns.eu -H second.ydns.eu -v
```

Supplying any `-H`/`--hosts` arguments replaces the entire host list from the file. The file is not needed when all three settings are supplied as arguments. Missing settings or an unreadable or malformed required config file cause exit code `2` before any API calls. `-v`/`--verbose` enables logging, including each host's response body from YDNS.

Repeat `-v` to show more detail:

- `-v`: current IP, YDNS responses, and update results.
- `-vv`: also show where settings came from, the cache path and IP comparison, and decisions for each host.
- `-vvv`: also show HTTP request URLs, timeout, status codes, and response bodies.

Repeated `--verbose` options work the same way. Without a verbosity option, normal execution is quiet. Password values and authorization headers are not logged.

## IP cache

The script stores the last successfully updated IP in `ydns_last_ip_<sha256>` inside the temporary directory selected by Python's `tempfile.gettempdir()`. This directory depends on the operating system and its temporary-directory environment settings. The fixed-length filename is derived from the normalized host set; host input is never inserted into the path. Reordering hosts uses the same cache file.

Old cache files with hostnames in their names are ignored. The next successful update creates a cache using the new filename.

When the external IP matches the cache, the script skips the update request. Changes made directly on the YDNS website are not reflected in this local cache. To force an API update and see the server response, use:

```bash
python3 updater.py --no-cache -vvv
```

`--no-cache` bypasses all cache reads and writes for that run. It updates the configured hosts through the API even when the external IP has not changed.

## Crontab Setup

To run this script every 15 minutes using `crontab`, add the following line to your crontab list:

```bash
*/15 * * * * /path/to/script/updater.py > /dev/null
```

Although this works on most all implementations of `crontab`, for more portability use this instead:

```bash
0,15,30,45 * * * * /path/to/script/updater.py > /dev/null
```

**NOTE:** To gain access to the crontab list to edit and add entries, execute `crontab -e` at the terminal

## Further notes

The code is licensed under the GNU Public License, version 3.

## Contribution

If you like to contribute useful changes to the script, simply fork the project, apply your changes and make a pull request.
