#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


API_PREFIX = "https://gitee.com/api/v5"


def _http_json(
    method: str,
    url: str,
    *,
    query: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict | list:
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"

    request_headers = {"Accept": "application/json"}
    payload = body
    if form is not None:
        payload = urllib.parse.urlencode(form).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(url=url, data=payload, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} @ {url}: {raw}") from exc


def _release_api(owner: str, repo: str) -> str:
    return f"{API_PREFIX}/repos/{owner}/{repo}/releases"


def _list_releases(owner: str, repo: str, token: str) -> list[dict]:
    result = _http_json("GET", _release_api(owner, repo), query={"access_token": token})
    if not isinstance(result, list):
        raise RuntimeError("Unexpected release-list response from Gitee API.")
    return result


def _ensure_release(
    *,
    owner: str,
    repo: str,
    token: str,
    tag: str,
    title: str,
    body: str,
    commitish: str,
) -> dict:
    releases = _list_releases(owner, repo, token)
    for release in releases:
        if release.get("tag_name") == tag:
            print(f"[Gitee] Reuse existing release: {tag}")
            return release

    print(f"[Gitee] Create release: {tag}")
    payload = {
        "access_token": token,
        "tag_name": tag,
        "name": title,
        "body": body,
        "target_commitish": commitish,
        "prerelease": "false",
    }
    try:
        created = _http_json("POST", _release_api(owner, repo), form=payload)
    except RuntimeError as exc:
        message = str(exc)
        if "already exists" in message or "Tag Name has already been taken" in message:
            releases = _list_releases(owner, repo, token)
            for release in releases:
                if release.get("tag_name") == tag:
                    return release
        raise

    if not isinstance(created, dict):
        raise RuntimeError("Unexpected create-release response from Gitee API.")
    return created


def _build_multipart(file_path: Path, token: str) -> tuple[bytes, str]:
    boundary = f"----InkCropBoundary{uuid.uuid4().hex}"
    file_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()

    chunks: list[bytes] = []
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="access_token"\r\n\r\n',
            token.encode("utf-8"),
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode(),
            f"Content-Type: {file_type}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


def _upload_asset(owner: str, repo: str, token: str, release_id: int, file_path: Path) -> None:
    url = f"{_release_api(owner, repo)}/{release_id}/attach_files"
    body, boundary = _build_multipart(file_path, token)
    print(f"[Gitee] Upload: {file_path.name}")
    _http_json(
        "POST",
        url,
        body=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish release artifacts to Gitee.")
    parser.add_argument("--owner", required=True, help="Gitee owner, e.g. BitterVan")
    parser.add_argument("--repo", required=True, help="Gitee repo, e.g. InkCrop")
    parser.add_argument("--token", required=True, help="Gitee personal access token")
    parser.add_argument("--tag", required=True, help="Tag name, e.g. v0.1.5")
    parser.add_argument("--title", default="", help="Release title (default: InkCrop <tag>)")
    parser.add_argument(
        "--body",
        default="",
        help="Release description (default: auto generated short text)",
    )
    parser.add_argument(
        "--commitish",
        default="main",
        help="Target commitish when creating missing release (default: main)",
    )
    parser.add_argument(
        "--artifacts-glob",
        required=True,
        help="Glob for artifacts, e.g. release-artifacts/*.zip",
    )
    args = parser.parse_args()

    artifacts = sorted(Path().glob(args.artifacts_glob))
    if not artifacts:
        print(f"[Gitee] ERROR: no artifacts found by glob: {args.artifacts_glob}")
        return 1

    release_title = args.title or f"InkCrop {args.tag}"
    release_body = args.body or f"Auto-synced from GitHub Actions for {args.tag}."
    release = _ensure_release(
        owner=args.owner,
        repo=args.repo,
        token=args.token,
        tag=args.tag,
        title=release_title,
        body=release_body,
        commitish=args.commitish,
    )

    release_id = release.get("id")
    if not isinstance(release_id, int):
        raise RuntimeError(f"Invalid release id from Gitee: {release_id!r}")

    for artifact in artifacts:
        _upload_asset(args.owner, args.repo, args.token, release_id, artifact)

    print(f"[Gitee] Done: uploaded {len(artifacts)} files to {args.tag}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
