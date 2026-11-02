import json
import tempfile
import unittest
from pathlib import Path
from domain_companion.core import Catalog, GovernanceError, compatibility, load, validate
from domain_companion.demo import REFERENCE_AS_OF, run_demo

ROOT=Path(__file__).resolve().parents[1]

class ContractTests(unittest.TestCase):
    def setUp(self):
        self.c=load(ROOT/"contracts"/"sales.order_lifecycle.v1.json")
        self.rows=json.loads((ROOT/"examples"/"orders.json").read_text())
    def test_valid(self):self.assertFalse(validate(self.c,self.rows,REFERENCE_AS_OF))
    def test_missing(self):
        rows=[dict(r) for r in self.rows];del rows[0]["amount"]
        self.assertTrue(validate(self.c,rows,REFERENCE_AS_OF))
    def test_negative(self):
        rows=[dict(r) for r in self.rows];rows[0]["amount"]=-10
        self.assertTrue(validate(self.c,rows,REFERENCE_AS_OF))
    def test_duplicates(self):
        rows=self.rows+[self.rows[0]]
        self.assertTrue(validate(self.c,rows,REFERENCE_AS_OF))
    def test_bool_is_not_number(self):
        rows=[dict(r) for r in self.rows];rows[0]["amount"]=True
        self.assertTrue(validate(self.c,rows,REFERENCE_AS_OF))
    def test_stale(self):
        rows=[dict(r) for r in self.rows];rows[0]["event_time"]="2020-01-01T00:00:00Z"
        self.assertTrue(validate(self.c,rows,REFERENCE_AS_OF))
    def test_future(self):
        rows=[dict(r) for r in self.rows];rows[0]["event_time"]="2027-01-01T00:00:00Z"
        self.assertTrue(validate(self.c,rows,REFERENCE_AS_OF))
    def test_incompatible(self):
        new=json.loads(json.dumps(self.c));del new["fields"]["amount"]
        self.assertTrue(compatibility(self.c,new))

class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
        self.output=Path(self.t.name)
        self.catalog=Catalog(ROOT/"contracts",self.output,REFERENCE_AS_OF)
        self.customers=json.loads((ROOT/"examples"/"customers.json").read_text())
    def test_publication_blocks_bad_rows(self):
        with self.assertRaises(GovernanceError):
            self.catalog.publish("customer.customer_profile",[{"customer_id":"bad"}],"customer")
        self.assertFalse((self.output/"published"/"customer.customer_profile.json").exists())
    def test_wrong_producer(self):
        with self.assertRaises(GovernanceError):
            self.catalog.publish("customer.customer_profile",self.customers,"sales")
    def test_access_boundary(self):
        self.catalog.publish("customer.customer_profile",self.customers,"customer")
        with self.assertRaises(GovernanceError):
            self.catalog.consume("customer.customer_profile","unknown")
    def test_preserve_previous_publication(self):
        self.catalog.publish("customer.customer_profile",self.customers,"customer")
        file=self.output/"published"/"customer.customer_profile.json";before=file.read_text()
        with self.assertRaises(GovernanceError):
            self.catalog.publish("customer.customer_profile",[],"customer")
        self.assertEqual(before,file.read_text())
    def test_demo_and_lineage(self):
        report=run_demo(ROOT,self.output)
        self.assertEqual(len(report["published_products"]),4)
        self.assertIn("analytics.business_performance",report["customer_contract_impact"])
        self.assertTrue((self.output/"run_report.json").exists())

if __name__=="__main__":unittest.main()
