"""Tests for distributed simulation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldsim.distributed.partitioning import SpatialPartitioner, LoadBalancer
from worldsim.distributed.protocol import MessageSerializer
import json

def test_spatial_partitioner():
    sp = SpatialPartitioner(width=50, height=50)
    agents = [{"id": f"a{i}", "position": (i % 50, i // 50)} for i in range(100)]
    assignments = sp.assign_agents(agents, num_nodes=4)
    assert len(assignments) == 4
    total = sum(len(v) for v in assignments.values())
    assert total == 100
    print("✓ SpatialPartitioner")

def test_load_balancer():
    lb = LoadBalancer()
    nodes = [
        {"id": "n0", "agent_count": 80, "load": 0.9},
        {"id": "n1", "agent_count": 20, "load": 0.2},
        {"id": "n2", "agent_count": 30, "load": 0.3},
    ]
    plan = lb.rebalance(nodes, threshold=0.7)
    assert "migrations" in plan
    print("✓ LoadBalancer")

def test_message_serializer():
    ms = MessageSerializer()
    state = {"tick": 42, "agents": [{"id": "a1", "x": 5, "y": 10}], "metrics": {"eff": 0.8}}
    serialized = ms.serialize(state)
    assert isinstance(serialized, bytes)
    restored = ms.deserialize(serialized)
    assert restored["tick"] == 42
    assert restored["agents"][0]["id"] == "a1"
    assert restored["metrics"]["eff"] == 0.8
    print("✓ MessageSerializer")

def test_protocol_messages():
    from worldsim.distributed.protocol import SimState, SyncRequest, SyncResponse
    state = SimState(tick=10, agent_updates={"a1": {"x": 5}}, metrics={"eff": 0.8})
    d = state.to_dict()
    assert d["tick"] == 10
    req = SyncRequest(source="n0", target="n1", tick=10)
    assert req.source == "n0"
    resp = SyncResponse(request_id="r1", state=state, success=True)
    assert resp.success
    print("✓ Protocol messages")

if __name__ == "__main__":
    test_spatial_partitioner()
    test_load_balancer()
    test_message_serializer()
    test_protocol_messages()
    print("\n✅ All distributed tests passed!")
