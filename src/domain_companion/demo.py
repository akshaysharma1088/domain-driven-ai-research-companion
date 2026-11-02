"""Reproducible synthetic cross-domain example."""
import json
from pathlib import Path
from .core import Catalog
REFERENCE_AS_OF="2026-11-01T12:00:00+00:00"
def run_demo(root:Path,output:Path,as_of=REFERENCE_AS_OF):
    root=Path(root);output=Path(output);catalog=Catalog(root/"contracts",output,as_of)
    customers=json.loads((root/"examples"/"customers.json").read_text())
    orders=json.loads((root/"examples"/"orders.json").read_text())
    counts={}
    counts["customer.customer_profile"]=catalog.publish("customer.customer_profile",customers,"customer")
    counts["sales.order_lifecycle"]=catalog.publish("sales.order_lifecycle",orders,"sales")
    approved_customers=catalog.consume("customer.customer_profile","analytics")
    approved_orders=catalog.consume("sales.order_lifecycle","analytics")
    perf=[{"customer_id":c["customer_id"],"segment":c["segment"],"completed_orders":sum(o["customer_id"]==c["customer_id"] and o["status"]=="completed" for o in approved_orders),"completed_revenue":round(sum(o["amount"] for o in approved_orders if o["customer_id"]==c["customer_id"] and o["status"]=="completed"),2)} for c in approved_customers]
    counts["analytics.business_performance"]=catalog.publish("analytics.business_performance",perf,"analytics")
    sales_orders=catalog.consume("sales.order_lifecycle","sales")
    features=[{"customer_id":c["customer_id"],"completed_order_count_30d":sum(o["customer_id"]==c["customer_id"] and o["status"]=="completed" for o in sales_orders)} for c in catalog.consume("customer.customer_profile","sales")]
    counts["sales.order_volume_feature"]=catalog.publish("sales.order_volume_feature",features,"sales")
    report={"reference_date":as_of,"published_products":counts,"lineage":catalog.lineage(),"customer_contract_impact":catalog.impact("customer.customer_profile"),"limitations":"Synthetic educational demonstration only; no production security or performance claims."}
    output.mkdir(parents=True,exist_ok=True);(output/"run_report.json").write_text(json.dumps(report,indent=2))
    return report
