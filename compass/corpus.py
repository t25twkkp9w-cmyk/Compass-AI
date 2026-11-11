"""Versioned policy units and catalog projections. Operational sources are excluded."""
import hashlib
import json
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

KNOWLEDGE = {1, 2, 3, 4, 5, 6, 7, 9}

def approximate_tokens(text): return len(re.findall(r"\w+|[^\w\s]", text))

def parse_markdown(text, filename, source_number):
    sid_match = re.search(r"- source_id:\s*(\S+)", text)
    sid = sid_match.group(1) if sid_match else Path(filename).stem
    version_match = re.search(r"- version:\s*(\S+)", text)
    version = version_match.group(1) if version_match else "unpublished"
    title_match = re.search(r"^# (.+)$", text, flags=re.M)
    title = title_match.group(1) if title_match else filename
    units = []
    for match in re.finditer(r"^## (S\d+)\. (.+)\n([\s\S]*?)(?=^## |\Z)", text, flags=re.M):
        section, heading, body = match.groups()
        units.append(Document(page_content=body.strip(), metadata=dict(citation_id=f"{sid}@{version}:{section}", source_id=sid,
            source_number=source_number, document_title=title, title=heading, version=version, section_id=section,
            authority="illustrative" if source_number == 5 else "authoritative", kind="policy", tenant="northstar",
            status="published", visibility="employees", parent_id=f"{sid}@{version}:{section}")))
    if not units: raise ValueError("Markdown must contain stable headings such as '## S01. Scope'.")
    return units

def catalog_text(kind, record):
    keys = {"tools": ["tool_id", "name", "status", "purpose", "deployment_ids", "account_requirement"],
            "models": ["model_version_id", "name", "role", "status", "approved_purposes", "limitations"],
            "deployments": ["deployment_id", "tool_id", "model_version_ids", "status", "permitted_data_classes", "purpose", "user_scope", "region", "excluded_data", "conditions", "identity", "retention"]}[kind]
    return "\n".join(f"{k.replace('_', ' ')}: {record.get(k)}" for k in keys)

class Corpus:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.sections = []
        self.sources = []
        digest = hashlib.sha256()
        for path in sorted(self.data_dir.glob("[0-9][0-9]_*")):
            number = int(path.name[:2])
            self.sources.append(dict(number=number, name=path.name, path=str(path), route="Knowledge" if number in KNOWLEDGE else "Structured records"))
            if number not in KNOWLEDGE: continue
            raw = path.read_text(); digest.update(raw.encode())
            if path.suffix == ".md": self.sections.extend(parse_markdown(raw, path.name, number))
            elif number == 2:
                catalog = json.loads(raw)
                for section in catalog["metadata"]["sections"]:
                    cid = f"REG-002@3.0:{section['section_id']}"
                    self.sections.append(Document(page_content=section["text"], metadata=dict(citation_id=cid, source_id="REG-002", source_number=2,
                        document_title=catalog["metadata"]["title"], title=section["title"], version="3.0", section_id=section["section_id"],
                        authority="authoritative", kind="catalog_rule", tenant="northstar", status="published", visibility="employees", parent_id=cid)))
                for kind, key in [("tools", "tool_id"), ("models", "model_version_id"), ("deployments", "deployment_id")]:
                    for record in catalog[kind]:
                        cid = record["citation_id"]
                        self.sections.append(Document(page_content=catalog_text(kind, record), metadata=dict(citation_id=cid, source_id="REG-002", source_number=2,
                            document_title="Approved AI Tools, Models & Deployments Register", title=record.get("name", record[key]), version="3.0",
                            section_id=record[key], authority="authoritative", kind=kind, tenant="northstar", status="published", visibility="employees", parent_id=cid)))
        self.manifest = "CORPUS-3.0-" + digest.hexdigest()[:12]
        self.by_id = {d.metadata["citation_id"]: d for d in self.sections}
        splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=60, length_function=approximate_tokens,
            separators=["\n\n", "\n", ". ", " ", ""])
        self.chunks = []
        for section in self.sections:
            for i, chunk in enumerate(splitter.split_documents([section])):
                chunk.metadata.update(chunk_id=section.metadata["citation_id"] + f":C{i+1:02}", manifest=self.manifest)
                # Include source and heading for retrieval; quoted evidence remains canonical body text.
                chunk.page_content = section.metadata["title"] + "\n" + chunk.page_content
                self.chunks.append(chunk)

    def reference(self, citation_id):
        return self.by_id.get(citation_id)

    def preview(self, filename, content, source_number):
        if source_number not in KNOWLEDGE: raise ValueError("Operational records are not embedded.")
        if filename.lower().endswith(".md"):
            return parse_markdown(content.decode(), filename, source_number)
        payload = json.loads(content)
        if source_number != 2 or not {"metadata", "tools", "models", "deployments"} <= payload.keys():
            raise ValueError("Catalog JSON requires metadata, tools, models and deployments.")
        return [Document(page_content=catalog_text(kind, record), metadata=dict(kind=kind, source_number=2))
                for kind in ["tools", "models", "deployments"] for record in payload[kind]]
