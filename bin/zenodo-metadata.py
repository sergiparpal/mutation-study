#!/usr/bin/env python3
"""
Write .zenodo.json from CITATION.cff, or check that the two agree.

Zenodo archives each published GitHub release of this repository and gives
it a DOI. When the repository holds a .zenodo.json, Zenodo reads that file
and ignores CITATION.cff. From CITATION.cff alone it would read the title,
abstract, authors, keywords, a single licence and the message, but not the
type: every record would be filed as software. So the metadata is written
once, in CITATION.cff, and .zenodo.json is derived from it here:

  type       -> upload_type   dataset or software
  title      -> title
  authors    -> creators      "Family, Given", with orcid and affiliation if given
  abstract   -> description   one HTML paragraph
  keywords   -> keywords
  license    -> license       the SPDX identifier in lower case, as Zenodo's
                              vocabulary has it (CC-BY-4.0 -> cc-by-4.0)
  message    -> notes

The version and the publication date are left out: Zenodo takes them from
the release's tag and date.

Usage:
    ./bin/zenodo-metadata.py           rewrite .zenodo.json
    ./bin/zenodo-metadata.py --check   exit 1 if .zenodo.json is not what CITATION.cff gives
"""

import html
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFF = os.path.join(ROOT, "CITATION.cff")
OUT = os.path.join(ROOT, ".zenodo.json")


def one_line(text):
    return " ".join(str(text).split())


def creator(author):
    family, given = author.get("family-names"), author.get("given-names")
    name = author.get("name") or ", ".join(p for p in (family, given) if p)
    out = {"name": name}
    if author.get("affiliation"):
        out["affiliation"] = author["affiliation"]
    if author.get("orcid"):
        out["orcid"] = author["orcid"].rsplit("/", 1)[-1]
    return out


def build(cff):
    kind = cff.get("type", "software")
    if kind not in ("dataset", "software"):
        sys.exit(f"CITATION.cff: type {kind!r} is neither dataset nor software")
    if not isinstance(cff.get("license"), str):
        sys.exit("CITATION.cff: license must be a single SPDX identifier")
    return {
        "upload_type": kind,
        "title": one_line(cff["title"]),
        "creators": [creator(a) for a in cff["authors"]],
        "description": "<p>" + html.escape(one_line(cff["abstract"]), quote=False) + "</p>",
        "keywords": list(cff.get("keywords", [])),
        "license": cff["license"].lower(),
        "notes": one_line(cff["message"]),
    }


def main():
    with open(CFF) as fh:
        cff = yaml.safe_load(fh)
    text = json.dumps(build(cff), indent=2, ensure_ascii=False) + "\n"
    if "--check" in sys.argv[1:]:
        try:
            with open(OUT) as fh:
                current = fh.read()
        except OSError:
            current = None
        if current != text:
            print(".zenodo.json does not match CITATION.cff: run ./bin/zenodo-metadata.py")
            sys.exit(1)
        print(".zenodo.json matches CITATION.cff")
        return
    with open(OUT, "w") as fh:
        fh.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
