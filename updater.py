#!/usr/bin/env python3
"""Update YDNS dynamic DNS hosts."""

import argparse
import base64
import configparser
import hashlib
import ipaddress
import json
import logging
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


CONFIG_FILE = "/etc/ydns-upater.conf"
API_URL = "https://ydns.io/api/v1"
TRACE = 5
logging.addLevelName(TRACE, "TRACE")
logger = logging.getLogger(__name__)


def normalize_host(host):
	try:
		host = host.encode("idna").decode("ascii").lower().removesuffix(".")
	except UnicodeError:
		raise ValueError("must be a valid DNS hostname") from None
	labels = host.split(".")
	if len(host) > 253 or len(labels) < 2 or any(
		re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
		for label in labels
	):
		raise ValueError("must be a fully qualified DNS hostname with valid labels")
	try:
		ipaddress.ip_address(host)
	except ValueError:
		return host
	raise ValueError("must be a DNS hostname, not an IP address")


def get_cache_path(hosts):
	cache_key = json.dumps(sorted(set(hosts)), separators=(",", ":")).encode("utf-8")
	digest = hashlib.sha256(cache_key).hexdigest()
	return Path(tempfile.gettempdir()) / f"ydns_last_ip_{digest}"


def request_text(url, username=None, password=None, *, accept_error_body=False):
	request = Request(url)
	logger.log(TRACE, "HTTP GET %s (timeout: 30 seconds)", url)
	if username is not None and password is not None:
		credentials = f"{username}:{password}".encode()
		encoded = base64.b64encode(credentials).decode()
		request.add_header("Authorization", f"Basic {encoded}")
	try:
		with urlopen(request, timeout=30) as response:
			logger.log(TRACE, "HTTP status: %s", response.status)
			body = response.read().decode().strip()
			logger.log(TRACE, "HTTP response body: %r", body)
			return body
	except HTTPError as error:
		with error:
			logger.log(TRACE, "HTTP status: %s", error.code)
			if accept_error_body:
				body = error.read().decode().strip()
				logger.log(TRACE, "HTTP response body: %r", body)
				logger.debug("Using HTTP error response body to determine the YDNS update result")
				return body
			logger.debug("IP lookup failed with HTTP status %s", error.code)
			return ""
	except (URLError, TimeoutError, OSError) as error:
		logger.debug("Request failed for %s: %s", url, error)
		return ""


def get_current_ip():
	logger.debug("Retrieving the external IP from YDNS")
	return request_text(f"{API_URL}/ip")


def update_hosts(hosts, username, password, current_ip):
	status = "nochg"
	for index, host in enumerate(hosts, start=1):
		logger.debug("Updating host %s (%s/%s) to %s", host, index, len(hosts), current_ip)
		query = urlencode({"host": host, "ip": current_ip})
		result = request_text(
			f"{API_URL}/update/?{query}", username, password, accept_error_body=True
		)
		logger.info("YDNS response for %s: %s", host, result)
		if result.startswith("good"):
			logger.debug("Host %s: YDNS accepted the new IP", host)
			status = "good"
		elif result.startswith("nochg"):
			logger.debug("Host %s: YDNS already has this IP", host)
		else:
			logger.debug("Stopping host updates after failure for %s; the cache will not be written", host)
			return result
	logger.debug("All %s host updates succeeded; combined result: %s", len(hosts), status)
	return status


def parse_args(argv=None):
	parser = argparse.ArgumentParser(
		description="YDNS updater",
		epilog=f"Settings not supplied as arguments are read from {CONFIG_FILE} ([ydns] section).",
	)
	parser.add_argument("-H", "--host", "--hosts", dest="hosts", action="append", metavar="HOST")
	parser.add_argument("-u", "--username", dest="username", metavar="USERNAME")
	parser.add_argument("-p", "--password", dest="password", metavar="PASSWORD")
	parser.add_argument("-v", "--verbose", dest="verbose", action="count", default=0, help="increase verbosity: -v results, -vv decisions, -vvv HTTP details")
	parser.add_argument("--no-cache", action="store_true", help="update through the API without reading or writing the IP cache")
	args = parser.parse_args(argv)
	args.setting_sources = {
		name: "command line" if getattr(args, name) is not None else CONFIG_FILE
		for name in ("username", "password", "hosts")
	}
	if any(getattr(args, name) is None for name in ("username", "password", "hosts")):
		config = configparser.ConfigParser(interpolation=None)
		try:
			with open(CONFIG_FILE, encoding="utf-8") as config_file:
				config.read_file(config_file)
		except FileNotFoundError:
			pass
		except (OSError, UnicodeError, configparser.Error):
			parser.error(f"Unable to read {CONFIG_FILE}; expected a readable INI file with a [ydns] section.")

		if args.username is None:
			args.username = config.get("ydns", "username", fallback=None)
		if args.password is None:
			args.password = config.get("ydns", "password", fallback=None)
		if args.hosts is None:
			args.hosts = config.get("ydns", "hosts", fallback="").split()

	missing = [name for name in ("username", "password", "hosts") if not getattr(args, name)]
	if args.hosts and any(not host.strip() for host in args.hosts):
		missing.append("hosts")
	if missing:
		parser.error(
			f"Missing required settings: {', '.join(missing)}. "
			f"Supply arguments or set them in the [ydns] section of {CONFIG_FILE}."
		)
	normalized_hosts = []
	for host in args.hosts:
		try:
			normalized_hosts.append(normalize_host(host))
		except ValueError as error:
			parser.error(f"Invalid host {host!r}: {error}")
	args.hosts = list(dict.fromkeys(normalized_hosts))
	return args


def main():
	args = parse_args()
	logging.basicConfig(
		level=(logging.CRITICAL + 1, logging.INFO, logging.DEBUG, TRACE)[min(args.verbose, 3)],
		format="[%(asctime)s] %(levelname)s: %(message)s",
		datefmt="%Y/%m/%dT%H:%M:%S",
	)
	if all(source == "command line" for source in args.setting_sources.values()):
		logger.debug("Configuration file skipped: all required settings came from command-line arguments")
	else:
		logger.debug("Loaded configuration from %s", CONFIG_FILE)
	for name, source in args.setting_sources.items():
		logger.debug("Setting %s comes from %s", name, source)
	hosts = args.hosts
	logger.debug("Configured hosts: %s; cache: %s", " ".join(hosts), "disabled" if args.no_cache else "enabled")
	current_ip = get_current_ip()

	if not current_ip:
		logger.error("Error: Unable to retrieve current public IP address.")
		return 92

	logger.info("Current IP: %s", current_ip)
	if not args.no_cache:
		last_ip_file = get_cache_path(hosts)
		logger.debug("Reading IP cache: %s", last_ip_file)
		try:
			with open(last_ip_file, encoding="utf-8") as cache:
				last_ip = cache.readline().strip()
		except FileNotFoundError:
			logger.debug("No IP cache file found; an update is required")
			last_ip = ""

		logger.debug("Comparing external IP %r with cached IP %r", current_ip, last_ip)
		if current_ip == last_ip:
			logger.info("Skipping YDNS update for %s: external IP matches the local cache", " ".join(hosts))
			return 0
		logger.debug("External IP differs from the local cache; contacting YDNS")
	else:
		logger.info("IP cache disabled; contacting YDNS for an update.")

	result = update_hosts(hosts, args.username, args.password, current_ip)
	if result.startswith("badauth"):
		logger.error(
			"YDNS host update failed: %s (authentication failed)",
			" ".join(hosts),
		)
		return 90
	if result.startswith("nohost"):
		logger.error("YDNS hostrecord %s does not exist.", " ".join(hosts))
		return 91
	if result.startswith(("good", "nochg")):
		if result.startswith("good"):
			logger.info("YDNS host updated successfully: %s (%s)", " ".join(hosts), current_ip)
		else:
			logger.info("YDNS entry unchanged.")
		if not args.no_cache:
			with open(last_ip_file, "w", encoding="utf-8") as cache:
				cache.write(current_ip + "\n")
			logger.debug("Saved IP %s to cache: %s", current_ip, last_ip_file)
		else:
			logger.debug("Skipping cache write because --no-cache is enabled")
		return 0

	logger.error("YDNS host update failed: %s (%s)", " ".join(hosts), result)
	return 91


if __name__ == "__main__":
	sys.exit(main())
