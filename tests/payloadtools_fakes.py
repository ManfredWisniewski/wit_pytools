"""Shared fake Payload client for payloadtools tests (no _test suffix,
so pytest does not collect this module)."""


class FakeClient:
    """Records calls; serves preset docs/media lookups like PayloadClient."""

    def __init__(self, docs=None, media=None, fail_writes=False):
        self.docs = docs or {}          # (collection, sourcePath) -> doc
        self.media_docs = media or {}   # sourceHash -> doc
        self.fail_writes = fail_writes
        self.created = []
        self.updated = []
        self.uploads = []
        self.globals = []
        self.global_docs = {}   # globals slug -> doc
        self.gets = 0

    def close(self):
        pass

    def get(self, path, params=None):
        self.gets += 1
        if path.startswith("globals/"):
            return self.global_docs.get(path.split("/", 1)[1], {})
        return {"docs": list(self.docs.values())}

    def find_doc(self, collection, field_name, value):
        self.gets += 1
        if field_name == "sourceHash":
            return self.media_docs.get(value)
        return self.docs.get((collection, value))

    def _write(self):
        if self.fail_writes:
            raise AssertionError("write attempted in dry-run")

    def create_doc(self, collection, payload):
        self._write()
        self.created.append((collection, payload))
        return {"doc": {"id": f"new-{len(self.created)}"}}

    def update_doc(self, collection, doc_id, payload):
        self._write()
        self.updated.append((collection, doc_id, payload))
        return {"doc": {"id": doc_id}}

    def upload_media(self, path, *, collection, alt="", caption="",
                     source_hash="", source_path=""):
        self._write()
        media_id = f"media-{len(self.uploads) + 1}"
        self.uploads.append({
            "path": str(path), "collection": collection, "alt": alt,
            "caption": caption, "source_hash": source_hash,
            "source_path": source_path,
        })
        self.media_docs[source_hash] = {"id": media_id}
        return media_id

    def update_global(self, slug, payload):
        self._write()
        self.globals.append((slug, payload))
        return {"id": slug}
