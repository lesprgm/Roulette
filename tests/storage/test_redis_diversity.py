import json

from api.generation.redis_diversity import build_site_descriptor, choose_experience_cell, record_site_descriptor


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.calls = []

    def set(self, *args):
        self.calls.append(("set", args))
        return self

    def setex(self, *args):
        self.calls.append(("setex", args))
        return self

    def zincrby(self, *args):
        self.calls.append(("zincrby", args))
        return self

    def zadd(self, *args):
        self.calls.append(("zadd", args))
        return self

    def hincrby(self, *args):
        self.calls.append(("hincrby", args))
        return self

    def hset(self, *args, **kwargs):
        self.calls.append(("hset", args, kwargs))
        return self

    def execute(self):
        for item in self.calls:
            op = item[0]
            if op == "set":
                key, value = item[1]
                self.redis.strings[key] = value
            elif op == "setex":
                key, _ttl, value = item[1]
                self.redis.strings[key] = value
            elif op == "zincrby":
                key, amount, member = item[1]
                self.redis.zsets.setdefault(key, {})
                self.redis.zsets[key][member] = self.redis.zsets[key].get(member, 0) + amount
            elif op == "zadd":
                key, mapping = item[1]
                self.redis.zsets.setdefault(key, {}).update(mapping)
            elif op == "hincrby":
                key, field, amount = item[1]
                self.redis.hashes.setdefault(key, {})
                self.redis.hashes[key][field] = int(self.redis.hashes[key].get(field, 0)) + amount
            elif op == "hset":
                key = item[1][0]
                mapping = item[2]["mapping"]
                self.redis.hashes.setdefault(key, {}).update(mapping)
        return []


class FakeRedis:
    def __init__(self):
        self.zsets = {}
        self.strings = {}
        self.hashes = {}
        self.events = []

    def zscore(self, key, member):
        return self.zsets.get(key, {}).get(member)

    def exists(self, key):
        return key in self.strings

    def pipeline(self):
        return FakePipeline(self)

    def xadd(self, key, payload, maxlen=None, approximate=True):
        self.events.append((key, payload, maxlen, approximate))


def _doc():
    plan = {
        "experience_archetype": "interactive_instrument",
        "primary_loop_type": "type_to_reveal",
        "semantic_anchors": {"material": "concrete"},
        "visitor_role": "signal operator",
        "visitor_goal": "decode the message",
        "layout_archetype": "stage_focus",
        "motion_archetype": "parallax_drift",
        "rendering_mode": "dom",
        "primary_loop": {
            "state_change": "message fragments unlock",
            "visible_response": "light appears",
            "continue_reason": "finish decoding",
        },
    }
    html = """
    <!doctype html><html><body><main><h1>Signal</h1><p>Start typing to complete progress.</p>
    <input id="x"><button id="reset">Reset</button><div id="out">Progress</div>
    <script>const state={progress:0};document.getElementById('x').addEventListener('input',e=>{state.progress++;document.getElementById('out').textContent='Progress '+state.progress;});</script>
    </main></body></html>
    """
    return {
        "kind": "full_page_html",
        "html": html,
        "ndw_debug": {
            "premium_plan": plan,
            "quality_score": {"score": 90},
        },
    }


def test_choose_experience_cell_prefers_underused_cells():
    redis = FakeRedis()
    redis.zsets["qd:count:experience_cell"] = {
        "interactive_instrument:type_to_reveal": 99,
        "museum_exhibit:scan_to_discover": 0,
    }
    cell = choose_experience_cell(seed=3, client=redis)
    assert cell["experience_archetype"]
    assert cell["primary_loop_type"]


def test_build_site_descriptor_includes_experience_fields():
    descriptor = build_site_descriptor(_doc(), site_id="site_test")
    assert descriptor["site_id"] == "site_test"
    assert descriptor["experience_archetype"] == "interactive_instrument"
    assert descriptor["primary_loop_type"] == "type_to_reveal"
    assert descriptor["input_modality"]


def test_record_site_descriptor_writes_strings_zsets_hashes_and_events():
    redis = FakeRedis()
    descriptor = record_site_descriptor(_doc(), client=redis)
    assert descriptor
    site_key = f"site:{descriptor['site_id']}:descriptor"
    assert site_key in redis.strings
    assert json.loads(redis.strings[site_key])["experience_archetype"] == "interactive_instrument"
    assert "qd:count:experience_cell" in redis.zsets
    assert redis.events and redis.events[0][0] == "generation:events"
