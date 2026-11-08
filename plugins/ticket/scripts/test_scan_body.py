"""Tests for scan_body.py."""

# ruff: noqa: S101, S105, S108, S603, INP001, D103, PLR2004
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("scan_body.py")


def run(tmp_path: Path, text: str, *flags: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "body").write_text(text)
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "body"), *flags],
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_body_exits_0(tmp_path: Path) -> None:
    result = run(tmp_path, "### Summary\n\nExports fail on widgets 2.4.1.\n")
    assert result.returncode == 0
    assert result.stdout.strip() == "clean"


def test_secret_is_masked(tmp_path: Path) -> None:
    token = "ghp_" + "a1B2" * 9
    result = run(tmp_path, f"log: Authorization failed for {token}\n")
    assert result.returncode == 1
    assert result.stdout.startswith("secret\t1\t")
    assert token not in result.stdout


def test_each_leak_kind(tmp_path: Path) -> None:
    text = (
        "cwd /home/alex/app\n"
        "host db1.corp and 10.0.3.7\n"
        "ask alex@example.com\n"
        "ping @alex\n"
        "changed (+142/-38 lines) see blob/main/x.py#L12\n"
    )
    kinds = {line.split("\t")[0] for line in run(tmp_path, text).stdout.splitlines()}
    assert kinds == {"path", "host", "email", "mention", "rot"}


def test_email_is_not_a_mention(tmp_path: Path) -> None:
    kinds = [line.split("\t")[0] for line in run(tmp_path, "mail a@b.io\n").stdout.splitlines()]
    assert kinds == ["email"]


def test_media_counts_markdown_html_and_wiki(tmp_path: Path) -> None:
    text = "![a](https://x.io/a.png)\n<img src='b.gif'>\n!c.png|width=300!\n[media]\n"
    assert run(tmp_path, text, "--media").stdout.splitlines()[0] == "media\t4"


def test_media_reads_adf_nodes_and_json_strings(tmp_path: Path) -> None:
    doc: dict[str, object] = {
        "fields": {
            "description": {
                "type": "doc",
                "content": [{"type": "mediaSingle", "content": [{"type": "media", "attrs": {}}]}],
            },
            "other": "![x](u.png)",
        }
    }
    assert run(tmp_path, json.dumps(doc), "--media").stdout.splitlines()[0] == "media\t2"


def test_unreadable_file_exits_2(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "missing")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2


def test_media_loss_after_write_exits_1(tmp_path: Path) -> None:
    (tmp_path / "written").write_text("![a](u.png) ![b](v.png)")
    (tmp_path / "fetched").write_text(json.dumps({"description": "![a](u.png)"}))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--media",
            str(tmp_path / "written"),
            str(tmp_path / "fetched"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "media lost" in result.stdout


def test_field_selector_ignores_comment_media(tmp_path: Path) -> None:
    (tmp_path / "written").write_text("![a](u.png)")
    fetched = {"fields": {"description": "no image", "comment": "![c](c.png)"}}
    (tmp_path / "fetched").write_text(json.dumps(fetched))
    args = [
        sys.executable,
        str(SCRIPT),
        "--media",
        str(tmp_path / "written"),
        str(tmp_path / "fetched"),
    ]
    assert subprocess.run(args, capture_output=True, text=True, check=False).returncode == 0
    args[2:2] = ["--field", "fields/description"]
    assert subprocess.run(args, capture_output=True, text=True, check=False).returncode == 1


def test_text_flattens_adf_and_prints_strings(tmp_path: Path) -> None:
    doc = {
        "type": "doc",
        "content": [
            {"type": "heading", "content": [{"type": "text", "text": "Plan"}]},
            {
                "type": "bulletList",
                "content": [
                    {
                        "type": "listItem",
                        "content": [
                            {"type": "paragraph", "content": [{"type": "text", "text": "one"}]}
                        ],
                    },
                ],
            },
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "b"},
                ],
            },
        ],
    }
    (tmp_path / "adf").write_text(json.dumps({"fields": {"description": doc}}))
    (tmp_path / "str").write_text(json.dumps({"body": "plain *text*"}))
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--text",
            "--field",
            "fields/description",
            str(tmp_path / "adf"),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert out == "Plan\n- one\na\nb\n"
    out = subprocess.run(
        [sys.executable, str(SCRIPT), "--text", "--field", "Body", str(tmp_path / "str")],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert out == "plain *text*\n"


def test_credentials_after_underscores_and_vendor_formats(tmp_path: Path) -> None:
    for line in (
        "DB_PASSWORD=hunter2hunter2",
        'password: "hunter2"',
        "AUTH_TOKEN=abcdef123456",
        "CLIENT_SECRET=abcdef123456",
        "key sk_live_" + "a1b2c3d4e5f6",
        "rk_live_" + "a1b2c3d4e5f6",
        "https://hooks.slack.com/services/T000/B000/XXXXXXXX",
    ):
        result = run(tmp_path, line + "\n")
        assert result.returncode == 1, line
        assert result.stdout.startswith("secret"), line


def test_word_containing_token_is_not_a_secret(tmp_path: Path) -> None:
    assert run(tmp_path, "the mytoken= value is 12345678\n").returncode == 0


def test_title_and_body_scan_together(tmp_path: Path) -> None:
    (tmp_path / "title.txt").write_text("Crash on /home/alex/app")
    (tmp_path / "body.md").write_text("clean body")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(tmp_path / "title.txt"), str(tmp_path / "body.md")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.strip() == "path\t1\t/home/alex/app\ttitle.txt"


def test_mask_replaces_credentials_only(tmp_path: Path) -> None:
    out = run(tmp_path, "run it\nAUTH_TOKEN=abcdef123456 now\n", "--mask").stdout
    assert out == "run it\nAUTH_<redacted> now\n"


def test_field_path_ignores_nested_comment_bodies(tmp_path: Path) -> None:
    (tmp_path / "written").write_text("![a](u.png)")
    fetched = {"body": "no image", "comments": [{"body": "![c](c.png)"}]}
    (tmp_path / "fetched").write_text(json.dumps(fetched))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--media",
            "--field",
            "body",
            str(tmp_path / "written"),
            str(tmp_path / "fetched"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1


def test_ref_kinds_and_new_path_roots(tmp_path: Path) -> None:
    text = "see acme/widgets#12, #34 (in-repo), !5 and ENG-123 in ~/work/x and /tmp/y.log\n"
    rows = [line.split("\t") for line in run(tmp_path, text).stdout.splitlines()]
    assert sorted((r[0], r[2]) for r in rows) == [
        ("path", "/tmp/y.log"),
        ("path", "~/work/x"),
        ("ref", "!5"),
        ("ref", "ENG-123"),
        ("ref", "acme/widgets#12"),
    ]


def test_standards_and_ids_are_not_refs(tmp_path: Path) -> None:
    assert run(tmp_path, "UTF-8 and SHA-256, color: #fff, a=b&#39;c\n").returncode == 0


def test_adf_text_keeps_links_cards_and_mentions(tmp_path: Path) -> None:
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "see "},
                    {
                        "type": "text",
                        "text": "the log",
                        "marks": [{"type": "link", "attrs": {"href": "https://x.io/l"}}],
                    },
                    {"type": "inlineCard", "attrs": {"url": "https://x.io/card"}},
                    {"type": "mention", "attrs": {"id": "1", "text": "@sam"}},
                ],
            }
        ],
    }
    (tmp_path / "adf").write_text(json.dumps({"fields": {"description": doc}}))
    out = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--text",
            "--field",
            "fields/description",
            str(tmp_path / "adf"),
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert out == "see the log (https://x.io/l)https://x.io/card@sam\n"


def test_keep_evidence_drops_only_counts_inside_evidence(tmp_path: Path) -> None:
    text = (
        "Fixed in acme/widgets#12 by @sam\n"
        "```\nlog: 12 files, closes org/repo#1, ping @bob\npath /home/alex/x\n```\n"
        "> quoted 5 lines and !7\n"
    )
    plain = [r.split("\t") for r in run(tmp_path, text).stdout.splitlines()]
    kept = [r.split("\t") for r in run(tmp_path, text, "--keep-evidence").stdout.splitlines()]
    assert ("rot", "12 files") in [(r[0], r[2]) for r in plain]
    assert ("rot", "12 files") not in [(r[0], r[2]) for r in kept]
    assert ("rot", "5 lines") not in [(r[0], r[2]) for r in kept]
    for expected in (
        ("mention", "@bob"),
        ("ref", "org/repo#1"),
        ("ref", "!7"),
        ("path", "/home/alex/x"),
    ):
        assert expected in [(r[0], r[2]) for r in kept]


def test_private_key_block_is_masked_whole(tmp_path: Path) -> None:
    key = (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA7\nQmFzZTY0Qm9keQ==\n"
        "-----END RSA PRIVATE KEY-----"
    )
    out = run(tmp_path, f"before\n{key}\nafter\n", "--mask").stdout
    assert out == "before\n<redacted>\nafter\n"
    assert run(tmp_path, key + "\n").stdout.startswith("secret\t1\t")


def test_vendor_token_prefixes_and_aws_secret(tmp_path: Path) -> None:
    secret = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    for line in (
        "t glpat-" + "a1B2c3D4e5F6g7H8i9J0",
        "t lin_api_" + "a1B2c3D4e5F6g7H8i9J0k1",
        "t ATATT" + "3xFfGF0a1B2c3D4e5F6g7H8i9J0",
        "t npm_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5",
        f"aws_secret_access_key = {secret}",
    ):
        assert run(tmp_path, line + "\n").stdout.startswith("secret"), line


def test_cut_candidates_lists_only_mechanical_rot_rows(tmp_path: Path) -> None:
    text = "Changed (+142/-38 lines), bundle grew to 4.2 MB, see x#L12\nroot /home/alex/x\n"
    result = run(tmp_path, text, "--cut-candidates")
    assert result.returncode == 0
    rows = [line.split("\t") for line in result.stdout.splitlines()]
    assert {r[0] for r in rows} == {"cut"}
    assert {"+142/-38", "#L12"} <= {r[2] for r in rows}
    assert any(r[2] == "4.2 MB" for r in rows)
    assert not any("alex" in r[2] for r in rows)


def test_aws_temporary_key_id(tmp_path: Path) -> None:
    assert run(tmp_path, "ASIA" + "ABCDEFGHIJKLMNOP\n").stdout.startswith("secret")
