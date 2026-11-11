"""Transactional records, case authorization, immutable history and audit events."""
import copy
import hashlib
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

from sqlalchemy import (create_engine, MetaData, Table, Column, String, Integer,
                        JSON, select, insert, update, and_)

from .schemas import DomainError, Principal

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def uid(prefix): return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"
def canonical(value): return json.dumps(value, sort_keys=True)

class Repository:
    def __init__(self, settings):
        self.settings = settings
        self.engine = create_engine(settings.db_url,
            connect_args={"check_same_thread": False, "timeout": 30} if settings.db_url.startswith("sqlite") else {},
            pool_pre_ping=True)
        meta = MetaData()
        self.records = Table("compass_records", meta,
            Column("kind", String(40), primary_key=True), Column("key", String(180), primary_key=True),
            Column("request_id", String(80), index=True), Column("version", Integer),
            Column("revision", Integer, nullable=False, default=0), Column("payload", JSON, nullable=False))
        self.audit = Table("compass_audit", meta, Column("sequence", Integer, primary_key=True, autoincrement=True),
            Column("request_id", String(80), index=True), Column("payload", JSON, nullable=False))
        self.control = Table("compass_control", meta, Column("key", String(80), primary_key=True), Column("value", String(250)))
        meta.create_all(self.engine)
        self.seed()

    def seed(self):
        with self.engine.begin() as c:
            if c.execute(select(self.control).where(self.control.c.key == "seed")).first(): return
            files = {
                "actors": ("08_REQ-008.json", "actors", "actor_id"),
                "requests": ("08_REQ-008.json", "requests", "request_id"),
                "snapshots": ("08_REQ-008.json", "submitted_snapshots", None),
                "reviews": ("10_DEC-010.json", "reviews", "review_id"),
                "decisions": ("10_DEC-010.json", "decisions", "decision_id"),
                "releases": ("10_DEC-010.json", "release_clearances", "release_id"),
                "conditions": ("11_EVD-011.json", "conditions", "condition_id"),
                "evidence": ("11_EVD-011.json", "evidence_artifacts", "evidence_id"),
                "tools": ("02_REG-002.json", "tools", "tool_id"),
                "models": ("02_REG-002.json", "models", "model_version_id"),
                "deployments": ("02_REG-002.json", "deployments", "deployment_id"),
            }
            for kind, (filename, array, key) in files.items():
                data = json.loads((self.settings.data_dir / filename).read_text())
                for payload in data[array]:
                    pk = payload[key] if key else f"{payload['request_id']}:v{payload['request_version']}"
                    self._put(c, kind, pk, payload)
            for event in json.loads((self.settings.data_dir / "12_AUD-012.json").read_text())["events"]:
                c.execute(insert(self.audit).values(request_id=event["request_id"], payload=event))
            c.execute(insert(self.control).values(key="seed", value="CORPUS-3.0"))

    def _put(self, c, kind, key, payload):
        c.execute(insert(self.records).values(kind=kind, key=key, request_id=payload.get("request_id"),
            version=payload.get("request_version", payload.get("current_version")), revision=0, payload=copy.deepcopy(payload)))

    def _get(self, c, kind, key):
        row = c.execute(select(self.records).where(and_(self.records.c.kind == kind, self.records.c.key == key))).mappings().first()
        if not row: raise DomainError(f"Record not found: {key}")
        return copy.deepcopy(row["payload"])

    def _rows(self, c, kind):
        return [copy.deepcopy(r[0]) for r in c.execute(select(self.records.c.payload).where(self.records.c.kind == kind))]

    def _replace(self, c, kind, key, payload, expected_revision=None):
        stmt = update(self.records).where(and_(self.records.c.kind == kind, self.records.c.key == key))
        if expected_revision is not None: stmt = stmt.where(self.records.c.revision == expected_revision)
        result = c.execute(stmt.values(payload=copy.deepcopy(payload), version=payload.get("current_version", payload.get("request_version")),
                                      revision=self.records.c.revision + 1))
        if result.rowcount != 1: raise DomainError("The record changed. Reload before acting.")

    def principal(self, actor_id):
        with self.engine.connect() as c: a = self._get(c, "actors", actor_id)
        return Principal(actor_id=a["actor_id"], name=a["name"], role=a["role"], demo=self.settings.demo_identities)

    def actors(self):
        with self.engine.connect() as c: return self._rows(c, "actors")

    def catalog(self, kind):
        if kind not in {"tools", "models", "deployments"}: raise DomainError("Unknown catalog entity.")
        with self.engine.connect() as c: return self._rows(c, kind)

    def _authorize(self, principal, request):
        # No implicit all-case access for administrators or auditors.
        if principal.actor_id not in request.get("visible_to_actor_ids", []):
            raise DomainError("You are not assigned to this case. No case facts were returned.")

    def requests(self, principal):
        with self.engine.connect() as c:
            return [r for r in self._rows(c, "requests") if principal.actor_id in r.get("visible_to_actor_ids", [])]

    def request(self, principal, request_id):
        with self.engine.connect() as c: r = self._get(c, "requests", request_id)
        self._authorize(principal, r)
        return r

    def case_records(self, principal, request_id, kind):
        if kind not in {"snapshots", "reviews", "decisions", "releases", "conditions", "evidence"}: raise DomainError("Unknown case record type.")
        self.request(principal, request_id)
        with self.engine.connect() as c:
            return [r[0] for r in c.execute(select(self.records.c.payload).where(and_(
                self.records.c.kind == kind, self.records.c.request_id == request_id)))]

    @contextmanager
    def _case_transaction(self, principal, request_id, action_key=None):
        with self.engine.begin() as c:
            if self.engine.dialect.name == "sqlite": c.exec_driver_sql("BEGIN IMMEDIATE")
            # Serialize formal writes per case on PostgreSQL. Revision checks protect stale forms.
            row = c.execute(select(self.records).where(and_(self.records.c.kind == "requests",
                self.records.c.key == request_id)).with_for_update()).mappings().first()
            if not row: raise DomainError("Request not found.")
            r = copy.deepcopy(row["payload"])
            self._authorize(principal, r)
            if action_key and c.execute(select(self.control).where(self.control.c.key == action_key)).first():
                raise DomainError("This action has already been recorded. Reload the case.")
            yield c, r, row["revision"]
            if action_key: c.execute(insert(self.control).values(key=action_key, value=now()))

    def _event(self, c, principal, request_id, version, action, details):
        # The control row provides one ledger writer lock across PostgreSQL case transactions.
        c.execute(select(self.control).where(self.control.c.key == "seed").with_for_update()).first()
        last = c.execute(select(self.audit.c.payload).order_by(self.audit.c.sequence.desc()).limit(1)).scalar()
        payload = dict(event_id=uid("EVT-RUN"), request_id=request_id, request_version=version,
            occurred_at_utc=now(), actor_id=principal.actor_id, action=action,
            details=details, synthetic=self.settings.demo_identities,
            previous_event_hash=last.get("event_hash", "0" * 64) if last else "0" * 64)
        payload["event_hash"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
        c.execute(insert(self.audit).values(request_id=request_id, payload=payload))

    def latest_reviews(self, principal, request_id):
        req = self.request(principal, request_id)
        return self._latest_reviews(self.case_records(principal, request_id, "reviews"), req["current_version"])

    @staticmethod
    def _latest_reviews(rows, version):
        latest = {}
        for r in sorted(rows, key=lambda x: x.get("reviewed_at") or ""):
            if r["request_version"] == version: latest[r["domain"]] = r
        return latest

    def audit_events(self, principal, request_id=None):
        permitted = {r["request_id"] for r in self.requests(principal)}
        if request_id:
            self.request(principal, request_id); permitted &= {request_id}
        with self.engine.connect() as c:
            if not permitted: return []
            return [r[0] for r in c.execute(select(self.audit.c.payload).where(self.audit.c.request_id.in_(permitted)).order_by(self.audit.c.sequence))]

    def create_request(self, principal, title, purpose, deployment_id, audience, personal_data=False):
        if not title.strip() or not purpose.strip(): raise DomainError("Title and business purpose are required.")
        if principal.actor_id == "ACT-004": raise DomainError("The default decision owner cannot submit a self-approved case. Use a requester identity.")
        dep = next((d for d in self.catalog("deployments") if d["deployment_id"] == deployment_id), None)
        if not dep: raise DomainError("Select a catalog deployment.")
        rid = uid("REQ-N")
        domains = ["Technology", "Security"] + (["Legal", "Compliance/Risk"] if audience == "Customers" else []) + (["Privacy"] if personal_data else [])
        reviewers = self.review_assignments(domains)
        request = dict(request_id=rid, current_version=1, title=title.strip()[:180], purpose=purpose.strip()[:6000],
            business_unit="New application", requester_actor_id=principal.actor_id, sponsor_actor_id="ACT-002",
            coordinator_actor_id="ACT-003", decision_owner_actor_id="ACT-004", sponsor_endorsed=False,
            required_review_domains=domains, risk_screening="High" if audience == "Customers" else "Moderate",
            lifecycle="Draft", approval_disposition="Pending", release_readiness="Blocked", created_at=now(),
            next_action="Confirm business sponsorship and submit the scoped request.",
            scope=dict(tool_id=dep["tool_id"], deployment_id=deployment_id, model_version_ids=dep["model_version_ids"],
                       region=dep["region"], data_description="Public/Internal proposed scope", personal_data_proposed=personal_data,
                       restricted_data_proposed=False, audience=audience, human_oversight="Human review and fallback required"),
            routing_version="AUTH-009@3.0", visible_to_actor_ids=list(dict.fromkeys([principal.actor_id, "ACT-002", "ACT-003", "ACT-004", "ACT-010", "ACT-011", *reviewers.values()])))
        with self.engine.begin() as c:
            self._put(c, "requests", rid, request)
            self._put(c, "snapshots", f"{rid}:v1", dict(request_id=rid, request_version=1, scope=request["scope"], purpose=purpose,
                source_snapshot="CORPUS-3.0", created_at=now(), submitted_at=None, immutable_after_submission=False))
            self._event(c, principal, rid, 1, "draft_created", {"title": request["title"]})
        return rid

    @staticmethod
    def review_assignments(domains):
        mapping = {"Technology": "ACT-006", "Security": "ACT-005", "Legal": "ACT-007", "Compliance/Risk": "ACT-008", "Privacy": "ACT-009", "Engineering/Quality": "ACT-014"}
        return {d: mapping[d] for d in domains}

    def endorse(self, principal, rid, version, action_key):
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version)
            if principal.actor_id != r["sponsor_actor_id"]: raise DomainError("Only the assigned sponsor can endorse this case.")
            if r["sponsor_endorsed"]: raise DomainError("Sponsorship is already recorded.")
            r["sponsor_endorsed"] = True
            self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version, "sponsor_endorsed", {})

    def submit(self, principal, rid, version, action_key):
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version)
            if principal.actor_id != r["requester_actor_id"] or r["lifecycle"] != "Draft": raise DomainError("Only the requester can submit a draft.")
            if not r["sponsor_endorsed"]: raise DomainError("Sponsor endorsement is required before submission.")
            r["lifecycle"] = "Under review"; r["next_action"] = "Assigned specialists must review the submitted version."
            s = self._get(c, "snapshots", f"{rid}:v{version}"); s.update(submitted_at=now(), immutable_after_submission=True)
            self._replace(c, "snapshots", f"{rid}:v{version}", s)
            for domain, actor in self.review_assignments(r["required_review_domains"]).items():
                review = dict(review_id=uid("REV"), request_id=rid, request_version=version, domain=domain,
                    reviewer_actor_id=actor, finding="Pending", blocking=False, rationale="Awaiting assigned review", reviewed_at=None)
                self._put(c, "reviews", review["review_id"], review)
            self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version, "request_submitted", {"routing_version": r["routing_version"]})

    @staticmethod
    def _version(r, version):
        if r["current_version"] != version: raise DomainError("The request version changed. Reload before acting.")

    def record_review(self, principal, rid, version, domain, finding, rationale, action_key):
        if finding not in {"Satisfactory", "Changes requested", "Blocking finding"}: raise DomainError("Invalid finding.")
        if not rationale.strip(): raise DomainError("A review rationale is required.")
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version)
            if r["approval_disposition"] != "Pending" or r["lifecycle"] not in {"Under review", "Awaiting information"}: raise DomainError("This request is not open for domain review.")
            if self.review_assignments(r["required_review_domains"]).get(domain) != principal.actor_id: raise DomainError("You are not assigned to this domain review.")
            if principal.actor_id == r["requester_actor_id"]: raise DomainError("A requester cannot review their own submission.")
            record = dict(review_id=uid("REV"), request_id=rid, request_version=version, domain=domain,
                reviewer_actor_id=principal.actor_id, finding=finding, blocking=finding == "Blocking finding", rationale=rationale.strip(), reviewed_at=now())
            self._put(c, "reviews", record["review_id"], record)
            r["lifecycle"] = "Awaiting information" if finding == "Changes requested" else "Under review"
            self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version, "review_recorded", {"review_id": record["review_id"], "domain": domain, "finding": finding})

    def record_decision(self, principal, rid, version, disposition, rationale, action_key):
        if disposition not in {"Approved with conditions", "Rejected", "Return for revision"}: raise DomainError("Invalid disposition.")
        if not rationale.strip(): raise DomainError("Decision rationale is required.")
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version)
            if principal.actor_id != r["decision_owner_actor_id"] or principal.actor_id == r["requester_actor_id"]: raise DomainError("Only the assigned independent decision owner can decide this case.")
            if r["approval_disposition"] != "Pending" or r["lifecycle"] in {"Draft", "Withdrawn"}: raise DomainError("The case is not pending a decision.")
            if disposition == "Approved with conditions":
                # Restrict by case before domain reduction.
                findings = self._latest_reviews([v for v in self._rows(c, "reviews") if v["request_id"] == rid], version)
                if not r["sponsor_endorsed"] or any(findings.get(d, {}).get("finding") != "Satisfactory" for d in r["required_review_domains"]): raise DomainError("All mandatory reviews and sponsor endorsement must be satisfactory.")
                dep = self._get(c, "deployments", r["scope"]["deployment_id"])
                if dep["status"] in {"Blocked", "Revoked"} or r["scope"].get("personal_data_proposed") or r["scope"].get("restricted_data_proposed") or r["risk_screening"] == "Prohibited": raise DomainError("This scope cannot be approved under the current policy and catalog restrictions.")
                existing = [v for v in self._rows(c, "conditions") if v["request_id"] == rid and v["request_version"] == version]
                if not existing:
                    kinds = ["Evaluation report", "Security and oversight evidence"] + (["Deployment catalog publication"] if dep["status"] != "Approved" else [])
                    for kind in kinds:
                        condition = dict(condition_id=uid("CON"), request_id=rid, request_version=version, kind=kind,
                            phase="pre_release", description=kind + " for the exact submitted configuration", owner_actor_id="ACT-010",
                            verifier_actor_id="ACT-011", due_at=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat(), status="Pending", evidence_ids=[], verification=None)
                        self._put(c, "conditions", condition["condition_id"], condition)
            record = dict(decision_id=uid("DEC"), request_id=rid, request_version=version, record_type="approval",
                disposition=disposition, decision_owner_actor_id=principal.actor_id, rationale=rationale.strip(), decided_at=now(),
                valid_from=now(), valid_until=(datetime.now(timezone.utc)+timedelta(days=90)).isoformat().replace("+00:00", "Z"), source_snapshot="CORPUS-3.0")
            self._put(c, "decisions", record["decision_id"], record)
            r.update(approval_disposition="Pending" if disposition == "Return for revision" else disposition,
                     lifecycle="Awaiting information" if disposition == "Return for revision" else "Closed", release_readiness="Blocked",
                     next_action="Address review feedback in a new version." if disposition == "Return for revision" else "Verify pre-release evidence before release." if disposition.startswith("Approved") else "Do not proceed with this proposal.")
            self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version, "decision_recorded", {"decision_id": record["decision_id"], "disposition": disposition})

    def revise(self, principal, rid, version, deployment_id, reason, action_key):
        if not reason.strip(): raise DomainError("A change reason is required.")
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version)
            if principal.actor_id != r["requester_actor_id"]: raise DomainError("Only the requester can prepare a revision.")
            dep = self._get(c, "deployments", deployment_id)
            r["scope"].update(deployment_id=deployment_id, tool_id=dep["tool_id"], model_version_ids=dep["model_version_ids"])
            r.update(current_version=version+1, lifecycle="Draft", approval_disposition="Pending", release_readiness="Blocked", sponsor_endorsed=False,
                next_action="New version needs endorsement, submission and fresh reviews.")
            s = dict(request_id=rid, request_version=version+1, scope=r["scope"], purpose=r["purpose"], created_at=now(),
                submitted_at=None, immutable_after_submission=False, supersedes_version=version, change_reason=reason.strip())
            self._put(c, "snapshots", f"{rid}:v{version+1}", s)
            self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version+1, "request_revised", {"reason": reason, "previous_version": version})

    def submit_evidence(self, principal, rid, version, condition_id, artifact, action_key):
        if not isinstance(artifact, dict): raise DomainError("Evidence must be a JSON object.")
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version)
            condition = self._get(c, "conditions", condition_id)
            if condition["request_id"] != rid or condition["request_version"] != version: raise DomainError("Condition belongs to a different request version.")
            if principal.actor_id != condition["owner_actor_id"]: raise DomainError("Only the assigned evidence owner may submit this artifact.")
            if r["approval_disposition"] not in {"Approved", "Approved with conditions"}: raise DomainError("The case has no applicable approval.")
            if condition["status"] == "Verified": raise DomainError("Verified evidence cannot be replaced silently. Open a new assessment.")
            manifest = artifact.get("configuration", {})
            if manifest.get("request_id") != rid or manifest.get("request_version") != version or manifest.get("deployment_id") != r["scope"]["deployment_id"] or sorted(manifest.get("model_version_ids", [])) != sorted(r["scope"]["model_version_ids"]): raise DomainError("Artifact configuration does not match the exact request version, deployment and models.")
            if not principal.demo and artifact.get("synthetic_fixture", True): raise DomainError("Synthetic evidence cannot satisfy production release requirements.")
            evidence_id = uid("EVD")
            item = dict(evidence_id=evidence_id, version=1, request_id=rid, request_version=version, condition_id=condition_id,
                submitted_by=principal.actor_id, submitted_at=now(), artifact_content=artifact,
                artifact_sha256=hashlib.sha256(canonical(artifact).encode()).hexdigest())
            self._put(c, "evidence", evidence_id, item)
            condition.update(status="Submitted", evidence_ids=[*condition.get("evidence_ids", []), evidence_id], verification=None)
            self._replace(c, "conditions", condition_id, condition)
            r["release_readiness"] = "Awaiting verification"; self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version, "evidence_submitted", {"evidence_id": evidence_id, "condition_id": condition_id})

    def verify(self, principal, rid, version, condition_id, accepted, reason, action_key):
        if not reason.strip(): raise DomainError("Verification rationale is required.")
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version); condition = self._get(c, "conditions", condition_id)
            if condition["request_id"] != rid or condition["request_version"] != version: raise DomainError("Condition scope mismatch.")
            if principal.actor_id != condition["verifier_actor_id"] or principal.actor_id == condition["owner_actor_id"]: raise DomainError("Only a distinct assigned verifier may verify evidence.")
            if condition["status"] != "Submitted" or not condition.get("evidence_ids"): raise DomainError("No submitted artifact is awaiting verification.")
            if r["approval_disposition"] not in {"Approved", "Approved with conditions"}: raise DomainError("No applicable approval.")
            item = self._get(c, "evidence", condition["evidence_ids"][-1])
            if principal.actor_id == item["submitted_by"]: raise DomainError("Evidence cannot be self-verified.")
            if not principal.demo and item["artifact_content"].get("synthetic_fixture", True): raise DomainError("A fictional fixture cannot satisfy production evidence.")
            condition.update(status="Verified" if accepted else "Returned", verification=dict(verifier_actor_id=principal.actor_id,
                evidence_id=item["evidence_id"], evidence_version=item["version"], verified_at=now(), result="accepted" if accepted else "returned", reason=reason.strip()))
            self._replace(c, "conditions", condition_id, condition)
            r["release_readiness"] = "Blocked"; self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version, "evidence_verified" if accepted else "evidence_returned", {"condition_id": condition_id, "reason": reason})

    def clear_release(self, principal, rid, version, reason, action_key):
        if not reason.strip(): raise DomainError("Release rationale is required.")
        with self._case_transaction(principal, rid, action_key) as (c, r, revision):
            self._version(r, version)
            if principal.actor_id != r["decision_owner_actor_id"] or principal.actor_id == r["requester_actor_id"]: raise DomainError("Only the assigned independent release authority can clear this case.")
            if r["release_readiness"] == "Cleared": raise DomainError("Release is already cleared.")
            if r["approval_disposition"] not in {"Approved", "Approved with conditions"}: raise DomainError("Pending, expired, rejected and revoked decisions cannot clear release.")
            ds = [v for v in self._rows(c, "decisions") if v["request_id"] == rid and v["request_version"] == version]
            latest = max(ds, key=lambda d: d.get("decided_at", ""), default={})
            if latest.get("disposition") not in {"Approved", "Approved with conditions"} or not latest.get("valid_until") or latest["valid_until"] < now(): raise DomainError("No current effective approval exists.")
            if latest.get("valid_from", "") > now(): raise DomainError("The approval is not yet effective.")
            conds = [v for v in self._rows(c, "conditions") if v["request_id"] == rid and v["request_version"] == version and v["phase"] == "pre_release"]
            if not conds or any(v["status"] != "Verified" for v in conds): raise DomainError("All pre-release conditions must be independently verified.")
            dep = self._get(c, "deployments", r["scope"]["deployment_id"])
            if dep["status"] != "Approved": raise DomainError("The exact deployment is not approved in the current catalog.")
            if sorted(dep["model_version_ids"]) != sorted(r["scope"]["model_version_ids"]) or dep["tool_id"] != r["scope"]["tool_id"]: raise DomainError("Deployment, tool and model versions do not match.")
            if r["scope"].get("personal_data_proposed") or r["scope"].get("restricted_data_proposed"): raise DomainError("Prohibited data scope cannot clear release.")
            item = dict(release_id=uid("REL"), request_id=rid, request_version=version, decision_id=latest["decision_id"],
                authorized_by=principal.actor_id, cleared_at=now(), scope=r["scope"], condition_ids=[v["condition_id"] for v in conds], rationale=reason.strip())
            self._put(c, "releases", item["release_id"], item)
            r.update(release_readiness="Cleared", next_action="Operate within approved scope and maintain ongoing obligations.")
            self._replace(c, "requests", rid, r, revision)
            self._event(c, principal, rid, version, "release_cleared", {"release_id": item["release_id"], "reason": reason})

    def export_case(self, principal, rid):
        request = self.request(principal, rid)
        with self._case_transaction(principal, rid) as (c, r, _):
            self._event(c, principal, rid, r["current_version"], "evidence_exported", {"scope": "authorized single case"})
        return dict(request=request, snapshots=self.case_records(principal, rid, "snapshots"),
            reviews=self.case_records(principal, rid, "reviews"), decisions=self.case_records(principal, rid, "decisions"),
            conditions=self.case_records(principal, rid, "conditions"), evidence=self.case_records(principal, rid, "evidence"),
            events=self.audit_events(principal, rid), synthetic=self.settings.demo_identities, exported_at=now())

    def save_guidance(self, principal, result):
        key = uid("GUIDE")
        with self.engine.begin() as c: self._put(c, "guidance", key, {"guidance_id": key, "actor_id": principal.actor_id, "created_at": now(), "result": result})
        return key

    def saved_guidance(self, principal):
        with self.engine.connect() as c: return [r for r in self._rows(c, "guidance") if r["actor_id"] == principal.actor_id]

    def save_eval(self, principal, result):
        if principal.actor_id not in {"ACT-003", "ACT-004", "ACT-012", "ACT-013", "ACT-014", "ACT-022"}: raise DomainError("Evaluation execution is limited to Quality, Governance and Platform roles.")
        key = uid("EVAL-RUN")
        with self.engine.begin() as c: self._put(c, "eval_runs", key, {"run_id": key, "actor_id": principal.actor_id, "created_at": now(), **result})
        return key

    def eval_runs(self, principal):
        if principal.actor_id not in {"ACT-003", "ACT-004", "ACT-012", "ACT-013", "ACT-014", "ACT-022"}: return []
        with self.engine.connect() as c: return self._rows(c, "eval_runs")

    def stage_upload(self, principal, name, content, source_number):
        if principal.actor_id != "ACT-013": raise DomainError("Only the source administrator can stage source uploads.")
        if source_number not in {1,2,3,4,5,6,7,9}: raise DomainError("Only knowledge sources #1–7 and #9 may be indexed.")
        if len(content) > 5_000_000: raise DomainError("Source file exceeds 5 MB.")
        text = content.decode("utf-8")
        if name.lower().endswith(".json"): json.loads(text)
        elif not name.lower().endswith(".md"): raise DomainError("Upload Markdown or JSON.")
        if not text.strip(): raise DomainError("Source is empty.")
        key = uid("UPLOAD")
        item = dict(upload_id=key, name=name[:180], source_number=source_number, text=text, actor_id=principal.actor_id,
            created_at=now(), status="Staged; not published", sha256=hashlib.sha256(content).hexdigest())
        with self.engine.begin() as c: self._put(c, "uploads", key, item)
        return key

    def uploads(self, principal):
        if principal.actor_id != "ACT-013": return []
        with self.engine.connect() as c: return self._rows(c, "uploads")
