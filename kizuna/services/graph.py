"""Knowledge graph built from relational data (no separate graph database).

Node types: expert, employee, procedure, module, step, skill, machine, equipment,
failure_mode, checkpoint, evidence. Edges carry a relation label, e.g.
expert —demonstrated→ procedure, step —requires→ skill,
failure_mode —mitigated_by→ checkpoint, employee —competent_in→ skill.
"""
from __future__ import annotations

from ..auth import can
from ..db import DB, loads
from . import common

SOURCE_LABEL = {"demonstration": "Demonstrated", "transcript": "Said", "expert_note": "Written note",
                "expert_edit": "Expert-authored", "inference": "Inferred"}


def build(db: DB, org_id: str, user: dict) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    unpublished_ok = can(user, "procedure.read_unpublished")

    def node(nid: str, ntype: str, label: str, **data) -> str:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, **data}
        return nid

    def edge(a: str, b: str, rel: str) -> None:
        edges.append({"source": a, "target": b, "rel": rel})

    skills = common.skills(db, org_id)
    for s in skills:
        node(f"skill:{s['code']}", "skill", s["name"], code=s["code"], name_ja=s["name_ja"], criticality=s["criticality"],
             category=s["category"])

    people = db.all("SELECT id, name, name_ja, role, title FROM users WHERE org_id = ? AND active = 1", (org_id,))
    by_id = {p["id"]: p for p in people}
    for h in db.all("SELECT e.user_id, e.proficiency, s.code FROM expert_skills e JOIN skills s ON s.id = e.skill_id "
                    "WHERE s.org_id = ?", (org_id,)):
        p = by_id.get(h["user_id"])
        if not p:
            continue
        nid = node(f"expert:{p['id']}", "expert", p["name"], name_ja=p["name_ja"], title=p["title"], person_id=p["id"])
        edge(nid, f"skill:{h['code']}", "holds" if h["proficiency"] >= 4 else "practises")

    procs = db.all("SELECT p.*, lv.status AS latest_status, lv.content_json AS latest_content, pv.content_json AS pub_content "
                   "FROM procedures p LEFT JOIN procedure_versions lv ON lv.id = p.latest_version_id "
                   "LEFT JOIN procedure_versions pv ON pv.id = p.published_version_id WHERE p.org_id = ?", (org_id,))
    for p in procs:
        if not unpublished_ok and not p["published_version_id"]:
            continue
        published = bool(p["published_version_id"])
        c = loads(p["pub_content"] if (published and not unpublished_ok) or (published and p["latest_status"] == "REJECTED")
                  else p["latest_content"], {}) or {}
        status = "PUBLISHED" if published and not unpublished_ok else p["latest_status"]
        pid = node(f"proc:{p['id']}", "procedure", f"{p['code']} {p['title']}", status=status, procedure_id=p["id"],
                   published=published, code=p["code"])
        owner = by_id.get(p["owner_expert_id"])
        if owner:
            eid = node(f"expert:{owner['id']}", "expert", owner["name"], name_ja=owner["name_ja"], title=owner["title"],
                       person_id=owner["id"])
            edge(eid, pid, "demonstrated")
        if published:
            mid = node(f"module:{p['id']}", "module", f"Training · {p['code']}", procedure_id=p["id"])
            edge(pid, mid, "taught_as")
            for code in c.get("skills", []):
                edge(mid, f"skill:{code}", "teaches")
        if c.get("machine"):
            mach = node(f"machine:{c['machine'].lower()}", "machine", c["machine"])
            edge(pid, mach, "performed_on")
        for e in c.get("equipment", [])[:8]:
            eq = node(f"equip:{e['name'].lower()}", "equipment", e["name"], kind=e["kind"])
            edge(pid, eq, "uses")
        checkpoints = {}
        for s in c.get("steps", []):
            sid = node(f"step:{p['id']}:{s['step_id']}", "step", s["title"], procedure_id=p["id"], step_id=s["step_id"],
                       source_type=s.get("source_type"), verified=s.get("evidence_verified"),
                       safety_critical=s.get("safety_critical"))
            edge(pid, sid, "contains")
            for code in s.get("skills", []) or c.get("skills", [])[:1]:
                if f"skill:{code}" in nodes:
                    edge(sid, f"skill:{code}", "requires")
            if s.get("source_timestamp") or s.get("evidence_quote"):
                evid = node(f"evidence:{p['id']}:{s['step_id']}", "evidence",
                            f"{SOURCE_LABEL.get(s.get('source_type'), 'Evidence')} {s.get('source_timestamp') or ''}".strip(),
                            quote=(s.get("evidence_quote") or "")[:200], verified=s.get("evidence_verified"),
                            procedure_id=p["id"], step_id=s["step_id"])
                edge(sid, evid, "has_evidence")
            if s.get("critical_checkpoint") and s.get("quality_check"):
                ck = node(f"check:{p['id']}:{s['step_id']}", "checkpoint", f"Checkpoint · {s['title']}",
                          detail=s["quality_check"][:200], procedure_id=p["id"], step_id=s["step_id"])
                edge(sid, ck, "verified_by")
                checkpoints[s["step_id"]] = ck
        for fm in c.get("failure_modes", []):
            fid = node(f"fm:{p['id']}:{fm['id']}", "failure_mode", fm["symptom"][:70], action=fm.get("action", "")[:200],
                       procedure_id=p["id"])
            target = checkpoints.get(fm.get("step_id")) or (f"step:{p['id']}:{fm['step_id']}" if fm.get("step_id") else pid)
            edge(fid, target, "mitigated_by")

    show_people = can(user, "competency.view_all")
    for r in db.all("SELECT c.user_id, c.status, s.code FROM competency_records c JOIN skills s ON s.id = c.skill_id WHERE c.org_id = ?",
                    (org_id,)):
        if not show_people and r["user_id"] != user["id"]:
            continue
        p = by_id.get(r["user_id"])
        if not p:
            continue
        nid = node(f"employee:{p['id']}", "employee", p["name"], name_ja=p["name_ja"], title=p["title"], person_id=p["id"])
        edge(nid, f"skill:{r['code']}", "competent_in" if r["status"] == "validated" else "training_in")

    # drop edges pointing to nodes that were filtered out
    edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    degree: dict[str, int] = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    for n in nodes.values():
        n["degree"] = degree.get(n["id"], 0)
    counts: dict[str, int] = {}
    for n in nodes.values():
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    return {"nodes": list(nodes.values()), "edges": edges, "counts": counts}
