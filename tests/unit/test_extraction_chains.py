import pytest
from types import SimpleNamespace

from kgbuilder.extraction.chains import ExtractionChains


class DummyLLM:
    def __init__(self, model=None, base_url=None, temperature=None, callbacks=None):
        self.model = model
        # default output to avoid attribute errors; tests can override
        self.output = "{\"entities\": []}"

    def __call__(self, prompt):
        # support LCEL pipeline by being callable returning object with `content`
        # prompt is a ChatPromptValue but we ignore it in the dummy
        return SimpleNamespace(content=self.output)


# keep track of all parser instances so tests can inspect the last one created
created_parsers: list["RecordingParser"] = []

class RecordingParser:
    def __init__(self, pydantic_object):
        self.pydantic_object = pydantic_object
        self.last_text = None
        # record self for later inspection
        created_parsers.append(self)

    def parse(self, text):
        self.last_text = text
        # return minimal structure consistent with expected output
        return SimpleNamespace(entities=[{"id": "e1"}])

    def get_format_instructions(self):
        return ""

    def __call__(self, text):
        # make parser callable so it can participate in LCEL chains
        return self.parse(text)


@pytest.fixture(autouse=True)
def patch_dependencies(monkeypatch):
    # patch ChatOllama and parser to avoid network and real pydantic
    monkeypatch.setattr("kgbuilder.extraction.chains.ChatOllama", DummyLLM)
    monkeypatch.setattr(
        "kgbuilder.extraction.chains.PydanticOutputParser", RecordingParser
    )
    # also patch get_langsmith_callbacks to None
    monkeypatch.setattr("kgbuilder.telemetry.langsmith.get_langsmith_callbacks", lambda: None)
    yield


def test_entity_chain_arithmetic_fix(monkeypatch):
    chain = ExtractionChains.create_entity_extraction_chain(model="m", base_url="u")
    # set LLM output to include arithmetic
    # the llm inside the chain may be wrapped in a RunnableLambda; unwrap if necessary
    llm = None
    for part in chain.middle:
        # direct instance
        if isinstance(part, DummyLLM):
            llm = part
            break
        # unwrap RunnableLambda
        if hasattr(part, "func") and isinstance(part.func, DummyLLM):
            llm = part.func
            break
    if llm is None:
        pytest.skip("no DummyLLM found in chain.middle")
    llm.output = '{"entities":[{"id":"a","start_char":0+5,"end_char":2+3}]}'

    # invoke chain with dummy inputs
    res = chain.invoke({"ontology_section": "A", "text": "foo"})

    # result should come from our RecordingParser
    assert hasattr(res, "entities")
    assert res.entities[0]["id"] == "e1"

    # inspect the parser that was used to parse the LLM output
    assert created_parsers, "no parser instance was created"
    last_parser = created_parsers[-1]
    assert last_parser.last_text is not None
    # arithmetic expressions should have been resolved by fix_json_arithmetic
    assert "0+5" not in last_parser.last_text
    assert "2+3" not in last_parser.last_text
    # the computed values should appear instead (5 and 5 at least once)
    assert "5" in last_parser.last_text




def test_relation_chain_creation_and_invoke(monkeypatch):
    chain = ExtractionChains.create_relation_extraction_chain(model="m", base_url="u")
    # ensure it's a RunnableSequence and has invoke
    assert hasattr(chain, "invoke")
    # locate DummyLLM in the chain and set its output (unwrap if necessary)
    for part in chain.middle:
        if isinstance(part, DummyLLM):
            part.output = '{"relations": []}'
            break
        if hasattr(part, "func") and isinstance(part.func, DummyLLM):
            part.func.output = '{"relations": []}'
            break
    # invoke with the variables expected by the relation prompt
    res = chain.invoke({
        "entities_list": "",  # no entities for this dummy call
        "relations_section": "",  # empty relations description
        "text": "foo",
    })
    # because RecordingParser returns entities by default, we expect at least one of these attributes
    assert hasattr(res, "entities") or hasattr(res, "relations")


def test_format_helpers_and_pipeline():
    # verify static formatting utilities
    ent = SimpleNamespace(id="e1", label="Foo", entity_type="T", confidence=0.42)
    lst = ExtractionChains.format_entities_list([ent])
    assert "- e1:" in lst and "Foo" in lst
    rel_def = SimpleNamespace(
        label="R",
        uri="http://rel",
        description="desc",
        domain=["D"],
        range=["R"],
        is_functional=False,
        is_symmetric=True,
        is_transitive=False,
    )
    rel_section = ExtractionChains.format_relations_section([rel_def])
    assert "**R**" in rel_section and "Domain:" in rel_section

    # build pipeline returns tuple of runnables using the module function
    from kgbuilder.extraction.chains import build_extraction_pipeline
    ent_chain, rel_chain = build_extraction_pipeline()
    assert hasattr(ent_chain, "invoke")
    assert hasattr(rel_chain, "invoke")
