#!/usr/bin/env python3
"""pydns-updater: update YDNS hosts using the current external IP."""

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


CONFIG_FILE = "/etc/pydns-updater.conf"
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
	logger.log(TRACE, "HTTP GET %s (timeout: 30s)", url)
	if username is not None and password is not None:
		credentials = f"{username}:{password}".encode()
		encoded = base64.b64encode(credentials).decode()
		request.add_header("Authorization", f"Basic {encoded}")
	try:
		with urlopen(request, timeout=30) as response:
			logger.log(TRACE, "HTTP status: %s", response.status)
			body = response.read().decode().strip()
			logger.log(TRACE, "HTTP body: %r", body)
			return body
	except HTTPError as error:
		with error:
			logger.log(TRACE, "HTTP status: %s", error.code)
			if accept_error_body:
				body = error.read().decode().strip()
				logger.log(TRACE, "HTTP body: %r", body)
				logger.debug("Checking YDNS status in HTTP error body")
				return body
			logger.debug("IP lookup failed: HTTP %s", error.code)
			return ""
	except (URLError, TimeoutError, OSError) as error:
		logger.debug("Request failed for %s: %s", url, error)
		return ""


def get_current_ip():
	logger.debug("Fetching IP from YDNS")
	return request_text(f"{API_URL}/ip")


def update_hosts(hosts, username, password, current_ip):
	status = "nochg"
	for index, host in enumerate(hosts, start=1):
		logger.debug("Updating %s (%s/%s): %s", host, index, len(hosts), current_ip)
		query = urlencode({"host": host, "ip": current_ip})
		result = request_text(
			f"{API_URL}/update/?{query}", username, password, accept_error_body=True
		)
		logger.info("YDNS %s: %s", host, result)
		if result.startswith("good"):
			logger.debug("%s: IP accepted", host)
			status = "good"
		elif result.startswith("nochg"):
			logger.debug("%s: IP unchanged at YDNS", host)
		else:
			logger.debug("Failed at %s; updates stopped, cache unchanged", host)
			return result
	logger.debug("All %s hosts OK: %s", len(hosts), status)
	return status


def parse_args(argv=None):
	parser = argparse.ArgumentParser(
		description="pydns-updater: update YDNS hosts using the current external IP",
		epilog=f"Settings not supplied as arguments are read from {CONFIG_FILE} ([ydns] section).",
	)
	parser.add_argument("-H", "--host", "--hosts", dest="hosts", action="append", metavar="HOST")
	parser.add_argument("-u", "--username", dest="username", metavar="USERNAME")
	parser.add_argument("-p", "--password", dest="password", metavar="PASSWORD")
	parser.add_argument("-v", "--verbose", dest="verbose", action="count", help="override config verbosity: -v results, -vv decisions, -vvv HTTP details")
	parser.add_argument("--no-cache", action="store_true", help="update through the API without reading or writing the IP cache")
	args = parser.parse_args(argv)
	args.setting_sources = {
		name: "command line" if getattr(args, name) is not None else CONFIG_FILE
		for name in ("username", "password", "hosts", "verbose")
	}
	requires_config = any(getattr(args, name) is None for name in ("username", "password", "hosts"))
	if requires_config or args.verbose is None:
		config = configparser.ConfigParser(interpolation=None)
		try:
			with open(CONFIG_FILE, encoding="utf-8") as config_file:
				config.read_file(config_file)
		except FileNotFoundError:
			pass
		except PermissionError:
			if requires_config:
				parser.error(f"Unable to read {CONFIG_FILE}: permission denied.")
		except (OSError, UnicodeError, configparser.Error):
			parser.error(f"Unable to read {CONFIG_FILE}; expected a readable INI file with a [ydns] section.")

		if args.username is None:
			args.username = config.get("ydns", "username", fallback=None)
		if args.password is None:
			args.password = config.get("ydns", "password", fallback=None)
		if args.hosts is None:
			args.hosts = config.get("ydns", "hosts", fallback="").split()
		if args.verbose is None:
			if config.has_option("ydns", "verbose"):
				try:
					args.verbose = config.getint("ydns", "verbose")
				except ValueError:
					parser.error(f"The verbose setting in {CONFIG_FILE} must be an integer from 0 to 3.")
				if not 0 <= args.verbose <= 3:
					parser.error(f"The verbose setting in {CONFIG_FILE} must be an integer from 0 to 3.")
			else:
				args.verbose = 0
				args.setting_sources["verbose"] = "default (0)"

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
		format="%(levelname)s: %(message)s",
	)
	if CONFIG_FILE in args.setting_sources.values():
		logger.debug("Config: %s", CONFIG_FILE)
	else:
		logger.debug("Using CLI settings and defaults")
	for name, source in args.setting_sources.items():
		logger.debug("%s source: %s", name, source)
	hosts = args.hosts
	logger.debug("Hosts: %s; cache: %s", " ".join(hosts), "disabled" if args.no_cache else "enabled")
	current_ip = get_current_ip()

	if not current_ip:
		logger.error("External IP lookup failed")
		return 92

	logger.info("Current IP: %s", current_ip)
	if not args.no_cache:
		last_ip_file = get_cache_path(hosts)
		logger.debug("Reading cache: %s", last_ip_file)
		try:
			with open(last_ip_file, encoding="utf-8") as cache:
				last_ip = cache.readline().strip()
		except FileNotFoundError:
			logger.debug("Cache missing; update required")
			last_ip = ""

		logger.debug("External IP: %r; cached: %r", current_ip, last_ip)
		if current_ip == last_ip:
			logger.info("Skipped %s: IP matches cache", " ".join(hosts))
			return 0
		logger.debug("Cache mismatch; updating YDNS")
	else:
		logger.info("Cache disabled; updating YDNS")

	result = update_hosts(hosts, args.username, args.password, current_ip)
	if result.startswith("badauth"):
		logger.error(
			"%s: authentication failed",
			" ".join(hosts),
		)
		return 90
	if result.startswith("nohost"):
		logger.error("%s: host not found", " ".join(hosts))
		return 91
	if result.startswith(("good", "nochg")):
		if result.startswith("good"):
			logger.info("Updated %s to %s", " ".join(hosts), current_ip)
		else:
			logger.info("YDNS IP unchanged")
		if not args.no_cache:
			with open(last_ip_file, "w", encoding="utf-8") as cache:
				cache.write(current_ip + "\n")
			logger.debug("Cached %s in %s", current_ip, last_ip_file)
		else:
			logger.debug("Cache write skipped (--no-cache)")
		return 0

	logger.error("Update failed for %s: %s", " ".join(hosts), result)
	return 91


if __name__ == "__main__":
	sys.exit(main())
