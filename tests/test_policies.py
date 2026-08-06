from app.policies.loader import load_all_policies


def test_default_policies_load():
    policies = load_all_policies()
    assert set(policies) == {"evidence", "conflict", "release"}
    assert policies["evidence"]["policy_id"] == "evidence-default"
