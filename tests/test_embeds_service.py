from md2beauty.embeds import RendererRegistry, DiagramService, AssetRenderer, RenderResult
import tempfile, os


class DummyRenderer(AssetRenderer):
    kind = "dummy"
    def render(self, code, attrs=None, preferred_formats=None, config=None):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
        tmp.write(code.encode("utf-8"))
        tmp.close()
        return RenderResult(path=tmp.name, mime="text/plain")


def test_registry_and_service():
    reg = RendererRegistry()
    reg.register(DummyRenderer())
    svc = DiagramService(reg)
    rr = svc.render("dummy", "hello")
    assert rr and os.path.exists(rr.path)
    assert rr.mime == "text/plain"
    rr.cleanup()
    assert not os.path.exists(rr.path)
