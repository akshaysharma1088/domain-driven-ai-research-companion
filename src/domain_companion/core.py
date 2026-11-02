"""Minimal data contract and publication gates. Demo-only, not production authorization."""
import json
from datetime import datetime, timezone
from pathlib import Path

class GovernanceError(Exception): pass

def instant(s):
    d=datetime.fromisoformat(s.replace("Z","+00:00"))
    if d.tzinfo is None: raise ValueError("Timezone required")
    return d.astimezone(timezone.utc)

def load(path):
    c=json.loads(Path(path).read_text())
    for k in ("product_id","domain","owner","version","fields","quality","allowed_consumers","dependencies"):
        if k not in c: raise GovernanceError("Missing contract key: "+k)
    return c

def validate(c,rows,as_of):
    errors=[]
    if len(rows)<c["quality"].get("min_rows",1): errors.append("Insufficient rows")
    seen=set()
    for i,row in enumerate(rows):
        for name,s in c["fields"].items():
            v=row.get(name)
            if v is None:
                if s.get("required"):errors.append(f"row {i}: missing {name}")
                continue
            t=s["type"]
            valid=(t=="string" and isinstance(v,str) or t=="integer" and type(v)==int or t=="number" and type(v) in (int,float) or t=="timestamp" and isinstance(v,str))
            if not valid:errors.append(f"row {i}: invalid {name}")
            if t=="timestamp" and valid:
                try: instant(v)
                except ValueError:errors.append(f"row {i}: invalid timestamp {name}")
        if set(row)-set(c["fields"]):errors.append(f"row {i}: undeclared fields")
        for key,minimum in c["quality"].get("minimums",{}).items():
            v=row.get(key)
            if type(v) in (int,float) and v<minimum:errors.append(f"row {i}: {key} below minimum")
        keys=c["quality"].get("unique_key",[])
        if keys and all(k in row for k in keys):
            value=tuple(row[k] for k in keys)
            if value in seen:errors.append(f"row {i}: duplicate key")
            seen.add(value)
        field=c["quality"].get("freshness_field")
        if field and isinstance(row.get(field),str):
            try:
                delta=(instant(as_of)-instant(row[field])).total_seconds()
                if delta<0 or delta>c["quality"].get("max_age_days",365)*86400:errors.append(f"row {i}: freshness check failed")
            except ValueError:pass
    return errors

def compatibility(old,new):
    errors=[]
    if old["product_id"]!=new["product_id"] or old["domain"]!=new["domain"]:errors.append("Identity changed")
    for k,s in old["fields"].items():
        if k not in new["fields"]:errors.append("Field removed: "+k)
        elif new["fields"][k]["type"]!=s["type"]:errors.append("Type changed: "+k)
    if old.get("description")!=new.get("description"):errors.append("Semantic review needed")
    return errors

class Catalog:
    def __init__(self,contracts_dir,output_dir,as_of):
        self.contracts={c["product_id"]:c for c in (load(p) for p in sorted(Path(contracts_dir).glob("*.json")))}
        self.output=Path(output_dir)
        self.as_of=as_of
    def publish(self,pid,rows,producer_domain):
        c=self.contracts[pid]
        if producer_domain!=c["domain"]:raise GovernanceError("Wrong publishing domain")
        for dep in c["dependencies"]:
            if producer_domain not in self.contracts[dep]["allowed_consumers"]:raise GovernanceError("Upstream access denied")
            self.consume(dep,producer_domain)
        errors=validate(c,rows,self.as_of)
        if errors:raise GovernanceError("; ".join(errors))
        directory=self.output/"published";directory.mkdir(parents=True,exist_ok=True)
        target=directory/(pid+".json");tmp=directory/(pid+".tmp")
        tmp.write_text(json.dumps({"product_id":pid,"domain":c["domain"],"owner":c["owner"],"contract_version":c["version"],"depends_on":c["dependencies"],"rows":rows},indent=2))
        tmp.replace(target)
        return len(rows)
    def consume(self,pid,consumer_domain):
        c=self.contracts[pid]
        if consumer_domain not in c["allowed_consumers"]:raise GovernanceError("Consumer not allowed")
        file=self.output/"published"/(pid+".json")
        if not file.exists():raise GovernanceError("Unpublished upstream: "+pid)
        data=json.loads(file.read_text())
        if data["contract_version"]!=c["version"]:raise GovernanceError("Version mismatch")
        return data["rows"]
    def lineage(self):
        return [{"from":d,"to":c["product_id"]} for c in self.contracts.values() for d in c["dependencies"] if (self.output/"published"/(c["product_id"]+".json")).exists()]
    def impact(self,pid):
        edges=self.lineage();reached=set();frontier=[pid]
        while frontier:
            cur=frontier.pop()
            for e in edges:
                if e["from"]==cur and e["to"] not in reached:
                    reached.add(e["to"]);frontier.append(e["to"])
        return sorted(reached-{pid})
